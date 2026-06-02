from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.common_utils import contract_date_value_from_number, normalize_text, parse_float
from app.company_requisites_service import find_company_requisites, match_company_to_library, sanitize_company_name
from app.disell_api import DiSellApiClient, DiSellApiError
from app.document_helpers import normalize_document_products


def resolve_claim_requisites(debtor: dict[str, Any], *, country: str) -> tuple[str, dict[str, str], str]:
    raw_company_name = sanitize_company_name(str(debtor.get("company") or ""))
    company_name_value = raw_company_name
    if country == "uz":
        company_name_value = match_company_to_library(raw_company_name, "uz")

    requisites = find_company_requisites(company_name_value, str(debtor.get("country") or country))
    if requisites is None:
        raise HTTPException(
            status_code=400,
            detail=f"Для компании «{company_name_value or '—'}» не найдены реквизиты.",
        )

    company_name = requisites.get("company_name") or company_name_value or "—"
    return company_name_value, requisites, company_name


def load_claim_crm_context(debtor: dict[str, Any], *, country: str) -> dict[str, Any]:
    try:
        return DiSellApiClient().lookup_lawsuit_context(
            str(debtor.get("contract_number") or ""),
            country=country,
        )
    except DiSellApiError:
        return {}


def resolve_claim_contract_data(
    debtor: dict[str, Any],
    crm_context: dict[str, Any],
    financials: dict[str, Any],
    *,
    debt_amount_override: float | None = None,
    prefer_crm_debt: bool = False,
) -> dict[str, Any]:
    contract_number = str(crm_context.get("contract_number") or debtor.get("contract_number") or "")
    contract_date = contract_date_value_from_number(contract_number)
    crm_contract_date = crm_context.get("contract_date")
    if isinstance(crm_contract_date, str) and crm_contract_date:
        try:
            contract_date = date.fromisoformat(crm_contract_date)
        except ValueError:
            pass

    contract_total_amount = crm_context.get("contract_total_amount")
    if contract_total_amount in (None, ""):
        contract_total_amount = debtor.get("contract_total_amount")
    if contract_total_amount in (None, ""):
        raise HTTPException(
            status_code=400,
            detail="Не заполнена сумма контракта. Сначала подтяните или заполните значение договора.",
        )
    contract_total_amount = parse_float(contract_total_amount)

    contract_advance_amount = crm_context.get("advance_amount")
    if contract_advance_amount in (None, ""):
        contract_advance_amount = debtor.get("contract_advance_amount")
    if contract_advance_amount in (None, ""):
        contract_advance_amount = max(round(contract_total_amount - financials["debt_amount"], 2), 0.0)
    else:
        contract_advance_amount = parse_float(contract_advance_amount)

    if debt_amount_override is not None:
        debt_amount = float(debt_amount_override)
    elif prefer_crm_debt and crm_context.get("debt_amount") not in (None, ""):
        debt_amount = parse_float(crm_context.get("debt_amount"))
    else:
        debt_amount = financials["debt_amount"]

    return {
        "contract_number": contract_number,
        "contract_date": contract_date,
        "contract_total_amount": contract_total_amount,
        "contract_advance_amount": contract_advance_amount,
        "debt_amount": debt_amount,
    }


def resolve_claim_products(
    crm_context: dict[str, Any],
    *,
    product_overrides: list[dict[str, Any]] | None = None,
    fallback_name: str = "Товар по договору",
) -> list[dict[str, Any]]:
    return normalize_document_products(
        product_overrides or crm_context.get("products"),
        fallback_name=fallback_name,
    )


def build_claim_output_path(generated_dir: Path, debtor: dict[str, Any], *, prefix: str) -> Path:
    generated_dir.mkdir(parents=True, exist_ok=True)
    safe_contract = re.sub(r"[^A-Za-z0-9_-]+", "_", str(debtor.get("contract_number") or debtor.get("id")))
    return generated_dir / f"{prefix}_{safe_contract}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"


def resolve_claim_client_contacts(
    debtor: dict[str, Any],
    crm_context: dict[str, Any],
) -> dict[str, str]:
    client_name = normalize_text(crm_context.get("client_name")) or normalize_text(debtor.get("client_name")) or "—"
    client_address = normalize_text(crm_context.get("client_address")) or normalize_text(debtor.get("address")) or "—"

    crm_phones = crm_context.get("client_phones") or []
    normalized_phones = [normalize_text(phone) for phone in crm_phones if normalize_text(phone)]
    if not normalized_phones:
        normalized_phones = [
            phone
            for phone in [normalize_text(debtor.get("mobile_phone")), normalize_text(debtor.get("home_phone"))]
            if phone
        ]
    client_phone = ", ".join(dict.fromkeys(normalized_phones)) if normalized_phones else "—"

    return {
        "client_name": client_name,
        "client_address": client_address,
        "client_phone": client_phone,
    }
