from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.reference_data import DEFAULT_COUNTRY, SUPPORTED_COUNTRIES, get_companies_by_country


@dataclass
class DiSellApiError(Exception):
    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


def normalize_contract_number(value: str | None) -> str:
    text = (value or "").strip().upper()
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
            "“": '"',
            "”": '"',
            "«": '"',
            "»": '"',
        }
    )
    normalized = text.translate(translation)
    return "".join(ch for ch in normalized if ch.isalnum())


def parse_money(value: Any) -> Decimal:
    if isinstance(value, dict):
        value = value.get("amount")
    if value in (None, ""):
        return Decimal("0")

    text = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def contract_date_from_number(value: str | None) -> date | None:
    text = (value or "").strip()
    match = None
    for candidate in (
        re.search(r"(\d{2})(\d{2})(\d{2})", text),
        re.search(r"(\d{2})[./-](\d{2})[./-](\d{2,4})", text),
    ):
        if candidate:
            match = candidate
            break
    if not match:
        return None

    day = int(match.group(1))
    month = int(match.group(2))
    year_fragment = match.group(3)
    year = int(year_fragment) if len(year_fragment) == 4 else 2000 + int(year_fragment)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def normalize_country_code(value: str | None) -> str:
    normalized = (value or DEFAULT_COUNTRY).strip().lower()
    return normalized if normalized in SUPPORTED_COUNTRIES else DEFAULT_COUNTRY


def normalize_company_key(value: str | None) -> str:
    text = (value or "").strip().lower()
    translation = str.maketrans(
        {
            "«": '"',
            "»": '"',
            "“": '"',
            "”": '"',
            "„": '"',
        }
    )
    normalized = text.translate(translation)
    collapsed = re.sub(r"[^a-z0-9а-яё]+", "", normalized, flags=re.IGNORECASE)
    for prefix in ("тоо", "too", "ооо", "ooo", "llp"):
        if collapsed.startswith(prefix):
            return collapsed[len(prefix) :]
    return collapsed


def get_country_context_keys(country: str) -> set[str]:
    normalized = normalize_country_code(country)
    if normalized == "uz":
        return {"uzbekistan", "uzbekiston", "oʻzbekiston", "ozbekiston", "ўзбекистон"}
    return {"kazakhstan", "kazakstan", "қазақстан", "казахстан"}

class DiSellApiClient:
    def __init__(self) -> None:
        local_config = self._load_local_config()
        self.api_base_url = str(
            os.getenv("DISELL_API_BASE_URL") or local_config.get("api_base_url") or "https://disell.eu/api/v1"
        ).rstrip("/")
        self.auth_base_url = str(
            os.getenv("DISELL_AUTH_BASE_URL") or local_config.get("auth_base_url") or "https://disell.eu/api"
        ).rstrip("/")
        self.username = str(os.getenv("DISELL_API_USERNAME") or local_config.get("username") or "").strip()
        self.password = str(os.getenv("DISELL_API_PASSWORD") or local_config.get("password") or "").strip()
        self.client_id = str(
            os.getenv("DISELL_API_CLIENT_ID") or local_config.get("client_id") or "crm_api"
        ).strip() or "crm_api"
        self.client_secret = str(
            os.getenv("DISELL_API_CLIENT_SECRET") or local_config.get("client_secret") or "crm_pass"
        ).strip() or "crm_pass"
        self.grant_type = str(
            os.getenv("DISELL_API_GRANT_TYPE") or local_config.get("grant_type") or "password"
        ).strip() or "password"
        self.timeout = float(os.getenv("DISELL_API_TIMEOUT") or local_config.get("timeout") or "20")
        self._token: str | None = None

    @staticmethod
    def _load_local_config() -> dict[str, Any]:
        path = Path(__file__).resolve().parent.parent / "data" / "crm_credentials.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def lookup_debtor_prefill(self, contract_number: str, country: str = DEFAULT_COUNTRY) -> dict[str, Any]:
        context = self.find_deal_context(contract_number, country=country)
        matched_deal = context["deal"]
        matched_company = context["company"]
        personal_details = context["personal_details"]
        sale_company_name = context["sale_company_name"]

        contract_total_amount = float(parse_money((matched_deal.get("priceForSet") or {}).get("amount")))
        payments_total = float(
            sum(parse_money(payment.get("amount")) for payment in (matched_deal.get("payments") or []))
        )
        debt_amount = max(round(contract_total_amount - payments_total, 2), 0.0)
        product_details = self.get_product_details_one_by_one(
            company_id=str(matched_company["id"]),
            inventory_items=matched_deal.get("inventory") or [],
        )

        address = self.format_address(personal_details.get("address"))
        city = self.normalize_optional_text((personal_details.get("address") or {}).get("city"))
        phone_numbers = personal_details.get("phoneNumbers") or {}

        return {
            "contract_number": str(matched_deal.get("number") or contract_number).strip(),
            "contract_date": matched_deal.get("signDate"),
            "client_name": self.build_full_name(personal_details),
            "company": sale_company_name,
            "city": city,
            "mobile_phone": self.normalize_optional_text(phone_numbers.get("cell")),
            "home_phone": self.normalize_optional_text(phone_numbers.get("home")),
            "address": address,
            "debt_amount": debt_amount,
            "contract_total_amount": contract_total_amount or None,
            "contract_advance_amount": round(payments_total, 2),
            "products": [
                {
                    "name": item["name"],
                    "quantity": item["quantity"],
                }
                for item in product_details
            ],
        }

    def lookup_lawsuit_context(self, contract_number: str, country: str = DEFAULT_COUNTRY) -> dict[str, Any]:
        context = self.find_deal_context(contract_number, country=country)
        deal = context["deal"]
        personal_details = context["personal_details"]
        company = context["company"]
        company_name = context["sale_company_name"]

        payments_total = float(sum(parse_money(payment.get("amount")) for payment in (deal.get("payments") or [])))
        contract_total_amount = float(parse_money((deal.get("priceForSet") or {}).get("amount")))
        discount_amount = float(parse_money(deal.get("discountAmount")))
        product_details = self.get_product_details_one_by_one(
            company_id=str(company["id"]),
            inventory_items=deal.get("inventory") or [],
        )
        product_names = [item["display_name"] for item in product_details]
        phone_numbers = personal_details.get("phoneNumbers") or {}

        return {
            "contract_number": str(deal.get("number") or contract_number).strip(),
            "contract_date": deal.get("signDate"),
            "client_name": self.build_full_name(personal_details),
            "client_short_name": self.build_short_name(personal_details),
            "client_inn": self.normalize_optional_text(
                personal_details.get("individualTaxNumber") or personal_details.get("identificationNumber")
            ),
            "client_address": self.format_address(personal_details.get("address")),
            "client_phones": [phone for phone in [phone_numbers.get("cell"), phone_numbers.get("home")] if phone],
            "company": company_name,
            "discount_amount": discount_amount,
            "contract_total_amount": contract_total_amount,
            "debt_amount": max(round(contract_total_amount - payments_total, 2), 0.0),
            "advance_amount": round(payments_total, 2),
            "product_names": product_names,
            "products": product_details,
        }

    def find_deal_context(self, contract_number: str, country: str = DEFAULT_COUNTRY) -> dict[str, Any]:
        target_number = normalize_contract_number(contract_number)
        if not target_number:
            raise DiSellApiError("Укажите номер договора для поиска в CRM.", status_code=400)
        contract_date = contract_date_from_number(contract_number)
        target_country = normalize_country_code(country)
        allowed_sale_company_keys = {
            normalize_company_key(company_name) for company_name in get_companies_by_country(target_country)
        }
        allowed_context_keys = allowed_sale_company_keys | get_country_context_keys(target_country)

        company_contexts = self.list_allowed_companies()
        if not company_contexts:
            raise DiSellApiError("CRM не вернула доступные компании для текущего аккаунта.", status_code=502)
        if allowed_context_keys:
            company_contexts = [
                company
                for company in company_contexts
                if normalize_company_key(company.get("name")) in allowed_context_keys
            ]
        if not company_contexts:
            raise DiSellApiError("Для выбранной страны в CRM не найдены доступные компании.", status_code=404)

        matched_deal: dict[str, Any] | None = None
        matched_company: dict[str, Any] | None = None

        for company in company_contexts:
            page = 1
            page_count = 1
            while page <= page_count:
                query = {"page": page}
                if contract_date is not None:
                    contract_date_iso = contract_date.isoformat()
                    query.update(
                        {
                            "filters[signDate][from]": contract_date_iso,
                            "filters[signDate][to]": contract_date_iso,
                        }
                    )
                response = self._get("/deals", query=query, company_id=str(company["id"]))
                deals = response.get("data") or []
                for deal in deals:
                    if normalize_contract_number(deal.get("number")) == target_number:
                        matched_deal = deal
                        matched_company = company
                        break

                if matched_deal is not None:
                    break

                meta = response.get("meta") or {}
                page_count = int(meta.get("pageCount") or 1)
                page += 1

            if matched_deal is not None:
                break

        if matched_deal is None or matched_company is None:
            raise DiSellApiError("Договор не найден в CRM.", status_code=404)

        personal_details_id = str(matched_deal.get("buyerPersonalDetailsId") or "").strip()
        if not personal_details_id:
            raise DiSellApiError("В найденной сделке CRM не хватает данных клиента.", status_code=502)

        personal_details = self.get_personal_details(str(matched_company["id"]), personal_details_id)
        sale_company_name = self.get_sale_company_name(
            company_context_id=str(matched_company["id"]),
            sale_company_id=str(matched_deal.get("saleCompanyId") or "").strip(),
            fallback_name=str(matched_company.get("name") or "").strip(),
        )

        return {
            "deal": matched_deal,
            "company": matched_company,
            "personal_details": personal_details,
            "sale_company_name": sale_company_name,
        }

    def list_allowed_companies(self) -> list[dict[str, Any]]:
        page = 1
        page_count = 1
        companies: list[dict[str, Any]] = []
        while page <= page_count:
            response = self._get("/auth/allowed-companies", query={"page": page})
            companies.extend(response.get("data") or [])
            meta = response.get("meta") or {}
            page_count = int(meta.get("pageCount") or 1)
            page += 1
        return companies

    def get_personal_details(self, company_id: str, personal_details_id: str) -> dict[str, Any]:
        response = self._get(
            "/personal-details",
            company_id=company_id,
            query={"filters[id]": personal_details_id},
        )
        data = response.get("data") or []
        if not data:
            raise DiSellApiError("В CRM не найдены персональные данные клиента по сделке.", status_code=404)
        return data[0]

    def get_sale_company_name(self, company_context_id: str, sale_company_id: str, fallback_name: str) -> str:
        if not sale_company_id:
            return fallback_name

        response = self._get(
            "/sale-companies",
            company_id=company_context_id,
            query={"filters[id]": sale_company_id},
        )
        data = response.get("data") or []
        if not data:
            return fallback_name
        return str(data[0].get("name") or fallback_name).strip()

    def format_address(self, address: dict[str, Any] | None) -> str | None:
        if not address:
            return None

        parts = [
            self.normalize_optional_text(address.get("firstLevelAdministrative")),
            self.normalize_optional_text(address.get("city")),
            self.normalize_optional_text(address.get("street")),
            self.normalize_optional_text(address.get("postalCode")),
        ]
        values = [part for part in parts if part]
        return ", ".join(values) if values else None

    def build_full_name(self, personal_details: dict[str, Any]) -> str:
        parts = [
            self.normalize_optional_text(personal_details.get("surname")),
            self.normalize_optional_text(personal_details.get("name")),
            self.normalize_optional_text(personal_details.get("patrymonic")),
        ]
        result = " ".join(part for part in parts if part).strip()
        if not result:
            raise DiSellApiError("В CRM у клиента не заполнено ФИО.", status_code=502)
        return result

    def build_short_name(self, personal_details: dict[str, Any]) -> str:
        surname = self.normalize_optional_text(personal_details.get("surname")) or ""
        name = self.normalize_optional_text(personal_details.get("name")) or ""
        patronymic = self.normalize_optional_text(personal_details.get("patrymonic")) or ""
        initials = " ".join(
            f"{part[0]}." for part in (name, patronymic) if part
        )
        result = " ".join(part for part in [surname, initials] if part).strip()
        return result or self.build_full_name(personal_details)

    def get_product_names(self, company_id: str, product_ids: list[str]) -> list[str]:
        normalized_ids = [product_id for product_id in dict.fromkeys(product_ids) if product_id]
        if not normalized_ids:
            return []

        response = self._get(
            "/products",
            company_id=company_id,
            query={"filters[id]": json.dumps(normalized_ids, ensure_ascii=False)},
        )
        products = response.get("data") or []
        names_by_id = {
            str(product.get("id") or ""): self.normalize_optional_text(product.get("name")) or "Товар по договору"
            for product in products
        }
        return [names_by_id[product_id] for product_id in normalized_ids if product_id in names_by_id]

    def get_product_names_one_by_one(self, company_id: str, product_ids: list[str]) -> list[str]:
        normalized_ids = [product_id for product_id in dict.fromkeys(product_ids) if product_id]
        if not normalized_ids:
            return []

        names: list[str] = []
        for product_id in normalized_ids:
            response = self._get(
                "/products",
                company_id=company_id,
                query={"filters[id]": product_id},
            )
            products = response.get("data") or []
            if not products:
                continue
            product_name = self.normalize_optional_text(products[0].get("name")) or "Товар по договору"
            names.append(product_name)
        return names

    def get_product_details_one_by_one(self, company_id: str, inventory_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        product_cache: dict[str, str] = {}
        items: list[dict[str, Any]] = []

        for inventory_item in inventory_items:
            product_id = str(inventory_item.get("productId") or "").strip()
            if not product_id:
                continue

            product_name = product_cache.get(product_id)
            if product_name is None:
                response = self._get(
                    "/products",
                    company_id=company_id,
                    query={"filters[id]": product_id},
                )
                products = response.get("data") or []
                if products:
                    product_name = self.normalize_optional_text(products[0].get("name")) or "РўРѕРІР°СЂ РїРѕ РґРѕРіРѕРІРѕСЂСѓ"
                else:
                    product_name = "РўРѕРІР°СЂ РїРѕ РґРѕРіРѕРІРѕСЂСѓ"
                product_cache[product_id] = product_name

            raw_quantity = (
                inventory_item.get("signed")
                or inventory_item.get("actual")
                or inventory_item.get("quantity")
                or inventory_item.get("count")
                or inventory_item.get("qty")
                or inventory_item.get("amount")
                or 1
            )
            try:
                quantity = int(float(raw_quantity))
            except (TypeError, ValueError):
                quantity = 1
            quantity = max(quantity, 1)

            items.append(
                {
                    "product_id": product_id,
                    "name": product_name,
                    "quantity": quantity,
                    "display_name": f"{product_name} — {quantity} шт.",
                }
            )
        return items

    @staticmethod
    def normalize_optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _get(self, path: str, *, query: dict[str, Any] | None = None, company_id: str | None = None) -> dict[str, Any]:
        return self._request_json("GET", path, query=query, company_id=company_id)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        company_id: str | None = None,
        use_auth_base: bool = False,
    ) -> dict[str, Any]:
        token = self.get_access_token() if not use_auth_base else None
        base_url = self.auth_base_url if use_auth_base else self.api_base_url
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query, doseq=True)}"

        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if company_id:
            headers["Company"] = company_id

        request = Request(url, data=payload, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = self._extract_error_message(exc)
            status = 401 if exc.code == 401 else 502
            raise DiSellApiError(detail, status_code=status) from exc
        except URLError as exc:
            raise DiSellApiError("Не удалось подключиться к CRM API.", status_code=502) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DiSellApiError("CRM API вернула ответ в неожиданном формате.", status_code=502) from exc

    def get_access_token(self) -> str:
        if self._token:
            return self._token

        if not self.username or not self.password:
            raise DiSellApiError(
                "Для CRM-подтяжки не настроены DISELL_API_USERNAME и DISELL_API_PASSWORD.",
                status_code=503,
            )

        response = self._request_json(
            "POST",
            "/oauth2/token",
            body={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": self.grant_type,
                "username": self.username,
                "password": self.password,
            },
            use_auth_base=True,
        )
        token = str(response.get("access_token") or "").strip()
        if not token:
            raise DiSellApiError("CRM API не вернула access token.", status_code=502)
        self._token = token
        return token

    @staticmethod
    def _extract_error_message(exc: HTTPError) -> str:
        try:
            payload = exc.read().decode("utf-8")
        except Exception:
            payload = ""

        if payload:
            try:
                data = json.loads(payload)
                for key in ("message", "error_description", "error", "name"):
                    value = data.get(key)
                    if value:
                        return str(value)
            except json.JSONDecodeError:
                pass

        if exc.code == 401:
            return "CRM API отклонила авторизацию. Проверьте логин, пароль и доступ компании."
        if exc.code == 404:
            return "Запрошенные данные не найдены в CRM."
        return f"CRM API вернула ошибку {exc.code}."
