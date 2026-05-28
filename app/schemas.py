from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DebtorBase(BaseModel):
    category: str = "Новый"
    client_name: str = Field(min_length=1, max_length=255)
    contract_number: str = Field(min_length=1, max_length=255)
    last_missed_payment_date: date
    company: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    court: str = Field(min_length=1, max_length=255)
    claim_sent: bool = False
    claim_sent_date: date | None = None
    debt_amount: float = Field(ge=0)
    lawsuit_sent: bool = False
    lawsuit_sent_date: date | None = None
    lawsuit_accepted: bool = False
    hearing_date: date | None = None
    decision_exists: bool = False
    decision: str | None = None
    decision_payout: float = Field(default=0, ge=0)
    received_amount: float = Field(default=0, ge=0)
    comment: str | None = None
    case_number: str | None = None


class DebtorCreate(BaseModel):
    country: str = Field(default="kz", min_length=2, max_length=8)
    client_name: str = Field(min_length=1, max_length=255)
    contract_number: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    city: str = Field(default="", max_length=255)
    court: str = Field(default="", max_length=255)
    last_missed_payment_date: date
    debt_amount: float = Field(ge=0)
    mobile_phone: str | None = Field(default=None, max_length=255)
    home_phone: str | None = Field(default=None, max_length=255)
    address: str | None = None
    contract_total_amount: float | None = Field(default=None, ge=0)
    contract_advance_amount: float | None = Field(default=None, ge=0)


class DebtorUpdate(BaseModel):
    country: str | None = None
    category: str | None = None
    client_name: str | None = None
    contract_number: str | None = None
    last_missed_payment_date: date | None = None
    company: str | None = None
    city: str | None = None
    court: str | None = None
    claim_sent: bool | None = None
    claim_sent_date: date | None = None
    debt_amount: float | None = Field(default=None, ge=0)
    lawsuit_sent: bool | None = None
    lawsuit_sent_date: date | None = None
    lawsuit_accepted: bool | None = None
    hearing_date: date | None = None
    decision_exists: bool | None = None
    decision: str | None = None
    decision_payout: float | None = Field(default=None, ge=0)
    received_amount: float | None = Field(default=None, ge=0)
    comment: str | None = None
    case_number: str | None = None
    mobile_phone: str | None = None
    home_phone: str | None = None
    address: str | None = None
    birth_date: date | None = None
    contract_total_amount: float | None = Field(default=None, ge=0)
    contract_advance_amount: float | None = Field(default=None, ge=0)
    lawsuit_installment_from: date | None = None
    lawsuit_installment_to: date | None = None
    lawsuit_monthly_payment_amount: float | None = Field(default=None, ge=0)
    lawsuit_first_period_paid_amount: float | None = Field(default=None, ge=0)


class DebtorView(BaseModel):
    id: int
    country: str
    entry_date: str
    created_at: str
    contract_date: str | None
    category: str
    client_name: str
    contract_number: str
    last_missed_payment_date: str | None
    company: str
    city: str
    court: str
    claim_sent: bool
    claim_sent_date: str | None
    claim_sent_days: int | None
    debt_days: int | None
    debt_amount: float
    penalty_amount: float
    state_duty_amount: float
    total_amount: float
    lawsuit_sent: bool
    lawsuit_sent_date: str | None
    lawsuit_accepted: bool
    hearing_date: str | None
    decision_exists: bool
    decision: str | None
    decision_payout: float
    received_amount: float
    comment: str | None
    case_number: str | None
    mobile_phone: str | None
    home_phone: str | None
    address: str | None
    birth_date: str | None
    contract_total_amount: float | None
    contract_advance_amount: float | None
    lawsuit_installment_from: str | None = None
    lawsuit_installment_to: str | None = None
    lawsuit_monthly_payment_amount: float | None = None
    lawsuit_first_period_paid_amount: float | None = None
    case_court: str
    is_hearing_overdue_without_decision: bool


class ImportPreviewRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)


class ImportApplyRequest(BaseModel):
    import_ok_rows_only: bool = True


class DocumentProductOverride(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    quantity: int = Field(default=1, ge=1, le=9999)


class ClaimPdfGenerateRequest(BaseModel):
    debt_amount_override: float | None = Field(default=None, ge=0)
    product_overrides: list[DocumentProductOverride] | None = None


class CourtCreate(BaseModel):
    country: str = Field(default="kz", min_length=2, max_length=8)
    name: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    region: str = Field(min_length=1, max_length=255)


class CrmDebtorLookupResponse(BaseModel):
    contract_number: str
    contract_date: str | None = None
    client_name: str
    company: str
    city: str | None = None
    mobile_phone: str | None = None
    home_phone: str | None = None
    address: str | None = None
    debt_amount: float = Field(ge=0)
    contract_total_amount: float | None = Field(default=None, ge=0)
    contract_advance_amount: float | None = Field(default=None, ge=0)
    products: list[DocumentProductOverride] = Field(default_factory=list)


class LawsuitPdfGenerateRequest(BaseModel):
    court_name: str = Field(min_length=1, max_length=500)
    debt_amount: float = Field(ge=0)
    penalty_amount: float = Field(ge=0)
    state_duty_amount: float = Field(ge=0)
    installment_from: date
    installment_to: date
    monthly_payment_amount: float = Field(gt=0)
    first_period_paid_amount: float = Field(default=0, ge=0)
    product_overrides: list[DocumentProductOverride] | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=32)
    temporary_password: str = Field(min_length=8, max_length=255)


class UserView(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    must_change_password: bool
    is_active: bool
    created_at: str
    updated_at: str


class AuthMeResponse(BaseModel):
    user: UserView
