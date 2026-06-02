from __future__ import annotations

from fastapi import HTTPException

from app.reference_data import DEFAULT_COUNTRY, SUPPORTED_COUNTRIES


def normalize_country_code(country: str | None) -> str:
    normalized = (country or DEFAULT_COUNTRY).strip().lower()
    if normalized not in SUPPORTED_COUNTRIES:
        raise HTTPException(status_code=400, detail="Неизвестная страна.")
    return normalized
