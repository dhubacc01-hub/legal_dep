from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


def parse_date_value(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return date.fromisoformat(text.split("T", 1)[0].split(" ", 1)[0])


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return bool(int(value or 0))


def parse_float(value: Any) -> float:
    return round(float(value or 0), 2)


def parse_int_value(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(round(float(value)))


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def format_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%d.%m.%Y")


def contract_date_value_from_number(contract_number: str) -> date | None:
    match = re.match(r"^(\d{2})(\d{2})(\d{2})", contract_number)
    if not match:
        return None

    day, month, year = match.groups()
    full_year = int(f"20{year}")
    try:
        return date(full_year, int(month), int(day))
    except ValueError:
        return None


def contract_date_from_number(contract_number: str) -> str | None:
    parsed = contract_date_value_from_number(contract_number)
    if parsed is None:
        return None
    return parsed.strftime("%d.%m.%Y")


def preferred_phone(row: dict[str, Any]) -> str:
    return normalize_text(row.get("mobile_phone")) or normalize_text(row.get("home_phone")) or "—"
