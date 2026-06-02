from __future__ import annotations

from typing import Any

from app.common_utils import normalize_text


def build_company_payment_details(requisites: dict[str, str]) -> str:
    parts = [
        requisites.get("bin"),
        requisites.get("bank_name"),
        f"ИИК: {requisites.get('iik')}" if requisites.get("iik") else "",
        f"БИК: {requisites.get('bik')}" if requisites.get("bik") else "",
        f"КБЕ: {requisites.get('kbe') or '—'}",
    ]
    return ", ".join(part for part in parts if part)


def build_company_payment_detail_lines(requisites: dict[str, str]) -> list[str]:
    lines: list[str] = []
    if requisites.get("bin"):
        lines.append(str(requisites["bin"]))
    if requisites.get("bank_name"):
        lines.append(f"Наименование банка: {requisites['bank_name']}")
    if requisites.get("iik"):
        lines.append(f"ИИК: {requisites['iik']}")
    if requisites.get("bik"):
        lines.append(f"БИК: {requisites['bik']}")
    return lines


def build_company_payment_detail_lines_uz(requisites: dict[str, str]) -> list[str]:
    lines: list[str] = []
    if requisites.get("bin"):
        lines.append(f"ИНН: {requisites['bin']}")
    if requisites.get("bank_name"):
        lines.append(f"Наименование банка: {requisites['bank_name']}")
    if requisites.get("account_number"):
        lines.append(f"Расчетный счет: {requisites['account_number']}")
    if requisites.get("bank_mfo"):
        lines.append(f"МФО банка: {requisites['bank_mfo']}")
    return lines


def normalize_document_products(
    raw_products: list[dict[str, Any]] | None,
    *,
    fallback_name: str,
) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for item in raw_products or []:
        name = normalize_text(item.get("name")) or normalize_text(item.get("display_name"))
        if not name:
            continue
        quantity_raw = item.get("quantity", 1)
        try:
            quantity = int(float(quantity_raw))
        except (TypeError, ValueError):
            quantity = 1
        quantity = max(quantity, 1)
        products.append(
            {
                "name": name,
                "quantity": quantity,
                "display_name": f"{name} — {quantity} шт.",
            }
        )
    if not products:
        products.append(
            {
                "name": fallback_name,
                "quantity": 1,
                "display_name": f"{fallback_name} — 1 шт.",
            }
        )
    return products


def build_company_header_lines(requisites: dict[str, str], company_name: str) -> list[str]:
    company_block = normalize_text(requisites.get("company_block"))
    if company_block:
        lines = [line.strip() for line in company_block.splitlines() if line.strip()]
        if lines:
            return lines

    address = normalize_text(requisites.get("address"))
    return [line for line in [company_name, address] if line] or [company_name or "—"]
