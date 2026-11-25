import re
import sqlite3
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import csi_writ, database, main
from app.schemas import CsiDispatchPdfRequest, CsiWritPdfRequest


DEBTOR = dict(id=1, country="kz", csi_transferred_at="2026-11-01", company='ТОО «SMstore»',
              client_name="Иванов Иван Иванович", contract_number="010125/1M-12", court="Павлодарский городской суд Павлодарской области",
              case_number="5510-26-00-2/123", hearing_date="2026-10-10", decision_payout=189000.50,
              received_amount=99999, address="г. Павлодар, улица Тестовая, 1", mobile_phone="87771234567")
REQUISITES = dict(company_name='ТОО «SMstore»', director_name="Кәгіліков Нұрсұлтан Дәнешұлы",
                  address="г. Алматы, улица Тестовая, 2", bin="БИН: 210640003564", iik="KZ123456789",
                  bank_name="Банк", bik="TESTKZ", phone="87770000000")
CRM = dict(client_inn="900101123456", client_phones=["87771234567", "87777654321"])
PAYMENTS = [dict(payment_date_iso="2026-11-01", amount=10000.25), dict(payment_date_iso="2026-11-10", amount=20000.25)]
PAYLOAD = CsiWritPdfRequest(judge_name="Судья Тестов Тест Тестович", lawyer_email="lawyer@example.com")


class CsiWritTests(unittest.TestCase):
    def test_dispatch_template_uses_current_company_client_and_decision_date(self):
        payload = CsiDispatchPdfRequest(lawyer_email="dispatch@example.com")
        blocks = csi_writ.build_dispatch_blocks({**DEBTOR, "decision": "Удовлетворить"}, PAYMENTS, payload,
                                               {**REQUISITES, "kbe": "17"}, CRM, today=date(2026, 11, 25))
        text = "\n".join(block.text for block in blocks)
        for expected in (DEBTOR["court"], "10.10.2026 принял решение", DEBTOR["case_number"], DEBTOR["client_name"],
                         REQUISITES["company_name"], REQUISITES["director_name"], REQUISITES["iik"], REQUISITES["bik"],
                         "КБЕ: 17", "ИИН: 900101123456", "87771234567, 87777654321", "dispatch@example.com", "25.11.2026",
                         "о направлении исполнительного листа судебному исполнителю", "требования были удовлетворены"):
            self.assertIn(expected, text)
        for stale in ("Конырбаев", "3166-26-00-2/2383", "170840012769", "Омарова", "медиации", PAYLOAD.judge_name):
            self.assertNotIn(stale, text)
        self.assertEqual([block.text[:2] for block in blocks if re.match(r"^[1-3]\.", block.text)], ["1.", "2.", "3."])
        self.assertIn("__________________", blocks[-1].text)
        self.assertTrue(all(isinstance(block, csi_writ.Block) for block in blocks))

    def test_dispatch_partial_decision_and_other_company_do_not_use_static_template_details(self):
        payload = CsiDispatchPdfRequest(lawyer_email="second@example.com")
        blocks = csi_writ.build_dispatch_blocks({**DEBTOR, "decision": "Частично"}, [], payload,
                                               {**REQUISITES, "company_name": "Другая компания", "director_name": "Другой директор"}, {})
        text = "\n".join(block.text for block in blocks)
        self.assertIn("требования были удовлетворены частично", text)
        self.assertIn("Другая компания", text)
        self.assertIn("Другой директор", text)
        self.assertNotIn(REQUISITES["company_name"], text)
        self.assertNotIn(REQUISITES["director_name"], text)
        blocks = csi_writ.build_dispatch_blocks(DEBTOR, [], payload, REQUISITES, {})
        self.assertNotIn("требования были удовлетворены", "\n".join(block.text for block in blocks))

    def test_dispatch_renderer_stays_on_a4_without_a_stamp_or_signature_image(self):
        blocks = csi_writ.build_dispatch_blocks(DEBTOR, PAYMENTS, CsiDispatchPdfRequest(lawyer_email="a@example.com"), REQUISITES, CRM)
        with patch.object(csi_writ.Image.Image, "paste", side_effect=AssertionError("No stamp or signature assets")):
            pages = csi_writ.render_writ_pages(blocks)
        try:
            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].size, (1654, 2339))
        finally:
            for page in pages:
                page.close()

    def test_template_amounts_payments_contacts_and_signature(self):
        blocks = csi_writ.build_writ_blocks(DEBTOR, PAYMENTS, PAYLOAD, REQUISITES, CRM, today=date(2026, 11, 25))
        text = "\n".join(block.text for block in blocks)
        for expected in ("189 000,50", "159 000,00", "сто пятьдесят девять тысяч тенге",
                         "01.11.2026 - 10 000,25", "10.11.2026 - 20 000,25", "900101123456",
                         "87771234567, 87777654321", REQUISITES["director_name"], "lawyer@example.com", "25.11.2026"):
            self.assertIn(expected, text)
        self.assertIn("вынесенным Павлодарским городским судом Павлодарской области", text)
        self.assertIn("судьи-медиатора Павлодарского городского суда Павлодарской области", text)
        self.assertEqual(sum(block.text.startswith("1.") for block in blocks), 1)
        self.assertEqual(sum(block.text.startswith("2.") for block in blocks), 1)
        self.assertEqual(sum(block.text.startswith("3.") for block in blocks), 1)
        self.assertTrue(next(block for block in blocks if block.text.startswith("На дату")).bold)
        self.assertNotIn("<b>", text)

    def test_legacy_no_payments_and_optional_address(self):
        legacy = [dict(payment_date_iso=None, amount=12000, legacy=True)]
        blocks = csi_writ.build_writ_blocks({**DEBTOR, "court_address": "Адрес суда"}, legacy, PAYLOAD, REQUISITES, {})
        text = "\n".join(block.text for block in blocks)
        self.assertIn("Дата не указана - 12 000,00", text)
        self.assertIn("177 000,50", text)
        self.assertIn("Адрес суда", text)
        blocks = csi_writ.build_writ_blocks(DEBTOR, [], PAYLOAD, REQUISITES, {})
        self.assertIn("Платежи не поступали.", [block.text for block in blocks])

    def test_required_data_and_country_guards(self):
        for changes in (dict(country="uz"), dict(csi_transferred_at=None), dict(case_number=""), dict(court=""),
                        dict(hearing_date=None), dict(hearing_date="invalid"), dict(decision_payout=0)):
            with self.subTest(changes=changes), self.assertRaises(HTTPException) as raised:
                csi_writ.validate_writ_debtor({**DEBTOR, **changes}, PAYMENTS)
            self.assertEqual(raised.exception.status_code, 400)
        for amount in (189000.50, 200000):
            with self.assertRaises(HTTPException):
                csi_writ.validate_writ_debtor(DEBTOR, [dict(amount=amount)])
        self.assertEqual(csi_writ.validate_writ_debtor({**DEBTOR, "decision_payout": .3}, [dict(amount=.1), dict(amount=.1)])[1], Decimal("0.10"))

    def test_schema_trims_and_validates_form_fields(self):
        self.assertEqual(CsiWritPdfRequest(judge_name="  Судья Тестов  ", lawyer_email=" lawyer@example.com ").judge_name, "Судья Тестов")
        for changes in (dict(judge_name="  "), dict(lawyer_email="not-email"), dict(lawyer_email="a@b\n.com")):
            with self.assertRaises(ValidationError):
                CsiWritPdfRequest(**{**PAYLOAD.model_dump(), **changes})

    def test_court_inflection_preserves_geographical_names(self):
        self.assertEqual(csi_writ.court_in_case("Специализированный межрайонный экономический суд города Алматы"),
                         "Специализированного межрайонного экономического суда города Алматы")
        self.assertEqual(csi_writ.court_in_case("Суд № 2 города Астаны", instrumental=True), "Судом № 2 города Астаны")

    def test_renderer_wraps_long_tokens_and_stays_within_a4_margins(self):
        blocks = csi_writ.build_writ_blocks(DEBTOR, PAYMENTS, PAYLOAD, REQUISITES, CRM)
        # Exercise character wrapping without making the test or generated fixture enormous.
        blocks.insert(-3, csi_writ.Block("ф" * 1000))
        original = csi_writ.ImageDraw.ImageDraw.text
        positions = []

        def capture(draw, xy, text, *args, **kwargs):
            bounds = draw.textbbox(xy, text, font=kwargs["font"])
            positions.append(bounds)
            return original(draw, xy, text, *args, **kwargs)

        with patch.object(csi_writ.ImageDraw.ImageDraw, "text", capture):
            pages = csi_writ.render_writ_pages(blocks)
        try:
            self.assertGreaterEqual(len(pages), 2)
            self.assertLessEqual(len(pages), 4)
            for page in pages:
                self.assertEqual(page.size, (1654, 2339))
            for x0, y0, x1, y1 in positions:
                self.assertGreaterEqual(x0, 110)
                self.assertLessEqual(x1, 1544)
                self.assertGreaterEqual(y0, 85)
                self.assertLessEqual(y1, 2254)
        finally:
            for page in pages:
                page.close()


class CsiWritApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.addCleanup(self.connection.close)
        with patch.object(database, "get_connection", return_value=self.connection):
            database.init_db()
        self.enterContext(patch.object(main, "get_connection", return_value=self.connection))
        self.enterContext(patch.dict(main.app.dependency_overrides, {main.require_app_user: lambda: {"id": 1, "role": "admin"}}))
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.temporary = tempfile.TemporaryDirectory(dir=main.GENERATED_DIR)
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.enterContext(patch.object(main, "GENERATED_DIR", self.output))
        self.enterContext(patch.object(csi_writ, "resolve_claim_requisites", return_value=("SMstore", REQUISITES, REQUISITES["company_name"])))
        self.enterContext(patch.object(csi_writ, "load_claim_crm_context", return_value=CRM))
        with self.connection:
            self.connection.execute("""INSERT INTO debtors
                (id, country, created_at, category, client_name, contract_number, last_missed_payment_date,
                company, city, court, case_number, hearing_date, decision_payout, received_amount, csi_transferred_at)
                VALUES (1, 'kz', '2026-11-01', 'В работе', ?, ?, '2026-01-01', ?, 'Павлодар', ?, ?, ?, ?, ?, ?)""",
                tuple(DEBTOR[key] for key in ("client_name", "contract_number", "company", "court", "case_number", "hearing_date",
                                             "decision_payout", "received_amount", "csi_transferred_at")))

    def test_generate_pdf_reads_history_without_changing_debtor(self):
        for payment in PAYMENTS:
            self.connection.execute("INSERT INTO debtor_received_payments (debtor_id, payment_date, amount, created_at) VALUES (1, ?, ?, '2026-11-01')",
                                    (payment["payment_date_iso"], payment["amount"]))
        self.connection.commit()
        before = dict(self.connection.execute("SELECT * FROM debtors WHERE id=1").fetchone())
        with patch.object(csi_writ, "build_writ_blocks", wraps=csi_writ.build_writ_blocks) as build:
            response = self.client.post("/api/debtors/1/csi-writ-pdf", json=PAYLOAD.model_dump())
        self.assertEqual(response.status_code, 200, response.text[:150] if response.status_code != 200 else "")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(len(build.call_args.args[1]), 2)
        self.assertEqual(dict(self.connection.execute("SELECT * FROM debtors WHERE id=1").fetchone()), before)

    def test_api_not_found_input_auth_and_fully_paid(self):
        self.assertEqual(self.client.post("/api/debtors/999/csi-writ-pdf", json=PAYLOAD.model_dump()).status_code, 404)
        self.assertEqual(self.client.post("/api/debtors/1/csi-writ-pdf", json={}).status_code, 422)
        self.connection.execute("UPDATE debtors SET received_amount=decision_payout WHERE id=1")
        response = self.client.post("/api/debtors/1/csi-writ-pdf", json=PAYLOAD.model_dump())
        self.assertEqual(response.status_code, 400, response.text)
        with patch.dict(main.app.dependency_overrides, {}, clear=True), patch.object(main, "get_optional_current_user", return_value=None):
            self.assertEqual(self.client.post("/api/debtors/1/csi-writ-pdf", json=PAYLOAD.model_dump()).status_code, 401)

    def test_dispatch_pdf_accepts_email_without_judge_and_does_not_modify_data(self):
        before = dict(self.connection.execute("SELECT * FROM debtors WHERE id=1").fetchone())
        response = self.client.post("/api/debtors/1/csi-dispatch-pdf", json={"lawyer_email": "dispatch@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("csi_dispatch_1.pdf", response.headers["content-disposition"])
        self.assertEqual(dict(self.connection.execute("SELECT * FROM debtors WHERE id=1").fetchone()), before)

    def test_dispatch_guards_missing_data_country_and_auth(self):
        payload = {"lawyer_email": "a@example.com"}
        self.assertEqual(self.client.post("/api/debtors/999/csi-dispatch-pdf", json=payload).status_code, 404)
        for data in ({}, {"lawyer_email": "invalid"}):
            self.assertEqual(self.client.post("/api/debtors/1/csi-dispatch-pdf", json=data).status_code, 422)
        for field, value in (("country", "uz"), ("csi_transferred_at", None), ("court", ""), ("case_number", ""),
                             ("hearing_date", None), ("decision_payout", 0), ("received_amount", DEBTOR["decision_payout"])):
            original = self.connection.execute(f"SELECT {field} FROM debtors WHERE id=1").fetchone()[0]
            self.connection.execute(f"UPDATE debtors SET {field}=? WHERE id=1", (value,))
            with self.subTest(field=field):
                response = self.client.post("/api/debtors/1/csi-dispatch-pdf", json=payload)
                self.assertEqual(response.status_code, 400, response.text)
            self.connection.execute(f"UPDATE debtors SET {field}=? WHERE id=1", (original,))
        with patch.dict(main.app.dependency_overrides, {}, clear=True), patch.object(main, "get_optional_current_user", return_value=None):
            self.assertEqual(self.client.post("/api/debtors/1/csi-dispatch-pdf", json=payload).status_code, 401)


if __name__ == "__main__":
    unittest.main()
