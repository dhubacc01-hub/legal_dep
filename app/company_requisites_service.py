from __future__ import annotations

from datetime import datetime

from app.company_requisites_data import COMPANY_REQUISITES_DATA
from app.database import get_connection
from app.reference_data import DEFAULT_COUNTRY, SUPPORTED_COUNTRIES, get_companies_by_country


def normalize_company_key(value: str | None) -> str:
    text = str(value or "").strip()
    translation = str.maketrans(
        {
            "А": "A",
            "В": "B",
            "Е": "E",
            "К": "K",
            "М": "M",
            "Н": "H",
            "О": "O",
            "Р": "P",
            "С": "C",
            "Т": "T",
            "Х": "X",
            "Ё": "E",
            "І": "I",
            "Ї": "I",
            "Ъ": "",
            "Ь": "",
            "“": '"',
            "”": '"',
            "«": '"',
            "»": '"',
        }
    )
    normalized = text.upper().translate(translation)
    return "".join(ch for ch in normalized if ch.isalnum())


def normalize_company_lookup_key(value: str | None) -> str:
    key = normalize_company_key(value)
    for prefix in ("TOO", "T00", "OOO", "LLP"):
        if key.startswith(prefix):
            key = key[len(prefix) :]
    return key


STATIC_COMPANY_REQUISITES: dict[str, dict[str, str]] = {
    normalize_company_key("ООО «Concept Evolution»"): {
        "company_name": "ООО «Concept Evolution»",
        "company_block": "ООО «Concept Evolution»\nг. Ташкент, Шайхонтахурский район, ул. Лабзак, 64-а",
        "director_name": "Умарова Хусния Бону Абдугофур кизи",
        "bank_name": 'JSC "KAPITALBANK"',
        "iik": "",
        "bik": "",
        "bin": "312040649",
        "address": "г. Ташкент, Шайхонтахурский район, ул. Лабзак, 64-а",
        "kbe": "",
        "account_number": "2020 8000 9072 3076 2001",
        "bank_mfo": "01158",
    },
    normalize_company_key("ООО «RRS RETAIL CITY»"): {
        "company_name": "ООО «RRS RETAIL CITY»",
        "company_block": "ООО «RRS RETAIL CITY»\nгород Ташкент, Мирзо Улугбекский район, МСГ Элобод, улица Чуст, дом 1.",
        "director_name": "Кульмедова Ася Бекчановна",
        "bank_name": 'JSC "KAPITALBANK"',
        "iik": "",
        "bik": "",
        "bin": "311463803",
        "address": "город Ташкент, Мирзо Улугбекский район, МСГ Элобод, улица Чуст, дом 1.",
        "kbe": "",
        "account_number": "2020 8000 4071 0632 2001",
        "bank_mfo": "01158",
    },
}


def get_seed_company_requisites() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for value in COMPANY_REQUISITES_DATA.values():
        if not isinstance(value, dict):
            continue
        company_name = str(value.get("company_name") or "").strip()
        if not company_name:
            continue
        records.append(
            {
                "country": "kz",
                "company_key": normalize_company_lookup_key(company_name),
                **{
                    field: str(value.get(field) or "")
                    for field in (
                        "company_name",
                        "company_block",
                        "director_name",
                        "bank_name",
                        "iik",
                        "bik",
                        "bin",
                        "address",
                        "kbe",
                        "account_number",
                        "bank_mfo",
                    )
                },
            }
        )

    for value in STATIC_COMPANY_REQUISITES.values():
        company_name = str(value.get("company_name") or "").strip()
        if not company_name:
            continue
        records.append(
            {
                "country": "uz",
                "company_key": normalize_company_lookup_key(company_name),
                **{
                    field: str(value.get(field) or "")
                    for field in (
                        "company_name",
                        "company_block",
                        "director_name",
                        "bank_name",
                        "iik",
                        "bik",
                        "bin",
                        "address",
                        "kbe",
                        "account_number",
                        "bank_mfo",
                    )
                },
            }
        )
    return records


def seed_company_requisites(connection) -> None:
    existing_rows = connection.execute("SELECT * FROM company_requisites").fetchall()
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    for record in get_seed_company_requisites():
        record_key = normalize_company_lookup_key(record["company_name"])
        matched_row = next(
            (
                row
                for row in existing_rows
                if str(row["country"]) == record["country"]
                and (
                    normalize_company_lookup_key(str(row["company_name"])) == record_key
                    or normalize_company_lookup_key(str(row["company_key"])) == record_key
                )
            ),
            None,
        )
        if matched_row:
            connection.execute(
                """
                UPDATE company_requisites
                SET
                    company_key = ?,
                    company_name = ?,
                    company_block = ?,
                    director_name = ?,
                    bank_name = ?,
                    iik = ?,
                    bik = ?,
                    bin = ?,
                    address = ?,
                    kbe = ?,
                    account_number = ?,
                    bank_mfo = ?,
                    is_active = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    record["company_key"],
                    record["company_name"],
                    record["company_block"],
                    record["director_name"],
                    record["bank_name"],
                    record["iik"],
                    record["bik"],
                    record["bin"],
                    record["address"],
                    record["kbe"],
                    record["account_number"],
                    record["bank_mfo"],
                    timestamp,
                    matched_row["id"],
                ),
            )
            continue
        connection.execute(
            """
            INSERT INTO company_requisites (
                country,
                company_key,
                company_name,
                company_block,
                director_name,
                bank_name,
                iik,
                bik,
                bin,
                address,
                kbe,
                account_number,
                bank_mfo,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                record["country"],
                record["company_key"],
                record["company_name"],
                record["company_block"],
                record["director_name"],
                record["bank_name"],
                record["iik"],
                record["bik"],
                record["bin"],
                record["address"],
                record["kbe"],
                record["account_number"],
                record["bank_mfo"],
                timestamp,
                timestamp,
            ),
        )


def find_company_requisites(company_name: str, country: str | None = None) -> dict[str, str] | None:
    company_key = normalize_company_key(company_name)
    normalized_lookup_key = normalize_company_lookup_key(company_name)
    normalized_country = (country or "").strip().lower()

    with get_connection() as connection:
        if normalized_country in SUPPORTED_COUNTRIES:
            rows = connection.execute(
                """
                SELECT *
                FROM company_requisites
                WHERE country = ? AND is_active = 1
                ORDER BY company_name COLLATE NOCASE ASC
                """,
                (normalized_country,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM company_requisites
                WHERE is_active = 1
                ORDER BY company_name COLLATE NOCASE ASC
                """
            ).fetchall()

    for row in rows:
        if str(row["company_key"]) == company_key:
            return dict(row)

    for row in rows:
        if normalize_company_lookup_key(str(row["company_key"])) == normalized_lookup_key:
            return dict(row)
    return None


def sanitize_company_name(company_name: str | None) -> str:
    text = str(company_name or "").strip()
    lowered = text.lower()
    if "boggner" in lowered or "bogner" in lowered or "??? ?boggner?" in lowered:
        return "ТОО «Boggner»"
    return text


def match_company_to_library(
    company_name: str,
    country: str = DEFAULT_COUNTRY,
) -> str:
    sanitized_source = sanitize_company_name(company_name)
    normalized_source = normalize_company_lookup_key(sanitized_source)
    if not normalized_source:
        return sanitized_source

    normalized_country = (country or DEFAULT_COUNTRY).strip().lower()
    exact_match: str | None = None
    partial_match: str | None = None

    for candidate in get_companies_by_country(normalized_country):
        normalized_candidate = normalize_company_lookup_key(candidate)
        if normalized_candidate == normalized_source:
            exact_match = candidate
            break
        if (
            normalized_source in normalized_candidate
            or normalized_candidate in normalized_source
        ) and partial_match is None:
            partial_match = candidate

    return exact_match or partial_match or sanitized_source
