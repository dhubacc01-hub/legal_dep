from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from fastapi import HTTPException


def build_short_client_name(full_name: str) -> str:
    parts = [part for part in str(full_name or "").strip().split(" ") if part]
    if not parts:
        return "—"
    surname = parts[0]
    initials = " ".join(f"{part[0]}." for part in parts[1:] if part)
    return " ".join(part for part in [surname, initials] if part)


def add_months_preserving_day(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def build_lawsuit_penalty_rows(
    start_date: date,
    end_date: date,
    claim_sent_date: date,
    monthly_payment_amount: float,
    first_period_paid_amount: float = 0,
) -> tuple[list[dict[str, Any]], float, int]:
    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="Период рассрочки заполнен некорректно.")
    if claim_sent_date <= start_date:
        raise HTTPException(status_code=400, detail="Дата претензии должна быть позже начала рассрочки.")

    rows: list[dict[str, Any]] = []
    current_start = start_date
    period_index = 1
    first_outstanding = max(round(monthly_payment_amount - first_period_paid_amount, 2), 0.0)
    schedule_end = min(end_date, claim_sent_date)

    while current_start < schedule_end:
        current_end = min(add_months_preserving_day(current_start, 1), schedule_end)
        days = max((current_end - current_start).days, 0)
        obligation = round(first_outstanding + monthly_payment_amount * max(period_index - 1, 0), 2)
        penalty_amount = round(obligation * 0.001 * days, 2)
        rows.append(
            {
                "period_from": current_start,
                "period_to": current_end,
                "days": days,
                "obligation_amount": obligation,
                "penalty_rate_percent": 0.1,
                "penalty_amount": penalty_amount,
            }
        )
        current_start = current_end
        period_index += 1

    if claim_sent_date > end_date:
        days = max((claim_sent_date - end_date).days, 0)
        final_obligation = round(first_outstanding + monthly_payment_amount * max(period_index - 1, 0), 2)
        penalty_amount = round(final_obligation * 0.001 * days, 2)
        rows.append(
            {
                "period_from": end_date,
                "period_to": claim_sent_date,
                "days": days,
                "obligation_amount": final_obligation,
                "penalty_rate_percent": 0.1,
                "penalty_amount": penalty_amount,
            }
        )

    computed_total = round(sum(row["penalty_amount"] for row in rows), 2)
    total_days = sum(row["days"] for row in rows)
    return rows, computed_total, total_days
