from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageDraw, ImageFont

from app.auth_service import (
    PASSWORD_MIN_LENGTH,
    ROLE_ADMIN,
    ROLE_LAWYER,
    ROLE_OWNER,
    SESSION_COOKIE_NAME,
    USER_ROLES,
    build_session_expiry,
    create_session_token,
    ensure_bootstrap_users,
    hash_password,
    serialize_user,
    utc_now,
    verify_password,
)
from app.company_requisites_service import (
    find_company_requisites,
    match_company_to_library,
    normalize_company_lookup_key,
    sanitize_company_name,
    seed_company_requisites,
)
from app.claim_pdf_service import (
    build_claim_output_path,
    load_claim_crm_context,
    resolve_claim_client_contacts,
    resolve_claim_contract_data,
    resolve_claim_products,
    resolve_claim_requisites,
)
from app.claim_pdf_renderers import render_claim_pdf as render_claim_pdf_renderer
from app.common_utils import (
    contract_date_from_number,
    contract_date_value_from_number,
    format_date,
    normalize_text,
    parse_bool,
    parse_date_value,
    parse_float,
    parse_int_value,
    preferred_phone as common_preferred_phone,
)
from app.country_service import normalize_country_code as normalize_country_code_service
from app.court_reference_service import (
    align_city_with_court as align_city_with_court_service,
    build_reference_catalog as build_reference_catalog_service,
    load_custom_courts as load_custom_courts_service,
    merge_static_court_catalog as merge_static_court_catalog_service,
)
from app.court_catalog import load_official_court_catalog, merge_court_catalog
from app.database import get_connection, init_db
from app.disell_api import DiSellApiClient, DiSellApiError
from app.document_helpers import (
    build_company_header_lines,
    build_company_payment_detail_lines,
    build_company_payment_detail_lines_uz,
    build_company_payment_details,
    normalize_document_products,
)
from app.financial_helpers import (
    compute_lawsuit_claim_price,
    compute_lawsuit_state_duty as compute_lawsuit_state_duty_base,
    compute_simple_penalty_amount,
    format_money,
)
from app.importer import (
    HEADER_ALIASES,
    build_headers_map,
    find_value_by_aliases,
    load_rows_from_path,
    normalize_import_row,
)
from app.lawsuit_calculations import (
    build_lawsuit_penalty_rows,
    build_short_client_name,
)
from app.lawsuit_pdf_renderers import render_lawsuit_pdf as render_lawsuit_pdf_renderer
from app.money_words import money_to_words_ru, money_to_words_sum_ru
from app.pdf_rendering import (
    draw_text_block as render_draw_text_block,
    load_font as render_load_font,
    wrap_text as render_wrap_text,
)
from app.reference_data import (
    CATEGORIES,
    COUNTRY_LABELS,
    DECISIONS,
    DEFAULT_COUNTRY,
    SUPPORTED_COUNTRIES,
    get_companies_by_country,
)
from app.schemas import (
    AuthMeResponse,
    ChangePasswordRequest,
    ClaimPdfGenerateRequest,
    CsiExportPdfRequest,
    CourtCreate,
    CrmDebtorLookupResponse,
    DebtorCreate,
    DebtorReceivedPaymentsUpdateRequest,
    DebtorUpdate,
    ImportApplyRequest,
    ImportPreviewRequest,
    IncomingClaimResponsePdfRequest,
    IncomingCorrespondenceCreate,
    IncomingCorrespondenceUpdate,
    LawsuitPdfGenerateRequest,
    LoginRequest,
    UserCreateRequest,
    UserView,
)

BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR.parent.parent
GENERATED_DIR = BASE_DIR.parent / "data" / "generated"
PDF_BROWSER_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]
SERIF_FONT_REGULAR_CANDIDATES = [
    Path(r"C:\Windows\Fonts\times.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSerif.ttf"),
]
SERIF_FONT_BOLD_CANDIDATES = [
    Path(r"C:\Windows\Fonts\timesbd.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"),
]

DEFAULT_CATEGORY = "Новый"
CATEGORY_PREPARE_LAWSUIT = "Готовим иск"
CATEGORY_LAWSUIT_FILED = "Иск подан"
CATEGORY_LAWSUIT_CLOSED = "Иск закрыт"
CATEGORY_NO_JURISDICTION = "Неподсудно"
CATEGORY_LIMITATION_EXPIRED = "Прошел срок исковой давности"
CATEGORY_SMALL_DEBT = "Маленькая сумма долга"
CATEGORY_WAITING_FOR_CLAIM_RESPONSE = "Ожидаем ответа по претензии"
CATEGORY_RETURNED_TO_LEGAL = "Возврат в работу Юр. Отдела"
CATEGORY_DEBT_CLOSED = "Долг закрыт"
CATEGORY_TRANSFER_TO_CSI = "Передать на ЧСИ"

DECISION_SATISFY = "Удовлетворить"
DECISION_PARTIAL = "Частично"
DECISION_SETTLEMENT = "По соглашению сторон"
DECISION_REFUSAL = "Отказ в иске"
DECISION_RETURN = "Возврат иска"

INCOMING_CORRESPONDENCE_CATEGORIES = [
    "Претензия",
    "Иск",
    "Исполнительный лист",
    "Ответ на претензию",
    "Постановление по делу об административном правонарушении",
    "Решение суда",
    "Постановление ОСП",
    "Судебный запрос",
    "Апелляционная жалоба",
    "Кассационная жалоба",
    "Прочее",
    "Возражения от клиента",
    "Судебная повестка",
    "Возвратная корреспонденция",
    "Арбитражный суд",
    "Медиация",
]
INCOMING_CATEGORY_CLAIM = "Претензия"
INCOMING_AUTHORITY_COURT = "court"
INCOMING_AUTHORITY_OTHER = "other"
TELEGRAM_BOT_TOKEN = os.getenv("LEGAL_DEP_TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("LEGAL_DEP_TELEGRAM_CHAT_ID", "").strip()

PRIORITY_CATEGORY_OVERRIDES = {
    "Закрытая компания",
    "Не должник",
    "Клиент частично оплачивает",
    "Требуется проверка решения в кабинете",
    CATEGORY_TRANSFER_TO_CSI,
}

DECISIONS_THAT_CLOSE_LAWSUIT = {
    DECISION_SATISFY,
    DECISION_PARTIAL,
    DECISION_SETTLEMENT,
}

SAFE_IMPORT_DECISION_CATEGORY_MAP = {
    CATEGORY_TRANSFER_TO_CSI: CATEGORY_TRANSFER_TO_CSI,
    "Прошел срок исковой давности": CATEGORY_LIMITATION_EXPIRED,
    "Маленькая сумма долга": CATEGORY_SMALL_DEBT,
    "Долг закрыт!": CATEGORY_DEBT_CLOSED,
    "Закрытая компания": "Закрытая компания",
    "Не должник": "Не должник",
    "Оплата по претензии": "Оплата по претензии",
}

SAFE_IMPORT_STAGE2_RULES: dict[tuple[str, str], dict[str, Any]] = {
    (CATEGORY_LAWSUIT_CLOSED, DECISION_SETTLEMENT): {
        "category": CATEGORY_LAWSUIT_CLOSED,
        "decision": DECISION_SETTLEMENT,
        "decision_exists": True,
        "claim_sent": True,
        "lawsuit_sent": True,
        "lawsuit_accepted": True,
        "imported_category_override": False,
    },
    (CATEGORY_LAWSUIT_CLOSED, DECISION_SATISFY): {
        "category": CATEGORY_LAWSUIT_CLOSED,
        "decision": DECISION_SATISFY,
        "decision_exists": True,
        "claim_sent": True,
        "lawsuit_sent": True,
        "lawsuit_accepted": True,
        "imported_category_override": False,
    },
    (CATEGORY_LAWSUIT_CLOSED, DECISION_PARTIAL): {
        "category": CATEGORY_LAWSUIT_CLOSED,
        "decision": DECISION_PARTIAL,
        "decision_exists": True,
        "claim_sent": True,
        "lawsuit_sent": True,
        "lawsuit_accepted": True,
        "imported_category_override": False,
    },
    ("Проверка решения в кабинете", ""): {
        "category": "Требуется проверка решения в кабинете",
        "decision": None,
        "decision_exists": False,
        "claim_sent": True,
        "lawsuit_sent": True,
        "lawsuit_accepted": True,
        "imported_category_override": True,
    },
    (CATEGORY_LAWSUIT_FILED, ""): {
        "category": CATEGORY_LAWSUIT_FILED,
        "decision": None,
        "decision_exists": False,
        "claim_sent": True,
        "lawsuit_sent": True,
        "lawsuit_accepted": False,
        "imported_category_override": False,
    },
    ("Возврат иска", "Отказ"): {
        "category": CATEGORY_NO_JURISDICTION,
        "decision": DECISION_REFUSAL,
        "decision_exists": True,
        "claim_sent": True,
        "lawsuit_sent": True,
        "lawsuit_accepted": True,
        "imported_category_override": False,
    },
    ("Возврат иска", DECISION_RETURN): {
        "category": CATEGORY_RETURNED_TO_LEGAL,
        "decision": DECISION_RETURN,
        "decision_exists": True,
        "claim_sent": True,
        "lawsuit_sent": True,
        "lawsuit_accepted": True,
        "imported_category_override": False,
    },
}

app = FastAPI(title="Legal Department", version="0.3.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
UZ_BRV_AMOUNT = 412000.0


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with get_connection() as connection:
        ensure_bootstrap_users(connection)
        seed_company_requisites(connection)
        connection.commit()


def get_session_user(connection, session_token: str | None) -> dict[str, Any] | None:
    if not session_token:
        return None

    row = connection.execute(
        """
        SELECT u.*
        FROM user_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.session_token = ?
        """,
        (session_token,),
    ).fetchone()
    if row is None:
        return None

    expires_at_row = connection.execute(
        "SELECT expires_at FROM user_sessions WHERE session_token = ?",
        (session_token,),
    ).fetchone()
    expires_at_value = expires_at_row["expires_at"] if expires_at_row else None
    if not expires_at_value:
        connection.execute("DELETE FROM user_sessions WHERE session_token = ?", (session_token,))
        connection.commit()
        return None

    expires_at = datetime.fromisoformat(str(expires_at_value))
    if expires_at <= utc_now():
        connection.execute("DELETE FROM user_sessions WHERE session_token = ?", (session_token,))
        connection.commit()
        return None

    user = dict(row)
    if not parse_bool(user.get("is_active")):
        connection.execute("DELETE FROM user_sessions WHERE session_token = ?", (session_token,))
        connection.commit()
        return None

    return user


def get_optional_current_user(request: Request) -> dict[str, Any] | None:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    with get_connection() as connection:
        return get_session_user(connection, session_token)


def require_authenticated_user(request: Request) -> dict[str, Any]:
    user = get_optional_current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTH_REQUIRED")
    return user


def require_app_user(request: Request) -> dict[str, Any]:
    user = require_authenticated_user(request)
    if parse_bool(user.get("must_change_password")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PASSWORD_CHANGE_REQUIRED")
    return user


def require_owner_user(request: Request) -> dict[str, Any]:
    user = require_app_user(request)
    if str(user.get("role")) != ROLE_OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="OWNER_REQUIRED")
    return user


def set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _legacy_normalize_country_code(country: str | None) -> str:
    normalized = (country or DEFAULT_COUNTRY).strip().lower()
    if normalized not in SUPPORTED_COUNTRIES:
        raise HTTPException(status_code=400, detail="Неизвестная страна.")
    return normalized


def _legacy_load_custom_courts(connection, country: str) -> list[dict[str, str]]:
    rows = connection.execute(
        """
        SELECT name, city, region
        FROM custom_courts
        WHERE COALESCE(country, ?) = ?
        ORDER BY name COLLATE NOCASE ASC
        """,
        (DEFAULT_COUNTRY, normalize_country_code(country)),
    ).fetchall()
    result: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        values = [str(item.get("name") or "").strip(), str(item.get("city") or "").strip(), str(item.get("region") or "").strip()]
        if not all(values):
            continue
        if any("?" in value for value in values):
            continue
        result.append(item)
    return result


def _legacy_build_reference_catalog(connection, country: str) -> dict[str, Any]:
    normalized_country = normalize_country_code(country)
    custom_courts = load_custom_courts(connection, normalized_country)
    if normalized_country == "uz":
        return merge_static_court_catalog(UZBEKISTAN_COURT_CATALOG, custom_courts)
    return merge_court_catalog(custom_courts)


def _legacy_merge_static_court_catalog(
    base_catalog: dict[str, Any], custom_courts: list[dict[str, str]]
) -> dict[str, Any]:
    regions = list(base_catalog["regions"])
    cities = set(base_catalog["cities"])
    courts_by_city = {city: list(items) for city, items in base_catalog["courtsByCity"].items()}
    courts_by_region = {region: list(items) for region, items in base_catalog["courtsByRegion"].items()}
    court_city_map = dict(base_catalog["courtCityMap"])
    court_region_map = dict(base_catalog["courtRegionMap"])
    city_region_map = dict(base_catalog["cityRegionMap"])
    cities_by_region = {region: list(items) for region, items in base_catalog["citiesByRegion"].items()}

    for item in custom_courts:
        name = str(item["name"]).strip()
        city = str(item["city"]).strip()
        region = str(item["region"]).strip()
        if not name or not city or not region:
            continue

        if region not in regions:
            regions.append(region)
        cities.add(city)
        court_city_map[name] = city
        court_region_map[name] = region
        city_region_map[city] = region
        courts_by_city.setdefault(city, [])
        if name not in courts_by_city[city]:
            courts_by_city[city].append(name)
        courts_by_region.setdefault(region, [])
        if name not in courts_by_region[region]:
            courts_by_region[region].append(name)
        cities_by_region.setdefault(region, [])
        if city not in cities_by_region[region]:
            cities_by_region[region].append(city)

    return {
        "regions": sorted(regions),
        "cities": sorted(cities),
        "courtsByCity": {city: sorted(set(items)) for city, items in courts_by_city.items()},
        "courtsByRegion": {region: sorted(set(items)) for region, items in courts_by_region.items()},
        "courtCityMap": court_city_map,
        "courtRegionMap": court_region_map,
        "cityRegionMap": city_region_map,
        "citiesByRegion": {region: sorted(set(items)) for region, items in cities_by_region.items()},
    }


def _legacy_align_city_with_court(connection, country: str, city: str, court: str) -> tuple[str, str]:
    normalized_city = city.strip()
    normalized_court = court.strip()
    catalog = build_reference_catalog(connection, country)
    mapped_city = catalog["courtCityMap"].get(normalized_court)
    if mapped_city:
        return mapped_city, normalized_court
    return normalized_city, normalized_court


@lru_cache(maxsize=1)
def get_kz_import_reference_data() -> dict[str, list[str]]:
    catalog = load_official_court_catalog()
    return {
        "companies": get_companies_by_country("kz"),
        "cities": sorted(str(city) for city in catalog.get("cities", [])),
        "courts": sorted(str(court) for court in dict(catalog.get("courtCityMap", {})).keys()),
    }


normalize_country_code = normalize_country_code_service
load_custom_courts = load_custom_courts_service
build_reference_catalog = build_reference_catalog_service
merge_static_court_catalog = merge_static_court_catalog_service
align_city_with_court = align_city_with_court_service
preferred_phone = common_preferred_phone


def _legacy_preferred_phone(row: dict[str, Any]) -> str:
    return normalize_text(row.get("mobile_phone")) or normalize_text(row.get("home_phone")) or "вЂ”"


def compute_lawsuit_state_duty(country: str, debt_amount: float, penalty_amount: float) -> float:
    return compute_lawsuit_state_duty_base(
        normalize_country_code(country),
        debt_amount,
        penalty_amount,
        uz_brv_amount=UZ_BRV_AMOUNT,
    )



def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return render_load_font(
        size,
        bold=bold,
        regular_candidates=SERIF_FONT_REGULAR_CANDIDATES,
        bold_candidates=SERIF_FONT_BOLD_CANDIDATES,
    )


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    return render_wrap_text(draw, text, font, max_width)


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    x: int,
    y: int,
    width: int,
    font: ImageFont.ImageFont,
    line_spacing: int,
    align: str = "left",
    paragraph_spacing: int = 0,
    first_line_indent: int = 0,
) -> int:
    return render_draw_text_block(
        draw,
        text,
        x=x,
        y=y,
        width=width,
        font=font,
        line_spacing=line_spacing,
        align=align,
        paragraph_spacing=paragraph_spacing,
        first_line_indent=first_line_indent,
    )




def render_claim_pdf(
    debtor: dict[str, Any],
    *,
    debt_amount_override: float | None = None,
    product_overrides: list[dict[str, Any]] | None = None,
) -> Path:
    return render_claim_pdf_renderer(
        debtor,
        compute_financials_fn=compute_financials,
        generated_dir=GENERATED_DIR,
        debt_amount_override=debt_amount_override,
        product_overrides=product_overrides,
    )


def render_lawsuit_pdf(debtor: dict[str, Any], payload: LawsuitPdfGenerateRequest) -> Path:
    return render_lawsuit_pdf_renderer(
        debtor,
        payload,
        compute_financials_fn=compute_financials,
        compute_lawsuit_state_duty_fn=compute_lawsuit_state_duty,
        generated_dir=GENERATED_DIR,
    )


def order_debtors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    children_by_parent: dict[int, list[dict[str, Any]]] = {}
    roots: list[dict[str, Any]] = []

    for row in rows:
        parent_id = row.get("parent_debtor_id")
        if parent_id:
            children_by_parent.setdefault(int(parent_id), []).append(row)
        else:
            roots.append(row)

    roots.sort(key=debtor_sort_key, reverse=True)
    for children in children_by_parent.values():
        children.sort(key=lambda item: int(item["id"]), reverse=True)

    ordered: list[dict[str, Any]] = []

    def append_branch(row: dict[str, Any]) -> None:
        ordered.append(row)
        for child in children_by_parent.get(int(row["id"]), []):
            append_branch(child)

    for root in roots:
        append_branch(root)

    return ordered


def debtor_sort_key(row: dict[str, Any]) -> tuple[date, int]:
    contract_date = contract_date_value_from_number(str(row.get("contract_number") or ""))
    return (contract_date or date.min, int(row["id"]))


def apply_pre_validation_defaults(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = merge_row(existing, updates)
    category = normalize_text(merged.get("category"))
    decision = normalize_text(merged.get("decision"))

    if category == CATEGORY_LAWSUIT_CLOSED and decision:
        updates["claim_sent"] = True
        updates["lawsuit_sent"] = True
        updates["lawsuit_accepted"] = True
        updates["decision_exists"] = True

    return updates


def apply_business_rules(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = merge_row(existing, updates)
    financials = compute_financials(merged)
    existing_category = normalize_text(existing.get("category")) or DEFAULT_CATEGORY
    has_explicit_decision_payout_update = "decision_payout" in updates

    if (
        existing.get("parent_debtor_id")
        and not parse_bool(existing.get("decision_exists"))
        and updates.get("decision_exists") is True
        and "category" not in updates
    ):
        updates["category"] = CATEGORY_PREPARE_LAWSUIT
        merged["category"] = CATEGORY_PREPARE_LAWSUIT

    if parse_bool(merged.get("lawsuit_sent")) and not parse_date_value(merged.get("lawsuit_sent_date")):
        updates["lawsuit_sent_date"] = date.today()
        merged["lawsuit_sent_date"] = updates["lawsuit_sent_date"]

    if parse_bool(merged.get("claim_sent")) and not parse_date_value(merged.get("claim_sent_date")):
        updates["claim_sent_date"] = date.today()
        merged["claim_sent_date"] = updates["claim_sent_date"]

    if not parse_bool(merged.get("claim_sent")):
        updates["claim_sent_date"] = None
        updates["lawsuit_sent"] = False
        updates["lawsuit_sent_date"] = None
        updates["lawsuit_accepted"] = False
        updates["hearing_date"] = None
        updates["decision_exists"] = False
        updates["decision"] = None
        updates["decision_payout"] = 0
        merged["claim_sent_date"] = None
        merged["lawsuit_sent"] = False
        merged["lawsuit_sent_date"] = None
        merged["lawsuit_accepted"] = False
        merged["hearing_date"] = None
        merged["decision_exists"] = False
        merged["decision"] = None
        merged["decision_payout"] = 0

    if not parse_bool(merged.get("lawsuit_sent")):
        updates["lawsuit_sent_date"] = None
        updates["lawsuit_accepted"] = False
        updates["hearing_date"] = None
        updates["decision_exists"] = False
        updates["decision"] = None
        updates["decision_payout"] = 0
        merged["lawsuit_sent_date"] = None
        merged["lawsuit_accepted"] = False
        merged["hearing_date"] = None
        merged["decision_exists"] = False
        merged["decision"] = None
        merged["decision_payout"] = 0

    if not parse_bool(merged.get("lawsuit_accepted")):
        updates["hearing_date"] = None
        updates["decision_exists"] = False
        updates["decision"] = None
        updates["decision_payout"] = 0
        merged["hearing_date"] = None
        merged["decision_exists"] = False
        merged["decision"] = None
        merged["decision_payout"] = 0

    if not parse_bool(merged.get("decision_exists")):
        updates["decision"] = None
        updates["decision_payout"] = 0
        merged["decision"] = None
        merged["decision_payout"] = 0

    existing_decision = normalize_text(existing.get("decision"))
    decision = normalize_text(merged.get("decision"))
    decision_changed = decision != existing_decision
    if decision_changed:
        updates["decision_payout"] = 0
        merged["decision_payout"] = 0

    if decision == DECISION_SATISFY and decision_changed and not has_explicit_decision_payout_update:
        updates["decision_payout"] = financials["total_amount"]
        merged["decision_payout"] = financials["total_amount"]

    auto_category = determine_auto_category(merged)
    if (
        parse_bool(existing.get("imported_category_override"))
        and existing_category == DEFAULT_CATEGORY
        and auto_category is not None
        and auto_category != DEFAULT_CATEGORY
        and "category" not in updates
    ):
        updates["category"] = auto_category
        updates["imported_category_override"] = False
        merged["category"] = auto_category
        merged["imported_category_override"] = False

    return updates


def validate_category_update(existing: dict[str, Any], updates: dict[str, Any]) -> None:
    requested_category = updates.get("category")
    if requested_category is None:
        return

    normalized_requested = normalize_text(requested_category)
    if normalized_requested not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Недопустимая категория.")

    if (
        not existing.get("parent_debtor_id")
        and existing.get("has_return_rework_child")
        and normalized_requested != CATEGORY_RETURNED_TO_LEGAL
    ):
        raise HTTPException(
            status_code=400,
            detail="У материнской записи с подстрокой возврата категория зафиксирована на «Возврат в работу Юр. Отдела».",
        )

    merged = merge_row(existing, updates)
    auto_category = determine_auto_category(merged)
    if (
        existing.get("parent_debtor_id")
        and not parse_bool(existing.get("decision_exists"))
        and updates.get("decision_exists") is True
        and normalized_requested == CATEGORY_PREPARE_LAWSUIT
    ):
        return
    if normalized_requested in PRIORITY_CATEGORY_OVERRIDES:
        return

    if auto_category is not None and normalized_requested != auto_category:
        raise HTTPException(
            status_code=400,
            detail="Эта категория выставляется автоматически. Доступны только приоритетные ручные статусы.",
        )

def validate_decision_update(existing: dict[str, Any], updates: dict[str, Any]) -> None:
    requested_decision = normalize_text(updates.get("decision"))
    is_return_rework = bool(existing.get("parent_debtor_id"))
    if is_return_rework and requested_decision == DECISION_RETURN:
        raise HTTPException(
            status_code=400,
            detail="Для подстроки возврата иска нельзя повторно выбрать решение «Возврат иска».",
        )

    return


def validate_stage_dependencies(existing: dict[str, Any], updates: dict[str, Any]) -> None:
    merged = merge_row(existing, updates)
    claim_sent = parse_bool(merged.get("claim_sent"))
    lawsuit_sent = parse_bool(merged.get("lawsuit_sent"))
    lawsuit_accepted = parse_bool(merged.get("lawsuit_accepted"))

    if updates.get("lawsuit_sent") is True and not claim_sent:
        raise HTTPException(
            status_code=400,
            detail="Нельзя установить «Направлен иск = Да», пока «Претензия = Нет».",
        )

    if updates.get("lawsuit_accepted") is True and (not claim_sent or not lawsuit_sent):
        raise HTTPException(
            status_code=400,
            detail="Нельзя установить «Иск принят = Да», пока претензия не отправлена и иск не направлен.",
        )

    if updates.get("decision_exists") is True and (not claim_sent or not lawsuit_sent or not lawsuit_accepted):
        raise HTTPException(
            status_code=400,
            detail="Нельзя установить «Есть решение = Да», пока претензия не отправлена, иск не направлен и иск не принят.",
        )


def ensure_return_rework_child(connection, row: dict[str, Any]) -> None:
    decision = normalize_text(row.get("decision"))
    if decision != DECISION_RETURN:
        return

    existing_child = connection.execute(
        "SELECT id FROM debtors WHERE parent_debtor_id = ? LIMIT 1",
        (row["id"],),
    ).fetchone()
    if existing_child is not None:
        return

    created_at = datetime.now().replace(microsecond=0).isoformat()
    connection.execute(
        """
        INSERT INTO debtors (
            created_at,
            country,
            category,
            parent_debtor_id,
            client_name,
            contract_number,
            last_missed_payment_date,
            company,
            city,
            court,
            claim_sent,
            claim_sent_date,
            debt_amount,
            imported_claim_sent_days,
            imported_debt_days,
            imported_penalty_amount,
            imported_state_duty_amount,
            imported_total_amount,
            lawsuit_sent,
            lawsuit_sent_date,
            lawsuit_accepted,
            hearing_date,
            decision_exists,
            decision,
            decision_payout,
            received_amount,
            comment,
            case_number
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            created_at,
            normalize_country_code(str(row.get("country") or DEFAULT_COUNTRY)),
            CATEGORY_PREPARE_LAWSUIT,
            row["id"],
            row["client_name"],
            row["contract_number"],
            row["last_missed_payment_date"],
            row["company"],
            row["city"],
            row["court"],
            1 if parse_bool(row.get("claim_sent")) else 0,
            row.get("claim_sent_date"),
            float(row.get("debt_amount") or 0),
            parse_int_value(row.get("imported_claim_sent_days")),
            parse_int_value(row.get("imported_debt_days")),
            float(row.get("imported_penalty_amount") or 0),
            float(row.get("imported_state_duty_amount") or 0),
            float(row.get("imported_total_amount") or 0),
            0,
            None,
            0,
            None,
            0,
            None,
            0,
            0,
            None,
            None,
        ),
    )


def has_return_rework_child(connection, debtor_id: int) -> bool:
    child = connection.execute(
        "SELECT 1 FROM debtors WHERE parent_debtor_id = ? LIMIT 1",
        (debtor_id,),
    ).fetchone()
    return child is not None


def mark_return_rework_children(rows: list[dict[str, Any]]) -> None:
    parent_ids = {int(row["parent_debtor_id"]) for row in rows if row.get("parent_debtor_id")}
    for row in rows:
        row["has_return_rework_child"] = int(row["id"]) in parent_ids


def create_import_batch(connection, source_path: str) -> int:
    created_at = datetime.now().replace(microsecond=0).isoformat()
    cursor = connection.execute(
        """
        INSERT INTO import_batches (
            created_at,
            source_path,
            source_filename,
            status,
            total_rows,
            ok_rows,
            needs_review_rows,
            blocked_rows,
            imported_rows,
            notes
        )
        VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, ?)
        """,
        (
            created_at,
            source_path,
            Path(source_path).name,
            "preview",
            "Черновой пакет импорта. Данные пока не попали в основную таблицу.",
        ),
    )
    return int(cursor.lastrowid)


def analyze_import_row(raw_row: dict[str, Any], *, row_index: int) -> dict[str, Any]:
    kz_reference = get_kz_import_reference_data()
    normalized_result = normalize_import_row(
        raw_row,
        categories=CATEGORIES,
        decisions=DECISIONS,
        companies=kz_reference["companies"],
        cities=kz_reference["cities"],
        courts=kz_reference["courts"],
    )
    normalized = normalized_result["normalized_data"]
    warnings = list(normalized_result["warnings"])
    errors = list(normalized_result["errors"])

    prepared = prepare_import_debtor_payload(normalized)
    source_category = normalize_text(normalized.get("category"))
    suggested_category = None

    if not errors:
        suggested_category = determine_auto_category(prepared) or source_category or DEFAULT_CATEGORY
        prepared["category"] = suggested_category

        if source_category and suggested_category and source_category != suggested_category:
            warnings.append(
                f"Категория из файла («{source_category}») не совпадает с категорией по правилам («{suggested_category}»)."
            )

        if normalize_text(prepared.get("decision")) and not parse_bool(prepared.get("decision_exists")):
            warnings.append("Решение указано, но признак «Есть решение» не был подтвержден в исходной строке.")

    status = "blocked" if errors else "needs_review" if warnings else "ok"
    return {
        "rowIndex": row_index,
        "status": status,
        "source_category": source_category,
        "suggested_category": suggested_category or source_category or DEFAULT_CATEGORY,
        "normalized_data": prepared,
        "warnings": dedupe_list(warnings),
        "errors": dedupe_list(errors),
    }


def build_safe_stage1_import_rows(source_path: str) -> list[dict[str, Any]]:
    kz_reference = get_kz_import_reference_data()
    safe_rows: list[dict[str, Any]] = []

    for row_index, raw_row in enumerate(load_rows_from_path(source_path), start=1):
        headers_map = build_headers_map(raw_row)
        raw_decision = normalize_text(find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["decision"]))
        if raw_decision not in SAFE_IMPORT_DECISION_CATEGORY_MAP:
            continue

        normalized_result = normalize_import_row(
            raw_row,
            categories=CATEGORIES,
            decisions=DECISIONS,
            companies=kz_reference["companies"],
            cities=kz_reference["cities"],
            courts=kz_reference["courts"],
        )
        normalized = normalized_result["normalized_data"]
        prepared = prepare_import_debtor_payload(normalized)
        prepared["company"] = prepared.get("company") or normalize_text(
            find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["company"])
        ) or ""
        prepared["city"] = prepared.get("city") or normalize_text(
            find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["city"])
        ) or ""
        prepared["court"] = prepared.get("court") or normalize_text(
            find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["court"])
        ) or ""
        prepared["category"] = SAFE_IMPORT_DECISION_CATEGORY_MAP[raw_decision]
        prepared["decision"] = None
        prepared["decision_exists"] = False
        prepared["imported_category_override"] = True
        if prepared.get("claim_sent_date") or prepared.get("imported_claim_sent_days") is not None:
            prepared["claim_sent"] = True
        if prepared.get("lawsuit_sent_date"):
            prepared["lawsuit_sent"] = True
        if prepared.get("hearing_date"):
            prepared["lawsuit_accepted"] = True

        reconstructed_date = reconstruct_last_missed_payment_date(prepared)
        prepared["last_missed_payment_date"] = reconstructed_date or ""
        prepared["client_name"] = prepared.get("client_name") or ""
        prepared["contract_number"] = prepared.get("contract_number") or ""
        prepared["company"] = prepared.get("company") or ""
        prepared["city"] = prepared.get("city") or ""
        prepared["court"] = prepared.get("court") or ""
        prepared["debt_amount"] = float(prepared.get("debt_amount") or 0)

        prepared["comment"] = normalize_text(prepared.get("comment")) or None

        safe_rows.append(
            {
                "row_index": row_index,
                "status": "ok",
                "source_data": raw_row,
                "normalized_data": prepared,
                "source_category": normalize_text(find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["category"])),
                "suggested_category": prepared["category"],
                "warnings": [],
                "errors": [],
            }
        )

    return safe_rows


def import_safe_stage1_file(source_path: str) -> dict[str, Any]:
    safe_rows = build_safe_stage1_import_rows(source_path)

    with get_connection() as connection:
        batch_id = create_import_batch(connection, source_path)
        imported_rows = 0
        skipped_rows = 0

        for safe_row in safe_rows:
            normalized = safe_row["normalized_data"]
            existing = connection.execute(
                """
                SELECT id FROM debtors
                WHERE imported_category_override = 1
                  AND client_name = ?
                  AND contract_number = ?
                  AND category = ?
                LIMIT 1
                """,
                (
                    normalized.get("client_name") or "",
                    normalized.get("contract_number") or "",
                    normalized.get("category") or DEFAULT_CATEGORY,
                ),
            ).fetchone()
            if existing is not None:
                skipped_rows += 1
                continue

            debtor_id = insert_imported_debtor(connection, safe_row)
            connection.execute(
                """
                INSERT INTO import_rows (
                    batch_id,
                    row_index,
                    status,
                    source_data_json,
                    normalized_data_json,
                    source_category,
                    suggested_category,
                    errors_json,
                    warnings_json,
                    debtor_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    safe_row["row_index"],
                    "ok",
                    dumps_json(safe_row["source_data"]),
                    dumps_json(safe_row["normalized_data"]),
                    safe_row["source_category"],
                    safe_row["suggested_category"],
                    dumps_json([]),
                    dumps_json([]),
                    debtor_id,
                ),
            )
            imported_rows += 1

        connection.execute(
            """
            UPDATE import_batches
            SET status = ?, total_rows = ?, ok_rows = ?, imported_rows = ?, notes = ?
            WHERE id = ?
            """,
            (
                "imported",
                len(safe_rows),
                len(safe_rows),
                imported_rows,
                f"Stage1 безопасный импорт статусов из решения. Пропущено дублей: {skipped_rows}.",
                batch_id,
            ),
        )
        connection.commit()

    return {
        "batch_id": batch_id,
        "total_rows": len(safe_rows),
        "imported_rows": imported_rows,
        "skipped_rows": skipped_rows,
    }


def build_safe_stage2_import_rows(source_path: str) -> list[dict[str, Any]]:
    kz_reference = get_kz_import_reference_data()
    safe_rows: list[dict[str, Any]] = []

    for row_index, raw_row in enumerate(load_rows_from_path(source_path), start=1):
        headers_map = build_headers_map(raw_row)
        raw_category = normalize_text(find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["category"])) or ""
        raw_decision = normalize_text(find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["decision"])) or ""
        if raw_decision in SAFE_IMPORT_DECISION_CATEGORY_MAP:
            continue

        rule = SAFE_IMPORT_STAGE2_RULES.get((raw_category, raw_decision))
        if rule is None:
            continue

        normalized_result = normalize_import_row(
            raw_row,
            categories=CATEGORIES,
            decisions=DECISIONS,
            companies=kz_reference["companies"],
            cities=kz_reference["cities"],
            courts=kz_reference["courts"],
        )
        normalized = normalized_result["normalized_data"]
        prepared = prepare_import_debtor_payload(normalized)
        prepared["company"] = prepared.get("company") or normalize_text(
            find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["company"])
        ) or ""
        prepared["city"] = prepared.get("city") or normalize_text(
            find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["city"])
        ) or ""
        prepared["court"] = prepared.get("court") or normalize_text(
            find_value_by_aliases(raw_row, headers_map, HEADER_ALIASES["court"])
        ) or ""
        prepared["category"] = rule["category"]
        prepared["decision"] = rule["decision"]
        prepared["decision_exists"] = rule["decision_exists"]
        prepared["claim_sent"] = rule["claim_sent"]
        prepared["lawsuit_sent"] = rule["lawsuit_sent"]
        prepared["lawsuit_accepted"] = rule["lawsuit_accepted"]
        prepared["imported_category_override"] = rule["imported_category_override"]

        reconstructed_date = reconstruct_last_missed_payment_date(prepared)
        prepared["last_missed_payment_date"] = reconstructed_date or ""
        prepared["client_name"] = prepared.get("client_name") or ""
        prepared["contract_number"] = prepared.get("contract_number") or ""
        prepared["company"] = prepared.get("company") or ""
        prepared["city"] = prepared.get("city") or ""
        prepared["court"] = prepared.get("court") or ""
        prepared["debt_amount"] = float(prepared.get("debt_amount") or 0)
        prepared["comment"] = normalize_text(prepared.get("comment")) or None

        safe_rows.append(
            {
                "row_index": row_index,
                "status": "ok",
                "source_data": raw_row,
                "normalized_data": prepared,
                "source_category": raw_category,
                "suggested_category": prepared["category"],
                "warnings": [],
                "errors": [],
            }
        )

    return safe_rows


def import_safe_stage2_file(source_path: str) -> dict[str, Any]:
    safe_rows = build_safe_stage2_import_rows(source_path)

    with get_connection() as connection:
        batch_id = create_import_batch(connection, source_path)
        imported_rows = 0
        skipped_rows = 0

        for safe_row in safe_rows:
            normalized = safe_row["normalized_data"]
            existing = connection.execute(
                """
                SELECT id FROM debtors
                WHERE client_name = ?
                  AND contract_number = ?
                  AND category = ?
                  AND COALESCE(decision, '') = COALESCE(?, '')
                LIMIT 1
                """,
                (
                    normalized.get("client_name") or "",
                    normalized.get("contract_number") or "",
                    normalized.get("category") or DEFAULT_CATEGORY,
                    normalized.get("decision"),
                ),
            ).fetchone()
            if existing is not None:
                skipped_rows += 1
                continue

            debtor_id = insert_imported_debtor(connection, safe_row)
            connection.execute(
                """
                INSERT INTO import_rows (
                    batch_id,
                    row_index,
                    status,
                    source_data_json,
                    normalized_data_json,
                    source_category,
                    suggested_category,
                    errors_json,
                    warnings_json,
                    debtor_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    safe_row["row_index"],
                    "ok",
                    dumps_json(safe_row["source_data"]),
                    dumps_json(safe_row["normalized_data"]),
                    safe_row["source_category"],
                    safe_row["suggested_category"],
                    dumps_json([]),
                    dumps_json([]),
                    debtor_id,
                ),
            )
            imported_rows += 1

        connection.execute(
            """
            UPDATE import_batches
            SET status = 'imported',
                total_rows = ?,
                ok_rows = ?,
                imported_rows = ?,
                notes = ?
            WHERE id = ?
            """,
            (
                len(safe_rows),
                len(safe_rows),
                imported_rows,
                f"Stage2 безопасный импорт процессуальных статусов и возвратов. Пропущено дублей: {skipped_rows}.",
                batch_id,
            ),
        )
        connection.commit()

    return {
        "batch_id": batch_id,
        "total_rows": len(safe_rows),
        "imported_rows": imported_rows,
        "skipped_rows": skipped_rows,
    }


def reconstruct_last_missed_payment_date(row: dict[str, Any]) -> str | None:
    claim_sent_date = parse_date_value(row.get("claim_sent_date"))
    if claim_sent_date is None:
        return None

    debt_days = parse_int_value(row.get("imported_debt_days"))
    if debt_days is not None and debt_days >= 0:
        return (claim_sent_date - timedelta(days=debt_days)).isoformat()

    debt_amount = parse_float(row.get("debt_amount"))
    if debt_amount <= 0:
        return None

    penalty_amount = row.get("imported_penalty_amount")
    if penalty_amount not in (None, ""):
        derived_days = parse_float(penalty_amount) / (debt_amount * 0.001)
        rounded_days = round(derived_days)
        if abs(derived_days - rounded_days) < 0.01 and rounded_days >= 0:
            return (claim_sent_date - timedelta(days=rounded_days)).isoformat()

    total_amount = row.get("imported_total_amount")
    if total_amount not in (None, ""):
        derived_penalty = parse_float(total_amount) - debt_amount
        if derived_penalty >= 0:
            derived_days = derived_penalty / (debt_amount * 0.001)
            rounded_days = round(derived_days)
            if abs(derived_days - rounded_days) < 0.01 and rounded_days >= 0:
                return (claim_sent_date - timedelta(days=rounded_days)).isoformat()

    return None


def prepare_import_debtor_payload(normalized: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "category": normalize_text(normalized.get("category")) or DEFAULT_CATEGORY,
        "parent_debtor_id": None,
        "client_name": normalized.get("client_name"),
        "contract_number": normalized.get("contract_number"),
        "last_missed_payment_date": normalized.get("last_missed_payment_date"),
        "company": normalized.get("company"),
        "city": normalized.get("city"),
        "court": normalized.get("court"),
        "claim_sent": normalized.get("claim_sent") if normalized.get("claim_sent") is not None else False,
        "claim_sent_date": normalized.get("claim_sent_date"),
        "debt_amount": normalized.get("debt_amount") if normalized.get("debt_amount") is not None else 0,
        "lawsuit_sent": normalized.get("lawsuit_sent") if normalized.get("lawsuit_sent") is not None else False,
        "lawsuit_sent_date": normalized.get("lawsuit_sent_date"),
        "lawsuit_accepted": (
            normalized.get("lawsuit_accepted") if normalized.get("lawsuit_accepted") is not None else False
        ),
        "hearing_date": normalized.get("hearing_date"),
        "decision_exists": (
            normalized.get("decision_exists")
            if normalized.get("decision_exists") is not None
            else bool(normalize_text(normalized.get("decision")))
        ),
        "decision": normalize_text(normalized.get("decision")),
        "decision_payout": normalized.get("decision_payout") if normalized.get("decision_payout") is not None else 0,
        "received_amount": normalized.get("received_amount") if normalized.get("received_amount") is not None else 0,
        "comment": normalize_text(normalized.get("comment")),
        "case_number": normalize_text(normalized.get("case_number")),
        "imported_claim_sent_days": parse_int_value(normalized.get("imported_claim_sent_days")),
        "imported_debt_days": parse_int_value(normalized.get("imported_debt_days")),
        "imported_penalty_amount": normalized.get("imported_penalty_amount") if normalized.get("imported_penalty_amount") is not None else 0,
        "imported_state_duty_amount": (
            normalized.get("imported_state_duty_amount") if normalized.get("imported_state_duty_amount") is not None else 0
        ),
        "imported_total_amount": normalized.get("imported_total_amount") if normalized.get("imported_total_amount") is not None else 0,
        "imported_category_override": False,
    }
    return apply_pre_validation_defaults({}, payload)


def serialize_import_batch(batch: dict[str, Any]) -> dict[str, Any]:
    created_at = datetime.fromisoformat(batch["created_at"])
    return {
        "id": batch["id"],
        "created_at": batch["created_at"],
        "created_at_label": created_at.strftime("%d.%m.%Y %H:%M"),
        "source_path": batch["source_path"],
        "source_filename": batch["source_filename"],
        "status": batch["status"],
        "total_rows": int(batch.get("total_rows") or 0),
        "ok_rows": int(batch.get("ok_rows") or 0),
        "needs_review_rows": int(batch.get("needs_review_rows") or 0),
        "blocked_rows": int(batch.get("blocked_rows") or 0),
        "imported_rows": int(batch.get("imported_rows") or 0),
        "notes": batch.get("notes"),
    }


def serialize_import_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "row_index": row["row_index"],
        "status": row["status"],
        "source_data": loads_json(row["source_data_json"]),
        "normalized_data": loads_json(row["normalized_data_json"]),
        "source_category": row.get("source_category"),
        "suggested_category": row.get("suggested_category"),
        "warnings": loads_json(row["warnings_json"]),
        "errors": loads_json(row["errors_json"]),
        "debtor_id": row.get("debtor_id"),
    }


def insert_imported_debtor(connection, import_row: dict[str, Any]) -> int:
    normalized = dict(import_row["normalized_data"])
    normalized = apply_import_insert_defaults(normalized)
    created_at = datetime.now().replace(microsecond=0).isoformat()
    cursor = connection.execute(
        """
        INSERT INTO debtors (
            created_at,
            country,
            category,
            parent_debtor_id,
            client_name,
            contract_number,
            last_missed_payment_date,
            company,
            city,
            court,
            claim_sent,
            claim_sent_date,
            debt_amount,
            imported_claim_sent_days,
            imported_debt_days,
            imported_penalty_amount,
            imported_state_duty_amount,
            imported_total_amount,
            imported_category_override,
            lawsuit_sent,
            lawsuit_sent_date,
            lawsuit_accepted,
            hearing_date,
            decision_exists,
            decision,
            decision_payout,
            received_amount,
            comment,
            case_number
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            created_at,
            normalize_country_code(str(normalized.get("country") or DEFAULT_COUNTRY)),
            normalized.get("category") or DEFAULT_CATEGORY,
            None,
            normalized["client_name"],
            normalized["contract_number"],
            normalized.get("last_missed_payment_date") or "",
            normalized["company"],
            normalized["city"],
            normalized["court"],
            1 if parse_bool(normalized.get("claim_sent")) else 0,
            normalized.get("claim_sent_date"),
            float(normalized.get("debt_amount") or 0),
            parse_int_value(normalized.get("imported_claim_sent_days")),
            parse_int_value(normalized.get("imported_debt_days")),
            float(normalized.get("imported_penalty_amount") or 0),
            float(normalized.get("imported_state_duty_amount") or 0),
            float(normalized.get("imported_total_amount") or 0),
            1 if parse_bool(normalized.get("imported_category_override")) else 0,
            1 if parse_bool(normalized.get("lawsuit_sent")) else 0,
            normalized.get("lawsuit_sent_date"),
            1 if parse_bool(normalized.get("lawsuit_accepted")) else 0,
            normalized.get("hearing_date"),
            1 if parse_bool(normalized.get("decision_exists")) else 0,
            normalized.get("decision"),
            float(normalized.get("decision_payout") or 0),
            float(normalized.get("received_amount") or 0),
            normalized.get("comment"),
            normalized.get("case_number"),
        ),
    )
    debtor_id = int(cursor.lastrowid)
    row = dict(connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone())
    ensure_return_rework_child(connection, row)
    return debtor_id


def apply_import_insert_defaults(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)

    if not parse_bool(normalized.get("decision_exists")):
        normalized["decision"] = None
        normalized["decision_payout"] = 0

    decision = normalize_text(normalized.get("decision"))
    if decision == DECISION_SATISFY and not parse_float(normalized.get("decision_payout")):
        financials = compute_financials(normalized)
        normalized["decision_payout"] = financials["total_amount"]

    return normalized


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def loads_json(value: str | None) -> Any:
    if not value:
        return []
    return json.loads(value)


def dedupe_list(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def merge_row(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged.update(updates)
    return merged


def normalize_updates(updates: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in updates.items():
        if isinstance(value, date):
            normalized[key] = value.isoformat()
        elif isinstance(value, bool):
            normalized[key] = int(value)
        elif value is None and key in {"last_missed_payment_date", "client_name", "contract_number", "company", "city", "court"}:
            normalized[key] = ""
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped and key in {"last_missed_payment_date", "client_name", "contract_number", "company", "city", "court"}:
                normalized[key] = ""
            else:
                normalized[key] = stripped if stripped else None
        else:
            normalized[key] = value
    return normalized


def apply_csi_transfer_state(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    if "category" not in updates:
        return updates

    requested_category = normalize_text(updates.get("category"))
    existing_category = normalize_text(existing.get("category"))
    existing_marker = normalize_text(existing.get("csi_transferred_at"))

    if requested_category == CATEGORY_TRANSFER_TO_CSI:
        if existing_category != CATEGORY_TRANSFER_TO_CSI or not existing_marker:
            updates["csi_transferred_at"] = datetime.now().replace(microsecond=0).isoformat()
        return updates

    if existing_marker:
        updates["csi_transferred_at"] = None

    return updates


def extract_lawsuit_schedule(row: dict[str, Any]) -> dict[str, Any] | None:
    installment_from = parse_date_value(row.get("lawsuit_installment_from"))
    installment_to = parse_date_value(row.get("lawsuit_installment_to"))
    monthly_payment_amount = parse_float(row.get("lawsuit_monthly_payment_amount"))
    first_period_paid_amount = parse_float(row.get("lawsuit_first_period_paid_amount"))

    if installment_from is None or installment_to is None or monthly_payment_amount <= 0:
        return None
    if installment_to <= installment_from:
        return None

    return {
        "installment_from": installment_from,
        "installment_to": installment_to,
        "monthly_payment_amount": monthly_payment_amount,
        "first_period_paid_amount": max(first_period_paid_amount, 0.0),
    }


def serialize_debtor(row: dict[str, Any]) -> dict[str, Any]:
    created_at = datetime.fromisoformat(row["created_at"])
    today = date.today()
    last_missed_payment_date = parse_date_value(row["last_missed_payment_date"])
    claim_sent_date = parse_date_value(row.get("claim_sent_date"))
    lawsuit_sent_date = parse_date_value(row.get("lawsuit_sent_date"))
    hearing_date = parse_date_value(row.get("hearing_date"))
    birth_date = parse_date_value(row.get("birth_date"))

    financials = compute_financials(row)
    category_state = resolve_category_state(row)
    decision_exists = parse_bool(row.get("decision_exists"))
    is_hearing_overdue_without_decision = bool(
        hearing_date and hearing_date < today and not decision_exists
    )

    return {
        "id": row["id"],
        "country": normalize_country_code(str(row.get("country") or DEFAULT_COUNTRY)),
        "csi_transferred_at": row.get("csi_transferred_at"),
        "parent_debtor_id": row.get("parent_debtor_id"),
        "is_return_rework": bool(row.get("parent_debtor_id")),
        "entry_date": format_date(created_at.date()),
        "entry_date_iso": created_at.date().isoformat(),
        "created_at": created_at.strftime("%d.%m.%Y %H:%M"),
        "contract_date": contract_date_from_number(row["contract_number"]),
        "category": category_state["category"],
        "category_is_locked": category_state["is_locked"],
        "category_is_auto": category_state["is_auto"],
        "category_options": category_state["options"],
        "client_name": row["client_name"],
        "contract_number": row["contract_number"],
        "last_missed_payment_date": format_date(last_missed_payment_date),
        "last_missed_payment_date_iso": last_missed_payment_date.isoformat() if last_missed_payment_date else None,
        "company": sanitize_company_name(row["company"]),
        "city": row["city"],
        "court": row["court"],
        "claim_sent": parse_bool(row.get("claim_sent")),
        "claim_sent_date": format_date(claim_sent_date) if claim_sent_date else None,
        "claim_sent_date_iso": claim_sent_date.isoformat() if claim_sent_date else None,
        "claim_sent_days": financials["claim_sent_days"],
        "debt_days": financials["debt_days"],
        "debt_amount": financials["debt_amount"],
        "penalty_amount": financials["penalty_amount"],
        "state_duty_amount": financials["state_duty_amount"],
        "total_amount": financials["total_amount"],
        "lawsuit_sent": parse_bool(row.get("lawsuit_sent")),
        "lawsuit_sent_date": format_date(lawsuit_sent_date) if lawsuit_sent_date else None,
        "lawsuit_sent_date_iso": lawsuit_sent_date.isoformat() if lawsuit_sent_date else None,
        "lawsuit_accepted": parse_bool(row.get("lawsuit_accepted")),
        "hearing_date": format_date(hearing_date) if hearing_date else None,
        "hearing_date_iso": hearing_date.isoformat() if hearing_date else None,
        "decision_exists": decision_exists,
        "decision": row.get("decision"),
        "decision_payout": parse_float(row.get("decision_payout")),
        "received_amount": parse_float(row.get("received_amount")),
        "comment": row.get("comment"),
        "case_number": row.get("case_number"),
        "mobile_phone": normalize_text(row.get("mobile_phone")),
        "home_phone": normalize_text(row.get("home_phone")),
        "address": normalize_text(row.get("address")),
        "birth_date": format_date(birth_date) if birth_date else None,
        "birth_date_iso": birth_date.isoformat() if birth_date else None,
            "contract_total_amount": (
                parse_float(row.get("contract_total_amount"))
                if row.get("contract_total_amount") not in (None, "")
                else None
            ),
        "contract_advance_amount": (
            parse_float(row.get("contract_advance_amount"))
            if row.get("contract_advance_amount") not in (None, "")
            else None
        ),
        "lawsuit_installment_from": (
            parse_date_value(row.get("lawsuit_installment_from")).isoformat()
            if parse_date_value(row.get("lawsuit_installment_from"))
            else None
        ),
        "lawsuit_installment_to": (
            parse_date_value(row.get("lawsuit_installment_to")).isoformat()
            if parse_date_value(row.get("lawsuit_installment_to"))
            else None
        ),
        "lawsuit_monthly_payment_amount": (
            parse_float(row.get("lawsuit_monthly_payment_amount"))
            if row.get("lawsuit_monthly_payment_amount") not in (None, "")
            else None
        ),
        "lawsuit_first_period_paid_amount": (
            parse_float(row.get("lawsuit_first_period_paid_amount"))
            if row.get("lawsuit_first_period_paid_amount") not in (None, "")
            else None
        ),
        "case_court": row["court"],
        "is_hearing_overdue_without_decision": is_hearing_overdue_without_decision,
    }


def list_debtor_received_payments(connection: sqlite3.Connection, debtor_row: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in connection.execute(
            """
            SELECT id, debtor_id, payment_date, amount, created_at
            FROM debtor_received_payments
            WHERE debtor_id = ?
            ORDER BY CASE WHEN payment_date = '' THEN 1 ELSE 0 END, payment_date ASC, id ASC
            """,
            (int(debtor_row["id"]),),
        ).fetchall()
    ]

    if not rows and parse_float(debtor_row.get("received_amount")) > 0:
        return [
            {
                "payment_date": None,
                "payment_date_iso": None,
                "amount": parse_float(debtor_row.get("received_amount")),
                "legacy": True,
                "persisted": True,
            }
        ]

    serialized: list[dict[str, Any]] = []
    for row in rows:
        payment_date = parse_date_value(row.get("payment_date"))
        serialized.append(
            {
                "payment_date": format_date(payment_date) if payment_date else None,
                "payment_date_iso": payment_date.isoformat() if payment_date else None,
                "amount": parse_float(row.get("amount")),
                "legacy": not bool(str(row.get("payment_date") or "").strip()),
                "persisted": True,
            }
        )
    return serialized


def build_csi_export_output_path(country: str, date_from: date, date_to: date) -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return GENERATED_DIR / f"csi_export_{country}_{date_from.isoformat()}_{date_to.isoformat()}_{timestamp}.pdf"


def collect_csi_export_rows(
    connection: sqlite3.Connection,
    *,
    country: str,
    date_from: date,
    date_to: date,
) -> tuple[list[dict[str, Any]], float]:
    rows = connection.execute(
        """
        SELECT
            d.id AS debtor_id,
            d.client_name,
            d.contract_number,
            p.payment_date,
            p.amount
        FROM debtor_received_payments p
        JOIN debtors d ON d.id = p.debtor_id
        WHERE COALESCE(d.country, ?) = ?
          AND d.csi_transferred_at IS NOT NULL
          AND COALESCE(NULLIF(TRIM(p.payment_date), ''), '') <> ''
          AND p.payment_date >= ?
          AND p.payment_date <= ?
        ORDER BY p.payment_date ASC, d.client_name COLLATE NOCASE ASC, d.id ASC, p.id ASC
        """,
        (DEFAULT_COUNTRY, country, date_from.isoformat(), date_to.isoformat()),
    ).fetchall()

    grouped: dict[int, dict[str, Any]] = {}
    total_amount = 0.0
    for row in rows:
        debtor_id = int(row["debtor_id"])
        entry = grouped.setdefault(
            debtor_id,
            {
                "client_name": str(row["client_name"] or "").strip(),
                "contract_number": str(row["contract_number"] or "").strip(),
                "amounts": [],
                "dates": [],
            },
        )
        amount = parse_float(row["amount"])
        payment_date = parse_date_value(row["payment_date"])
        entry["amounts"].append(format_money(amount))
        entry["dates"].append(format_date(payment_date) if payment_date else "")
        total_amount += amount

    return list(grouped.values()), round(total_amount, 2)


def render_csi_export_pdf(country: str, date_from: date, date_to: date, rows: list[dict[str, Any]], total_amount: float) -> Path:
    pdf_path = build_csi_export_output_path(country, date_from, date_to)
    page_width = 1240
    page_height = 1754
    margin_left = 70
    margin_right = 70
    margin_top = 80
    margin_bottom = 80
    table_width = page_width - margin_left - margin_right

    title_font = load_font(28, bold=True)
    meta_font = load_font(20)
    header_font = load_font(18, bold=True)
    body_font = load_font(18)
    total_font = load_font(20, bold=True)

    column_widths = [340, 220, 280, 260]
    col_x: list[int] = [margin_left]
    for width in column_widths[:-1]:
        col_x.append(col_x[-1] + width)

    pages: list[Image.Image] = []

    def create_page() -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
        image = Image.new("RGB", (page_width, page_height), "white")
        draw = ImageDraw.Draw(image)
        y = margin_top
        draw.text((margin_left, y), "Отчет ЧСИ", fill="#111111", font=title_font)
        y += 46
        draw.text(
            (margin_left, y),
            f"Период: {format_date(date_from)} - {format_date(date_to)}    Страна: {country.upper()}",
            fill="#111111",
            font=meta_font,
        )
        y += 42
        return image, draw, y

    def draw_table_header(draw: ImageDraw.ImageDraw, y: int) -> int:
        header_height = 52
        headers = ["ФИО клиента", "Номер договора", "Получено (тг)", "Дата получения"]
        x = margin_left
        for index, header in enumerate(headers):
            width = column_widths[index]
            draw.rectangle((x, y, x + width, y + header_height), outline="#111111", width=2)
            draw.text((x + 8, y + 16), header, fill="#111111", font=header_font)
            x += width
        return y + header_height

    def draw_row(draw: ImageDraw.ImageDraw, row: dict[str, Any], y: int) -> int:
        cell_padding = 8
        line_bbox = draw.textbbox((0, 0), "Ag", font=body_font)
        line_height = (line_bbox[3] - line_bbox[1]) + 6
        cell_texts = [
            [row["client_name"] or ""],
            wrap_text(draw, row["contract_number"] or "", body_font, column_widths[1] - cell_padding * 2),
            [str(item) for item in (row["amounts"] or [])] or [""],
            [str(item) for item in (row["dates"] or [])] or [""],
        ]
        row_height = max(len(lines) for lines in cell_texts) * line_height + cell_padding * 2

        x = margin_left
        for index, lines in enumerate(cell_texts):
            width = column_widths[index]
            draw.rectangle((x, y, x + width, y + row_height), outline="#111111", width=1)
            text_y = y + cell_padding
            for line in lines:
                draw.text((x + cell_padding, text_y), line, fill="#111111", font=body_font)
                text_y += line_height
            x += width
        return y + row_height

    current_page, current_draw, current_y = create_page()
    current_y = draw_table_header(current_draw, current_y)
    max_y = page_height - margin_bottom - 80

    printable_rows = rows or [
        {
            "client_name": "Нет данных за выбранный период",
            "contract_number": "",
            "amounts": [""],
            "dates": [""],
        }
    ]

    for row in printable_rows:
        probe_bbox = current_draw.textbbox((0, 0), "Ag", font=body_font)
        probe_height = (probe_bbox[3] - probe_bbox[1]) + 6
        estimated_lines = max(
            1,
            len(wrap_text(current_draw, row["contract_number"] or "", body_font, column_widths[1] - 16)),
            len(row.get("amounts") or [""]),
            len(row.get("dates") or [""]),
        )
        estimated_height = estimated_lines * probe_height + 16
        if current_y + estimated_height > max_y:
            pages.append(current_page)
            current_page, current_draw, current_y = create_page()
            current_y = draw_table_header(current_draw, current_y)
        current_y = draw_row(current_draw, row, current_y)

    if current_y + 60 > page_height - margin_bottom:
        pages.append(current_page)
        current_page, current_draw, current_y = create_page()

    current_draw.text(
        (margin_left, current_y + 22),
        f"Итоговая сумма за период: {format_money(total_amount)}",
        fill="#111111",
        font=total_font,
    )
    pages.append(current_page)

    first_page, *other_pages = pages
    if other_pages:
        first_page.save(pdf_path, "PDF", resolution=150.0, save_all=True, append_images=other_pages)
    else:
        first_page.save(pdf_path, "PDF", resolution=150.0)
    return pdf_path


def serialize_incoming_correspondence(row: dict[str, Any]) -> dict[str, Any]:
    received_date = parse_date_value(row.get("received_date"))
    response_date = parse_date_value(row.get("response_date"))
    sent_date = parse_date_value(row.get("sent_date"))
    claim_response_generated_at = parse_date_value(row.get("claim_response_generated_at"))
    authority_kind = str(row.get("authority_kind") or INCOMING_AUTHORITY_COURT).strip() or INCOMING_AUTHORITY_COURT
    court = str(row.get("court") or "").strip() or None
    other_authority = str(row.get("other_authority") or "").strip() or None
    authority_display = court if authority_kind == INCOMING_AUTHORITY_COURT else other_authority
    claim_response_pdf_name = str(row.get("claim_response_pdf_name") or "").strip() or None

    return {
        "id": row["id"],
        "country": normalize_country_code(str(row.get("country") or DEFAULT_COUNTRY)),
        "category": str(row.get("category") or "").strip(),
        "received_date": format_date(received_date) if received_date else None,
        "received_date_iso": received_date.isoformat() if received_date else None,
        "receive_method": str(row.get("receive_method") or "").strip(),
        "company": str(row.get("company") or "").strip(),
        "client_name": str(row.get("client_name") or "").strip(),
        "authority_kind": authority_kind,
        "authority_display": authority_display or "",
        "court": court,
        "other_authority": other_authority,
        "contract_number": str(row.get("contract_number") or "").strip() or None,
        "responsible_person": str(row.get("responsible_person") or "").strip() or None,
        "response_text": str(row.get("response_text") or "").strip() or None,
        "response_date": format_date(response_date) if response_date else None,
        "response_date_iso": response_date.isoformat() if response_date else None,
        "sent_date": format_date(sent_date) if sent_date else None,
        "sent_date_iso": sent_date.isoformat() if sent_date else None,
        "claim_response_pdf_name": claim_response_pdf_name,
        "claim_response_generated_at": (
            claim_response_generated_at.isoformat()
            if claim_response_generated_at
            else str(row.get("claim_response_generated_at") or "").strip() or None
        ),
        "comment": str(row.get("comment") or "").strip() or None,
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def validate_incoming_correspondence_payload(payload: dict[str, Any]) -> None:
    category = str(payload.get("category") or "").strip()
    authority_kind = str(payload.get("authority_kind") or INCOMING_AUTHORITY_COURT).strip() or INCOMING_AUTHORITY_COURT
    receive_method = str(payload.get("receive_method") or "").strip()
    company = str(payload.get("company") or "").strip()
    client_name = str(payload.get("client_name") or "").strip()
    contract_number = str(payload.get("contract_number") or "").strip()

    if category not in INCOMING_CORRESPONDENCE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Некорректная категория входящей корреспонденции.")
    if authority_kind not in {INCOMING_AUTHORITY_COURT, INCOMING_AUTHORITY_OTHER}:
        raise HTTPException(status_code=400, detail="Некорректный тип органа.")
    if not receive_method:
        raise HTTPException(status_code=400, detail="Укажите способ получения.")
    if not company:
        raise HTTPException(status_code=400, detail="Укажите компанию.")
    if not client_name:
        raise HTTPException(status_code=400, detail="Укажите ФИО клиента.")
    if category == INCOMING_CATEGORY_CLAIM and not contract_number:
        raise HTTPException(status_code=400, detail="Для претензии требуется номер договора.")

    if authority_kind == INCOMING_AUTHORITY_COURT:
        if not str(payload.get("court") or "").strip():
            raise HTTPException(status_code=400, detail="Укажите суд.")
    elif not str(payload.get("other_authority") or "").strip():
        raise HTTPException(status_code=400, detail="Укажите другой орган.")


def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode("utf-8")
    request = urllib_request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=15) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
            return bool(response_payload.get("ok"))
    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError):
        return False


def process_due_incoming_claim_alerts(connection, country: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    due_date_iso = (date.today() - timedelta(days=9)).isoformat()
    rows = connection.execute(
        """
        SELECT id, contract_number
        FROM incoming_correspondence
        WHERE COALESCE(country, ?) = ?
          AND category = ?
          AND received_date <= ?
          AND COALESCE(TRIM(response_text), '') = ''
          AND claim_due_alert_sent_at IS NULL
        ORDER BY received_date ASC, id ASC
        """,
        (DEFAULT_COUNTRY, country, INCOMING_CATEGORY_CLAIM, due_date_iso),
    ).fetchall()

    if not rows:
        return

    sent_at = datetime.now().replace(microsecond=0).isoformat()
    for row in rows:
        contract_number = str(row["contract_number"] or "").strip() or "без номера договора"
        if not send_telegram_message(f"Требуется срочный ответ на претензию! {contract_number}"):
            continue
        connection.execute(
            "UPDATE incoming_correspondence SET claim_due_alert_sent_at = ?, updated_at = ? WHERE id = ?",
            (sent_at, sent_at, row["id"]),
        )
    connection.commit()


def build_incoming_claim_response_output_path(record_id: int) -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return GENERATED_DIR / f"incoming_claim_response_{record_id}_{timestamp}.pdf"


def resolve_incoming_claim_response_file_path(file_name: str) -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    return GENERATED_DIR / Path(str(file_name or "")).name


def build_incoming_claim_response_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    width: int,
) -> list[dict[str, int | str]]:
    normalized_text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraph_indent = 89
    lines: list[dict[str, int | str]] = []
    for raw_line in normalized_text.split("\n"):
        if not raw_line.strip():
            lines.append({"text": "", "indent": 0})
            continue
        words = raw_line.strip().split()
        if not words:
            lines.append({"text": "", "indent": 0})
            continue

        first_line_words: list[str] = []
        remaining_words = list(words)
        while remaining_words:
            candidate_words = first_line_words + [remaining_words[0]]
            candidate = " ".join(candidate_words).strip()
            if draw.textlength(candidate, font=font) <= max(40, width - paragraph_indent):
                first_line_words.append(remaining_words.pop(0))
            else:
                break

        if first_line_words:
            lines.append({"text": " ".join(first_line_words), "indent": paragraph_indent})

        if remaining_words:
            for wrapped_line in wrap_text(draw, " ".join(remaining_words), font, width):
                lines.append({"text": wrapped_line, "indent": 0})
    return lines


def render_incoming_claim_response_pdf(
    record: dict[str, Any],
    payload: IncomingClaimResponsePdfRequest,
) -> Path:
    raw_company_name = str(record.get("company") or "").strip()
    country = normalize_country_code(str(record.get("country") or DEFAULT_COUNTRY))
    company_name = match_company_to_library(raw_company_name, country)
    requisites = find_company_requisites(company_name, country=country)
    if not requisites:
        requisites = find_company_requisites(raw_company_name, country=country) or find_company_requisites(company_name)
    if not requisites:
        raise HTTPException(status_code=400, detail="Для компании не найдены реквизиты.")

    contract_number = str(record.get("contract_number") or "").strip()
    if not contract_number:
        raise HTTPException(status_code=400, detail="У записи не заполнен номер договора.")

    try:
        crm_context = DiSellApiClient().lookup_lawsuit_context(contract_number, country=country)
    except DiSellApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    client_name = normalize_text(crm_context.get("client_name")) or str(record.get("client_name") or "").strip()
    client_birth_date = format_date(parse_date_value(crm_context.get("client_birth_date")))
    client_inn = normalize_text(crm_context.get("client_inn"))
    client_address = normalize_text(crm_context.get("client_address"))
    client_phones = ", ".join(
        phone.strip()
        for phone in crm_context.get("client_phones") or []
        if str(phone).strip()
    )

    page_width = 1240
    page_height = 1754
    margin_left = 110
    margin_right = 110
    margin_top = 90
    margin_bottom = 90
    content_width = page_width - margin_left - margin_right
    right_block_width = 470

    body_font = load_font(22)
    body_bold_font = load_font(22, bold=True)
    title_font = load_font(22, bold=True)
    small_font = load_font(22)

    scratch_draw = ImageDraw.Draw(Image.new("RGB", (32, 32), "white"))
    line_bbox = scratch_draw.textbbox((0, 0), "Аг", font=body_font)
    body_line_spacing = 0
    body_font_size = int(getattr(body_font, "size", 22) or 22)
    small_font_size = int(getattr(small_font, "size", 22) or 22)
    body_line_height = max((line_bbox[3] - line_bbox[1]) + body_line_spacing, int(body_font_size * 1.25))
    small_line_bbox = scratch_draw.textbbox((0, 0), "Аг", font=small_font)
    header_line_spacing = 4
    header_line_height = max((small_line_bbox[3] - small_line_bbox[1]) + header_line_spacing, int(small_font_size * 1.25))
    signature_line_height = header_line_height
    paragraph_indent = 0
    paragraph_spacing = max(int(body_line_height * 0.5), 14)

    company_header_lines = [
        f"От: {requisites.get('company_name') or company_name}",
        str(requisites.get("bin") or "").strip(),
        f"Директор: {str(requisites.get('director_name') or '').strip()}",
        f"Юридический адрес: {str(requisites.get('address') or '').strip()}",
    ]
    company_header_lines = [line for line in company_header_lines if line.strip()]

    recipient_lines = [f"Кому: {client_name}"]
    if client_birth_date:
        recipient_lines.append(f"Дата рождения: {client_birth_date}")
    if client_inn:
        recipient_lines.append(f"ИНН: {client_inn}")
    if client_address:
        recipient_lines.append(f"Адрес: {client_address}")
    if client_phones:
        recipient_lines.append(f"Контактный телефон: {client_phones}")

    outgoing_number = str(payload.outgoing_number or "").strip()
    body_text = str(payload.body_text or "").strip()
    body_lines: list[str] = []
    normalized_body_lines = body_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for raw_line in normalized_body_lines:
        if not raw_line.strip():
            body_lines.append("")
            continue
        body_lines.extend(wrap_text(scratch_draw, raw_line.strip(), body_font, content_width))

    while body_lines and not body_lines[-1]:
        body_lines.pop()
    signature_lines = [
        "С уважением,",
        "Директор",
        str(requisites.get("director_name") or "").strip(),
        str(requisites.get("company_name") or company_name).strip(),
    ]
    signature_height = len(signature_lines) * signature_line_height + 24

    pages: list[Image.Image] = []

    def draw_line_group(
        draw: ImageDraw.ImageDraw,
        source_lines: list[str],
        *,
        x: int,
        y: int,
        width: int,
        font: ImageFont.ImageFont,
        line_height: int,
    ) -> int:
        for source_line in source_lines:
            if not source_line.strip():
                y += line_height
                continue
            wrapped_lines = wrap_text(draw, source_line, font, width)
            for wrapped_line in wrapped_lines:
                draw.text((x, y), wrapped_line, fill="#111111", font=font)
                y += line_height
        return y

    def create_page(first_page: bool) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
        image = Image.new("RGB", (page_width, page_height), "#FFFFFF")
        draw = ImageDraw.Draw(image)
        current_y = margin_top

        if first_page:
            right_x = page_width - margin_right - right_block_width
            current_y = draw_line_group(
                draw,
                company_header_lines,
                x=right_x,
                y=current_y,
                width=right_block_width,
                font=small_font,
                line_height=header_line_height,
            )
            current_y += 12
            current_y = draw_line_group(
                draw,
                recipient_lines,
                x=right_x,
                y=current_y,
                width=right_block_width,
                font=small_font,
                line_height=header_line_height,
            )

            if outgoing_number:
                current_y = draw_text_block(
                    draw,
                    f"Исх. {outgoing_number}",
                    x=margin_left,
                    y=current_y + 8,
                    width=content_width,
                    font=body_font,
                    line_spacing=body_line_spacing,
                    paragraph_spacing=12,
                )

            current_y = draw_text_block(
                draw,
                "Ответ на претензию",
                x=margin_left,
                y=current_y + 8,
                width=content_width,
                font=title_font,
                line_spacing=body_line_spacing,
                align="center",
                paragraph_spacing=20,
            )
        return image, draw, current_y

    image, draw, current_y = create_page(True)
    blank_line_height = max(int(body_line_height * 0.6), 12)
    for line in body_lines:
        line_height = blank_line_height if not line else body_line_height
        if current_y + line_height > page_height - margin_bottom - signature_height:
            pages.append(image)
            image, draw, current_y = create_page(False)

        if not line:
            current_y += blank_line_height
            continue

        draw.text((margin_left, current_y), line, fill="#111111", font=body_font)
        current_y += body_line_height

    if current_y + signature_height > page_height - margin_bottom:
        pages.append(image)
        image, draw, current_y = create_page(False)

    current_y += 18
    for index, line in enumerate(signature_lines):
        font = body_bold_font if index == 0 else body_font
        draw.text((margin_left, current_y), line, fill="#111111", font=font)
        current_y += signature_line_height

    pages.append(image)

    output_path = build_incoming_claim_response_output_path(int(record["id"]))
    first_page, *other_pages = pages
    first_page.save(output_path, "PDF", resolution=300.0, save_all=True, append_images=other_pages)
    return output_path


def resolve_category_state(row: dict[str, Any]) -> dict[str, Any]:
    stored_category = normalize_text(row.get("category")) or DEFAULT_CATEGORY
    auto_category = determine_auto_category(row)
    manual_override_active = stored_category in PRIORITY_CATEGORY_OVERRIDES
    is_return_rework = bool(row.get("parent_debtor_id"))
    decision_exists = parse_bool(row.get("decision_exists"))
    has_return_rework_child = bool(row.get("has_return_rework_child"))
    imported_category_override = parse_bool(row.get("imported_category_override"))

    if not is_return_rework and has_return_rework_child:
        return {
            "category": CATEGORY_RETURNED_TO_LEGAL,
            "is_locked": True,
            "is_auto": True,
            "options": [CATEGORY_RETURNED_TO_LEGAL],
        }

    if is_return_rework and not decision_exists:
        return {
            "category": stored_category,
            "is_locked": False,
            "is_auto": False,
            "options": CATEGORIES,
        }

    if imported_category_override:
        return {
            "category": stored_category,
            "is_locked": False,
            "is_auto": False,
            "options": CATEGORIES,
        }

    if manual_override_active and auto_category is not None:
        effective_category = stored_category
        options = category_options_for(auto_category, stored_category)
        return {"category": effective_category, "is_locked": True, "is_auto": False, "options": options}

    if auto_category is not None:
        options = category_options_for(auto_category, stored_category)
        return {"category": auto_category, "is_locked": True, "is_auto": True, "options": options}

    return {
        "category": stored_category,
        "is_locked": False,
        "is_auto": False,
        "options": CATEGORIES,
    }


def category_options_for(auto_category: str | None, stored_category: str) -> list[str]:
    options: list[str] = []
    if auto_category:
        options.append(auto_category)
    if stored_category in PRIORITY_CATEGORY_OVERRIDES and stored_category not in options:
        options.append(stored_category)
    for category in CATEGORIES:
        if category in PRIORITY_CATEGORY_OVERRIDES and category not in options:
            options.append(category)
    return options


def determine_auto_category(row: dict[str, Any]) -> str | None:
    decision = normalize_text(row.get("decision"))
    lawsuit_sent = parse_bool(row.get("lawsuit_sent"))
    claim_sent = parse_bool(row.get("claim_sent"))
    financials = compute_financials(row)
    decision_payout = parse_float(row.get("decision_payout"))
    received_amount = parse_float(row.get("received_amount"))
    stored_category = normalize_text(row.get("category")) or DEFAULT_CATEGORY

    if row.get("parent_debtor_id") and not parse_bool(row.get("decision_exists")):
        return None

    if decision_payout > 0 and abs(received_amount - decision_payout) < 0.01:
        return CATEGORY_DEBT_CLOSED
    if decision == DECISION_RETURN:
        return CATEGORY_RETURNED_TO_LEGAL
    if decision == DECISION_REFUSAL:
        return CATEGORY_NO_JURISDICTION
    if decision in DECISIONS_THAT_CLOSE_LAWSUIT:
        return CATEGORY_LAWSUIT_CLOSED
    if financials["total_amount"] < 150000:
        return CATEGORY_SMALL_DEBT
    if lawsuit_sent:
        return CATEGORY_LAWSUIT_FILED
    if financials["debt_days"] is not None and financials["debt_days"] > 365 * 3:
        return CATEGORY_LIMITATION_EXPIRED
    if claim_sent and financials["claim_sent_days"] is not None and financials["claim_sent_days"] > 10:
        return CATEGORY_PREPARE_LAWSUIT
    if claim_sent:
        return CATEGORY_WAITING_FOR_CLAIM_RESPONSE
    return None


def compute_financials(row: dict[str, Any]) -> dict[str, Any]:
    today = date.today()
    last_missed_payment_date = parse_date_value(row.get("last_missed_payment_date"))
    claim_sent_date = parse_date_value(row.get("claim_sent_date"))
    debt_amount = parse_float(row.get("debt_amount"))

    if last_missed_payment_date is None:
        imported_claim_sent_days = parse_int_value(row.get("imported_claim_sent_days"))
        imported_debt_days = parse_int_value(row.get("imported_debt_days"))
        imported_penalty_amount = parse_float(row.get("imported_penalty_amount"))
        imported_total_amount = parse_float(row.get("imported_total_amount"))
        imported_state_duty_amount = parse_float(row.get("imported_state_duty_amount"))
        penalty_amount = imported_penalty_amount
        total_amount = imported_total_amount or round(debt_amount + penalty_amount, 2)
        state_duty_amount = imported_state_duty_amount or round(total_amount * 0.03, 2)
        claim_sent_days = imported_claim_sent_days if imported_claim_sent_days is not None else (
            (today - claim_sent_date).days if claim_sent_date else None
        )
        return {
            "debt_days": imported_debt_days,
            "debt_amount": debt_amount,
            "penalty_amount": penalty_amount,
            "total_amount": total_amount,
            "state_duty_amount": state_duty_amount,
            "claim_sent_days": claim_sent_days,
        }

    lawsuit_schedule = extract_lawsuit_schedule(row)
    debt_stop_date = claim_sent_date or today
    if lawsuit_schedule is not None and debt_stop_date > lawsuit_schedule["installment_from"]:
        try:
            _, penalty_amount, debt_days = build_lawsuit_penalty_rows(
                lawsuit_schedule["installment_from"],
                lawsuit_schedule["installment_to"],
                debt_stop_date,
                lawsuit_schedule["monthly_payment_amount"],
                lawsuit_schedule["first_period_paid_amount"],
            )
            total_amount = round(debt_amount + penalty_amount, 2)
            state_duty_amount = round(total_amount * 0.03, 2)
            claim_sent_days = (today - claim_sent_date).days if claim_sent_date else None
            return {
                "debt_days": debt_days,
                "debt_amount": debt_amount,
                "penalty_amount": penalty_amount,
                "total_amount": total_amount,
                "state_duty_amount": state_duty_amount,
                "claim_sent_days": claim_sent_days,
            }
        except HTTPException:
            pass

    debt_days = max((debt_stop_date - last_missed_payment_date).days, 0)
    penalty_amount = round(debt_amount * 0.001 * debt_days, 2)
    total_amount = round(debt_amount + penalty_amount, 2)
    state_duty_amount = round(total_amount * 0.03, 2)
    claim_sent_days = (today - claim_sent_date).days if claim_sent_date else None

    return {
        "debt_days": debt_days,
        "debt_amount": debt_amount,
        "penalty_amount": penalty_amount,
        "total_amount": total_amount,
        "state_duty_amount": state_duty_amount,
        "claim_sent_days": claim_sent_days,
    }

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    user = get_optional_current_user(request)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "page_title": "Legal Department Login"},
        )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "page_title": "Legal Department",
            "active_page": "debtors",
            "show_create_button": True,
            "app_context_json": json.dumps({"user": serialize_user(user), "page": "debtors"}, ensure_ascii=False),
        },
    )
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "page_title": "Юридический департамент"},
    )

@app.get("/incoming-correspondence", response_class=HTMLResponse)
def incoming_correspondence_page(request: Request) -> HTMLResponse:
    user = get_optional_current_user(request)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "page_title": "Legal Department Login"},
        )
    return templates.TemplateResponse(
        "incoming_correspondence.html",
        {
            "request": request,
            "page_title": "Входящая корреспонденция",
            "active_page": "incoming",
            "app_context_json": json.dumps({"user": serialize_user(user), "page": "incoming"}, ensure_ascii=False),
        },
    )


@app.get("/csi", response_class=HTMLResponse)
def csi_page(request: Request) -> HTMLResponse:
    user = get_optional_current_user(request)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "page_title": "Legal Department Login"},
        )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "page_title": "ЧСИ",
            "active_page": "csi",
            "show_create_button": False,
            "app_context_json": json.dumps({"user": serialize_user(user), "page": "csi"}, ensure_ascii=False),
        },
    )


@app.post("/api/auth/login", response_model=AuthMeResponse)
def login(payload: LoginRequest) -> Response:
    username = payload.username.strip()
    with get_connection() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE lower(username) = lower(?)",
            (username,),
        ).fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS")

        user_dict = dict(user)
        if not parse_bool(user_dict.get("is_active")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="USER_DISABLED")
        if not verify_password(payload.password, str(user_dict["password_hash"]), str(user_dict["password_salt"])):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS")

        session_token = create_session_token()
        created_at = utc_now().isoformat()
        expires_at = build_session_expiry()
        connection.execute(
            """
            INSERT INTO user_sessions (user_id, session_token, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (int(user_dict["id"]), session_token, created_at, expires_at),
        )
        connection.commit()

    response = Response(
        content=json.dumps({"user": serialize_user(user_dict)}, ensure_ascii=False),
        media_type="application/json",
    )
    set_session_cookie(response, session_token)
    return response


@app.post("/api/auth/logout")
def logout(request: Request, _user: dict[str, Any] = Depends(require_authenticated_user)) -> Response:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    with get_connection() as connection:
        if session_token:
            connection.execute("DELETE FROM user_sessions WHERE session_token = ?", (session_token,))
            connection.commit()
    response = Response(content="{}", media_type="application/json")
    clear_session_cookie(response)
    return response


@app.get("/api/auth/me", response_model=AuthMeResponse)
def auth_me(user: dict[str, Any] = Depends(require_authenticated_user)) -> dict[str, Any]:
    return {"user": serialize_user(user)}


@app.post("/api/auth/change-password", response_model=AuthMeResponse)
def change_password(payload: ChangePasswordRequest, user: dict[str, Any] = Depends(require_authenticated_user)) -> dict[str, Any]:
    if len(payload.new_password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PASSWORD_TOO_SHORT")
    if not verify_password(payload.current_password, str(user["password_hash"]), str(user["password_salt"])):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_CURRENT_PASSWORD")

    password_hash, password_salt = hash_password(payload.new_password)
    updated_at = utc_now().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, password_salt = ?, must_change_password = 0, updated_at = ?
            WHERE id = ?
            """,
            (password_hash, password_salt, updated_at, int(user["id"])),
        )
        connection.commit()
        updated_user = connection.execute("SELECT * FROM users WHERE id = ?", (int(user["id"]),)).fetchone()

    return {"user": serialize_user(updated_user)}


@app.get("/api/users", response_model=list[UserView])
def list_users(_user: dict[str, Any] = Depends(require_owner_user)) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM users ORDER BY role ASC, username COLLATE NOCASE ASC").fetchall()
    return [serialize_user(row) for row in rows]


@app.post("/api/users", response_model=UserView, status_code=201)
def create_user(payload: UserCreateRequest, _user: dict[str, Any] = Depends(require_owner_user)) -> dict[str, Any]:
    role = payload.role.strip().lower()
    if role not in USER_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_ROLE")
    if len(payload.temporary_password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PASSWORD_TOO_SHORT")

    password_hash, password_salt = hash_password(payload.temporary_password)
    timestamp = utc_now().isoformat()
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE lower(username) = lower(?)",
            (payload.username.strip(),),
        ).fetchone()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="USERNAME_ALREADY_EXISTS")

        cursor = connection.execute(
            """
            INSERT INTO users (
                username,
                full_name,
                role,
                password_hash,
                password_salt,
                must_change_password,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (
                payload.username.strip(),
                payload.full_name.strip(),
                role,
                password_hash,
                password_salt,
                timestamp,
                timestamp,
            ),
        )
        user_id = cursor.lastrowid
        connection.commit()
        created_user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    return serialize_user(created_user)


@app.get("/api/reference-data")
def reference_data(country: str = DEFAULT_COUNTRY, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, Any]:
    normalized_country = normalize_country_code(country)
    with get_connection() as connection:
        catalog = build_reference_catalog(connection, normalized_country)

    return {
        "categories": CATEGORIES,
        "companies": get_companies_by_country(normalized_country),
        "cities": catalog["cities"],
        "regions": catalog["regions"],
        "courtsByCity": catalog["courtsByCity"],
        "courtsByRegion": catalog["courtsByRegion"],
        "courtCityMap": catalog["courtCityMap"],
        "courtRegionMap": catalog["courtRegionMap"],
        "cityRegionMap": catalog["cityRegionMap"],
        "citiesByRegion": catalog["citiesByRegion"],
        "decisions": DECISIONS,
        "priorityCategoryOverrides": sorted(PRIORITY_CATEGORY_OVERRIDES),
        "currentCountry": normalized_country,
        "countries": [
            {"code": code, "label": COUNTRY_LABELS[code]["ru"]}
            for code in SUPPORTED_COUNTRIES
        ],
    }


@app.get("/api/incoming-correspondence/reference-data")
def incoming_correspondence_reference_data(
    country: str = DEFAULT_COUNTRY,
    _user: dict[str, Any] = Depends(require_app_user),
) -> dict[str, Any]:
    normalized_country = normalize_country_code(country)
    with get_connection() as connection:
        catalog = build_reference_catalog(connection, normalized_country)

    return {
        "categories": INCOMING_CORRESPONDENCE_CATEGORIES,
        "companies": get_companies_by_country(normalized_country),
        "courts": sorted(str(court) for court in dict(catalog["courtCityMap"]).keys()),
        "currentCountry": normalized_country,
        "countries": [
            {"code": code, "label": COUNTRY_LABELS[code]["ru"]}
            for code in SUPPORTED_COUNTRIES
        ],
    }


@app.get("/api/crm/debtor-prefill", response_model=CrmDebtorLookupResponse)
def crm_debtor_prefill(contract_number: str, country: str = DEFAULT_COUNTRY, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, Any]:
    try:
        payload = DiSellApiClient().lookup_debtor_prefill(contract_number, country=normalize_country_code(country))
    except DiSellApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    payload["company"] = match_company_to_library(payload["company"], normalize_country_code(country))
    payload["city"] = normalize_text(payload.get("city")) or ""
    payload["address"] = normalize_text(payload.get("address"))
    payload["mobile_phone"] = normalize_text(payload.get("mobile_phone"))
    payload["home_phone"] = normalize_text(payload.get("home_phone"))
    payload["products"] = normalize_document_products(
        payload.get("products"),
        fallback_name="Товар по договору",
    )
    return payload


@app.post("/api/courts", status_code=201)
def create_court(payload: CourtCreate, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, str]:
    country = normalize_country_code(payload.country)
    name = payload.name.strip()
    city = payload.city.strip()
    region = payload.region.strip()

    with get_connection() as connection:
        catalog = build_reference_catalog(connection, country)
        if name in catalog["courtCityMap"]:
            raise HTTPException(status_code=400, detail="Суд с таким названием уже существует.")

        existing = connection.execute(
            "SELECT 1 FROM custom_courts WHERE lower(name) = lower(?) AND country = ?",
            (name, country),
        ).fetchone()
        if existing is not None:
            raise HTTPException(status_code=400, detail="Суд с таким названием уже существует.")

        created_at = datetime.now().replace(microsecond=0).isoformat()
        connection.execute(
            """
            INSERT INTO custom_courts (name, city, region, country, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, city, region, country, created_at),
        )
        connection.commit()

    return {"name": name, "city": city, "region": region, "country": country}


@app.get("/api/imports")
def list_import_batches(_user: dict[str, Any] = Depends(require_app_user)) -> list[dict[str, Any]]:
    with get_connection() as connection:
        batches = connection.execute(
            "SELECT * FROM import_batches ORDER BY id DESC"
        ).fetchall()
    return [serialize_import_batch(dict(batch)) for batch in batches]


@app.get("/api/imports/{batch_id}")
def get_import_batch(batch_id: int, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, Any]:
    with get_connection() as connection:
        batch = connection.execute(
            "SELECT * FROM import_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            raise HTTPException(status_code=404, detail="Пакет импорта не найден.")

        rows = connection.execute(
            "SELECT * FROM import_rows WHERE batch_id = ? ORDER BY row_index ASC",
            (batch_id,),
        ).fetchall()

    return {
        "batch": serialize_import_batch(dict(batch)),
        "rows": [serialize_import_row(dict(row)) for row in rows],
    }


@app.post("/api/imports/preview-local", status_code=201)
def preview_import_file(payload: ImportPreviewRequest, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, Any]:
    source_path = str(Path(payload.path).expanduser())
    try:
        raw_rows = load_rows_from_path(source_path)
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with get_connection() as connection:
        batch_id = create_import_batch(connection, source_path)
        counts = {"ok": 0, "needs_review": 0, "blocked": 0}

        for row_index, raw_row in enumerate(raw_rows, start=1):
            analyzed_row = analyze_import_row(raw_row, row_index=row_index)
            counts[analyzed_row["status"]] += 1
            connection.execute(
                """
                INSERT INTO import_rows (
                    batch_id,
                    row_index,
                    status,
                    source_data_json,
                    normalized_data_json,
                    source_category,
                    suggested_category,
                    errors_json,
                    warnings_json,
                    debtor_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    row_index,
                    analyzed_row["status"],
                    dumps_json(raw_row),
                    dumps_json(analyzed_row["normalized_data"]),
                    analyzed_row["source_category"],
                    analyzed_row["suggested_category"],
                    dumps_json(analyzed_row["errors"]),
                    dumps_json(analyzed_row["warnings"]),
                    None,
                ),
            )

        status = "needs_review" if counts["needs_review"] or counts["blocked"] else "ready"
        connection.execute(
            """
            UPDATE import_batches
            SET status = ?, total_rows = ?, ok_rows = ?, needs_review_rows = ?, blocked_rows = ?
            WHERE id = ?
            """,
            (
                status,
                len(raw_rows),
                counts["ok"],
                counts["needs_review"],
                counts["blocked"],
                batch_id,
            ),
        )
        connection.commit()

        batch = connection.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
        rows = connection.execute(
            "SELECT * FROM import_rows WHERE batch_id = ? ORDER BY row_index ASC LIMIT 100",
            (batch_id,),
        ).fetchall()

    return {
        "batch": serialize_import_batch(dict(batch)),
        "rows": [serialize_import_row(dict(row)) for row in rows],
        "rowsTruncated": len(raw_rows) > 100,
    }


@app.post("/api/imports/safe-stage2-local", status_code=201)
def import_safe_stage2_local(payload: ImportPreviewRequest, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, Any]:
    source_path = str(Path(payload.path).expanduser())
    try:
        return import_safe_stage2_file(source_path)
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/imports/{batch_id}/apply")
def apply_import_batch(batch_id: int, payload: ImportApplyRequest, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, Any]:
    with get_connection() as connection:
        batch = connection.execute(
            "SELECT * FROM import_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            raise HTTPException(status_code=404, detail="Пакет импорта не найден.")

        if payload.import_ok_rows_only:
            import_rows = connection.execute(
                """
                SELECT * FROM import_rows
                WHERE batch_id = ? AND status = 'ok' AND debtor_id IS NULL
                ORDER BY row_index ASC
                """,
                (batch_id,),
            ).fetchall()
        else:
            import_rows = connection.execute(
                """
                SELECT * FROM import_rows
                WHERE batch_id = ? AND status != 'blocked' AND debtor_id IS NULL
                ORDER BY row_index ASC
                """,
                (batch_id,),
            ).fetchall()

        imported_count = 0
        for import_row in import_rows:
            debtor_id = insert_imported_debtor(connection, serialize_import_row(dict(import_row)))
            connection.execute(
                "UPDATE import_rows SET debtor_id = ? WHERE id = ?",
                (debtor_id, import_row["id"]),
            )
            imported_count += 1

        connection.execute(
            """
            UPDATE import_batches
            SET imported_rows = imported_rows + ?, status = ?
            WHERE id = ?
            """,
            (
                imported_count,
                "imported" if imported_count else dict(batch)["status"],
                batch_id,
            ),
        )
        connection.commit()

        updated_batch = connection.execute(
            "SELECT * FROM import_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()

    return {
        "batch": serialize_import_batch(dict(updated_batch)),
        "importedRows": imported_count,
    }


@app.get("/api/debtors")
def list_debtors(country: str = DEFAULT_COUNTRY, _user: dict[str, Any] = Depends(require_app_user)) -> list[dict[str, Any]]:
    normalized_country = normalize_country_code(country)
    with get_connection() as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM debtors
                WHERE COALESCE(country, ?) = ?
                  AND csi_transferred_at IS NULL
                """,
                (DEFAULT_COUNTRY, normalized_country),
            ).fetchall()
        ]

    mark_return_rework_children(rows)
    ordered_rows = order_debtors(rows)
    return [serialize_debtor(row) for row in ordered_rows]


@app.get("/api/csi-debtors")
def list_csi_debtors(
    country: str = DEFAULT_COUNTRY,
    _user: dict[str, Any] = Depends(require_app_user),
) -> list[dict[str, Any]]:
    normalized_country = normalize_country_code(country)
    with get_connection() as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM debtors
                WHERE COALESCE(country, ?) = ?
                  AND csi_transferred_at IS NOT NULL
                """,
                (DEFAULT_COUNTRY, normalized_country),
            ).fetchall()
        ]

    mark_return_rework_children(rows)
    ordered_rows = order_debtors(rows)
    return [serialize_debtor(row) for row in ordered_rows]


@app.get("/api/debtors/{debtor_id}/received-payments")
def get_debtor_received_payments(
    debtor_id: int,
    _user: dict[str, Any] = Depends(require_app_user),
) -> dict[str, Any]:
    with get_connection() as connection:
        debtor_row = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()
        if debtor_row is None:
            raise HTTPException(status_code=404, detail="Р—Р°РїРёСЃСЊ РЅРµ РЅР°Р№РґРµРЅР°.")

        debtor = dict(debtor_row)
        payments = list_debtor_received_payments(connection, debtor)

    return {
        "debtor_id": debtor_id,
        "total_amount": parse_float(debtor.get("received_amount")),
        "payments": payments,
    }


@app.put("/api/debtors/{debtor_id}/received-payments")
def update_debtor_received_payments(
    debtor_id: int,
    payload: DebtorReceivedPaymentsUpdateRequest,
    _user: dict[str, Any] = Depends(require_app_user),
) -> dict[str, Any]:
    created_at = datetime.now().replace(microsecond=0).isoformat()

    with get_connection() as connection:
        debtor_row = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()
        if debtor_row is None:
            raise HTTPException(status_code=404, detail="Р—Р°РїРёСЃСЊ РЅРµ РЅР°Р№РґРµРЅР°.")

        debtor = dict(debtor_row)
        if payload.payments and parse_float(debtor.get("decision_payout")) <= 0:
            raise HTTPException(
                status_code=400,
                detail="РќРµР»СЊР·СЏ Р·Р°С„РёРєСЃРёСЂРѕРІР°С‚СЊ РїРѕР»СѓС‡РµРЅРЅСѓСЋ СЃСѓРјРјСѓ Р±РµР· СЃСѓРјРјС‹ РІС‹РїР»Р°С‚С‹ РїРѕ СЂРµС€РµРЅРёСЋ.",
            )

        normalized_payments: list[tuple[str, float]] = []
        for item in payload.payments:
            amount = round(float(item.amount), 2)
            if amount <= 0:
                raise HTTPException(status_code=400, detail="РЎСѓРјРјР° РїР»Р°С‚РµР¶Р° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ РЅСѓР»СЏ.")
            if not item.legacy and item.payment_date is None:
                raise HTTPException(status_code=400, detail="РЈРєР°Р¶РёС‚Рµ РґР°С‚Сѓ РїР»Р°С‚РµР¶Р°.")
            normalized_payments.append((item.payment_date.isoformat() if item.payment_date else "", amount))

        connection.execute("DELETE FROM debtor_received_payments WHERE debtor_id = ?", (debtor_id,))
        for payment_date, amount in normalized_payments:
            connection.execute(
                """
                INSERT INTO debtor_received_payments (debtor_id, payment_date, amount, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (debtor_id, payment_date, amount, created_at),
            )

        total_amount = round(sum(amount for _, amount in normalized_payments), 2)
        connection.execute(
            "UPDATE debtors SET received_amount = ? WHERE id = ?",
            (total_amount, debtor_id),
        )
        updated_debtor_row = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()
        connection.commit()

        updated_debtor = dict(updated_debtor_row)
        payments = list_debtor_received_payments(connection, updated_debtor)

    return {
        "debtor_id": debtor_id,
        "total_amount": parse_float(updated_debtor.get("received_amount")),
        "payments": payments,
    }


@app.post("/api/csi/export-pdf")
def export_csi_pdf(
    payload: CsiExportPdfRequest,
    country: str = DEFAULT_COUNTRY,
    _user: dict[str, Any] = Depends(require_app_user),
) -> FileResponse:
    normalized_country = normalize_country_code(country)
    date_from = payload.date_from
    date_to = payload.date_to
    if date_to < date_from:
        raise HTTPException(status_code=400, detail="Дата окончания не может быть раньше даты начала.")

    with get_connection() as connection:
        rows, total_amount = collect_csi_export_rows(
            connection,
            country=normalized_country,
            date_from=date_from,
            date_to=date_to,
        )

    pdf_path = render_csi_export_pdf(normalized_country, date_from, date_to, rows, total_amount)
    filename = f"csi_export_{normalized_country}_{date_from.isoformat()}_{date_to.isoformat()}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


@app.get("/api/incoming-correspondence")
def list_incoming_correspondence(
    country: str = DEFAULT_COUNTRY,
    _user: dict[str, Any] = Depends(require_app_user),
) -> list[dict[str, Any]]:
    normalized_country = normalize_country_code(country)
    with get_connection() as connection:
        process_due_incoming_claim_alerts(connection, normalized_country)
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM incoming_correspondence
                WHERE COALESCE(country, ?) = ?
                ORDER BY received_date DESC, id DESC
                """,
                (DEFAULT_COUNTRY, normalized_country),
            ).fetchall()
        ]
    return [serialize_incoming_correspondence(row) for row in rows]


@app.post("/api/incoming-correspondence", status_code=201)
def create_incoming_correspondence(
    payload: IncomingCorrespondenceCreate,
    _user: dict[str, Any] = Depends(require_app_user),
) -> dict[str, Any]:
    country = normalize_country_code(payload.country)
    created_at = datetime.now().replace(microsecond=0).isoformat()
    payload_data = payload.model_dump()
    payload_data["country"] = country
    validate_incoming_correspondence_payload(payload_data)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO incoming_correspondence (
                created_at,
                updated_at,
                country,
                category,
                received_date,
                receive_method,
                company,
                client_name,
                authority_kind,
                court,
                other_authority,
                contract_number,
                responsible_person,
                response_text,
                response_date,
                sent_date,
                comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                created_at,
                country,
                payload.category.strip(),
                payload.received_date.isoformat(),
                payload.receive_method.strip(),
                payload.company.strip(),
                payload.client_name.strip(),
                payload.authority_kind.strip(),
                (payload.court or "").strip(),
                (payload.other_authority or "").strip(),
                (payload.contract_number or "").strip(),
                (payload.responsible_person or "").strip(),
                str(payload.response_text or "").strip() or None,
                payload.response_date.isoformat() if payload.response_date else None,
                payload.sent_date.isoformat() if payload.sent_date else None,
                str(payload.comment or "").strip() or None,
            ),
        )
        record_id = cursor.lastrowid
        connection.commit()
        row = connection.execute(
            "SELECT * FROM incoming_correspondence WHERE id = ?",
            (record_id,),
        ).fetchone()
    return serialize_incoming_correspondence(dict(row))


@app.patch("/api/incoming-correspondence/{record_id}")
def update_incoming_correspondence(
    record_id: int,
    payload: IncomingCorrespondenceUpdate,
    _user: dict[str, Any] = Depends(require_app_user),
) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Нет полей для обновления.")

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT * FROM incoming_correspondence WHERE id = ?",
            (record_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Запись не найдена.")

        existing_dict = dict(existing)
        country = normalize_country_code(str(updates.get("country") or existing_dict.get("country") or DEFAULT_COUNTRY))
        merged_payload = {
            "country": country,
            "category": updates.get("category", existing_dict.get("category")),
            "received_date": updates.get("received_date", parse_date_value(existing_dict.get("received_date"))),
            "receive_method": updates.get("receive_method", existing_dict.get("receive_method")),
            "company": updates.get("company", existing_dict.get("company")),
            "client_name": updates.get("client_name", existing_dict.get("client_name")),
            "authority_kind": updates.get("authority_kind", existing_dict.get("authority_kind")),
            "court": updates.get("court", existing_dict.get("court")),
            "other_authority": updates.get("other_authority", existing_dict.get("other_authority")),
            "contract_number": updates.get("contract_number", existing_dict.get("contract_number")),
            "responsible_person": updates.get("responsible_person", existing_dict.get("responsible_person")),
            "response_text": updates.get("response_text", existing_dict.get("response_text")),
            "response_date": updates.get("response_date", parse_date_value(existing_dict.get("response_date"))),
            "sent_date": updates.get("sent_date", parse_date_value(existing_dict.get("sent_date"))),
            "comment": updates.get("comment", existing_dict.get("comment")),
        }
        validate_incoming_correspondence_payload(merged_payload)

        normalized_updates: dict[str, Any] = {}
        for key, value in updates.items():
            if key == "country":
                normalized_updates[key] = country
            elif key in {"received_date", "response_date", "sent_date"}:
                normalized_updates[key] = value.isoformat() if value else None
            elif isinstance(value, str):
                normalized_updates[key] = value.strip()
            else:
                normalized_updates[key] = value

        normalized_updates["updated_at"] = datetime.now().replace(microsecond=0).isoformat()
        assignments = ", ".join(f"{field} = ?" for field in normalized_updates)
        values = list(normalized_updates.values()) + [record_id]
        connection.execute(
            f"UPDATE incoming_correspondence SET {assignments} WHERE id = ?",
            values,
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM incoming_correspondence WHERE id = ?",
            (record_id,),
        ).fetchone()
    return serialize_incoming_correspondence(dict(row))


@app.delete("/api/incoming-correspondence/{record_id}", status_code=204, response_class=Response)
def delete_incoming_correspondence(
    record_id: int,
    _user: dict[str, Any] = Depends(require_app_user),
) -> Response:
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT claim_response_pdf_name FROM incoming_correspondence WHERE id = ?",
            (record_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Запись не найдена.")
        connection.execute("DELETE FROM incoming_correspondence WHERE id = ?", (record_id,))
        connection.commit()
    return Response(status_code=204)


@app.post("/api/incoming-correspondence/{record_id}/claim-response-pdf")
def generate_incoming_claim_response_pdf(
    record_id: int,
    payload: IncomingClaimResponsePdfRequest,
    _user: dict[str, Any] = Depends(require_app_user),
) -> FileResponse:
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT * FROM incoming_correspondence WHERE id = ?",
            (record_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Запись не найдена.")
        record = dict(existing)

    if str(record.get("category") or "").strip() != INCOMING_CATEGORY_CLAIM:
        raise HTTPException(status_code=400, detail="Ответ на претензию можно сформировать только для претензии.")

    pdf_path = render_incoming_claim_response_pdf(record, payload)
    file_name = pdf_path.name
    generated_at = datetime.now().replace(microsecond=0).isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE incoming_correspondence
            SET claim_response_pdf_name = ?, claim_response_generated_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (file_name, generated_at, generated_at, record_id),
        )
        connection.commit()
    return FileResponse(pdf_path, media_type="application/pdf", filename=file_name)


@app.get("/api/incoming-correspondence/{record_id}/claim-response-file")
def download_incoming_claim_response_file(
    record_id: int,
    _user: dict[str, Any] = Depends(require_app_user),
) -> FileResponse:
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT claim_response_pdf_name FROM incoming_correspondence WHERE id = ?",
            (record_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Р—Р°РїРёСЃСЊ РЅРµ РЅР°Р№РґРµРЅР°.")
        file_name = str(existing["claim_response_pdf_name"] or "").strip()

    if not file_name:
        raise HTTPException(status_code=404, detail="Р”РѕРєСѓРјРµРЅС‚ РѕС‚РІРµС‚Р° РµС‰Рµ РЅРµ СЃС„РѕСЂРјРёСЂРѕРІР°РЅ.")

    file_path = resolve_incoming_claim_response_file_path(file_name)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Р¤Р°Р№Р» РѕС‚РІРµС‚Р° РЅРµ РЅР°Р№РґРµРЅ.")

    return FileResponse(file_path, media_type="application/pdf", filename=file_path.name)


@app.post("/api/debtors", status_code=201)
def create_debtor(payload: DebtorCreate, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, Any]:
    created_at = datetime.now().replace(microsecond=0).isoformat()
    country = normalize_country_code(payload.country)
    normalized_contract_number = normalize_text(payload.contract_number)

    with get_connection() as connection:
        existing_duplicate = connection.execute(
            """
            SELECT id
            FROM debtors
            WHERE COALESCE(country, ?) = ?
              AND UPPER(TRIM(contract_number)) = UPPER(TRIM(?))
            LIMIT 1
            """,
            (DEFAULT_COUNTRY, country, normalized_contract_number),
        ).fetchone()
        if existing_duplicate is not None:
            raise HTTPException(status_code=409, detail="CLIENT_ALREADY_EXISTS")

        if payload.preserve_city_with_manual_court:
            city_value = str(payload.city or "").strip()
            court_value = str(payload.court or "").strip()
        else:
            city_value, court_value = align_city_with_court(connection, country, payload.city, payload.court)
        cursor = connection.execute(
            """
            INSERT INTO debtors (
                created_at,
                country,
                category,
                parent_debtor_id,
                client_name,
                contract_number,
                last_missed_payment_date,
                company,
                city,
                court,
                debt_amount,
                mobile_phone,
                home_phone,
                address,
                contract_total_amount,
                contract_advance_amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                country,
                DEFAULT_CATEGORY,
                None,
                payload.client_name.strip(),
                payload.contract_number.strip(),
                payload.last_missed_payment_date.isoformat(),
                payload.company.strip(),
                city_value,
                court_value,
                float(payload.debt_amount),
                normalize_text(payload.mobile_phone),
                normalize_text(payload.home_phone),
                normalize_text(payload.address),
                float(payload.contract_total_amount) if payload.contract_total_amount is not None else None,
                float(payload.contract_advance_amount) if payload.contract_advance_amount is not None else None,
            ),
        )
        debtor_id = cursor.lastrowid
        connection.commit()
        row = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()

    debtor = dict(row)
    debtor["has_return_rework_child"] = False
    return serialize_debtor(debtor)


@app.patch("/api/debtors/{debtor_id}")
def update_debtor(debtor_id: int, payload: DebtorUpdate, _user: dict[str, Any] = Depends(require_app_user)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    preserve_city_with_manual_court = bool(updates.pop("preserve_city_with_manual_court", False))
    if not updates:
        raise HTTPException(status_code=400, detail="Нет полей для обновления.")

    with get_connection() as connection:
        existing = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Запись не найдена.")

        existing_dict = dict(existing)
        country = normalize_country_code(str(existing_dict.get("country") or DEFAULT_COUNTRY))
        existing_dict["has_return_rework_child"] = has_return_rework_child(connection, debtor_id)
        if "last_missed_payment_date" in updates and existing_dict.get("lawsuit_installment_from"):
            updates["lawsuit_installment_from"] = updates.get("last_missed_payment_date")
        if "court" in updates:
            city_candidate = str(updates.get("city") or existing_dict.get("city") or "")
            court_candidate = str(updates.get("court") or "")
            if preserve_city_with_manual_court:
                updates["city"] = city_candidate.strip()
                updates["court"] = court_candidate.strip()
            else:
                aligned_city, aligned_court = align_city_with_court(connection, country, city_candidate, court_candidate)
                updates["city"] = aligned_city
                updates["court"] = aligned_court
        elif "city" in updates:
            updates["city"] = str(updates["city"] or "").strip()
        updates = apply_pre_validation_defaults(existing_dict, updates)
        validate_stage_dependencies(existing_dict, updates)
        updates = apply_business_rules(existing_dict, updates)
        validate_category_update(existing_dict, updates)
        validate_decision_update(existing_dict, updates)
        updates = apply_csi_transfer_state(existing_dict, updates)
        normalized = normalize_updates(updates)
        assignments = ", ".join(f"{field} = ?" for field in normalized)
        values = list(normalized.values()) + [debtor_id]

        connection.execute(f"UPDATE debtors SET {assignments} WHERE id = ?", values)
        row = dict(connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone())
        ensure_return_rework_child(connection, row)
        row["has_return_rework_child"] = has_return_rework_child(connection, debtor_id)
        connection.commit()

    return serialize_debtor(row)


@app.delete("/api/debtors/{debtor_id}", status_code=204, response_class=Response)
def delete_debtor(debtor_id: int, _user: dict[str, Any] = Depends(require_app_user)) -> Response:
    with get_connection() as connection:
        existing = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Запись не найдена.")

        row = dict(existing)
        if row.get("parent_debtor_id"):
            connection.execute("DELETE FROM debtors WHERE id = ?", (debtor_id,))
        else:
            connection.execute(
                "DELETE FROM debtors WHERE id = ? OR parent_debtor_id = ?",
                (debtor_id, debtor_id),
            )
        connection.commit()
    return Response(status_code=204)


@app.get("/api/debtors/{debtor_id}/claim-pdf")
def generate_claim_pdf(debtor_id: int, _user: dict[str, Any] = Depends(require_app_user)) -> FileResponse:
    with get_connection() as connection:
        existing = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Запись не найдена.")

        connection.execute(
            """
            UPDATE debtors
            SET lawsuit_installment_from = ?,
                lawsuit_installment_to = ?,
                lawsuit_monthly_payment_amount = ?,
                lawsuit_first_period_paid_amount = ?
            WHERE id = ?
            """,
            (
                payload.installment_from.isoformat(),
                payload.installment_to.isoformat(),
                float(payload.monthly_payment_amount),
                float(payload.first_period_paid_amount or 0),
                debtor_id,
            ),
        )
        row = dict(existing)
        row["has_return_rework_child"] = has_return_rework_child(connection, debtor_id)
        row["lawsuit_installment_from"] = payload.installment_from.isoformat()
        row["lawsuit_installment_to"] = payload.installment_to.isoformat()
        row["lawsuit_monthly_payment_amount"] = float(payload.monthly_payment_amount)
        row["lawsuit_first_period_paid_amount"] = float(payload.first_period_paid_amount or 0)
        connection.commit()

    pdf_path = render_claim_pdf(row)
    file_name = f"pretenziya_{debtor_id}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=file_name)


@app.post("/api/debtors/{debtor_id}/claim-pdf")
def generate_claim_pdf_with_confirmation(
    debtor_id: int,
    payload: ClaimPdfGenerateRequest,
    _user: dict[str, Any] = Depends(require_app_user),
) -> FileResponse:
    with get_connection() as connection:
        existing = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Запись не найдена.")

        row = dict(existing)
        row["has_return_rework_child"] = has_return_rework_child(connection, debtor_id)

    pdf_path = render_claim_pdf(
        row,
        debt_amount_override=payload.debt_amount_override,
        product_overrides=[item.model_dump() for item in (payload.product_overrides or [])],
    )
    file_name = f"pretenziya_{debtor_id}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=file_name)


@app.post("/api/debtors/{debtor_id}/lawsuit-pdf")
def generate_lawsuit_pdf_with_confirmation(
    debtor_id: int,
    payload: LawsuitPdfGenerateRequest,
    _user: dict[str, Any] = Depends(require_app_user),
) -> FileResponse:
    with get_connection() as connection:
        existing = connection.execute("SELECT * FROM debtors WHERE id = ?", (debtor_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Р—Р°РїРёСЃСЊ РЅРµ РЅР°Р№РґРµРЅР°.")

        row = dict(existing)
        row["has_return_rework_child"] = has_return_rework_child(connection, debtor_id)

    pdf_path = render_lawsuit_pdf(row, payload)
    file_name = f"isk_{debtor_id}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=file_name)


