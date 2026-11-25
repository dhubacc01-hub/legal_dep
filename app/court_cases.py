"""Cases brought against our companies; independent of debt collection."""
from datetime import date, datetime
from pathlib import Path
import json
import re
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.common_utils import contract_date_value_from_number, format_date, parse_date_value
from app.company_requisites_service import normalize_company_lookup_key
from app.disell_api import normalize_contract_number

class CourtCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    country: Literal["kz", "uz"]
    notification_date: date | None = None
    contract_date: date | None = None
    client_name: str = Field(min_length=1, max_length=255)
    contract_number: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    city: str = Field(default="", max_length=255)
    court: str = Field(default="", max_length=1000)
    claim_sent: bool = False
    claim_date: date | None = None
    lawsuit_exists: bool = False
    hearing_date: date | None = None
    decision: Literal["Удовлетворить", "Частично", "По соглашению сторон", "Не удовлетворен"] | None = None
    decision_payout: float = Field(default=0, ge=0, allow_inf_nan=False)
    comment: str | None = Field(default=None, max_length=20000)
    case_number: str | None = Field(default=None, max_length=255)
    case_court: str = Field(default="", max_length=1000)

    @field_validator("decision", mode="before")
    @classmethod
    def empty_decision(cls, value):
        return value or None

    @model_validator(mode="after")
    def dependencies(self):
        if not self.claim_sent:
            self.claim_date = None
        if not self.lawsuit_exists:
            self.hearing_date = None
        if not self.decision:
            self.decision_payout = 0
        if not self.contract_date:
            self.contract_date = contract_date_value_from_number(self.contract_number)
        return self


class CourtCaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country: Literal["kz", "uz"] | None = None
    notification_date: date | None = None
    contract_date: date | None = None
    client_name: str | None = None
    contract_number: str | None = None
    company: str | None = None
    city: str | None = None
    court: str | None = None
    claim_sent: bool | None = None
    claim_date: date | None = None
    lawsuit_exists: bool | None = None
    hearing_date: date | None = None
    decision: str | None = None
    decision_payout: float | None = None
    comment: str | None = None
    case_number: str | None = None
    case_court: str | None = None


def link_key(row):
    return (row["country"], normalize_company_lookup_key(row["company"]),
            normalize_contract_number(row["contract_number"]))


def serialize_cases(connection, rows, resolve_file):
    # Resolve live links on every read, so regenerating a response never leaves a stale copy.
    replies = {}
    countries = {row["country"] for row in rows}
    for country in countries:
        for reply in connection.execute("""
            SELECT * FROM incoming_correspondence
            WHERE country = ? AND category = 'Претензия' AND claim_response_pdf_name IS NOT NULL
            ORDER BY claim_response_generated_at DESC, id DESC
        """, (country,)):
            reply = dict(reply)
            if resolve_file(reply["claim_response_pdf_name"]).is_file():
                replies.setdefault(link_key(reply), reply)
    result = []
    for source in rows:
        row = dict(source)
        for field in ("notification_date", "contract_date", "claim_date", "hearing_date"):
            value = parse_date_value(row.get(field))
            row[field + "_iso"] = value.isoformat() if value else None
            row[field] = format_date(value) if value else None
        entry = datetime.fromisoformat(row["created_at"]).date()
        row.update(entry_date=format_date(entry), entry_date_iso=entry.isoformat())
        reply = replies.get(link_key(row))
        row["response_exists"] = "Да" if reply else "Нет"
        row["response_record_id"] = reply["id"] if reply else None
        row["response_file_url"] = f"/api/court-cases/{row['id']}/response-file" if reply else None
        row["claim_sent"] = bool(row["claim_sent"])
        row["lawsuit_exists"] = bool(row["lawsuit_exists"])
        result.append(row)
    return result


MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
INLINE_DOCUMENT_TYPES = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".txt": "text/plain",
}


def matching_replies(connection, case, resolve_file):
    for row in connection.execute("""
        SELECT * FROM incoming_correspondence
        WHERE country = ? AND category = 'Претензия' AND claim_response_pdf_name IS NOT NULL
        ORDER BY claim_response_generated_at DESC, id DESC
    """, (case["country"],)):
        reply = dict(row)
        if link_key(reply) == link_key(case) and resolve_file(reply["claim_response_pdf_name"]).is_file():
            yield reply


def create_router(authorize, get_connection, resolve_file, documents_dir):
    router = APIRouter(prefix="/api/court-cases", dependencies=[Depends(authorize)])

    def require_case(connection, record_id):
        row = connection.execute("SELECT * FROM court_cases WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Запись не найдена.")
        return dict(row)

    def stored_path(name):
        if not re.fullmatch(r"[a-f0-9]{32}", name):
            raise HTTPException(404, "Файл не найден.")
        return documents_dir() / name

    @router.get("/{record_id}/documents")
    def list_documents(record_id: int):
        with get_connection() as connection:
            case = require_case(connection, record_id)
            documents = []
            for source in connection.execute("SELECT * FROM court_case_documents WHERE court_case_id = ?", (record_id,)):
                doc = dict(source)
                documents.append({
                    "id": f"upload-{doc['id']}", "source": "upload", "title": doc["title"],
                    "description": doc["description"], "filename": doc["original_filename"],
                    "size_bytes": doc["size_bytes"], "created_at": doc["created_at"],
                    "download_url": f"/api/court-cases/{record_id}/documents/{doc['id']}/file",
                })
            for reply in matching_replies(connection, case, resolve_file):
                path = resolve_file(reply["claim_response_pdf_name"])
                documents.append({
                    "id": f"reply-{reply['id']}", "source": "correspondence", "title": "Ответ на претензию",
                    "description": "Автоматически из входящей корреспонденции",
                    "filename": path.name, "size_bytes": path.stat().st_size,
                    "created_at": reply["claim_response_generated_at"] or reply["updated_at"] or reply["created_at"],
                    "download_url": f"/api/court-cases/{record_id}/documents/replies/{reply['id']}/file",
                })
        return sorted(documents, key=lambda item: (item["created_at"], item["id"]), reverse=True)

    @router.post("/{record_id}/documents", status_code=201)
    def upload_document(record_id: int, title: str = Form(min_length=1, max_length=255),
                        description: str = Form(default="", max_length=2000), file: UploadFile = File()):
        title = title.strip()
        if not title:
            raise HTTPException(422, "Укажите название документа.")
        filename = re.sub(r"[\x00-\x1f\x7f]", "", (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]).strip()[:255]
        if not filename or filename in {".", ".."}:
            raise HTTPException(422, "Выберите файл.")
        with get_connection() as connection:
            require_case(connection, record_id)
        path = stored_path(uuid4().hex)
        path.parent.mkdir(parents=True, exist_ok=True)
        committed = False
        try:
            size = 0
            with path.open("xb") as target:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_DOCUMENT_BYTES:
                        raise HTTPException(413, "Размер файла не должен превышать 20 МБ.")
                    target.write(chunk)
            if not size:
                raise HTTPException(422, "Нельзя загрузить пустой файл.")
            with get_connection() as connection:
                require_case(connection, record_id)
                cursor = connection.execute("""
                    INSERT INTO court_case_documents
                        (court_case_id, title, description, original_filename, storage_name, size_bytes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (record_id, title, description.strip(), filename, path.name, size, datetime.now().isoformat()))
            committed = True
            return {"id": cursor.lastrowid}
        finally:
            file.file.close()
            if not committed:
                path.unlink(missing_ok=True)

    @router.get("/{record_id}/documents/{document_id}/file")
    def download_document(record_id: int, document_id: int):
        with get_connection() as connection:
            require_case(connection, record_id)
            doc = connection.execute("SELECT * FROM court_case_documents WHERE id = ? AND court_case_id = ?",
                                     (document_id, record_id)).fetchone()
            if doc is None:
                raise HTTPException(404, "Документ не найден.")
            path = stored_path(doc["storage_name"])
            if not path.is_file():
                raise HTTPException(404, "Файл не найден.")
        # Never render uploaded HTML, SVG or other active content on the application's origin.
        media_type = INLINE_DOCUMENT_TYPES.get(Path(doc["original_filename"]).suffix.lower())
        return FileResponse(path, media_type=media_type or "application/octet-stream", filename=doc["original_filename"],
                            content_disposition_type="inline" if media_type else "attachment",
                            headers={"X-Content-Type-Options": "nosniff"})

    @router.get("/{record_id}/documents/replies/{reply_id}/file")
    def download_reply(record_id: int, reply_id: int):
        with get_connection() as connection:
            case = require_case(connection, record_id)
            reply = next((item for item in matching_replies(connection, case, resolve_file) if item["id"] == reply_id), None)
            if reply is None:
                raise HTTPException(404, "Ответ на претензию не найден.")
            path = resolve_file(reply["claim_response_pdf_name"])
        return FileResponse(path, media_type="application/pdf", filename=path.name,
                            content_disposition_type="inline",
                            headers={"X-Content-Type-Options": "nosniff"})

    @router.get("")
    def list_cases(country: Literal["kz", "uz"] = "kz"):
        with get_connection() as connection:
            rows = connection.execute("SELECT * FROM court_cases WHERE country = ? ORDER BY id DESC", (country,)).fetchall()
            return serialize_cases(connection, [dict(row) for row in rows], resolve_file)

    def save_case(payload, record_id=None):
        data = payload.model_dump(mode="json", exclude_unset=record_id is not None)
        with get_connection() as connection:
            if record_id is None:
                data["created_at"] = datetime.now().replace(microsecond=0).isoformat()
                fields = ", ".join(data)
                placeholders = ", ".join("?" for _ in data)
                record_id = connection.execute(
                    f"INSERT INTO court_cases ({fields}) VALUES ({placeholders})", list(data.values())
                ).lastrowid
            else:
                existing = connection.execute("SELECT * FROM court_cases WHERE id = ?", (record_id,)).fetchone()
                if existing is None:
                    raise HTTPException(404, "Запись не найдена.")
                merged = {key: existing[key] for key in CourtCaseInput.model_fields}
                try:
                    data = CourtCaseInput.model_validate({**merged, **data}).model_dump(mode="json")
                except ValidationError as exc:
                    raise HTTPException(422, json.loads(exc.json())) from exc
                assignments = ", ".join(f"{key} = ?" for key in data)
                connection.execute(f"UPDATE court_cases SET {assignments} WHERE id = ?", [*data.values(), record_id])
            row = dict(connection.execute("SELECT * FROM court_cases WHERE id = ?", (record_id,)).fetchone())
            return serialize_cases(connection, [row], resolve_file)[0]

    @router.post("", status_code=201)
    def create_case(payload: CourtCaseInput):
        return save_case(payload)

    @router.patch("/{record_id}")
    def update_case(record_id: int, payload: CourtCaseUpdate):
        return save_case(payload, record_id)

    @router.delete("/{record_id}", status_code=204)
    def delete_case(record_id: int):
        with get_connection() as connection:
            files = [row["storage_name"] for row in connection.execute(
                "SELECT storage_name FROM court_case_documents WHERE court_case_id = ?", (record_id,))]
            connection.execute("DELETE FROM court_case_documents WHERE court_case_id = ?", (record_id,))
            if not connection.execute("DELETE FROM court_cases WHERE id = ?", (record_id,)).rowcount:
                raise HTTPException(404, "Запись не найдена.")
        for name in files:
            stored_path(name).unlink(missing_ok=True)
        return Response(status_code=204)

    @router.get("/{record_id}/response-file")
    def response_file(record_id: int):
        with get_connection() as connection:
            source = connection.execute("SELECT * FROM court_cases WHERE id = ?", (record_id,)).fetchone()
            if source is None:
                raise HTTPException(404, "Запись не найдена.")
            row = serialize_cases(connection, [dict(source)], resolve_file)[0]
            if not row["response_record_id"]:
                raise HTTPException(404, "Файл ответа не найден.")
            reply = connection.execute("SELECT claim_response_pdf_name FROM incoming_correspondence WHERE id = ?",
                                       (row["response_record_id"],)).fetchone()
            path = resolve_file(reply["claim_response_pdf_name"])
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    return router
