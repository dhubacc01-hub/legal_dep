from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont

from app.claim_pdf_service import (
    build_claim_output_path,
    load_claim_crm_context,
    resolve_claim_client_contacts,
    resolve_claim_contract_data,
    resolve_claim_products,
    resolve_claim_requisites,
)
from app.common_utils import contract_date_value_from_number, format_date, normalize_text, preferred_phone
from app.country_service import normalize_country_code
from app.document_helpers import (
    build_company_header_lines,
    build_company_payment_detail_lines,
    build_company_payment_detail_lines_uz,
)
from app.financial_helpers import format_money
from app.money_words import money_to_words_ru, money_to_words_sum_ru
from app.pdf_rendering import draw_text_block as render_draw_text_block, load_font as render_load_font
from app.reference_data import DEFAULT_COUNTRY

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


def _render_claim_pdf_kz(
    debtor: dict[str, Any],
    *,
    compute_financials_fn,
    generated_dir: Path,
    debt_amount_override: float | None = None,
    product_overrides: list[dict[str, Any]] | None = None,
) -> Path:
    _, requisites, company_name = resolve_claim_requisites(debtor, country="kz")
    financials = compute_financials_fn(debtor)
    crm_context = load_claim_crm_context(
        debtor,
        country=str(debtor.get("country") or DEFAULT_COUNTRY),
    )
    claim_contract = resolve_claim_contract_data(
        debtor,
        crm_context,
        financials,
        debt_amount_override=debt_amount_override,
    )
    contract_number = claim_contract["contract_number"]
    contract_date = claim_contract["contract_date"]
    contract_total_amount = claim_contract["contract_total_amount"]
    contract_advance_amount = claim_contract["contract_advance_amount"]
    debt_amount = claim_contract["debt_amount"]
    products = resolve_claim_products(
        crm_context,
        product_overrides=product_overrides,
        fallback_name="Товар по договору",
    )
    pdf_path = build_claim_output_path(generated_dir, debtor, prefix="claim")
    image_width = 1654
    image_height = 2339
    margin_left = 128
    margin_right = 128
    margin_top = 82
    margin_bottom = 82
    content_width = image_width - margin_left - margin_right
    right_block_width = 520
    title_width = content_width
    content_x = margin_left
    paragraph_indent = 44

    regular_font = _load_font(23)
    title_font = _load_font(29, bold=True)
    ask_font = _load_font(27, bold=True)
    small_font = _load_font(21)

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)

    y = margin_top
    right_x = content_x + content_width - right_block_width
    right_lines = [
        debtor.get("client_name") or "—",
        normalize_text(debtor.get("address")) or "—",
        preferred_phone(debtor),
    ]
    for line in right_lines:
        y = _draw_text_block(
            draw,
            str(line),
            x=right_x,
            y=y,
            width=right_block_width,
            font=regular_font,
            line_spacing=12,
            align="left",
            paragraph_spacing=2,
        )

    y += 12
    for line in build_company_header_lines(requisites, company_name):
        y = _draw_text_block(
            draw,
            line,
            x=right_x,
            y=y,
            width=right_block_width,
            font=regular_font,
            line_spacing=12,
            align="left",
            paragraph_spacing=1,
        )

    y += 20
    y = _draw_text_block(
        draw,
        "Досудебная претензия",
        x=content_x,
        y=y,
        width=title_width,
        font=title_font,
        line_spacing=12,
        align="center",
        paragraph_spacing=28,
    )

    paragraphs = [
        (
            f"Между {company_name} и Вами заключен договор купли-продажи товара № "
            f"{contract_number or '—'} от {format_date(contract_date) or '—'}, "
            f"в соответствии с условиями которого {company_name} передала в собственность "
            "покупателя товар:"
        ),
        (
            f"Согласно условиям заключенного договора покупатель принял на себя обязательства "
            f"по оплате стоимости полученного товара. Стоимость переданного товара составила "
            f"{format_money(contract_total_amount)} тенге, из которых "
            f"{format_money(contract_advance_amount)} тенге были оплачены в качестве "
            "первоначального взноса. Оставшаяся сумма подлежала оплате в соответствии с "
            f"графиком платежей, предусмотренным пунктом 2.1 договора купли-продажи № "
            f"{contract_number or '—'}."
        ),
        (
            "В соответствии со статьей 406 Гражданского кодекса Республики Казахстан по "
            "договору купли-продажи одна сторона (продавец) обязуется передать имущество "
            "(товар) в собственность, хозяйственное ведение либо оперативное управление "
            "другой стороне (покупателю), а покупатель обязуется принять указанный товар "
            "и уплатить за него определенную денежную сумму (цену)."
        ),
        (
            "Согласно статье 272 Гражданского кодекса Республики Казахстан обязательства "
            "должны исполняться надлежащим образом в соответствии с условиями обязательства "
            "и требованиями законодательства, а при отсутствии таких условий и требований — "
            "в соответствии с обычаями делового оборота и иными обычно предъявляемыми "
            "требованиями."
        ),
        (
            "В силу статьи 277 Гражданского кодекса Республики Казахстан, если обязательство "
            "предусматривает или позволяет определить день его исполнения либо период времени, "
            "в течение которого оно должно быть исполнено, обязательство подлежит исполнению "
            "в установленный срок."
        ),
        (
            f"Однако принятые на себя обязательства Вами исполнены не были, что привело к "
            f"нарушению прав и законных интересов {company_name}."
        ),
        (
            "Кроме того, условиями заключенного между сторонами договора предусмотрено, что "
            "в случае просрочки очередного платежа при оплате товара в рассрочку покупатель "
            "обязан уплатить продавцу неустойку (пеню) в размере 0,1% за каждый день "
            "просрочки от суммы платежа, подлежащего оплате."
        ),
    ]

    intro_paragraph = paragraphs[0]
    y = _draw_text_block(
        draw,
        intro_paragraph,
        x=content_x,
        y=y,
        width=content_width,
        font=regular_font,
        line_spacing=11,
        align="left",
        paragraph_spacing=8,
        first_line_indent=paragraph_indent,
    )

    for product in products:
        display_name = normalize_text(product.get("display_name")) or normalize_text(product.get("name")) or "РўРѕРІР°СЂ"
        y = _draw_text_block(
            draw,
            display_name,
            x=content_x,
            y=y,
            width=content_width,
            font=regular_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=4,
            first_line_indent=0,
        )

    y += 6
    paragraphs = paragraphs[1:]
    products = []

    for paragraph in paragraphs:
        y = _draw_text_block(
            draw,
            paragraph,
            x=content_x,
            y=y,
            width=content_width,
            font=regular_font,
            line_spacing=11,
            align="left",
            paragraph_spacing=8,
            first_line_indent=paragraph_indent,
        )

    for product in products:
        display_name = normalize_text(product.get("display_name")) or normalize_text(product.get("name")) or "Товар"
        y = _draw_text_block(
            draw,
            display_name,
            x=content_x,
            y=y,
            width=content_width,
            font=regular_font,
            line_spacing=10,
            align="left",
            paragraph_spacing=4,
            first_line_indent=0,
        )

    y += 18
    y = _draw_text_block(
        draw,
        "ПРОШУ:",
        x=content_x,
        y=y,
        width=content_width,
        font=ask_font,
        line_spacing=12,
        align="center",
        paragraph_spacing=24,
    )

    payment_detail_lines = build_company_payment_detail_lines(requisites)

    ask_paragraphs = [
        (
            f"В течение 7 (семи) календарных дней с момента получения настоящей претензии "
            f"осуществить в пользу {company_name} выплату суммы задолженности в размере "
            f"{format_money(debt_amount)} ({money_to_words_ru(debt_amount)}) тенге по следующим реквизитам:"
        ),
        "Настоящая досудебная претензия направляется в рамках претензионно-исковой работы.",
        (
            f"В случае неудовлетворения требований {company_name}, выражающихся в погашении "
            "задолженности в добровольном порядке, "
            f"{company_name} будет вынуждена обратиться в судебные органы за защитой своих "
            "прав и законных интересов с возложением на Вас дополнительных расходов, включая "
            "неустойку, государственную пошлину, а также расходы на оплату услуг представителя."
        ),
        "Надеемся на понимание и урегулирование сложившейся ситуации в добровольном порядке.",
    ]

    for index, paragraph in enumerate(ask_paragraphs):
        y = _draw_text_block(
            draw,
            paragraph,
            x=content_x,
            y=y,
            width=content_width,
            font=regular_font,
            line_spacing=11,
            align="left",
            paragraph_spacing=8 if index != 1 else 12,
            first_line_indent=paragraph_indent if index != 1 else 0,
        )

        if index == 0 and payment_detail_lines:
            for payment_line in payment_detail_lines:
                y = _draw_text_block(
                    draw,
                    payment_line,
                    x=content_x,
                    y=y,
                    width=content_width,
                    font=regular_font,
                    line_spacing=11,
                    align="left",
                    paragraph_spacing=4,
                    first_line_indent=0,
                )
            y += 10

    signature_y = max(y + 28, image_height - margin_bottom - 104)
    director_name = requisites.get("director_name") or "—"
    signature_text = f"Директор {company_name}"
    draw.text((margin_left, signature_y), signature_text, fill="#111111", font=small_font)

    label_width = draw.textlength(signature_text, font=small_font)
    line_start_x = int(margin_left + label_width + 18)
    line_end_x = line_start_x + 200
    line_y = signature_y + 24
    draw.line((line_start_x, line_y, line_end_x, line_y), fill="#111111", width=1)

    draw.text((line_end_x + 18, signature_y), director_name, fill="#111111", font=small_font)

    generated_date = format_date(date.today()) or date.today().isoformat()
    date_bbox = draw.textbbox((0, 0), generated_date, font=small_font)
    date_width = date_bbox[2] - date_bbox[0]
    draw.text((image_width - margin_right - date_width, signature_y + 22), generated_date, fill="#111111", font=small_font)

    try:
        image.save(pdf_path, "PDF", resolution=150.0)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF претензии.") from exc

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF претензии.")

    return pdf_path


def _render_claim_pdf_uz(
    debtor: dict[str, Any],
    *,
    compute_financials_fn,
    generated_dir: Path,
    debt_amount_override: float | None = None,
    product_overrides: list[dict[str, Any]] | None = None,
) -> Path:
    _, requisites, company_name = resolve_claim_requisites(debtor, country="uz")
    crm_context = load_claim_crm_context(debtor, country="uz")
    financials = compute_financials_fn(debtor)
    claim_contract = resolve_claim_contract_data(
        debtor,
        crm_context,
        financials,
        debt_amount_override=debt_amount_override,
        prefer_crm_debt=True,
    )
    contract_number = claim_contract["contract_number"]
    contract_date = claim_contract["contract_date"]
    contract_total_amount = claim_contract["contract_total_amount"]
    contract_advance_amount = claim_contract["contract_advance_amount"]
    debt_amount = claim_contract["debt_amount"]
    products = resolve_claim_products(
        crm_context,
        product_overrides=product_overrides,
        fallback_name="Товар по договору",
    )
    claim_contacts = resolve_claim_client_contacts(debtor, crm_context)
    client_name = claim_contacts["client_name"]
    client_address = claim_contacts["client_address"]
    client_phone = claim_contacts["client_phone"]
    pdf_path = build_claim_output_path(generated_dir, debtor, prefix="claim_uz")
    debt_words_ru = money_to_words_sum_ru(debt_amount)
    payment_detail_lines_ru = build_company_payment_detail_lines_uz(requisites)
    payment_detail_lines_uz = []
    if requisites.get("bin"):
        payment_detail_lines_uz.append(f"ИНН: {requisites['bin']}")
    if requisites.get("bank_name"):
        payment_detail_lines_uz.append(f"Банк номи: {requisites['bank_name']}")
    if requisites.get("account_number"):
        payment_detail_lines_uz.append(f"Ҳисоб рақами: {requisites['account_number']}")
    if requisites.get("bank_mfo"):
        payment_detail_lines_uz.append(f"Банк МФОси: {requisites['bank_mfo']}")

    ru_paragraphs = [
        f"Между {company_name} и Вами заключен договор купли/продажи товара № {contract_number} от {format_date(contract_date) or '—'}, в соответствии с которым {company_name} в собственность покупателя передан товар:",
        f"Согласно условиям заключенного договора определено, что покупатель принял на себя обязательства по оплате стоимости полученного товара. Стоимость переданного товара была определена в размере {format_money(contract_total_amount)} сум, из которых {format_money(contract_advance_amount)} сум были оплачены в качестве предоплаты, остальная оплата по договору осуществлялась согласно графика указанного в 2.2 договора купли-продажи.",
        "В соответствии со статьёй 386 Гражданского кодекса Республики Узбекистан, по договору купли-продажи одна сторона (продавец) обязуется передать товар в собственность другой стороне (покупателю), а покупатель — принять товар и уплатить за него установленную договором денежную сумму.",
        "В силу статьи 236 Гражданского кодекса Республики Узбекистан, обязательства должны исполняться надлежащим образом в соответствии с условиями обязательства и требованиями законодательства.",
        f"Однако обязательства, принятые на себя, Вы не исполнили, что привело к нарушению прав и охраняемых законом интересов {company_name}.",
        "Одновременно с этим, пунктом 2.3 заключенного договора определено, что в случае просрочки очередного платежа при оплате товара в рассрочку покупатель уплачивает продавцу пеню в размере 0,1 % за каждый день просрочки от суммы платежа, подлежащего уплате.",
    ]

    uz_paragraphs = [
        f"{company_name} ва Сиз ўртасида {format_date(contract_date) or '—'} санадаги {contract_number}-сонли товар олди-сотди шартномаси тузилган бўлиб, унга кўра {company_name} харидорга қуйидаги товарларни топширган:",
        f"Шартнома шартларига кўра, харидор олинган товар қийматини тўлаш мажбуриятини олган. Товар қиймати {format_money(contract_total_amount)} сўм этиб белгиланган, шундан {format_money(contract_advance_amount)} сўм олдиндан тўлов сифатида тўланган, қолган қисми эса олди-сотди шартномасининг 2.2-бандида кўрсатилган жадвал асосида тўланиши лозим бўлган.",
        "Ўзбекистон Республикаси Фуқаролик кодексининг 386-моддасига кўра, олди-сотди шартномаси бўйича сотувчи товарни харидорга мулк қилиб топшириши, харидор эса товарни қабул қилиб, белгиланган пул суммасини тўлаши шарт.",
        "Фуқаролик кодексининг 236-моддасига мувофиқ, мажбуриятлар шартнома шартлари ва қонунчилик талабларига мувофиқ лозим даражада бажарилиши керак.",
        f"Бироқ Сиз зиммангизга олган мажбуриятларни бажармагансиз, бу эса {company_name}нинг ҳуқуқлари ва қонуний манфаатлари бузилишига олиб келган.",
        "Шунингдек, шартноманинг 2.3-бандига кўра, муддатли тўлов бўйича навбатдаги тўлов кечиктирилган тақдирда, харидор тўланиши лозим бўлган суммадан ҳар бир кечиктирилган кун учун 0,1 % миқдорида пеня тўлайди.",
    ]

    ru_ask = [
        f"В течении 7 дней осуществить в пользу {company_name} выплату суммы задолженности в размере {format_money(debt_amount)} ({debt_words_ru}) сум по следующим реквизитам:",
        "Сообщаем, что указанная досудебная претензия направлена в рамках претензионно-исковой работы. В случае неудовлетворения требования, указанного в настоящей претензии, компания будет вынуждена обратиться в суд за защитой своих интересов, с возложением на Вас дополнительных расходов по уплате неустойки, государственной пошлины и услуг представителя.",
        "Мы надеемся на добросовестный подход к исполнению обязательств и предлагаем урегулировать вопрос в досудебном порядке.",
    ]
    uz_ask = [
        f"7 кун ичида {company_name} фойдасига {format_money(debt_amount)} сўм миқдоридаги қарздорликни қуйидаги реквизитлар бўйича тўлашингизни сўраймиз:",
        "Мазкур судгача бўлган талабнома даъво ишларини юритиш доирасида юборилмоқда. Агар ундаги талаблар бажарилмаса, компания ўз манфаатларини ҳимоя қилиш учун судга мурожаат қилишга, шунингдек Сизнинг зиммангизга пеня, давлат божи ва вакил хизматлари харажатларини юклашга мажбур бўлади.",
        "Мажбуриятларни виждонан бажаришингизга умид қиламиз ва масалани судгача бўлган тартибда ҳал этишни таклиф қиламиз.",
    ]

    pdf_path = build_claim_output_path(generated_dir, debtor, prefix="claim_uz")

    image_width = 1654
    image_height = 2339
    margin_left = 90
    margin_right = 90
    margin_top = 70
    margin_bottom = 80
    content_width = image_width - margin_left - margin_right
    center_x = image_width // 2
    line_spacing = 11

    title_font = _load_font(30, bold=True)
    section_font = _load_font(26, bold=True)
    regular_font = _load_font(22)
    small_font = _load_font(20)

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)

    y = margin_top
    centered_header_lines = [
        company_name,
        normalize_text(requisites.get("address")) or "—",
        f"ИНН: {normalize_text(requisites.get('bin')) or '—'}",
    ]
    for line in centered_header_lines:
        y = _draw_text_block(
            draw,
            line,
            x=margin_left,
            y=y,
            width=content_width,
            font=section_font if line == company_name else regular_font,
            line_spacing=8,
            align="center",
            paragraph_spacing=4,
        )

    divider_y = y + 10
    draw.line((margin_left, divider_y, image_width - margin_right, divider_y), fill="#111111", width=2)

    right_block_x = image_width - margin_right - 420
    right_y = divider_y + 18
    client_lines = [
        client_name,
        client_address,
        client_phone,
    ]
    for line in client_lines:
        right_y = _draw_text_block(
            draw,
            line,
            x=right_block_x,
            y=right_y,
            width=420,
            font=regular_font,
            line_spacing=8,
            align="left",
            paragraph_spacing=2,
        )

    columns_y = right_y + 16
    gutter = 30
    column_width = (content_width - gutter) // 2
    left_x = margin_left
    right_col_x = left_x + column_width + gutter
    vertical_line_x = left_x + column_width + gutter // 2
    draw.line((vertical_line_x, columns_y, vertical_line_x, image_height - margin_bottom - 70), fill="#111111", width=2)

    left_y = columns_y
    right_y = columns_y

    def draw_column_title(x: int, y_value: int, text: str) -> int:
        return _draw_text_block(
            draw,
            text,
            x=x,
            y=y_value,
            width=column_width,
            font=section_font,
            line_spacing=8,
            align="center",
            paragraph_spacing=16,
        )

    def draw_column_paragraph(x: int, y_value: int, text: str, *, indent: int = 26, spacing: int = 10) -> int:
        return _draw_text_block(
            draw,
            text,
            x=x,
            y=y_value,
            width=column_width,
            font=regular_font,
            line_spacing=line_spacing,
            align="left",
            paragraph_spacing=spacing,
            first_line_indent=indent,
        )

    left_y = draw_column_title(left_x, left_y, "Досудебная претензия")
    right_y = draw_column_title(right_col_x, right_y, "Судгача бўлган талабнома")

    for ru_text, uz_text in zip(ru_paragraphs, uz_paragraphs):
        left_y = draw_column_paragraph(left_x, left_y, ru_text)
        right_y = draw_column_paragraph(right_col_x, right_y, uz_text)

    for product in products:
        display_name = normalize_text(product.get("display_name")) or normalize_text(product.get("name")) or "Товар"
        left_y = draw_column_paragraph(left_x, left_y, display_name, indent=0, spacing=5)
        right_y = draw_column_paragraph(right_col_x, right_y, display_name, indent=0, spacing=5)

    left_y += 12
    right_y += 12
    left_y = draw_column_title(left_x, left_y, "Прошу:")
    right_y = draw_column_title(right_col_x, right_y, "Сўраймиз:")

    left_y = draw_column_paragraph(left_x, left_y, ru_ask[0])
    right_y = draw_column_paragraph(right_col_x, right_y, uz_ask[0])

    for payment_line in payment_detail_lines_ru:
        left_y = draw_column_paragraph(left_x, left_y, payment_line, indent=0, spacing=4)
    for payment_line in payment_detail_lines_uz:
        right_y = draw_column_paragraph(right_col_x, right_y, payment_line, indent=0, spacing=4)

    left_y += 8
    right_y += 8
    for ru_text, uz_text in zip(ru_ask[1:], uz_ask[1:]):
        left_y = draw_column_paragraph(left_x, left_y, ru_text)
        right_y = draw_column_paragraph(right_col_x, right_y, uz_text)

    signature_y = max(left_y, right_y) + 54
    signature_y = min(signature_y, image_height - margin_bottom - 90)
    signature_label_ru = f"Директор {company_name}"
    signature_label_uz = f"Директор {company_name}"
    director_name = normalize_text(requisites.get("director_name")) or "—"
    generated_date = format_date(date.today()) or date.today().isoformat()

    def draw_signature_block(block_x: int, label: str) -> None:
        draw.text((block_x, signature_y), label, fill="#111111", font=small_font)
        draw.text((block_x, signature_y + 34), generated_date, fill="#111111", font=small_font)

        director_width_local = draw.textlength(director_name, font=small_font)
        right_name_x = block_x + max(0, column_width - director_width_local)
        draw.text((right_name_x, signature_y), director_name, fill="#111111", font=small_font)

    draw_signature_block(left_x, signature_label_ru)
    draw_signature_block(right_col_x, signature_label_uz)

    try:
        image.save(pdf_path, "PDF", resolution=150.0)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="РќРµ СѓРґР°Р»РѕСЃСЊ СЃС„РѕСЂРјРёСЂРѕРІР°С‚СЊ PDF РїСЂРµС‚РµРЅР·РёРё.") from exc

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="РќРµ СѓРґР°Р»РѕСЃСЊ СЃС„РѕСЂРјРёСЂРѕРІР°С‚СЊ PDF РїСЂРµС‚РµРЅР·РёРё.")

    return pdf_path

def _render_claim_pdf_uz_v2(
    debtor: dict[str, Any],
    *,
    compute_financials_fn,
    generated_dir: Path,
    debt_amount_override: float | None = None,
    product_overrides: list[dict[str, Any]] | None = None,
) -> Path:
    _, requisites, company_name = resolve_claim_requisites(debtor, country="uz")
    crm_context = load_claim_crm_context(debtor, country="uz")
    financials = compute_financials_fn(debtor)
    claim_contract = resolve_claim_contract_data(
        debtor,
        crm_context,
        financials,
        debt_amount_override=debt_amount_override,
        prefer_crm_debt=True,
    )
    contract_number = claim_contract["contract_number"]
    contract_date = claim_contract["contract_date"]
    contract_total_amount = claim_contract["contract_total_amount"]
    contract_advance_amount = claim_contract["contract_advance_amount"]
    debt_amount = claim_contract["debt_amount"]
    products = resolve_claim_products(
        crm_context,
        product_overrides=product_overrides,
        fallback_name="Товар по договору",
    )
    claim_contacts = resolve_claim_client_contacts(debtor, crm_context)
    client_name = claim_contacts["client_name"]
    client_address = claim_contacts["client_address"]
    client_phone = claim_contacts["client_phone"]
    pdf_path = build_claim_output_path(generated_dir, debtor, prefix="claim_uz")
    debt_words_ru = money_to_words_sum_ru(debt_amount)
    payment_detail_lines_ru = build_company_payment_detail_lines_uz(requisites)
    payment_detail_lines_uz: list[str] = []
    if requisites.get("bin"):
        payment_detail_lines_uz.append(f"ИНН: {requisites['bin']}")
    if requisites.get("bank_name"):
        payment_detail_lines_uz.append(f"Банк номи: {requisites['bank_name']}")
    if requisites.get("account_number"):
        payment_detail_lines_uz.append(f"Ҳисоб рақами: {requisites['account_number']}")
    if requisites.get("bank_mfo"):
        payment_detail_lines_uz.append(f"Банк МФОси: {requisites['bank_mfo']}")

    ru_paragraphs = [
        f"Между {company_name} и Вами заключен договор купли/продажи товара № {contract_number} от {format_date(contract_date) or '—'}, в соответствии с которым {company_name} в собственность покупателя передан товар:",
        f"Согласно условиям заключенного договора определено, что покупатель принял на себя обязательства по оплате стоимости полученного товара. Стоимость переданного товара была определена в размере {format_money(contract_total_amount)} сум, из которых {format_money(contract_advance_amount)} сум были оплачены в качестве предоплаты, остальная оплата по договору осуществлялась согласно графика указанного в 2.2 договора купли-продажи.",
        "В соответствии со статьёй 386 Гражданского кодекса Республики Узбекистан, по договору купли-продажи одна сторона (продавец) обязуется передать товар в собственность другой стороне (покупателю), а покупатель — принять товар и уплатить за него установленную договором денежную сумму.",
        "В силу статьи 236 Гражданского кодекса Республики Узбекистан, обязательства должны исполняться надлежащим образом в соответствии с условиями обязательства и требованиями законодательства.",
        f"Однако обязательства, принятые на себя, Вы не исполнили, что привело к нарушению прав и охраняемых законом интересов {company_name}.",
        "Одновременно с этим, пунктом 2.3 заключенного договора определено, что в случае просрочки очередного платежа при оплате товара в рассрочку покупатель уплачивает продавцу пеню в размере 0,1 % за каждый день просрочки от суммы платежа, подлежащего уплате.",
    ]

    uz_paragraphs = [
        f"{company_name} ва Сиз ўртасида {format_date(contract_date) or '—'} санадаги {contract_number}-сонли товар олди-сотди шартномаси тузилган бўлиб, унга кўра {company_name} харидорга қуйидаги товарларни топширган:",
        f"Шартнома шартларига кўра, харидор олинган товар қийматини тўлаш мажбуриятини олган. Товар қиймати {format_money(contract_total_amount)} сўм этиб белгиланган, шундан {format_money(contract_advance_amount)} сўм олдиндан тўлов сифатида тўланган, қолган қисми эса олди-сотди шартномасининг 2.2-бандида кўрсатилган жадвал асосида тўланиши лозим бўлган.",
        "Ўзбекистон Республикаси Фуқаролик кодексининг 386-моддасига кўра, олди-сотди шартномаси бўйича сотувчи товарни харидорга мулк қилиб топшириши, харидор эса товарни қабул қилиб, белгиланган пул суммасини тўлаши шарт.",
        "Фуқаролик кодексининг 236-моддасига мувофиқ, мажбуриятлар шартнома шартлари ва қонунчилик талабларига мувофиқ лозим даражада бажарилиши керак.",
        f"Бироқ Сиз зиммангизга олган мажбуриятларни бажармагансиз, бу эса {company_name}нинг ҳуқуқлари ва қонуний манфаатлари бузилишига олиб келган.",
        "Шунингдек, шартноманинг 2.3-бандига кўра, муддатли тўлов бўйича навбатдаги тўлов кечиктирилган тақдирда, харидор тўланиши лозим бўлган суммадан ҳар бир кечиктирилган кун учун 0,1 % миқдорида пеня тўлайди.",
    ]

    ru_ask = [
        f"В течении 7 дней осуществить в пользу {company_name} выплату суммы задолженности в размере {format_money(debt_amount)} ({debt_words_ru}) сум по следующим реквизитам:",
        "Сообщаем, что указанная досудебная претензия направлена в рамках претензионно-исковой работы. В случае неудовлетворения требования, указанного в настоящей претензии, компания будет вынуждена обратиться в суд за защитой своих интересов, с возложением на Вас дополнительных расходов по уплате неустойки, государственной пошлины и услуг представителя.",
        "Мы надеемся на добросовестный подход к исполнению обязательств и предлагаем урегулировать вопрос в досудебном порядке.",
    ]
    uz_ask = [
        f"7 кун ичида {company_name} фойдасига {format_money(debt_amount)} сўм миқдоридаги қарздорликни қуйидаги реквизитлар бўйича тўлашингизни сўраймиз:",
        "Мазкур судгача бўлган талабнома даъво ишларини юритиш доирасида юборилмоқда. Агар ундаги талаблар бажарилмаса, компания ўз манфаатларини ҳимоя қилиш учун судга мурожаат қилишга, шунингдек Сизнинг зиммангизга пеня, давлат божи ва вакил хизматлари харажатларини юклашга мажбур бўлади.",
        "Мажбуриятларни виждонан бажаришингизга умид қиламиз ва масалани судгача бўлган тартибда ҳал этишни таклиф қиламиз.",
    ]

    pdf_path = build_claim_output_path(generated_dir, debtor, prefix="claim_uz")

    image_width = 1654
    image_height = 2339
    margin_left = 90
    margin_right = 90
    margin_top = 70
    margin_bottom = 80
    content_width = image_width - margin_left - margin_right
    line_spacing = 11

    section_font = _load_font(26, bold=True)
    regular_font = _load_font(22)
    small_font = _load_font(20)

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)

    y = margin_top
    centered_header_lines = [
        company_name,
        normalize_text(requisites.get("address")) or "—",
        f"ИНН: {normalize_text(requisites.get('bin')) or '—'}",
    ]
    for line in centered_header_lines:
        y = _draw_text_block(
            draw,
            line,
            x=margin_left,
            y=y,
            width=content_width,
            font=section_font if line == company_name else regular_font,
            line_spacing=8,
            align="center",
            paragraph_spacing=4,
        )

    divider_y = y + 10
    draw.line((margin_left, divider_y, image_width - margin_right, divider_y), fill="#111111", width=2)

    right_block_x = image_width - margin_right - 420
    right_y = divider_y + 18
    for line in [client_name, client_address, client_phone]:
        right_y = _draw_text_block(
            draw,
            line,
            x=right_block_x,
            y=right_y,
            width=420,
            font=regular_font,
            line_spacing=8,
            align="left",
            paragraph_spacing=2,
        )

    columns_y = right_y + 16
    gutter = 30
    column_width = (content_width - gutter) // 2
    left_x = margin_left
    right_col_x = left_x + column_width + gutter
    vertical_line_x = left_x + column_width + gutter // 2
    draw.line((vertical_line_x, columns_y, vertical_line_x, image_height - margin_bottom - 70), fill="#111111", width=2)

    left_y = columns_y
    right_y = columns_y

    def draw_column_title(x: int, y_value: int, text: str) -> int:
        return _draw_text_block(
            draw,
            text,
            x=x,
            y=y_value,
            width=column_width,
            font=section_font,
            line_spacing=8,
            align="center",
            paragraph_spacing=16,
        )

    def draw_column_paragraph(x: int, y_value: int, text: str, *, indent: int = 26, spacing: int = 10) -> int:
        return _draw_text_block(
            draw,
            text,
            x=x,
            y=y_value,
            width=column_width,
            font=regular_font,
            line_spacing=line_spacing,
            align="left",
            paragraph_spacing=spacing,
            first_line_indent=indent,
        )

    left_y = draw_column_title(left_x, left_y, "Досудебная претензия")
    right_y = draw_column_title(right_col_x, right_y, "Судгача бўлган талабнома")

    left_y = draw_column_paragraph(left_x, left_y, ru_paragraphs[0])
    right_y = draw_column_paragraph(right_col_x, right_y, uz_paragraphs[0])

    for product in products:
        display_name = normalize_text(product.get("display_name")) or normalize_text(product.get("name")) or "Товар"
        quantity_raw = product.get("quantity")
        try:
            quantity = max(1, int(float(quantity_raw if quantity_raw not in (None, "") else 1)))
        except (TypeError, ValueError):
            quantity = 1
        product_line = f"{display_name} — {quantity} шт."
        left_y = draw_column_paragraph(left_x, left_y, product_line, indent=0, spacing=5)
        right_y = draw_column_paragraph(right_col_x, right_y, product_line, indent=0, spacing=5)

    left_y += 8
    right_y += 8
    for ru_text, uz_text in zip(ru_paragraphs[1:], uz_paragraphs[1:]):
        left_y = draw_column_paragraph(left_x, left_y, ru_text)
        right_y = draw_column_paragraph(right_col_x, right_y, uz_text)

    left_y += 12
    right_y += 12
    left_y = draw_column_title(left_x, left_y, "Прошу:")
    right_y = draw_column_title(right_col_x, right_y, "Сўраймиз:")

    left_y = draw_column_paragraph(left_x, left_y, ru_ask[0])
    right_y = draw_column_paragraph(right_col_x, right_y, uz_ask[0])

    for payment_line in payment_detail_lines_ru:
        left_y = draw_column_paragraph(left_x, left_y, payment_line, indent=0, spacing=4)
    for payment_line in payment_detail_lines_uz:
        right_y = draw_column_paragraph(right_col_x, right_y, payment_line, indent=0, spacing=4)

    left_y += 8
    right_y += 8
    for ru_text, uz_text in zip(ru_ask[1:], uz_ask[1:]):
        left_y = draw_column_paragraph(left_x, left_y, ru_text)
        right_y = draw_column_paragraph(right_col_x, right_y, uz_text)

    signature_y = max(left_y, right_y) + 54
    signature_y = min(signature_y, image_height - margin_bottom - 130)
    director_name = normalize_text(requisites.get("director_name")) or "—"
    generated_date = format_date(date.today()) or date.today().isoformat()

    def draw_signature_block(block_x: int) -> None:
        local_y = signature_y
        local_y = _draw_text_block(
            draw,
            company_name,
            x=block_x,
            y=local_y,
            width=column_width,
            font=small_font,
            line_spacing=6,
            align="left",
            paragraph_spacing=2,
        )
        local_y = _draw_text_block(
            draw,
            director_name,
            x=block_x,
            y=local_y + 4,
            width=column_width,
            font=small_font,
            line_spacing=6,
            align="left",
            paragraph_spacing=2,
        )
        draw.text((block_x, local_y + 10), generated_date, fill="#111111", font=small_font)

    draw_signature_block(left_x)
    draw_signature_block(right_col_x)

    try:
        image.save(pdf_path, "PDF", resolution=150.0)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF претензии.") from exc

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="Не удалось сформировать PDF претензии.")

    return pdf_path


def render_claim_pdf(
    debtor: dict[str, Any],
    *,
    compute_financials_fn,
    generated_dir: Path,
    debt_amount_override: float | None = None,
    product_overrides: list[dict[str, Any]] | None = None,
) -> Path:
    if normalize_country_code(str(debtor.get("country") or DEFAULT_COUNTRY)) == "uz":
        return _render_claim_pdf_uz_v2(
            debtor,
            compute_financials_fn=compute_financials_fn,
            generated_dir=generated_dir,
            debt_amount_override=debt_amount_override,
            product_overrides=product_overrides,
        )
    return _render_claim_pdf_kz(
        debtor,
        compute_financials_fn=compute_financials_fn,
        generated_dir=generated_dir,
        debt_amount_override=debt_amount_override,
        product_overrides=product_overrides,
    )


