from __future__ import annotations


def format_money(value: float | int | None) -> str:
    amount = round(float(value or 0), 2)
    integer_part = int(amount)
    decimal_part = int(round((amount - integer_part) * 100))
    integer_display = f"{integer_part:,}".replace(",", " ")
    return f"{integer_display},{decimal_part:02d}"


def compute_lawsuit_claim_price(debt_amount: float, penalty_amount: float) -> float:
    return round(float(debt_amount or 0) + float(penalty_amount or 0), 2)


def compute_lawsuit_state_duty(
    country_code: str,
    debt_amount: float,
    penalty_amount: float,
    *,
    uz_brv_amount: float,
) -> float:
    claim_price_amount = compute_lawsuit_claim_price(debt_amount, penalty_amount)
    if (country_code or "").strip().lower() == "uz":
        return max(round(claim_price_amount * 0.04, 2), uz_brv_amount)
    return round(claim_price_amount * 0.03, 2)


def compute_simple_penalty_amount(debt_amount: float, overdue_days: int) -> float:
    return round(max(float(debt_amount or 0), 0.0) * 0.001 * max(int(overdue_days or 0), 0), 2)
