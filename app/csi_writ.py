from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageDraw

from app.claim_pdf_service import load_claim_crm_context, resolve_claim_client_contacts, resolve_claim_requisites
from app.common_utils import format_date, normalize_text, parse_date_value
from app.document_helpers import build_company_payment_detail_lines
from app.financial_helpers import format_money
from app.lawsuit_pdf_renderers import SERIF_FONT_BOLD_CANDIDATES, SERIF_FONT_REGULAR_CANDIDATES
from app.money_words import money_to_words_ru
from app.pdf_rendering import load_font, wrap_text
from app.schemas import CsiDispatchPdfRequest, CsiWritPdfRequest


@dataclass(frozen=True)
class Block:
    text: str
    bold: bool = False
    align: str = "left"
    indent: bool = True
    gap: int = 14


def court_in_case(name: str, *, instrumental: bool = False) -> str:
    # Decline only the court's head and its adjectives, not the locality/region after it.
    match = re.search(r"\bсуд\b", name, re.IGNORECASE)
    if not match:
        return name

    def adjective(item):
        word = item.group()
        lowered = word.lower()
        if lowered.endswith(("кий", "кой", "гий", "гой", "хий", "хой")):
            ending = "им" if instrumental else "ого"
        elif lowered.endswith("ний"):
            ending = "им" if instrumental else "его"
        elif lowered.endswith(("ый", "ой")):
            ending = "ым" if instrumental else "ого"
        else:
            return word
        return word[:-2] + (ending.upper() if word.isupper() else ending)

    prefix = re.sub(r"[А-Яа-яЁё]+", adjective, name[:match.start()])
    noun = "судом" if instrumental else "суда"
    if match.group().isupper():
        noun = noun.upper()
    elif match.group()[0].isupper():
        noun = noun.capitalize()
    return prefix + noun + name[match.end():]


def validate_writ_debtor(debtor: dict, payments: list[dict]) -> tuple[Decimal, Decimal]:
    if debtor.get("country") != "kz":
        raise HTTPException(400, "Этот шаблон заявления предназначен для Казахстана.")
    if not debtor.get("csi_transferred_at"):
        raise HTTPException(400, "Заявление доступно только для клиентов в разделе ЧСИ.")
    missing = [label for key, label in (("court", "Суд по делу"), ("case_number", "Номер дела"),
                                      ("hearing_date", "Дата заседания")) if not normalize_text(debtor.get(key))]
    if missing:
        raise HTTPException(400, "Заполните поля: " + ", ".join(missing) + ".")
    try:
        hearing_date = parse_date_value(debtor.get("hearing_date"))
    except (ValueError, TypeError):
        hearing_date = None
    if not hearing_date:
        raise HTTPException(400, "Дата заседания заполнена некорректно.")
    payout = Decimal(str(debtor.get("decision_payout") or 0)).quantize(Decimal("0.01"))
    paid = sum((Decimal(str(item.get("amount") or 0)) for item in payments), Decimal("0")).quantize(Decimal("0.01"))
    if payout <= 0:
        raise HTTPException(400, "Укажите сумму выплаты по решению.")
    if payout <= paid:
        raise HTTPException(400, "Задолженность по решению полностью погашена.")
    return payout, payout - paid


def build_csi_header(debtor: dict, requisites: dict, crm: dict, *, include_bank: bool = True,
                     client_tax_label: str = "ИНН") -> list[Block]:
    company = requisites.get("company_name") or debtor["company"]
    contacts = resolve_claim_client_contacts(debtor, crm)
    client = contacts["client_name"]
    header = [normalize_text(debtor["court"])]
    if debtor.get("court_address"):
        header.append(normalize_text(debtor["court_address"]))
    header += ["", f"Истец: {company}", str(requisites.get("address") or "")]
    if include_bank:
        header += build_company_payment_detail_lines(requisites)
    elif requisites.get("bin"):
        header.append(str(requisites["bin"]))
    if requisites.get("phone"):
        header.append(f"Телефон: {requisites['phone']}")
    header += ["", f"Ответчик: {client}", f"{client_tax_label}: {normalize_text(crm.get('client_inn')) or '—'}",
               contacts["client_address"], f"Номер телефона: {contacts['client_phone']}", "", f"Дело №: {debtor['case_number']}"]
    return [Block(line, align="header", indent=False, gap=0) for line in header]


def build_writ_blocks(debtor: dict, payments: list[dict], payload: CsiWritPdfRequest,
                      requisites: dict, crm: dict, *, today: date | None = None) -> list[Block]:
    payout, remaining = validate_writ_debtor(debtor, payments)
    company = requisites.get("company_name") or debtor["company"]
    client = resolve_claim_client_contacts(debtor, crm)["client_name"]
    court = normalize_text(debtor["court"])
    court_genitive = court_in_case(court)
    court_instrumental = court_in_case(court, instrumental=True)
    hearing = format_date(parse_date_value(debtor["hearing_date"]))
    case = normalize_text(debtor["case_number"])
    blocks = build_csi_header(debtor, requisites, crm)
    blocks += [
        Block("ЗАЯВЛЕНИЕ", bold=True, align="center", indent=False, gap=4),
        Block("о выдаче исполнительного листа\nдля принудительного исполнения медиативного соглашения\n"
              "и его направлении частному судебному исполнителю", bold=True, align="center", indent=False, gap=20),
        Block(f"Определением, вынесенным {court_instrumental} об утверждении соглашения об урегулировании спора "
              f"в порядке медиации от {hearing}, было утверждено соглашение об урегулировании спора в порядке "
              f"медиации по гражданскому делу № {case} по иску {company} (далее - Истец), к {client} "
              "(далее - Ответчик) о взыскании суммы задолженности (далее - Соглашение)."),
        Block(f"Согласно пункту 1 Соглашения, Ответчик обязался полностью выплатить Истцу долг в размере "
              f"{format_money(payout)} ({money_to_words_ru(payout)}) согласно установленному Соглашением графику."),
        Block("Определение суда, которым утверждено Соглашение, вступило в законную силу."),
        Block("В соответствии с частью 4 статьи 180 ГПК РК, исполнение соглашения об урегулировании спора "
              "(конфликта) в порядке медиации, утвержденного судом, производится по правилам исполнения мирового "
              "соглашения, установленным статьей 178 ГПК РК. В соответствии с частью 1 статьи 178 ГПК РК, мировое "
              "соглашение исполняется лицами, его заключившими, добровольно в порядке и сроки, которые предусмотрены "
              "этим соглашением. Но Ответчик нарушил установленное Соглашением обязательство по уплате долга, "
              "и до настоящего времени по медиативному соглашению Истцу поступило:"),
    ]
    for item in payments:
        payment_date = format_date(parse_date_value(item.get("payment_date_iso"))) or item.get("payment_date") or "Дата не указана"
        blocks.append(Block(f"{payment_date} - {format_money(item['amount'])} тенге.", indent=False, gap=4))
    if not payments:
        blocks.append(Block("Платежи не поступали.", indent=False))
    else:
        blocks.append(Block("Больше платежей не поступало."))
    blocks += [
        Block(f"На дату направления настоящего заявления за Ответчиком числится задолженность в размере "
              f"{format_money(remaining)} ({money_to_words_ru(remaining)}).", bold=True),
        Block("В соответствии с Определением суда, Соглашение об урегулировании спора (конфликта) в порядке "
              "медиации, не исполненное добровольно, подлежит принудительному исполнению на основании "
              "исполнительного листа, выдаваемого судом. Таким образом, Истец имеет право обратиться в суд "
              "для получения исполнительного листа о взыскании всей суммы задолженности, указанной в Соглашении "
              "в принудительном порядке."),
        Block("На основании части 2 статьи 178 ГПК РК, мировое соглашение, не исполненное добровольно, "
              "подлежит принудительному исполнению на основании исполнительного листа, выдаваемого судом "
              "по ходатайству лица, заключившего мировое соглашение."),
        Block("Согласно части 4 статьи 241 ГПК РК, исполнительный лист выписывается судом первой инстанции "
              "в течение трех рабочих дней со дня вступления решения в законную силу."),
        Block("В соответствии с частью 5 статьи 241 ГПК РК, исполнительный лист выдается взыскателю либо "
              "по его заявлению направляется судом для исполнения в соответствующий орган юстиции либо "
              "в региональную палату частных судебных исполнителей по территориальности."),
        Block("На основании вышеизложенного,"),
        Block("просим суд:", bold=True, align="center", indent=False),
        Block(f"1. Выписать исполнительный лист на принудительное исполнение медиативного соглашения, "
              f"утвержденного определением судьи-медиатора {court_genitive} {payload.judge_name} от {hearing} "
              f"по гражданскому делу № {case} по иску {company} к {client} о взыскании суммы задолженности "
              f"на сумму долга в размере {format_money(remaining)} ({money_to_words_ru(remaining)}).", indent=False),
        Block("2. Исполнительный лист просим направить на исполнение в соответствующий орган юстиции либо "
              "в региональную палату частных судебных исполнителей по территориальности.", indent=False),
        Block("3. Сообщить адрес частного судебного исполнителя, которому направлен исполнительный лист "
              f"на исполнение по эл. почте: {payload.lawyer_email}", indent=False),
        Block(format_date(today or date.today()), indent=False),
        Block(f"Истец: {company}", indent=False),
        Block(f"Директор: {requisites.get('director_name') or '—'} __________________", indent=False),
    ]
    return blocks


def build_dispatch_blocks(debtor: dict, payments: list[dict], payload: CsiDispatchPdfRequest,
                          requisites: dict, crm: dict, *, today: date | None = None) -> list[Block]:
    validate_writ_debtor(debtor, payments)
    company = requisites.get("company_name") or debtor["company"]
    client = resolve_claim_client_contacts(debtor, crm)["client_name"]
    court = normalize_text(debtor["court"])
    hearing = format_date(parse_date_value(debtor["hearing_date"]))
    case = normalize_text(debtor["case_number"])
    outcome = {
        "Удовлетворить": ", которым исковые требования были удовлетворены",
        "Частично": ", которым исковые требования были удовлетворены частично",
    }.get(debtor.get("decision"), "")
    # Party labels keep Kazakh personal names unchanged instead of guessing their declension.
    parties = f"истец - {company}; ответчик - {client}"
    blocks = build_csi_header(debtor, requisites, crm, include_bank=False, client_tax_label="ИИН")
    blocks += [
        Block("ЗАЯВЛЕНИЕ", bold=True, align="center", indent=False, gap=4),
        Block("о направлении исполнительного листа судебному исполнителю",
              align="center", indent=False, gap=20),
        Block(f"{court} {hearing} принял решение по гражданскому делу № {case} "
              f"({parties}) о взыскании задолженности{outcome}."),
        Block("Для принудительного исполнения решения суда необходимо выдать исполнительный лист. "
              "Исполнительный лист просим направить частному судебному исполнителю и сообщить адрес "
              "частного судебного исполнителя, которому направлен исполнительный лист на исполнение."),
        Block("Реквизиты для оплаты:", bold=True),
    ]
    for line in build_company_payment_detail_lines(requisites):
        blocks.append(Block(line, indent=False, gap=0))
    if requisites.get("kbe"):
        blocks.append(Block(f"КБЕ: {requisites['kbe']}", indent=False, gap=0))
    blocks += [
        Block("На основании изложенного, руководствуясь статьей 241 Гражданского процессуального кодекса РК,"),
        Block("Прошу суд:", align="center", indent=False),
        Block(f"1. Выдать исполнительный лист по решению суда по гражданскому делу № {case} "
              f"о взыскании задолженности ({parties}).", indent=False),
        Block("2. Исполнительный лист просим направить на исполнение в соответствующий орган юстиции "
              "либо в региональную палату частных судебных исполнителей по территориальности.", indent=False),
        Block("3. Сообщить адрес частного судебного исполнителя, которому направлен исполнительный лист "
              f"на исполнение по эл. почте: {payload.lawyer_email}.", indent=False),
        Block(format_date(today or date.today()), indent=False, gap=90),
        Block(f"Истец: {company}", indent=False),
        Block(f"Директор: {requisites.get('director_name') or '—'} __________________", indent=False),
    ]
    return blocks


def render_writ_pages(blocks: list[Block]) -> list[Image.Image]:
    width, height = 1654, 2339
    left, right, top, bottom = 112, 112, 85, 85
    body_width = width - left - right
    fonts = {bold: load_font(28, bold=bold, regular_candidates=SERIF_FONT_REGULAR_CANDIDATES,
                             bold_candidates=SERIF_FONT_BOLD_CANDIDATES) for bold in (False, True)}
    line_height = 36
    pages = [Image.new("RGB", (width, height), "white")]
    draw = ImageDraw.Draw(pages[-1])
    y = top
    last_align = None
    for index, block in enumerate(blocks):
        if index == len(blocks) - 3:
            signature_height = sum(
                len(wrap_text(draw, tail.text, fonts[tail.bold], body_width)) * line_height + tail.gap
                for tail in blocks[index:]
            )
            if signature_height <= height - top - bottom and y + signature_height > height - bottom:
                pages.append(Image.new("RGB", (width, height), "white"))
                draw = ImageDraw.Draw(pages[-1])
                y = top
        if last_align == "header" and block.align != "header":
            y += 28
        font = fonts[block.bold]
        block_width = 680 if block.align == "header" else body_width
        x = width - right - block_width if block.align == "header" else left
        for paragraph in block.text.split("\n"):
            # Wrap a first-line indent with the same width used to draw that line.
            remaining = " ".join(paragraph.split())
            first = True
            if not remaining:
                y += line_height // 2
            while remaining:
                indent = 42 if first and block.indent else 0
                lines = wrap_text(draw, remaining, font, block_width - indent)
                line = lines[0]
                remaining = remaining[len(line):].lstrip()
                if y + line_height > height - bottom:
                    pages.append(Image.new("RGB", (width, height), "white"))
                    draw = ImageDraw.Draw(pages[-1])
                    y = top
                line_x = x + indent
                if block.align == "center":
                    line_x = x + (block_width - draw.textlength(line, font=font)) / 2
                draw.text((line_x, y), line, fill="#111111", font=font)
                y += line_height
                first = False
        y += block.gap
        last_align = block.align
    return pages


def render_writ_pdf(debtor: dict, payments: list[dict], payload: CsiWritPdfRequest, *, generated_dir: Path) -> Path:
    validate_writ_debtor(debtor, payments)
    _, requisites, _ = resolve_claim_requisites(debtor, country="kz")
    crm = load_claim_crm_context(debtor, country="kz")
    blocks = build_writ_blocks(debtor, payments, payload, requisites, crm)
    return save_csi_pdf(blocks, debtor_id=debtor["id"], prefix="csi_writ", generated_dir=generated_dir)


def render_dispatch_pdf(debtor: dict, payments: list[dict], payload: CsiDispatchPdfRequest, *, generated_dir: Path) -> Path:
    validate_writ_debtor(debtor, payments)
    _, requisites, _ = resolve_claim_requisites(debtor, country="kz")
    crm = load_claim_crm_context(debtor, country="kz")
    blocks = build_dispatch_blocks(debtor, payments, payload, requisites, crm)
    return save_csi_pdf(blocks, debtor_id=debtor["id"], prefix="csi_dispatch", generated_dir=generated_dir)


def save_csi_pdf(blocks: list[Block], *, debtor_id: int, prefix: str, generated_dir: Path) -> Path:
    generated_dir.mkdir(parents=True, exist_ok=True)
    path = generated_dir / f"{prefix}_{debtor_id}_{uuid4().hex}.pdf"
    pages = render_writ_pages(blocks)
    try:
        pages[0].save(path, "PDF", resolution=200, save_all=True, append_images=pages[1:])
    finally:
        for page in pages:
            page.close()
    return path
