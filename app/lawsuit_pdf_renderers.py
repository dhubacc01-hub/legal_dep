from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont

from app.claim_pdf_service import load_claim_crm_context
from app.common_utils import contract_date_value_from_number, format_date, normalize_text, parse_float
from app.company_requisites_service import find_company_requisites, match_company_to_library, sanitize_company_name
from app.country_service import normalize_country_code
from app.disell_api import DiSellApiClient, DiSellApiError
from app.document_helpers import build_company_payment_detail_lines_uz, normalize_document_products
from app.financial_helpers import compute_lawsuit_claim_price, compute_simple_penalty_amount, format_money
from app.lawsuit_calculations import build_lawsuit_penalty_rows, build_short_client_name
from app.money_words import money_to_words_ru, money_to_words_sum_ru
from app.pdf_rendering import draw_text_block as render_draw_text_block, load_font as render_load_font, wrap_text as render_wrap_text
from app.reference_data import DEFAULT_COUNTRY
from app.schemas import LawsuitPdfGenerateRequest

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


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return render_load_font(
        size,
        bold=bold,
        regular_candidates=SERIF_FONT_REGULAR_CANDIDATES,
        bold_candidates=SERIF_FONT_BOLD_CANDIDATES,
    )


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    return render_wrap_text(draw, text, font, max_width)


def _draw_text_block(
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


def _render_lawsuit_pdf_old(
    debtor: dict[str, Any],
    payload: LawsuitPdfGenerateRequest,
    *,
    compute_financials_fn,
    compute_lawsuit_state_duty_fn,
    generated_dir: Path,
) -> Path:
    company_name_value = sanitize_company_name(str(debtor.get("company") or ""))
    requisites = find_company_requisites(
        company_name_value,
        str(debtor.get("country") or DEFAULT_COUNTRY),
    )
    if requisites is None:
        raise HTTPException(
            status_code=400,
            detail=f"Р”Р»СЏ РєРѕРјРїР°РЅРёРё В«{debtor.get('company') or '—'}В» РЅРµ РЅР°Р№РґРµРЅС‹ СЂРµРєРІРёР·РёС‚С‹.",
        )

    try:
        crm_context = DiSellApiClient().lookup_lawsuit_context(
            str(debtor.get("contract_number") or ""),
            country=str(debtor.get("country") or DEFAULT_COUNTRY),
        )
    except DiSellApiError:
        crm_context = {}

    company_name = requisites.get("company_name") or company_name_value or "—"
    company_phone = normalize_text(requisites.get("phone")) or "—"
    court_name = normalize_text(payload.court_name) or normalize_text(debtor.get("court")) or "—"
    client_name = normalize_text(crm_context.get("client_name")) or normalize_text(debtor.get("client_name")) or "—"
    client_short_name = normalize_text(crm_context.get("client_short_name")) or build_short_client_name(client_name)
    client_inn = normalize_text(crm_context.get("client_inn")) or "—"
    client_address = normalize_text(crm_context.get("client_address")) or normalize_text(debtor.get("address")) or "—"

    crm_phones = crm_context.get("client_phones") or []
    normalized_phones = [normalize_text(phone) for phone in crm_phones if normalize_text(phone)]
    if not normalized_phones:
        normalized_phones = [
            phone
            for phone in [normalize_text(debtor.get("mobile_phone")), normalize_text(debtor.get("home_phone"))]
            if phone
        ]
    client_phones = ", ".join(dict.fromkeys(normalized_phones)) if normalized_phones else "—"

    contract_number = str(crm_context.get("contract_number") or debtor.get("contract_number") or "—")
    contract_date = contract_date_value_from_number(contract_number)
    crm_contract_date = crm_context.get("contract_date")
    if isinstance(crm_contract_date, str) and crm_contract_date:
        try:
            contract_date = date.fromisoformat(crm_contract_date)
        except ValueError:
            pass

    contract_total_amount = parse_float(
        crm_context.get("contract_total_amount")
        if crm_context.get("contract_total_amount") is not None
        else debtor.get("contract_total_amount")
    )
    debt_amount = round(float(payload.debt_amount), 2)
    advance_amount = parse_float(
        crm_context.get("advance_amount")
        if crm_context.get("advance_amount") is not None
        else debtor.get("contract_advance_amount")
    )
    if advance_amount <= 0 and contract_total_amount > 0:
        advance_amount = max(round(contract_total_amount - debt_amount, 2), 0.0)

    discount_amount = parse_float(crm_context.get("discount_amount"))
    installment_balance_amount = max(round(contract_total_amount - advance_amount, 2), 0.0)
    total_payments_amount = parse_float(crm_context.get("advance_amount"))
    post_advance_payments = max(round(total_payments_amount - advance_amount, 2), 0.0)
    claim_sent_date_raw = debtor.get("claim_sent_date")
    if not claim_sent_date_raw:
        raise HTTPException(status_code=400, detail="Для формирования иска укажите дату отправки претензии.")
    try:
        claim_sent_date = date.fromisoformat(str(claim_sent_date_raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Дата отправки претензии заполнена некорректно.") from exc

    product_names = crm_context.get("product_names") or []
    if not product_names:
        product_names = ["РўРѕРІР°СЂ РїРѕ РґРѕРіРѕРІРѕСЂСѓ"]

    penalty_rows, adjusted_penalty_amount, total_overdue_days = build_lawsuit_penalty_rows(
        payload.installment_from,
        payload.installment_to,
        claim_sent_date,
        float(payload.monthly_payment_amount),
        float(payload.first_period_paid_amount or 0),
    )
    penalty_amount = adjusted_penalty_amount
    state_duty_amount = round((debt_amount + penalty_amount) * 0.03, 2)

    generated_dir.mkdir(parents=True, exist_ok=True)
    safe_contract = re.sub(r"[^A-Za-z0-9_-]+", "_", str(debtor.get("contract_number") or debtor.get("id")))
    pdf_path = generated_dir / f"lawsuit_{safe_contract}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    image_width = 1654
    image_height = 2339
    margin_left = 112
    margin_right = 112
    margin_top = 74
    margin_bottom = 82
    content_width = image_width - margin_left - margin_right
    block_width = 560
    paragraph_indent = 42

    regular_font = _load_font(24)
    title_font = _load_font(32, bold=True)
    section_font = _load_font(24, bold=True)
    small_font = _load_font(22)
    table_font = _load_font(20)
    table_font_bold = _load_font(20, bold=True)

    pages: list[Image.Image] = []
    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)
    current_y = margin_top

    def new_page() -> None:
        nonlocal image, draw, current_y
        pages.append(image)
        image = Image.new("RGB", (image_width, image_height), "white")
        draw = ImageDraw.Draw(image)
        current_y = margin_top

    def estimate_block_height(
        text: str,
        font: ImageFont.ImageFont,
        width: int,
        line_spacing: int,
        first_line_indent: int = 0,
    ) -> int:
        normalized = " ".join((text or "").split())
        if not normalized:
            return 0
        bbox = draw.textbbox((0, 0), "РђРі", font=font)
        line_height = (bbox[3] - bbox[1]) + line_spacing
        if first_line_indent > 0:
            words = normalized.split(" ")
            first_line_words: list[str] = []
            while words:
                candidate_words = first_line_words + [words[0]]
                candidate = " ".join(candidate_words).strip()
                if draw.textlength(candidate, font=font) <= max(40, width - first_line_indent):
                    first_line_words.append(words.pop(0))
                else:
                    break
            remaining = " ".join(words).strip()
            lines = 1 if first_line_words else 0
            if remaining:
                lines += len(_wrap_text(draw, remaining, font, width))
            return max(lines, 1) * line_height
        return max(len(_wrap_text(draw, normalized, font, width)), 1) * line_height

    def ensure_space(required_height: int) -> None:
        nonlocal current_y
        if current_y + required_height > image_height - margin_bottom:
            new_page()

    def draw_paragraph(
        text: str,
        *,
        font: ImageFont.ImageFont = regular_font,
        align: str = "left",
        spacing_after: int = 12,
        first_line_indent: int = paragraph_indent,
    ) -> None:
        nonlocal current_y
        estimate = estimate_block_height(text, font, content_width, 14, first_line_indent) + spacing_after
        ensure_space(estimate)
        current_y = _draw_text_block(
            draw,
            text,
            x=margin_left,
            y=current_y,
            width=content_width,
            font=font,
            line_spacing=14,
            align=align,
            paragraph_spacing=spacing_after,
            first_line_indent=first_line_indent if align == "left" else 0,
        )

    top_right_x = image_width - margin_right - block_width
    current_y = _draw_text_block(
        draw,
        court_name,
        x=top_right_x,
        y=current_y,
        width=block_width,
        font=section_font,
        line_spacing=12,
        align="left",
        paragraph_spacing=18,
    )

    plaintiff_lines = [
        "РСЃС‚РµС†:",
        company_name,
        normalize_text(requisites.get("bin")) or "—",
        normalize_text(requisites.get("address")) or "—",
        "Email: sud.process.dp@gmail.com",
        "РўРµР»: +7 700 739 9636",
    ]
    for line in plaintiff_lines:
        current_y = _draw_text_block(
            draw,
            line,
            x=top_right_x,
            y=current_y,
            width=block_width,
            font=regular_font if line != "РСЃС‚РµС†:" else section_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=2,
        )

    current_y += 14
    defendant_lines = [
        "РћС‚РІРµС‚С‡РёРє:",
        client_name,
        client_inn,
        client_address,
        client_phones,
    ]
    for line in defendant_lines:
        current_y = _draw_text_block(
            draw,
            line,
            x=top_right_x,
            y=current_y,
            width=block_width,
            font=regular_font if line != "РћС‚РІРµС‚С‡РёРє:" else section_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=2,
        )

    current_y += 32
    ensure_space(120)
    current_y = _draw_text_block(
        draw,
        "РСЃРє\nРѕ РІР·С‹СЃРєР°РЅРёРё Р·Р°РґРѕР»Р¶РµРЅРЅРѕСЃС‚Рё",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=title_font,
        line_spacing=12,
        align="center",
        paragraph_spacing=28,
    )

    body_paragraphs = [
        "Р”РёСЃРїРѕР·РёС†РёРµР№ СЃС‚Р°С‚СЊРё 9 Р“СЂР°Р¶РґР°РЅСЃРєРѕРіРѕ РєРѕРґРµРєСЃР° Р РµСЃРїСѓР±Р»РёРєРё РљР°Р·Р°С…СЃС‚Р°РЅ (РґР°Р»РµРµ – Р“Рљ) Р·Р°РєСЂРµРїР»РµРЅРѕ, С‡С‚Рѕ Р·Р°С‰РёС‚Р° РіСЂР°Р¶РґР°РЅСЃРєРёС… РїСЂР°РІ РѕСЃСѓС‰РµСЃС‚РІР»СЏРµС‚СЃСЏ СЃСѓРґРѕРј, Р°СЂР±РёС‚СЂР°Р¶РµРј РїСѓС‚РµРј: РїСЂРёР·РЅР°РЅРёСЏ РїСЂР°РІ; РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёСЏ РїРѕР»РѕР¶РµРЅРёСЏ, СЃСѓС‰РµСЃС‚РІРѕРІР°РІС€РµРіРѕ РґРѕ РЅР°СЂСѓС€РµРЅРёСЏ РїСЂР°РІР°; РїСЂРµСЃРµС‡РµРЅРёСЏ РґРµР№СЃС‚РІРёР№, РЅР°СЂСѓС€Р°СЋС‰РёС… РїСЂР°РІРѕ РёР»Рё СЃРѕР·РґР°СЋС‰РёС… СѓРіСЂРѕР·Сѓ РµРіРѕ РЅР°СЂСѓС€РµРЅРёСЏ; РїСЂРёСЃСѓР¶РґРµРЅРёСЏ Рє РёСЃРїРѕР»РЅРµРЅРёСЋ РѕР±СЏР·Р°РЅРЅРѕСЃС‚Рё РІ РЅР°С‚СѓСЂРµ; РІР·С‹СЃРєР°РЅРёСЏ СѓР±С‹С‚РєРѕРІ, РЅРµСѓСЃС‚РѕР№РєРё; РїСЂРёР·РЅР°РЅРёСЏ РѕСЃРїРѕСЂРёРјРѕР№ СЃРґРµР»РєРё РЅРµРґРµР№СЃС‚РІРёС‚РµР»СЊРЅРѕР№ и применения последствий ее недействительности, применения последствий недействительности ничтожной сделки; компенсации морального вреда; прекращения или изменения правоотношений; признания недействительным или не подлежащим применению не соответствующего законодательству Республики Казахстан акта органа государственного управления или местного представительного либо исполнительного органа; взыскания штрафа с государственного органа или должностного лица за воспрепятствование гражданину или юридическому лицу в приобретении или осуществлении права, а также иными способами, предусмотренными законодательными актами.",
        f"РњРµР¶РґСѓ {company_name} и {client_short_name} заключен договор купли/продажи № {contract_number} от {format_date(contract_date) or '—'}, в соответствии с которым в собственность передан товар, а именно:",
    ]
    for paragraph in body_paragraphs:
        draw_paragraph(paragraph)

    for product_name in product_names:
        draw_paragraph(product_name, first_line_indent=0, spacing_after=6)

    remaining_paragraphs = [
        "РЎС‚Р°С‚СЊРµР№ 7 ГК определено, что гражданские права и обязанности возникают, изменяются и прекращаются из оснований, предусмотренных законодательством Республики Казахстан, а также из действий граждан и юридических лиц, которые хотя и не предусмотрены им, но в силу общих начал и смысла гражданского законодательства порождают гражданские права и обязанности. В соответствии с этим гражданские права и обязанности возникают, изменяются и прекращаются, помимо прочих, из договоров и иных сделок, предусмотренных законодательством Республики Казахстан, а также из сделок, хотя и не предусмотренных им, но не противоречащих законодательству Республики Казахстан.",
        "РЎС‚Р°С‚СЊРµР№ 378 ГК определено, что договором признается соглашение двух или нескольких лиц об установлении, изменении или прекращении гражданских прав и обязанностей.",
        "В силу статьи 393 ГК договор считается заключенным, когда между сторонами в требуемой в подлежащих случаях форме достигнуто соглашение по всем существенным его условиям. Существенными являются условия о предмете договора, условия, которые признаны существенными законодательством или необходимы для договоров данного вида, а также все те условия, относительно которых по заявлению одной из сторон должно быть достигнуто соглашение. Если в соответствии с законодательными актами для заключения договора необходима передача имущества, договор считается заключенным с момента передачи соответствующего имущества.",
        "В соответствии со статьей 406 ГК по договору купли-продажи одна сторона (продавец) обязуется передать имущество (товар) в собственность, хозяйственное ведение или оперативное управление другой стороне (покупателю), а покупатель обязуется принять это имущество (товар) и уплатить за него определенную денежную сумму (цену).",
        f"Согласно условиям заключенного договора определено, что ответчик принял на себя обязательства по оплате стоимости полученного товара. Стоимость переданного товара с учетом скидки {format_money(discount_amount)} тенге была определена в размере {format_money(contract_total_amount)} тенге, из которых {format_money(advance_amount)} тенге были оплачены в качестве предоплаты, оставшаяся сумма в размере {format_money(installment_balance_amount)} тенге подлежала оплате в рассрочку в период с {format_date(payload.installment_from) or '—'} года по {format_date(payload.installment_to) or '—'} года равными платежами по {format_money(payload.monthly_payment_amount)} тенге.",
        f"Ответчиком были внесены платежи в размере {format_money(post_advance_payments)} тенге, в связи с чем сумма задолженности на данный момент составила {format_money(debt_amount)} тенге.",
        f"Однако обязательства, принятые на себя, ответчик на сумму в размере {format_money(debt_amount)} тенге не исполнил, что привело к нарушению прав и охраняемых законом интересов {company_name}.",
        "В силу статьи 272 ГК обязательство должно исполняться надлежащим образом в соответствии с условиями обязательства и требованиями законодательства, а при отсутствии таких условий и требований - в соответствии с обычаями делового оборота или иными обычно предъявляемыми требованиями. Согласно статье 277 ГК, если обязательство предусматривает или позволяет определить день его исполнения или период времени, в течение которого оно должно быть исполнено, обязательство подлежит исполнению в этот день или, соответственно, в любой момент в пределах такого периода.",
        "В соответствии с пунктом 1 статьи 353 Гражданского кодекса Республики Казахстан, при неисполнении или ненадлежащем исполнении денежного обязательства должник обязан уплатить кредитору неустойку (пеню) в размере 0,1% от суммы долга за каждый день просрочки.",
        f"На основании вышеуказанного положения закона, произведён расчёт пени по обязательству в размере {format_money(debt_amount)} тенге, {total_overdue_days} календарных дней просрочки, с учётом поэтапного увеличения задолженности следующим образом: {format_money(penalty_amount)} тенге, согласно нижеприведенному расчету:",
    ]
    for paragraph in remaining_paragraphs:
        draw_paragraph(paragraph)

    table_header_height = 76
    row_height = 44
    table_total_height = table_header_height + (len(penalty_rows) * row_height) + row_height + 42
    ensure_space(table_total_height)
    table_x = margin_left
    table_y = current_y + 8
    col_widths = [150, 150, 180, 360, 160, 210]

    def draw_cell(x: int, y: int, width: int, height: int, text: str, *, font: ImageFont.ImageFont, align: str = "center", bold: bool = False) -> None:
        draw.rectangle((x, y, x + width, y + height), outline="#111111", width=1)
        text_font = table_font_bold if bold else font
        lines = _wrap_text(draw, text, text_font, max(width - 10, 20))
        bbox = draw.textbbox((0, 0), "РђРі", font=text_font)
        line_height = (bbox[3] - bbox[1]) + 4
        block_height = len(lines) * line_height
        line_y = y + max((height - block_height) / 2, 4)
        for line in lines:
            line_width = draw.textlength(line, font=text_font)
            if align == "left":
                line_x = x + 6
            elif align == "right":
                line_x = x + width - line_width - 6
            else:
                line_x = x + max((width - line_width) / 2, 4)
            draw.text((line_x, line_y), line, fill="#111111", font=text_font)
            line_y += line_height

    first_header_y = table_y
    second_header_y = table_y + int(table_header_height / 2)
    x = table_x
    draw_cell(x, first_header_y, col_widths[0] + col_widths[1], int(table_header_height / 2), "РџРµСЂРёРѕРґ", font=table_font, bold=True)
    x += col_widths[0] + col_widths[1]
    for label, width in zip(
        [
            "РљРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№ РїСЂРѕСЃСЂРѕС‡РєРё",
            "РЎСѓРјРјР° РЅРµРёСЃРїРѕР»РЅРµРЅРЅРѕРіРѕ РѕР±СЏР·Р°С‚РµР»СЊСЃС‚РІР° (С‚РµРЅРіРµ)",
            "Р Р°Р·РјРµСЂ РїРµРЅРё (РґРµРЅСЊ %)",
            "РЎСѓРјРјР° РїРµРЅРё (С‚РµРЅРіРµ)",
        ],
        col_widths[2:],
    ):
        draw_cell(x, first_header_y, width, table_header_height, label, font=table_font, bold=True)
        x += width
    draw_cell(table_x, second_header_y, col_widths[0], int(table_header_height / 2), "РћС‚", font=table_font, bold=True)
    draw_cell(table_x + col_widths[0], second_header_y, col_widths[1], int(table_header_height / 2), "Р”Рѕ", font=table_font, bold=True)

    current_row_y = table_y + table_header_height
    for row in penalty_rows:
        cell_values = [
            format_date(row["period_from"]) or "—",
            format_date(row["period_to"]) or "—",
            str(row["days"]),
            format_money(row["obligation_amount"]),
            "0,1",
            format_money(row["penalty_amount"]),
        ]
        x = table_x
        for value, width in zip(cell_values, col_widths):
            draw_cell(x, current_row_y, width, row_height, value, font=table_font)
            x += width
        current_row_y += row_height

    summary_width = sum(col_widths[:-1])
    draw_cell(table_x, current_row_y, summary_width, row_height, "РС‚РѕРіРѕ", font=table_font, align="right", bold=True)
    draw_cell(table_x + summary_width, current_row_y, col_widths[-1], row_height, format_money(penalty_amount), font=table_font, bold=True)
    current_y = current_row_y + row_height + 20

    closing_paragraphs = [
        f"Требования {company_name}, адресованные {client_short_name}, о необходимости исполнения обязательства оставлены последним без удовлетворения.",
        f"Совокупность приведенных норм законодательства и изложенных обстоятельств позволяет сделать вывод о том, что с {client_short_name} в пользу {company_name} подлежат взысканию сумма задолженности в размере {format_money(debt_amount)} тенге и пеня в размере {format_money(penalty_amount)} тенге.",
        "В силу статьи 4 Гражданского процессуального кодекса Республики Казахстан (далее – ГПК) задачами гражданского судопроизводства являются защита и восстановление нарушенных или оспариваемых прав, свобод и законных интересов граждан, государства и юридических лиц, соблюдение законности в гражданском обороте, обеспечение полного и своевременного рассмотрения дела, содействие мирному урегулированию спора, предупреждение правонарушений и формирование в обществе уважительного отношения к закону и суду.",
        "На основании изложенного, руководствуясь статьями 148, 149, ГПК РК",
    ]
    for paragraph in closing_paragraphs:
        draw_paragraph(paragraph)

    ensure_space(260)
    current_y = _draw_text_block(
        draw,
        "РџСЂРѕС€Сѓ:",
        x=margin_left,
        y=current_y + 6,
        width=content_width,
        font=section_font,
        line_spacing=12,
        align="left",
        paragraph_spacing=18,
    )

    ask_line = (
        f"1. Взыскать с {client_name} в пользу {company_name} сумму задолженности в размере "
        f"{format_money(debt_amount)} ({money_to_words_ru(debt_amount)}) тенге, пеню в размере "
        f"{format_money(penalty_amount)} ({money_to_words_ru(penalty_amount)}) тенге, государственную пошлину "
        f"в размере {format_money(state_duty_amount)} ({money_to_words_ru(state_duty_amount)}) тенге."
    )
    draw_paragraph(ask_line, first_line_indent=0, spacing_after=18)

    current_y = _draw_text_block(
        draw,
        "РџСЂРёР»РѕР¶РµРЅРёРµ:",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=section_font,
        line_spacing=12,
        align="left",
        paragraph_spacing=10,
    )

    attachments = [
        "1) Квитанция об уплате государственной пошлины;",
        "2) Копия договора купли-продажи с актом приема-передачи;",
        "3) Копия устава;",
        "4) Копия свидетельства (справка о государственной регистрации);",
        "5) Копия досудебной претензии с квитанцией об отправке.",
    ]
    for item in attachments:
        draw_paragraph(item, first_line_indent=0, spacing_after=6)

    signature_y = max(current_y + 24, image_height - margin_bottom - 84)
    director_name = normalize_text(requisites.get("director_name")) or "—"
    left_signature = f"Директор {company_name}"
    draw.text((margin_left, signature_y), left_signature, fill="#111111", font=small_font)
    director_width = draw.textlength(director_name, font=small_font)
    draw.text((image_width - margin_right - director_width, signature_y), director_name, fill="#111111", font=small_font)
    generated_date = format_date(date.today()) or date.today().isoformat()
    draw.text((margin_left, signature_y + 38), generated_date, fill="#111111", font=small_font)

    pages.append(image)

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)
    current_y = margin_top

    uz_court_lines = [line.strip() for line in str(court_name).splitlines() if line.strip()] or [court_name]
    for line in uz_court_lines:
        current_y = _draw_text_block(
            draw,
            line,
            x=header_block_x,
            y=current_y,
            width=header_block_width,
            font=section_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=2,
        )
    current_y += 18

    uz_left_block_lines = [
        company_name,
        normalize_text(requisites.get("address")) or "—",
        f"СТИР: {normalize_text(requisites.get('bin')) or '—'}",
        f"Тел.: {company_phone}",
        f"МФО: {normalize_text(requisites.get('bank_mfo')) or '—'}",
    ]
    uz_right_block_lines = [
        client_name,
        f"ЖШШИР/СТИР: {client_inn}",
        client_address,
        f"Тел.: {client_phones}",
        f"Даъво баҳоси: {format_money(claim_price_amount)} сўм",
    ]
    uz_block_top = current_y
    uz_plaintiff_bottom = draw_block(uz_left_block_lines, header_block_x, uz_block_top, header_block_width, "Даъвогар:")
    uz_defendant_top = uz_plaintiff_bottom + block_gap
    uz_defendant_bottom = draw_block(
        uz_right_block_lines,
        header_block_x,
        uz_defendant_top,
        header_block_width,
        "Жавобгар:",
    )
    current_y = uz_defendant_bottom + 28

    current_y = _draw_text_block(
        draw,
        "Қарздорликни ундириш тўғрисида\nдаъво аризаси",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=title_font,
        line_spacing=10,
        align="center",
        paragraph_spacing=24,
    )

    uz_contract_amount_sentence = (
        f"Шартнома шартларига кўра, жавобгар олинган товар қийматини тўлаш мажбуриятини зиммасига олган. "
        f"Берилган товарнинг қиймати {format_money(contract_total_amount)} сўм этиб белгиланган бўлиб, шундан "
        f"{format_money(advance_amount)} сўм олдиндан тўлов сифатида тўланган, қолган {format_money(installment_balance_amount)} сўм "
        f"шартномада назарда тутилган тўлов жадвалига мувофиқ тўланиши лозим эди."
    )
    if discount_amount > 0:
        uz_contract_amount_sentence = (
            f"Шартнома шартларига кўра, жавобгар олинган товар қийматини тўлаш мажбуриятини зиммасига олган. "
            f"Товар қиймати {format_money(discount_amount)} сўм чегирма ҳисобга олинган ҳолда {format_money(contract_total_amount)} сўм этиб белгиланган бўлиб, "
            f"шундан {format_money(advance_amount)} сўм олдиндан тўлов сифатида тўланган, қолган {format_money(installment_balance_amount)} сўм "
            f"шартномада назарда тутилган тўлов жадвалига мувофиқ тўланиши лозим эди."
        )

    uz_intro_paragraphs = [
        "Ўзбекистон Республикаси Фуқаролик кодексининг 353, 357 ва 364-моддаларига кўра, мажбуриятлар шартномадан келиб чиқади ва тарафлар томонидан шартнома шартларига мувофиқ лозим даражада бажарилиши шарт.",
        f"{company_name} ҳамда {client_short_name} ўртасида {format_date(contract_date) or '—'} санада {contract_number}-сонли олди-сотди шартномаси тузилган бўлиб, унга мувофиқ жавобгар тасарруфига қуйидаги товарлар топширилган:",
    ]
    for paragraph in uz_intro_paragraphs:
        draw_paragraph(paragraph)

    for product in products:
        draw_paragraph(
            normalize_text(product.get("display_name")) or normalize_text(product.get("name")) or "Товар",
            first_line_indent=0,
            spacing_after=6,
        )

    uz_body_paragraphs = [
        "Ўзбекистон Республикаси Фуқаролик кодексининг 386-моддасига кўра, олди-сотди шартномаси бўйича бир тараф товарни бошқа тарафнинг мулки қилиб топшириш, харидор эса товарни қабул қилиш ва унинг учун шартномада белгиланган пул суммасини тўлаш мажбуриятини олади.",
        "Фуқаролик кодексининг 236-моддасига мувофиқ, мажбуриятлар тегишли тарзда, шартнома шартлари ва қонун талабларига мувофиқ бажарилиши лозим.",
        uz_contract_amount_sentence,
        f"Жавобгар томонидан {format_money(advance_amount)} сўм миқдорида тўлов амалга оширилган, шу муносабат билан ҳозирги кундаги қарздорлик суммаси {format_money(debt_amount)} сўмни ташкил қилади.",
        f"Бироқ жавобгар зиммасига олган мажбуриятларни {format_money(debt_amount)} сўм қисмида бажармаган, бу эса {company_name}нинг ҳуқуқ ва қонуний манфаатлари бузилишига олиб келган.",
        "Шартноманинг 2.3-бандига мувофиқ, товарни бўлиб-бўлиб тўлашда навбатдаги тўлов кечиктирилган тақдирда, харидор тўланиши лозим бўлган тўлов суммасидан ҳар бир кечиктирилган кун учун 0,1 фоиз миқдорида пеня тўлайди.",
        f"Мазкур шартларга асосан {total_overdue_days} календарь кун кечиктириш учун пеня ҳисоб-китоби босқичма-босқич ортиб борувчи қарздорлик асосида {format_money(penalty_amount)} сўм миқдорида аниқланди. Ҳисоб-китоб қуйида келтирилган:",
    ]
    for paragraph in uz_body_paragraphs:
        draw_paragraph(paragraph)

    uz_table_header_height = 76
    uz_row_height = 44
    uz_table_total_height = uz_table_header_height + (len(penalty_rows) * uz_row_height) + uz_row_height + 42
    ensure_space(uz_table_total_height)
    uz_table_x = margin_left
    uz_table_y = current_y + 8

    first_header_y = uz_table_y
    second_header_y = uz_table_y + int(uz_table_header_height / 2)
    x = uz_table_x
    draw_cell(x, first_header_y, col_widths[0] + col_widths[1], int(uz_table_header_height / 2), "Давр", font=table_font, bold=True)
    x += col_widths[0] + col_widths[1]
    for label, width in zip(
        [
            "Кечиктирилган кунлар сони",
            "Бажарилмаган мажбурият суммаси (сўм)",
            "Пеня миқдори (кун %)",
            "Пеня суммаси (сўм)",
        ],
        col_widths[2:],
    ):
        draw_cell(x, first_header_y, width, uz_table_header_height, label, font=table_font, bold=True)
        x += width
    draw_cell(uz_table_x, second_header_y, col_widths[0], int(uz_table_header_height / 2), "дан", font=table_font, bold=True)
    draw_cell(uz_table_x + col_widths[0], second_header_y, col_widths[1], int(uz_table_header_height / 2), "гача", font=table_font, bold=True)

    current_row_y = uz_table_y + uz_table_header_height
    for row in penalty_rows:
        cell_values = [
            format_date(row["period_from"]) or "—",
            format_date(row["period_to"]) or "—",
            str(row["days"]),
            format_money(row["obligation_amount"]),
            str(row["penalty_rate_percent"]).replace(".", ","),
            format_money(row["penalty_amount"]),
        ]
        x = uz_table_x
        for value, width in zip(cell_values, col_widths):
            draw_cell(x, current_row_y, width, uz_row_height, value, font=table_font)
            x += width
        current_row_y += uz_row_height

    uz_summary_width = sum(col_widths[:-1])
    draw_cell(uz_table_x, current_row_y, uz_summary_width, uz_row_height, "Жами", font=table_font, align="right", bold=True)
    draw_cell(uz_table_x + uz_summary_width, current_row_y, col_widths[-1], uz_row_height, format_money(penalty_amount), font=table_font, bold=True)
    current_y = current_row_y + uz_row_height + 20

    uz_closing_paragraphs = [
        f"{company_name}нинг {client_short_name}га нисбатан мажбуриятни бажариш ҳақидаги талаблари жавобгар томонидан қаноатлантирилмасдан қолдирилган.",
        f"Юқорида келтирилган қонун нормалари ва иш ҳолатларидан келиб чиқиб, {client_short_name}дан {company_name} фойдасига {format_money(debt_amount)} сўм қарздорлик ҳамда {format_money(penalty_amount)} сўм пеня ундирилиши лозим, деган хулосага келиш мумкин.",
        f"Даъво баҳоси {format_money(claim_price_amount)} сўмни ташкил қилади. Мазкур даъво бўйича давлат божи даъво баҳосининг 4 фоизи, бироқ камида 1 БРВ миқдорида бўлади ва ушбу ҳолатда {format_money(state_duty_amount)} сўмга тенг.",
        "Ўзбекистон Республикаси Фуқаролик процессуал кодексининг 4-моддасига кўра, фуқаролик суд ишларини юритишнинг вазифаси фуқаролар ва юридик шахсларнинг бузилган ҳуқуқ ҳамда қонуний манфаатларини ҳимоя қилишдан иборат.",
        "Юқоридагиларга асосан, Ўзбекистон Республикаси Фуқаролик процессуал кодексининг 4, 193 ва 257-моддаларига таяниб,",
    ]
    for paragraph in uz_closing_paragraphs:
        draw_paragraph(paragraph)

    current_y = _draw_text_block(
        draw,
        "Сўрайман:",
        x=margin_left,
        y=current_y + 6,
        width=content_width,
        font=section_font,
        line_spacing=10,
        align="left",
        paragraph_spacing=18,
    )

    uz_ask_line = (
        f"1. {client_name}дан {company_name} фойдасига {format_money(debt_amount)} сўм қарздорлик, "
        f"{format_money(penalty_amount)} сўм пеня ва {format_money(state_duty_amount)} сўм давлат божи ундирилсин."
    )
    draw_paragraph(uz_ask_line, first_line_indent=0, spacing_after=18)

    current_y = _draw_text_block(
        draw,
        "Иловалар:",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=section_font,
        line_spacing=10,
        align="left",
        paragraph_spacing=10,
    )

    uz_attachments = [
        "1) Давлат божи тўланганлиги ҳақидаги квитанция;",
        "2) Қабул қилиш-топшириш ҳужжати билан олди-сотди шартномаси нусхаси;",
        "3) Устав нусхаси;",
        "4) Давлат рўйхатидан ўтганлик тўғрисидаги ҳужжат нусхаси;",
        "5) Жўнатилганлиги ҳақидаги квитанция билан судгача бўлган претензия нусхаси.",
    ]
    for item in uz_attachments:
        draw_paragraph(item, first_line_indent=0, spacing_after=6)

    uz_signature_y = max(current_y + 24, image_height - margin_bottom - 84)
    draw.text((margin_left, uz_signature_y), f"Раҳбар {company_name}", fill="#111111", font=small_font)
    director_width = draw.textlength(director_name, font=small_font)
    draw.text((image_width - margin_right - director_width, uz_signature_y), director_name, fill="#111111", font=small_font)
    draw.text((margin_left, uz_signature_y + 34), generated_date, fill="#111111", font=small_font)

    pages.append(image)
    try:
        first_page, *other_pages = pages
        first_page.save(pdf_path, "PDF", resolution=150.0, save_all=True, append_images=other_pages)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF иска.") from exc

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF иска.")

    return pdf_path

def _render_lawsuit_pdf_uz(
    debtor: dict[str, Any],
    payload: LawsuitPdfGenerateRequest,
    *,
    compute_financials_fn,
    compute_lawsuit_state_duty_fn,
    generated_dir: Path,
) -> Path:
    company_name_value = sanitize_company_name(str(debtor.get("company") or ""))
    requisites = find_company_requisites(company_name_value, str(debtor.get("country") or DEFAULT_COUNTRY))
    if requisites is None:
        raise HTTPException(
            status_code=400,
            detail=f"Для компании «{company_name_value or '—'}» не найдены реквизиты.",
        )

    claim_sent_date_raw = debtor.get("claim_sent_date")
    if not claim_sent_date_raw:
        raise HTTPException(status_code=400, detail="Для генерации иска сначала заполните дату отправки претензии.")
    try:
        claim_sent_date = date.fromisoformat(str(claim_sent_date_raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Дата отправки претензии заполнена некорректно.") from exc

    try:
        crm_context = DiSellApiClient().lookup_lawsuit_context(
            str(debtor.get("contract_number") or ""),
            country="uz",
        )
    except DiSellApiError:
        crm_context = {}

    company_name = requisites.get("company_name") or company_name_value or "—"
    company_phone = normalize_text(requisites.get("phone")) or "—"
    court_name = normalize_text(payload.court_name) or normalize_text(debtor.get("court")) or "—"
    client_name = normalize_text(crm_context.get("client_name")) or normalize_text(debtor.get("client_name")) or "—"
    client_short_name = normalize_text(crm_context.get("client_short_name")) or build_short_client_name(client_name)
    client_inn = normalize_text(crm_context.get("client_inn")) or "—"
    client_address = normalize_text(crm_context.get("client_address")) or normalize_text(debtor.get("address")) or "—"

    crm_phones = crm_context.get("client_phones") or []
    normalized_phones = [normalize_text(phone) for phone in crm_phones if normalize_text(phone)]
    if not normalized_phones:
        normalized_phones = [
            phone
            for phone in [normalize_text(debtor.get("mobile_phone")), normalize_text(debtor.get("home_phone"))]
            if phone
        ]
    client_phones = ", ".join(dict.fromkeys(normalized_phones)) if normalized_phones else "—"

    contract_number = str(crm_context.get("contract_number") or debtor.get("contract_number") or "—")
    contract_date = contract_date_value_from_number(contract_number)
    crm_contract_date = crm_context.get("contract_date")
    if isinstance(crm_contract_date, str) and crm_contract_date:
        try:
            contract_date = date.fromisoformat(crm_contract_date)
        except ValueError:
            pass

    contract_total_amount = parse_float(
        crm_context.get("contract_total_amount")
        if crm_context.get("contract_total_amount") is not None
        else debtor.get("contract_total_amount")
    )
    debt_amount = parse_float(
        crm_context.get("debt_amount")
        if crm_context.get("debt_amount") is not None
        else payload.debt_amount
    )
    advance_amount = parse_float(
        crm_context.get("advance_amount")
        if crm_context.get("advance_amount") is not None
        else debtor.get("contract_advance_amount")
    )
    if advance_amount <= 0 and contract_total_amount > 0:
        advance_amount = max(round(contract_total_amount - debt_amount, 2), 0.0)

    discount_amount = parse_float(crm_context.get("discount_amount"))
    installment_balance_amount = max(round(contract_total_amount - advance_amount, 2), 0.0)
    products = normalize_document_products(
        [item.model_dump() for item in (payload.product_overrides or [])] or crm_context.get("products"),
        fallback_name="Товар по договору",
    )

    penalty_rows, penalty_amount, total_overdue_days = build_lawsuit_penalty_rows(
        payload.installment_from,
        payload.installment_to,
        claim_sent_date,
        float(payload.monthly_payment_amount),
        float(payload.first_period_paid_amount or 0),
    )
    claim_price_amount = compute_lawsuit_claim_price(debt_amount, penalty_amount)
    state_duty_amount = compute_lawsuit_state_duty_fn("uz", debt_amount, penalty_amount)

    generated_dir.mkdir(parents=True, exist_ok=True)
    safe_contract = re.sub(r"[^A-Za-z0-9_-]+", "_", str(debtor.get("contract_number") or debtor.get("id")))
    pdf_path = generated_dir / f"lawsuit_uz_{safe_contract}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    image_width = 1654
    image_height = 2339
    margin_left = 112
    margin_right = 112
    margin_top = 72
    margin_bottom = 82
    content_width = image_width - margin_left - margin_right
    block_gap = 20
    header_block_width = min(620, content_width)
    header_block_x = image_width - margin_right - header_block_width
    paragraph_indent = 42

    regular_font = _load_font(24)
    title_font = _load_font(31, bold=True)
    section_font = _load_font(24, bold=True)
    small_font = _load_font(21)
    table_font = _load_font(19)
    table_font_bold = _load_font(19, bold=True)

    pages: list[Image.Image] = []
    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)
    current_y = margin_top

    def new_page() -> None:
        nonlocal image, draw, current_y
        pages.append(image)
        image = Image.new("RGB", (image_width, image_height), "white")
        draw = ImageDraw.Draw(image)
        current_y = margin_top

    def estimate_block_height(text: str, font: ImageFont.ImageFont, width: int, line_spacing: int, first_line_indent: int = 0) -> int:
        normalized = " ".join((text or "").split())
        if not normalized:
            return 0
        bbox = draw.textbbox((0, 0), "Аг", font=font)
        line_height = (bbox[3] - bbox[1]) + line_spacing
        if first_line_indent > 0:
            words = normalized.split(" ")
            first_line_words: list[str] = []
            while words:
                candidate_words = first_line_words + [words[0]]
                candidate = " ".join(candidate_words).strip()
                if draw.textlength(candidate, font=font) <= max(40, width - first_line_indent):
                    first_line_words.append(words.pop(0))
                else:
                    break
            remaining = " ".join(words).strip()
            lines = 1 if first_line_words else 0
            if remaining:
                lines += len(_wrap_text(draw, remaining, font, width))
            return max(lines, 1) * line_height
        return max(len(_wrap_text(draw, normalized, font, width)), 1) * line_height

    def ensure_space(required_height: int) -> None:
        nonlocal current_y
        if current_y + required_height > image_height - margin_bottom:
            new_page()

    def draw_paragraph(
        text: str,
        *,
        font: ImageFont.ImageFont = regular_font,
        align: str = "left",
        spacing_after: int = 12,
        first_line_indent: int = paragraph_indent,
        width: int = content_width,
        x: int = margin_left,
    ) -> None:
        nonlocal current_y
        estimate = estimate_block_height(text, font, width, 12, first_line_indent) + spacing_after
        ensure_space(estimate)
        current_y = _draw_text_block(
            draw,
            text,
            x=x,
            y=current_y,
            width=width,
            font=font,
            line_spacing=12,
            align=align,
            paragraph_spacing=spacing_after,
            first_line_indent=first_line_indent if align == "left" else 0,
        )

    def draw_block(lines: list[str], x: int, y: int, width: int, title: str) -> int:
        block_y = _draw_text_block(
            draw,
            title,
            x=x,
            y=y,
            width=width,
            font=section_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=6,
        )
        for line in lines:
            block_y = _draw_text_block(
                draw,
                line,
                x=x,
                y=block_y,
                width=width,
                font=regular_font,
                line_spacing=8,
                align="left",
                paragraph_spacing=2,
            )
        return block_y

    court_lines = [line.strip() for line in str(court_name).splitlines() if line.strip()] or [court_name]
    for line in court_lines:
        current_y = _draw_text_block(
            draw,
            line,
            x=header_block_x,
            y=current_y,
            width=header_block_width,
            font=section_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=2,
        )
    current_y += 18

    left_block_lines = [
        company_name,
        normalize_text(requisites.get("address")) or "—",
        f"ИНН: {normalize_text(requisites.get('bin')) or '—'}",
        "Тел.:",
        f"МФО: {normalize_text(requisites.get('bank_mfo')) or '—'}",
    ]
    right_block_lines = [
        client_name,
        f"ИНН: {client_inn}",
        client_address,
        f"Тел.: {client_phones}",
        f"Цена иска: {format_money(claim_price_amount)} сум",
    ]
    block_top = current_y
    plaintiff_bottom = draw_block(left_block_lines, header_block_x, block_top, header_block_width, "Истец:")
    defendant_top = plaintiff_bottom + block_gap
    defendant_bottom = draw_block(
        right_block_lines,
        header_block_x,
        defendant_top,
        header_block_width,
        "Ответчик:",
    )
    current_y = defendant_bottom + 28

    current_y = _draw_text_block(
        draw,
        "Иск\nо взыскании задолженности",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=title_font,
        line_spacing=10,
        align="center",
        paragraph_spacing=24,
    )

    contract_amount_sentence = (
        f"Согласно условиям заключенного договора определено, что ответчик принял на себя обязательства по оплате стоимости полученного товара. "
        f"Стоимость переданного товара была определена в размере {format_money(contract_total_amount)} сум, из которых "
        f"{format_money(advance_amount)} сум были оплачены в качестве предоплаты, оставшаяся сумма в размере "
        f"{format_money(installment_balance_amount)} сум подлежала оплате в соответствии с графиком платежей, предусмотренным договором."
    )
    if discount_amount > 0:
        contract_amount_sentence = (
            f"Согласно условиям заключенного договора определено, что ответчик принял на себя обязательства по оплате стоимости полученного товара. "
            f"Стоимость переданного товара с учетом скидки {format_money(discount_amount)} сум была определена в размере "
            f"{format_money(contract_total_amount)} сум, из которых {format_money(advance_amount)} сум были оплачены в качестве предоплаты, "
            f"оставшаяся сумма в размере {format_money(installment_balance_amount)} сум подлежала оплате в соответствии с графиком платежей, предусмотренным договором."
        )

    intro_paragraphs = [
        "В соответствии со статьями 353, 357 и 364 Гражданского кодекса Республики Узбекистан обязательства возникают из договора и подлежат обязательному исполнению сторонами в соответствии с его условиями.",
        f"Между {company_name} и {client_short_name} заключен договор купли-продажи № {contract_number} от {format_date(contract_date) or '—'}, в соответствии с которым в собственность ответчика был передан товар, а именно:",
    ]
    for paragraph in intro_paragraphs:
        draw_paragraph(paragraph)

    for product in products:
        draw_paragraph(
            normalize_text(product.get('display_name')) or normalize_text(product.get("name")) or "Товар",
            first_line_indent=0,
            spacing_after=6,
        )

    body_paragraphs = [
        "Статьей 386 Гражданского кодекса Республики Узбекистан предусмотрено, что по договору купли-продажи одна сторона обязуется передать товар в собственность другой стороне, а покупатель — принять товар и уплатить за него установленную договором денежную сумму.",
        "В силу статьи 236 Гражданского кодекса Республики Узбекистан обязательства должны исполняться надлежащим образом в соответствии с условиями обязательства и требованиями законодательства.",
        contract_amount_sentence,
        f"Ответчиком были внесены платежи в размере {format_money(advance_amount)} сум, в связи с чем сумма задолженности на текущий момент составляет {format_money(debt_amount)} сум.",
        f"Однако обязательства, принятые на себя, ответчик на сумму в размере {format_money(debt_amount)} сум не исполнил, что привело к нарушению прав и охраняемых законом интересов {company_name}.",
        "Пунктом 2.3 заключенного договора определено, что в случае просрочки очередного платежа при оплате товара в рассрочку покупатель уплачивает продавцу пеню в размере 0,1 % за каждый день просрочки от суммы платежа, подлежащего уплате.",
        f"На основании указанных условий произведен расчет пени по обязательству в размере {format_money(debt_amount)} сум, {total_overdue_days} календарных дней просрочки, с учетом поэтапного увеличения задолженности следующим образом: {format_money(penalty_amount)} сум, согласно нижеприведенному расчету:",
    ]
    for paragraph in body_paragraphs:
        draw_paragraph(paragraph)

    table_header_height = 76
    row_height = 44
    table_total_height = table_header_height + (len(penalty_rows) * row_height) + row_height + 42
    ensure_space(table_total_height)
    table_x = margin_left
    table_y = current_y + 8
    col_widths = [150, 150, 180, 360, 160, 210]

    def draw_cell(x: int, y: int, width: int, height: int, text: str, *, font: ImageFont.ImageFont, align: str = "center", bold: bool = False) -> None:
        draw.rectangle((x, y, x + width, y + height), outline="#111111", width=1)
        text_font = table_font_bold if bold else font
        lines = _wrap_text(draw, text, text_font, max(width - 10, 20))
        bbox = draw.textbbox((0, 0), "Аг", font=text_font)
        line_height = (bbox[3] - bbox[1]) + 4
        total_height = max(len(lines), 1) * line_height
        text_y = y + max((height - total_height) / 2, 4)
        for line in lines or [""]:
            line_width = draw.textlength(line, font=text_font)
            if align == "right":
                text_x = x + width - line_width - 6
            elif align == "left":
                text_x = x + 6
            else:
                text_x = x + max((width - line_width) / 2, 4)
            draw.text((text_x, text_y), line, fill="#111111", font=text_font)
            text_y += line_height

    first_header_y = table_y
    second_header_y = table_y + int(table_header_height / 2)
    x = table_x
    draw_cell(x, first_header_y, col_widths[0] + col_widths[1], int(table_header_height / 2), "Период", font=table_font, bold=True)
    x += col_widths[0] + col_widths[1]
    for label, width in zip(
        [
            "Количество дней просрочки",
            "Сумма неисполненного обязательства (сум)",
            "Размер пени (день %)",
            "Сумма пени (сум)",
        ],
        col_widths[2:],
    ):
        draw_cell(x, first_header_y, width, table_header_height, label, font=table_font, bold=True)
        x += width
    draw_cell(table_x, second_header_y, col_widths[0], int(table_header_height / 2), "От", font=table_font, bold=True)
    draw_cell(table_x + col_widths[0], second_header_y, col_widths[1], int(table_header_height / 2), "До", font=table_font, bold=True)

    current_row_y = table_y + table_header_height
    for row in penalty_rows:
        cell_values = [
            format_date(row["period_from"]) or "—",
            format_date(row["period_to"]) or "—",
            str(row["days"]),
            format_money(row["obligation_amount"]),
            str(row["penalty_rate_percent"]).replace(".", ","),
            format_money(row["penalty_amount"]),
        ]
        x = table_x
        for value, width in zip(cell_values, col_widths):
            draw_cell(x, current_row_y, width, row_height, value, font=table_font)
            x += width
        current_row_y += row_height

    summary_width = sum(col_widths[:-1])
    draw_cell(table_x, current_row_y, summary_width, row_height, "Итого", font=table_font, align="right", bold=True)
    draw_cell(table_x + summary_width, current_row_y, col_widths[-1], row_height, format_money(penalty_amount), font=table_font, bold=True)
    current_y = current_row_y + row_height + 20

    closing_paragraphs = [
        f"Требования {company_name}, адресованные {client_short_name}, о необходимости исполнения обязательства оставлены последним без удовлетворения.",
        f"Совокупность приведенных норм законодательства и изложенных обстоятельств позволяет сделать вывод о том, что с {client_short_name} в пользу {company_name} подлежат взысканию сумма задолженности в размере {format_money(debt_amount)} сум и пеня в размере {format_money(penalty_amount)} сум.",
        f"Цена иска составляет {format_money(claim_price_amount)} сум. Государственная пошлина по настоящему иску составляет 4 процента от цены иска, но не менее 1 БРВ, и в данном случае равна {format_money(state_duty_amount)} сум.",
        "В силу статьи 4 Гражданского процессуального кодекса Республики Узбекистан задачами гражданского судопроизводства являются защита и восстановление нарушенных прав и законных интересов граждан и юридических лиц, обеспечение законности и своевременного рассмотрения дела.",
        "На основании изложенного, руководствуясь статьями 4, 193, 257 Гражданского процессуального кодекса Республики Узбекистан,",
    ]
    for paragraph in closing_paragraphs:
        draw_paragraph(paragraph)

    current_y = _draw_text_block(
        draw,
        "Прошу:",
        x=margin_left,
        y=current_y + 6,
        width=content_width,
        font=section_font,
        line_spacing=10,
        align="left",
        paragraph_spacing=18,
    )

    ask_line = (
        f"1. Взыскать с {client_name} в пользу {company_name} сумму задолженности в размере "
        f"{format_money(debt_amount)} ({money_to_words_sum_ru(debt_amount)}) сум, пеню в размере "
        f"{format_money(penalty_amount)} ({money_to_words_sum_ru(penalty_amount)}) сум, государственную пошлину "
        f"в размере {format_money(state_duty_amount)} ({money_to_words_sum_ru(state_duty_amount)}) сум."
    )
    draw_paragraph(ask_line, first_line_indent=0, spacing_after=18)

    current_y = _draw_text_block(
        draw,
        "Приложения:",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=section_font,
        line_spacing=10,
        align="left",
        paragraph_spacing=10,
    )

    attachments = [
        "1) Квитанция об уплате государственной пошлины;",
        "2) Копия договора купли-продажи с актом приема-передачи;",
        "3) Копия устава;",
        "4) Копия свидетельства (справка о государственной регистрации);",
        "5) Копия досудебной претензии с квитанцией об отправке.",
    ]
    for item in attachments:
        draw_paragraph(item, first_line_indent=0, spacing_after=6)

    signature_y = max(current_y + 24, image_height - margin_bottom - 84)
    director_name = normalize_text(requisites.get("director_name")) or "—"
    left_signature = f"Директор {company_name}"
    draw.text((margin_left, signature_y), left_signature, fill="#111111", font=small_font)
    director_width = draw.textlength(director_name, font=small_font)
    draw.text((image_width - margin_right - director_width, signature_y), director_name, fill="#111111", font=small_font)
    generated_date = format_date(date.today()) or date.today().isoformat()
    draw.text((margin_left, signature_y + 34), generated_date, fill="#111111", font=small_font)

    pages.append(image)

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)
    current_y = margin_top

    uz_court_lines = [line.strip() for line in str(court_name).splitlines() if line.strip()] or [court_name]
    for line in uz_court_lines:
        current_y = _draw_text_block(
            draw,
            line,
            x=header_block_x,
            y=current_y,
            width=header_block_width,
            font=section_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=2,
        )
    current_y += 18

    uz_left_block_lines = [
        company_name,
        normalize_text(requisites.get("address")) or "—",
        f"СТИР: {normalize_text(requisites.get('bin')) or '—'}",
        f"Тел.: {company_phone}",
        f"МФО: {normalize_text(requisites.get('bank_mfo')) or '—'}",
    ]
    uz_right_block_lines = [
        client_name,
        f"ЖШШИР/СТИР: {client_inn}",
        client_address,
        f"Тел.: {client_phones}",
        f"Даъво баҳоси: {format_money(claim_price_amount)} сўм",
    ]
    uz_block_top = current_y
    uz_plaintiff_bottom = draw_block(uz_left_block_lines, header_block_x, uz_block_top, header_block_width, "Даъвогар:")
    uz_defendant_top = uz_plaintiff_bottom + block_gap
    uz_defendant_bottom = draw_block(
        uz_right_block_lines,
        header_block_x,
        uz_defendant_top,
        header_block_width,
        "Жавобгар:",
    )
    current_y = uz_defendant_bottom + 28

    current_y = _draw_text_block(
        draw,
        "Қарздорликни ундириш тўғрисида\nдаъво аризаси",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=title_font,
        line_spacing=10,
        align="center",
        paragraph_spacing=24,
    )

    uz_contract_amount_sentence = (
        f"Шартнома шартларига кўра, жавобгар олинган товар қийматини тўлаш мажбуриятини зиммасига олган. "
        f"Берилган товарнинг қиймати {format_money(contract_total_amount)} сўм этиб белгиланган бўлиб, шундан "
        f"{format_money(advance_amount)} сўм олдиндан тўлов сифатида тўланган, қолган {format_money(installment_balance_amount)} сўм "
        f"шартномада назарда тутилган тўлов жадвалига мувофиқ тўланиши лозим эди."
    )
    if discount_amount > 0:
        uz_contract_amount_sentence = (
            f"Шартнома шартларига кўра, жавобгар олинган товар қийматини тўлаш мажбуриятини зиммасига олган. "
            f"Товар қиймати {format_money(discount_amount)} сўм чегирма ҳисобга олинган ҳолда {format_money(contract_total_amount)} сўм этиб белгиланган бўлиб, "
            f"шундан {format_money(advance_amount)} сўм олдиндан тўлов сифатида тўланган, қолган {format_money(installment_balance_amount)} сўм "
            f"шартномада назарда тутилган тўлов жадвалига мувофиқ тўланиши лозим эди."
        )

    uz_intro_paragraphs = [
        "Ўзбекистон Республикаси Фуқаролик кодексининг 353, 357 ва 364-моддаларига кўра, мажбуриятлар шартномадан келиб чиқади ва тарафлар томонидан шартнома шартларига мувофиқ лозим даражада бажарилиши шарт.",
        f"{company_name} ҳамда {client_short_name} ўртасида {format_date(contract_date) or '—'} санада {contract_number}-сонли олди-сотди шартномаси тузилган бўлиб, унга мувофиқ жавобгар тасарруфига қуйидаги товарлар топширилган:",
    ]
    for paragraph in uz_intro_paragraphs:
        draw_paragraph(paragraph)

    for product in products:
        draw_paragraph(
            normalize_text(product.get("display_name")) or normalize_text(product.get("name")) or "Товар",
            first_line_indent=0,
            spacing_after=6,
        )

    uz_body_paragraphs = [
        "Ўзбекистон Республикаси Фуқаролик кодексининг 386-моддасига кўра, олди-сотди шартномаси бўйича бир тараф товарни бошқа тарафнинг мулки қилиб топшириш, харидор эса товарни қабул қилиш ва унинг учун шартномада белгиланган пул суммасини тўлаш мажбуриятини олади.",
        "Фуқаролик кодексининг 236-моддасига мувофиқ, мажбуриятлар тегишли тарзда, шартнома шартлари ва қонун талабларига мувофиқ бажарилиши лозим.",
        uz_contract_amount_sentence,
        f"Жавобгар томонидан {format_money(advance_amount)} сўм миқдорида тўлов амалга оширилган, шу муносабат билан ҳозирги кундаги қарздорлик суммаси {format_money(debt_amount)} сўмни ташкил қилади.",
        f"Бироқ жавобгар зиммасига олган мажбуриятларни {format_money(debt_amount)} сўм қисмида бажармаган, бу эса {company_name}нинг ҳуқуқ ва қонуний манфаатлари бузилишига олиб келган.",
        "Шартноманинг 2.3-бандига мувофиқ, товарни бўлиб-бўлиб тўлашда навбатдаги тўлов кечиктирилган тақдирда, харидор тўланиши лозим бўлган тўлов суммасидан ҳар бир кечиктирилган кун учун 0,1 фоиз миқдорида пеня тўлайди.",
        f"Мазкур шартларга асосан {total_overdue_days} календарь кун кечиктириш учун пеня ҳисоб-китоби босқичма-босқич ортиб борувчи қарздорлик асосида {format_money(penalty_amount)} сўм миқдорида аниқланди. Ҳисоб-китоб қуйида келтирилган:",
    ]
    for paragraph in uz_body_paragraphs:
        draw_paragraph(paragraph)

    uz_table_header_height = 76
    uz_row_height = 44
    uz_table_total_height = uz_table_header_height + (len(penalty_rows) * uz_row_height) + uz_row_height + 42
    ensure_space(uz_table_total_height)
    uz_table_x = margin_left
    uz_table_y = current_y + 8

    first_header_y = uz_table_y
    second_header_y = uz_table_y + int(uz_table_header_height / 2)
    x = uz_table_x
    draw_cell(x, first_header_y, col_widths[0] + col_widths[1], int(uz_table_header_height / 2), "Давр", font=table_font, bold=True)
    x += col_widths[0] + col_widths[1]
    for label, width in zip(
        [
            "Кечиктирилган кунлар сони",
            "Бажарилмаган мажбурият суммаси (сўм)",
            "Пеня миқдори (кун %)",
            "Пеня суммаси (сўм)",
        ],
        col_widths[2:],
    ):
        draw_cell(x, first_header_y, width, uz_table_header_height, label, font=table_font, bold=True)
        x += width
    draw_cell(uz_table_x, second_header_y, col_widths[0], int(uz_table_header_height / 2), "дан", font=table_font, bold=True)
    draw_cell(uz_table_x + col_widths[0], second_header_y, col_widths[1], int(uz_table_header_height / 2), "гача", font=table_font, bold=True)

    current_row_y = uz_table_y + uz_table_header_height
    for row in penalty_rows:
        cell_values = [
            format_date(row["period_from"]) or "—",
            format_date(row["period_to"]) or "—",
            str(row["days"]),
            format_money(row["obligation_amount"]),
            str(row["penalty_rate_percent"]).replace(".", ","),
            format_money(row["penalty_amount"]),
        ]
        x = uz_table_x
        for value, width in zip(cell_values, col_widths):
            draw_cell(x, current_row_y, width, uz_row_height, value, font=table_font)
            x += width
        current_row_y += uz_row_height

    uz_summary_width = sum(col_widths[:-1])
    draw_cell(uz_table_x, current_row_y, uz_summary_width, uz_row_height, "Жами", font=table_font, align="right", bold=True)
    draw_cell(uz_table_x + uz_summary_width, current_row_y, col_widths[-1], uz_row_height, format_money(penalty_amount), font=table_font, bold=True)
    current_y = current_row_y + uz_row_height + 20

    uz_closing_paragraphs = [
        f"{company_name}нинг {client_short_name}га нисбатан мажбуриятни бажариш ҳақидаги талаблари жавобгар томонидан қаноатлантирилмасдан қолдирилган.",
        f"Юқорида келтирилган қонун нормалари ва иш ҳолатларидан келиб чиқиб, {client_short_name}дан {company_name} фойдасига {format_money(debt_amount)} сўм қарздорлик ҳамда {format_money(penalty_amount)} сўм пеня ундирилиши лозим, деган хулосага келиш мумкин.",
        f"Даъво баҳоси {format_money(claim_price_amount)} сўмни ташкил қилади. Мазкур даъво бўйича давлат божи даъво баҳосининг 4 фоизи, бироқ камида 1 БРВ миқдорида бўлади ва ушбу ҳолатда {format_money(state_duty_amount)} сўмга тенг.",
        "Ўзбекистон Республикаси Фуқаролик процессуал кодексининг 4-моддасига кўра, фуқаролик суд ишларини юритишнинг вазифаси фуқаролар ва юридик шахсларнинг бузилган ҳуқуқ ҳамда қонуний манфаатларини ҳимоя қилишдан иборат.",
        "Юқоридагиларга асосан, Ўзбекистон Республикаси Фуқаролик процессуал кодексининг 4, 193 ва 257-моддаларига таяниб,",
    ]
    for paragraph in uz_closing_paragraphs:
        draw_paragraph(paragraph)

    current_y = _draw_text_block(
        draw,
        "Сўрайман:",
        x=margin_left,
        y=current_y + 6,
        width=content_width,
        font=section_font,
        line_spacing=10,
        align="left",
        paragraph_spacing=18,
    )

    uz_ask_line = (
        f"1. {client_name}дан {company_name} фойдасига {format_money(debt_amount)} сўм қарздорлик, "
        f"{format_money(penalty_amount)} сўм пеня ва {format_money(state_duty_amount)} сўм давлат божи ундирилсин."
    )
    draw_paragraph(uz_ask_line, first_line_indent=0, spacing_after=18)

    current_y = _draw_text_block(
        draw,
        "Иловалар:",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=section_font,
        line_spacing=10,
        align="left",
        paragraph_spacing=10,
    )

    uz_attachments = [
        "1) Давлат божи тўланганлиги ҳақидаги квитанция;",
        "2) Қабул қилиш-топшириш ҳужжати билан олди-сотди шартномаси нусхаси;",
        "3) Устав нусхаси;",
        "4) Давлат рўйхатидан ўтганлик тўғрисидаги ҳужжат нусхаси;",
        "5) Жўнатилганлиги ҳақидаги квитанция билан досудеб претензия нусхаси.",
    ]
    for item in uz_attachments:
        draw_paragraph(item, first_line_indent=0, spacing_after=6)

    uz_signature_y = max(current_y + 24, image_height - margin_bottom - 84)
    draw.text((margin_left, uz_signature_y), f"Директор {company_name}", fill="#111111", font=small_font)
    director_width = draw.textlength(director_name, font=small_font)
    draw.text((image_width - margin_right - director_width, uz_signature_y), director_name, fill="#111111", font=small_font)
    draw.text((margin_left, uz_signature_y + 34), generated_date, fill="#111111", font=small_font)

    pages.append(image)
    try:
        first_page, *other_pages = pages
        first_page.save(pdf_path, "PDF", resolution=150.0, save_all=True, append_images=other_pages)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF иска.") from exc

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF иска.")

    return pdf_path


def render_lawsuit_pdf(
    debtor: dict[str, Any],
    payload: LawsuitPdfGenerateRequest,
    *,
    compute_financials_fn,
    compute_lawsuit_state_duty_fn,
    generated_dir: Path,
) -> Path:
    country_code = normalize_country_code(str(debtor.get("country") or DEFAULT_COUNTRY))
    if country_code == "uz":
        return _render_lawsuit_pdf_uz(
            debtor,
            payload,
            compute_financials_fn=compute_financials_fn,
            compute_lawsuit_state_duty_fn=compute_lawsuit_state_duty_fn,
            generated_dir=generated_dir,
        )

    company_name_value = sanitize_company_name(str(debtor.get("company") or ""))
    requisites = find_company_requisites(company_name_value, str(debtor.get("country") or DEFAULT_COUNTRY))
    if requisites is None:
        raise HTTPException(
            status_code=400,
            detail=f"Для компании «{company_name_value or '—'}» не найдены реквизиты.",
        )

    claim_sent_date_raw = debtor.get("claim_sent_date")
    if not claim_sent_date_raw:
        raise HTTPException(status_code=400, detail="Для генерации иска сначала заполните дату отправки претензии.")
    try:
        claim_sent_date = date.fromisoformat(str(claim_sent_date_raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Дата отправки претензии заполнена некорректно.") from exc

    try:
        crm_context = DiSellApiClient().lookup_lawsuit_context(
            str(debtor.get("contract_number") or ""),
            country=str(debtor.get("country") or DEFAULT_COUNTRY),
        )
    except DiSellApiError:
        crm_context = {}

    company_name = requisites.get("company_name") or company_name_value or "—"
    court_name = normalize_text(payload.court_name) or normalize_text(debtor.get("court")) or "—"
    client_name = normalize_text(crm_context.get("client_name")) or normalize_text(debtor.get("client_name")) or "—"
    client_short_name = normalize_text(crm_context.get("client_short_name")) or build_short_client_name(client_name)
    client_inn = normalize_text(crm_context.get("client_inn")) or "—"
    client_address = normalize_text(crm_context.get("client_address")) or normalize_text(debtor.get("address")) or "—"

    crm_phones = crm_context.get("client_phones") or []
    normalized_phones = [normalize_text(phone) for phone in crm_phones if normalize_text(phone)]
    if not normalized_phones:
        normalized_phones = [
            phone
            for phone in [normalize_text(debtor.get("mobile_phone")), normalize_text(debtor.get("home_phone"))]
            if phone
        ]
    client_phones = ", ".join(dict.fromkeys(normalized_phones)) if normalized_phones else "—"

    contract_number = str(crm_context.get("contract_number") or debtor.get("contract_number") or "—")
    contract_date = contract_date_value_from_number(contract_number)
    crm_contract_date = crm_context.get("contract_date")
    if isinstance(crm_contract_date, str) and crm_contract_date:
        try:
            contract_date = date.fromisoformat(crm_contract_date)
        except ValueError:
            pass

    contract_total_amount = parse_float(
        crm_context.get("contract_total_amount")
        if crm_context.get("contract_total_amount") is not None
        else debtor.get("contract_total_amount")
    )
    debt_amount = round(float(payload.debt_amount), 2)
    advance_amount = parse_float(
        crm_context.get("advance_amount")
        if crm_context.get("advance_amount") is not None
        else debtor.get("contract_advance_amount")
    )
    if advance_amount <= 0 and contract_total_amount > 0:
        advance_amount = max(round(contract_total_amount - debt_amount, 2), 0.0)

    discount_amount = parse_float(crm_context.get("discount_amount"))
    installment_balance_amount = max(round(contract_total_amount - advance_amount, 2), 0.0)
    total_payments_amount = parse_float(crm_context.get("advance_amount"))
    post_advance_payments = max(round(total_payments_amount - advance_amount, 2), 0.0)

    products = normalize_document_products(
        [item.model_dump() for item in (payload.product_overrides or [])] or crm_context.get("products"),
        fallback_name="Товар по договору",
    )

    penalty_rows, adjusted_penalty_amount, total_overdue_days = build_lawsuit_penalty_rows(
        payload.installment_from,
        payload.installment_to,
        claim_sent_date,
        float(payload.monthly_payment_amount),
        float(payload.first_period_paid_amount or 0),
    )
    penalty_amount = adjusted_penalty_amount
    state_duty_amount = compute_lawsuit_state_duty_fn(country_code, debt_amount, penalty_amount)

    generated_dir.mkdir(parents=True, exist_ok=True)
    safe_contract = re.sub(r"[^A-Za-z0-9_-]+", "_", str(debtor.get("contract_number") or debtor.get("id")))
    pdf_path = generated_dir / f"lawsuit_{safe_contract}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    image_width = 1654
    image_height = 2339
    margin_left = 112
    margin_right = 112
    margin_top = 74
    margin_bottom = 82
    content_width = image_width - margin_left - margin_right
    block_width = 560
    paragraph_indent = 42

    regular_font = _load_font(24)
    title_font = _load_font(32, bold=True)
    section_font = _load_font(24, bold=True)
    small_font = _load_font(22)
    table_font = _load_font(20)
    table_font_bold = _load_font(20, bold=True)

    pages: list[Image.Image] = []
    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)
    current_y = margin_top

    def new_page() -> None:
        nonlocal image, draw, current_y
        pages.append(image)
        image = Image.new("RGB", (image_width, image_height), "white")
        draw = ImageDraw.Draw(image)
        current_y = margin_top

    def estimate_block_height(text: str, font: ImageFont.ImageFont, width: int, line_spacing: int, first_line_indent: int = 0) -> int:
        normalized = " ".join((text or "").split())
        if not normalized:
            return 0
        bbox = draw.textbbox((0, 0), "Аг", font=font)
        line_height = (bbox[3] - bbox[1]) + line_spacing
        if first_line_indent > 0:
            words = normalized.split(" ")
            first_line_words: list[str] = []
            while words:
                candidate_words = first_line_words + [words[0]]
                candidate = " ".join(candidate_words).strip()
                if draw.textlength(candidate, font=font) <= max(40, width - first_line_indent):
                    first_line_words.append(words.pop(0))
                else:
                    break
            remaining = " ".join(words).strip()
            lines = 1 if first_line_words else 0
            if remaining:
                lines += len(_wrap_text(draw, remaining, font, width))
            return max(lines, 1) * line_height
        return max(len(_wrap_text(draw, normalized, font, width)), 1) * line_height

    def ensure_space(required_height: int) -> None:
        nonlocal current_y
        if current_y + required_height > image_height - margin_bottom:
            new_page()

    def draw_paragraph(
        text: str,
        *,
        font: ImageFont.ImageFont = regular_font,
        align: str = "left",
        spacing_after: int = 12,
        first_line_indent: int = paragraph_indent,
    ) -> None:
        nonlocal current_y
        estimate = estimate_block_height(text, font, content_width, 14, first_line_indent) + spacing_after
        ensure_space(estimate)
        current_y = _draw_text_block(
            draw,
            text,
            x=margin_left,
            y=current_y,
            width=content_width,
            font=font,
            line_spacing=14,
            align=align,
            paragraph_spacing=spacing_after,
            first_line_indent=first_line_indent if align == "left" else 0,
        )

    top_right_x = image_width - margin_right - block_width
    current_y = _draw_text_block(
        draw,
        court_name,
        x=top_right_x,
        y=current_y,
        width=block_width,
        font=section_font,
        line_spacing=12,
        align="left",
        paragraph_spacing=18,
    )

    plaintiff_lines = [
        "Истец:",
        company_name,
        f"БИН: {normalize_text(requisites.get('bin')) or '—'}",
        normalize_text(requisites.get("address")) or "—",
        "Email: sud.process.dp@gmail.com",
        "Тел: +7 700 739 9636",
    ]
    for line in plaintiff_lines:
        current_y = _draw_text_block(
            draw,
            line,
            x=top_right_x,
            y=current_y,
            width=block_width,
            font=regular_font if line != "Истец:" else section_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=2,
        )

    current_y += 14
    defendant_lines = [
        "Ответчик:",
        client_name,
        f"ИИН: {client_inn}",
        client_address,
        client_phones,
    ]
    for line in defendant_lines:
        current_y = _draw_text_block(
            draw,
            line,
            x=top_right_x,
            y=current_y,
            width=block_width,
            font=regular_font if line != "Ответчик:" else section_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=2,
        )

    current_y += 32
    ensure_space(120)
    current_y = _draw_text_block(
        draw,
        "Иск\nо взыскании задолженности",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=title_font,
        line_spacing=12,
        align="center",
        paragraph_spacing=28,
    )

    intro_paragraphs = [
        "Диспозицией статьи 9 Гражданского кодекса Республики Казахстан (далее – ГК) закреплено, что защита гражданских прав осуществляется судом, арбитражем путем: признания прав; восстановления положения, существовавшего до нарушения права; пресечения действий, нарушающих право или создающих угрозу его нарушения; присуждения к исполнению обязанности в натуре; взыскания убытков, неустойки; признания оспоримой сделки недействительной и применения последствий ее недействительности, применения последствий недействительности ничтожной сделки; компенсации морального вреда; прекращения или изменения правоотношений; признания недействительным или не подлежащим применению не соответствующего законодательству Республики Казахстан акта органа государственного управления или местного представительного либо исполнительного органа; взыскания штрафа с государственного органа или должностного лица за воспрепятствование гражданину или юридическому лицу в приобретении или осуществлении права, а также иными способами, предусмотренными законодательными актами Республики Казахстан.",
        f"Между {company_name} и {client_short_name} заключен договор купли/продажи № {contract_number} от {format_date(contract_date) or '—'}, в соответствии с которым в собственность передан товар, а именно:",
    ]
    for paragraph in intro_paragraphs:
        draw_paragraph(paragraph)

    for product in products:
        draw_paragraph(
            normalize_text(product.get("display_name")) or normalize_text(product.get("name")) or "Товар",
            first_line_indent=0,
            spacing_after=6,
        )

    main_paragraphs = [
        "Статьей 7 ГК определено, что гражданские права и обязанности возникают, изменяются и прекращаются из оснований, предусмотренных законодательством Республики Казахстан, а также из действий граждан и юридических лиц, которые хотя и не предусмотрены им, но в силу общих начал и смысла гражданского законодательства порождают гражданские права и обязанности. В соответствии с этим гражданские права и обязанности возникают, изменяются и прекращаются, помимо прочих, из договоров и иных сделок, предусмотренных законодательством Республики Казахстан, а также из сделок, хотя и не предусмотренных им, но не противоречащих законодательству Республики Казахстан.",
        "Статьей 378 ГК определено, что договором признается соглашение двух или нескольких лиц об установлении, изменении или прекращении гражданских прав и обязанностей.",
        "В силу статьи 393 ГК договор считается заключенным, когда между сторонами в требуемой в подлежащих случаях форме достигнуто соглашение по всем существенным его условиям. Существенными являются условия о предмете договора, условия, которые признаны существенными законодательством или необходимы для договоров данного вида, а также все те условия, относительно которых по заявлению одной из сторон должно быть достигнуто соглашение. Если в соответствии с законодательными актами для заключения договора необходима передача имущества, договор считается заключенным с момента передачи соответствующего имущества.",
        "В соответствии со статьей 406 ГК по договору купли-продажи одна сторона (продавец) обязуется передать имущество (товар) в собственность, хозяйственное ведение или оперативное управление другой стороне (покупателю), а покупатель обязуется принять это имущество (товар) и уплатить за него определенную денежную сумму (цену).",
        f"Согласно условиям заключенного договора определено, что ответчик принял на себя обязательства по оплате стоимости полученного товара. Стоимость переданного товара с учетом скидки {format_money(discount_amount)} тенге была определена в размере {format_money(contract_total_amount)} тенге, из которых {format_money(advance_amount)} тенге были оплачены в качестве предоплаты, оставшаяся сумма в размере {format_money(installment_balance_amount)} тенге подлежала оплате в рассрочку в период с {format_date(payload.installment_from) or '—'} года по {format_date(payload.installment_to) or '—'} года равными платежами по {format_money(payload.monthly_payment_amount)} тенге.",
        f"Ответчиком были внесены платежи в размере {format_money(post_advance_payments)} тенге, в связи с чем сумма задолженности на данный момент составила {format_money(debt_amount)} тенге.",
        f"Однако обязательства, принятые на себя, ответчик на сумму в размере {format_money(debt_amount)} тенге не исполнил, что привело к нарушению прав и охраняемых законом интересов {company_name}.",
        "В силу статьи 272 ГК обязательство должно исполняться надлежащим образом в соответствии с условиями обязательства и требованиями законодательства, а при отсутствии таких условий и требований - в соответствии с обычаями делового оборота или иными обычно предъявляемыми требованиями. Согласно статье 277 ГК, если обязательство предусматривает или позволяет определить день его исполнения или период времени, в течение которого оно должно быть исполнено, обязательство подлежит исполнению в этот день или, соответственно, в любой момент в пределах такого периода.",
        "В соответствии с пунктом 1 статьи 353 Гражданского кодекса Республики Казахстан, при неисполнении или ненадлежащем исполнении денежного обязательства должник обязан уплатить кредитору неустойку (пеню) в размере 0,1% от суммы долга за каждый день просрочки.",
        f"На основании вышеуказанного положения закона, произведён расчёт пени по обязательству в размере {format_money(debt_amount)} тенге, {total_overdue_days} календарных дней просрочки, с учётом поэтапного увеличения задолженности следующим образом: {format_money(penalty_amount)} тенге, согласно нижеприведенному расчету:",
    ]
    for paragraph in main_paragraphs:
        draw_paragraph(paragraph)

    table_header_height = 76
    row_height = 44
    table_total_height = table_header_height + (len(penalty_rows) * row_height) + row_height + 42
    ensure_space(table_total_height)
    table_x = margin_left
    table_y = current_y + 8
    col_widths = [150, 150, 180, 360, 160, 210]

    def draw_cell(x: int, y: int, width: int, height: int, text: str, *, font: ImageFont.ImageFont, align: str = "center", bold: bool = False) -> None:
        draw.rectangle((x, y, x + width, y + height), outline="#111111", width=1)
        text_font = table_font_bold if bold else font
        lines = _wrap_text(draw, text, text_font, max(width - 10, 20))
        bbox = draw.textbbox((0, 0), "Аг", font=text_font)
        line_height = (bbox[3] - bbox[1]) + 4
        block_height = len(lines) * line_height
        line_y = y + max((height - block_height) / 2, 4)
        for line in lines:
            line_width = draw.textlength(line, font=text_font)
            if align == "left":
                line_x = x + 6
            elif align == "right":
                line_x = x + width - line_width - 6
            else:
                line_x = x + max((width - line_width) / 2, 4)
            draw.text((line_x, line_y), line, fill="#111111", font=text_font)
            line_y += line_height

    first_header_y = table_y
    second_header_y = table_y + int(table_header_height / 2)
    x = table_x
    draw_cell(x, first_header_y, col_widths[0] + col_widths[1], int(table_header_height / 2), "Период", font=table_font, bold=True)
    x += col_widths[0] + col_widths[1]
    for label, width in zip(
        [
            "Количество дней просрочки",
            "Сумма неисполненного обязательства (тенге)",
            "Размер пени (день %)",
            "Сумма пени (тенге)",
        ],
        col_widths[2:],
    ):
        draw_cell(x, first_header_y, width, table_header_height, label, font=table_font, bold=True)
        x += width
    draw_cell(table_x, second_header_y, col_widths[0], int(table_header_height / 2), "От", font=table_font, bold=True)
    draw_cell(table_x + col_widths[0], second_header_y, col_widths[1], int(table_header_height / 2), "До", font=table_font, bold=True)

    current_row_y = table_y + table_header_height
    for row in penalty_rows:
        cell_values = [
            format_date(row["period_from"]) or "—",
            format_date(row["period_to"]) or "—",
            str(row["days"]),
            format_money(row["obligation_amount"]),
            "0,1",
            format_money(row["penalty_amount"]),
        ]
        x = table_x
        for value, width in zip(cell_values, col_widths):
            draw_cell(x, current_row_y, width, row_height, value, font=table_font)
            x += width
        current_row_y += row_height

    summary_width = sum(col_widths[:-1])
    draw_cell(table_x, current_row_y, summary_width, row_height, "Итого", font=table_font, align="right", bold=True)
    draw_cell(table_x + summary_width, current_row_y, col_widths[-1], row_height, format_money(penalty_amount), font=table_font, bold=True)
    current_y = current_row_y + row_height + 20

    closing_paragraphs = [
        f"Требования {company_name}, адресованные {client_short_name}, о необходимости исполнения обязательства оставлены последним без удовлетворения.",
        f"Совокупность приведенных норм законодательства и изложенных обстоятельств позволяет сделать вывод о том, что с {client_short_name} в пользу {company_name} подлежат взысканию сумма задолженности в размере {format_money(debt_amount)} тенге и пеня в размере {format_money(penalty_amount)} тенге.",
        "В силу статьи 4 Гражданского процессуального кодекса Республики Казахстан (далее – ГПК) задачами гражданского судопроизводства являются защита и восстановление нарушенных или оспариваемых прав, свобод и законных интересов граждан, государства и юридических лиц, соблюдение законности в гражданском обороте, обеспечение полного и своевременного рассмотрения дела, содействие мирному урегулированию спора, предупреждение правонарушений и формирование в обществе уважительного отношения к закону и суду.",
        "На основании изложенного, руководствуясь статьями 148, 149, ГПК РК",
    ]
    for paragraph in closing_paragraphs:
        draw_paragraph(paragraph)

    ensure_space(260)
    current_y = _draw_text_block(
        draw,
        "Прошу:",
        x=margin_left,
        y=current_y + 6,
        width=content_width,
        font=section_font,
        line_spacing=12,
        align="left",
        paragraph_spacing=18,
    )

    ask_line = (
        f"1. Взыскать с {client_name} в пользу {company_name} сумму задолженности в размере "
        f"{format_money(debt_amount)} ({money_to_words_ru(debt_amount)}) тенге, пеню в размере "
        f"{format_money(penalty_amount)} ({money_to_words_ru(penalty_amount)}) тенге, государственную пошлину "
        f"в размере {format_money(state_duty_amount)} ({money_to_words_ru(state_duty_amount)}) тенге."
    )
    draw_paragraph(ask_line, first_line_indent=0, spacing_after=18)

    current_y = _draw_text_block(
        draw,
        "Приложение:",
        x=margin_left,
        y=current_y,
        width=content_width,
        font=section_font,
        line_spacing=12,
        align="left",
        paragraph_spacing=10,
    )

    attachments = [
        "1) Квитанция об уплате государственной пошлины;",
        "2) Копия договора купли-продажи с актом приема-передачи;",
        "3) Копия устава;",
        "4) Копия свидетельства (справка о государственной регистрации);",
        "5) Копия досудебной претензии с квитанцией об отправке.",
    ]
    for item in attachments:
        draw_paragraph(item, first_line_indent=0, spacing_after=6)

    signature_y = max(current_y + 24, image_height - margin_bottom - 84)
    director_name = normalize_text(requisites.get("director_name")) or "—"
    left_signature = f"Директор {company_name}"
    draw.text((margin_left, signature_y), left_signature, fill="#111111", font=small_font)
    director_width = draw.textlength(director_name, font=small_font)
    draw.text((image_width - margin_right - director_width, signature_y), director_name, fill="#111111", font=small_font)
    generated_date = format_date(date.today()) or date.today().isoformat()
    draw.text((margin_left, signature_y + 38), generated_date, fill="#111111", font=small_font)

    pages.append(image)
    try:
        first_page, *other_pages = pages
        first_page.save(pdf_path, "PDF", resolution=150.0, save_all=True, append_images=other_pages)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF иска.") from exc

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF иска.")

    return pdf_path

