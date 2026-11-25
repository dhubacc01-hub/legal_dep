import sqlite3
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import database, main


class CourtCasesTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.addCleanup(self.connection.close)
        with patch.object(database, "get_connection", return_value=self.connection):
            database.init_db()
            database.init_db()  # Startup remains safe on an existing schema.
        self.enterContext(patch.object(main, "get_connection", return_value=self.connection))
        self.enterContext(patch.dict(main.app.dependency_overrides, {
            main.require_app_user: lambda: {"id": 1, "role": "lawyer"},
        }))
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.temporary = tempfile.TemporaryDirectory(dir=main.GENERATED_DIR)
        self.addCleanup(self.temporary.cleanup)
        self.uploads = Path(self.temporary.name)
        self.enterContext(patch.object(main, "COURT_DOCUMENTS_DIR", self.uploads))
        self.payload = dict(country="kz", contract_number="010125/1M-1", client_name="Test Client", company="Test company")

    def create(self, **changes):
        response = self.client.post("/api/court-cases", json={**self.payload, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_crud_country_isolation_and_no_debtor_created(self):
        kz = self.create(notification_date="2026-11-25", city="Алматы", court="Суд")
        uz = self.create(country="uz")
        self.assertEqual(kz["contract_date_iso"], "2025-01-01")
        self.assertEqual(kz["notification_date"], "25.11.2026")
        self.assertTrue(kz["entry_date_iso"])
        self.assertEqual([row["id"] for row in self.client.get("/api/court-cases?country=kz").json()], [kz["id"]])
        self.assertEqual([row["id"] for row in self.client.get("/api/court-cases?country=uz").json()], [uz["id"]])
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM debtors").fetchone()[0], 0)
        response = self.client.patch(f"/api/court-cases/{kz['id']}", json={**self.payload, "comment": "Updated", "decision": "Частично", "decision_payout": 120})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["decision_payout"], 120)
        self.assertEqual(response.json()["created_at"], kz["created_at"])
        response = self.client.patch(f"/api/court-cases/{kz['id']}", json={"comment": "Inline change"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["decision_payout"], 120)
        self.assertEqual(response.json()["comment"], "Inline change")
        self.assertEqual(self.client.patch(f"/api/court-cases/{kz['id']}", json={"decision_payout": -1}).status_code, 422)
        self.assertEqual(self.client.delete(f"/api/court-cases/{kz['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/court-cases?country=kz").json(), [])
        self.assertEqual(self.client.get(f"/api/court-cases/{kz['id']}/response-file").status_code, 404)

    def test_dependencies_and_invalid_input(self):
        row = self.create(claim_date="2026-11-01", hearing_date="2026-12-01", decision_payout=100)
        self.assertIsNone(row["claim_date_iso"])
        self.assertIsNone(row["hearing_date_iso"])
        self.assertEqual(row["decision_payout"], 0)
        row = self.create(claim_sent=True, claim_date="2026-11-01", lawsuit_exists=True, hearing_date="2026-12-01", decision="Не удовлетворен", decision_payout=123)
        self.assertEqual(row["claim_date_iso"], "2026-11-01")
        self.assertEqual(row["hearing_date_iso"], "2026-12-01")
        self.assertEqual(row["decision_payout"], 123)
        for changes in ({"decision": "Отказ в иске"}, {"decision_payout": -1}, {"country": "xx"}, {"client_name": "   "}, {"notification_date": "2026-02-31"}, {"response_exists": "Да"}):
            self.assertEqual(self.client.post("/api/court-cases", json={**self.payload, **changes}).status_code, 422)

    def test_live_correspondence_link_scoped_by_contract_country_company_and_existing_file(self):
        case = self.create()
        for country, company, contract, file_name in (
            ("uz", "Test company", "010125/1M-1", "foreign.pdf"),
            ("kz", "Other", "010125/1M-1", "other.pdf"),
            ("kz", "Test company", "010125/1M-2", "different.pdf"),
            ("kz", "Test company", "010125/1M-1", "missing.pdf"),
        ):
            self.insert_reply(country, company, contract, file_name)
        with patch.object(main, "resolve_incoming_claim_response_file_path", side_effect=lambda name: Path(__file__) if name != "missing.pdf" else Path(__file__).with_suffix(".absent")):
            self.assertEqual(self.client.get("/api/court-cases").json()[0]["response_exists"], "Нет")
            reply_id = self.insert_reply("kz", "Test company", "010125/1М-1", "exists.pdf")
            row = self.client.get("/api/court-cases").json()[0]
            self.assertEqual(row["response_exists"], "Да")
            self.assertEqual(row["response_record_id"], reply_id)
            response = self.client.get(row["response_file_url"])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, Path(__file__).read_bytes())
            self.connection.execute("UPDATE incoming_correspondence SET claim_response_pdf_name = NULL WHERE id = ?", (reply_id,))
            self.connection.commit()
            self.assertEqual(self.client.get("/api/court-cases").json()[0]["response_exists"], "Нет")
        self.assertEqual(self.client.delete(f"/api/court-cases/{case['id']}").status_code, 204)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM incoming_correspondence").fetchone()[0], 5)

    def insert_reply(self, country, company, contract, file_name):
        with self.connection:
            return self.connection.execute("""
                INSERT INTO incoming_correspondence (country, company, contract_number, category,
                    claim_response_pdf_name, created_at, updated_at, received_date, receive_method,
                    client_name, authority_kind)
                VALUES (?, ?, ?, 'Претензия', ?, '2026-11-01', '2026-11-01', '2026-11-01', 'Почта', 'Client', 'court')
            """, (country, company, contract, file_name)).lastrowid

    def test_auth_required(self):
        main.app.dependency_overrides.pop(main.require_app_user)
        self.assertEqual(self.client.get("/api/court-cases").status_code, 401)
        self.assertEqual(self.client.post("/api/court-cases", json=self.payload).status_code, 401)

    def upload(self, record_id, title="Документ", body=b"sample file", filename="document.txt"):
        return self.client.post(f"/api/court-cases/{record_id}/documents",
            data={"title": title, "description": "Краткое описание"}, files={"file": (filename, body, "text/plain")})

    def test_upload_list_download_and_record_scope(self):
        first, second = self.create(), self.create(country="uz")
        response = self.upload(first["id"], filename="../../my document.txt")
        self.assertEqual(response.status_code, 201, response.text)
        doc_id = response.json()["id"]
        rows = self.client.get(f"/api/court-cases/{first['id']}/documents").json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Документ")
        self.assertEqual(rows[0]["filename"], "my document.txt")
        self.assertEqual(rows[0]["description"], "Краткое описание")
        download = self.client.get(rows[0]["download_url"])
        self.assertEqual(download.content, b"sample file")
        self.assertEqual(download.headers["x-content-type-options"], "nosniff")
        self.assertIn("inline", download.headers["content-disposition"])
        self.assertIn("text/plain", download.headers["content-type"])
        self.assertEqual(self.client.get(f"/api/court-cases/{second['id']}/documents").json(), [])
        self.assertEqual(self.client.get(f"/api/court-cases/{second['id']}/documents/{doc_id}/file").status_code, 404)
        self.assertEqual(len(list(self.uploads.iterdir())), 1)
        self.assertEqual(self.client.delete(f"/api/court-cases/{first['id']}").status_code, 204)
        self.assertEqual(list(self.uploads.iterdir()), [])
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM court_case_documents").fetchone()[0], 0)

    def test_upload_rejects_empty_oversized_unnamed_and_missing_case_without_orphans(self):
        case = self.create()
        self.assertEqual(self.upload(case["id"], title="   ").status_code, 422)
        self.assertEqual(self.upload(case["id"], body=b"").status_code, 422)
        with patch("app.court_cases.MAX_DOCUMENT_BYTES", 4):
            self.assertEqual(self.upload(case["id"], body=b"12345").status_code, 413)
        self.assertEqual(self.upload(999999).status_code, 404)
        self.assertEqual(list(self.uploads.iterdir()), [])
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM court_case_documents").fetchone()[0], 0)

    def test_pdf_opens_inline_but_active_or_unsupported_content_is_downloaded(self):
        case = self.create()
        for filename, expected_type, disposition in (
            ("Response.PDF", "application/pdf", "inline"), ("image.png", "image/png", "inline"),
            ("document.docx", "application/octet-stream", "attachment"),
            ("unsafe.html", "application/octet-stream", "attachment"),
            ("unsafe.svg", "application/octet-stream", "attachment"),
        ):
            doc_id = self.upload(case["id"], filename=filename).json()["id"]
            response = self.client.get(f"/api/court-cases/{case['id']}/documents/{doc_id}/file")
            self.assertEqual(response.status_code, 200)
            self.assertIn(expected_type, response.headers["content-type"])
            self.assertTrue(response.headers["content-disposition"].startswith(disposition))

    def test_documents_merge_replies_in_descending_chronological_order(self):
        case, other_case = self.create(), self.create(company="Other company")
        reply_id = self.insert_reply("kz", "Test company", "010125/1M-1", "reply.pdf")
        doc_id = self.upload(case["id"]).json()["id"]
        with self.connection:
            self.connection.execute("UPDATE court_case_documents SET created_at='2026-11-02T00:00:00' WHERE id=?", (doc_id,))
            self.connection.execute("UPDATE incoming_correspondence SET claim_response_generated_at='2026-11-03T00:00:00' WHERE id=?", (reply_id,))
        with patch.object(main, "resolve_incoming_claim_response_file_path", return_value=Path(__file__)):
            rows = self.client.get(f"/api/court-cases/{case['id']}/documents").json()
            self.assertEqual([row["source"] for row in rows], ["correspondence", "upload"])
            reply = self.client.get(rows[0]["download_url"])
            self.assertEqual(reply.content, Path(__file__).read_bytes())
            self.assertTrue(reply.headers["content-disposition"].startswith("inline"))
            self.assertEqual(self.client.get(f"/api/court-cases/{other_case['id']}/documents/replies/{reply_id}/file").status_code, 404)
            self.assertEqual(self.client.get(f"/api/court-cases/{other_case['id']}/documents").json(), [])
        with self.connection:
            self.connection.execute("UPDATE court_case_documents SET created_at='2026-11-04T00:00:00' WHERE id=?", (doc_id,))
        with patch.object(main, "resolve_incoming_claim_response_file_path", return_value=Path(__file__)):
            rows = self.client.get(f"/api/court-cases/{case['id']}/documents").json()
            self.assertEqual([row["source"] for row in rows], ["upload", "correspondence"])

    def test_documents_require_authorization(self):
        case = self.create()
        main.app.dependency_overrides.pop(main.require_app_user)
        for method, path in (("get", "documents"), ("get", "documents/1/file"), ("get", "documents/replies/1/file")):
            self.assertEqual(getattr(self.client, method)(f"/api/court-cases/{case['id']}/{path}").status_code, 401)
        self.assertEqual(self.upload(case["id"]).status_code, 401)

    def test_page_has_shared_calendar_and_new_fields(self):
        user = dict(id=1, username="test", full_name="Test", role="lawyer", must_change_password=0, is_active=1, created_at="2026-11-25", updated_at="2026-11-25")
        with patch.object(main, "get_optional_current_user", return_value=user):
            response = self.client.get("/court-cases")
        self.assertEqual(response.status_code, 200, response.text)
        for expected in ('court_cases.js', 'name="notification_date"', 'name="decision_payout"', 'incoming-date-picker-popover'):
            self.assertIn(expected, response.text)
