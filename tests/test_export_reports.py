from contextlib import closing
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import database, main
from app.export_reports import payment_report, render_pdf, table_report


class ExportReportsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.db_path = self.output / "test.sqlite3"
        self.db_patch = patch.object(database, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.directory_patch = patch.object(main, "GENERATED_DIR", self.output / "generated")
        self.directory_patch.start()
        self.addCleanup(self.directory_patch.stop)
        with closing(database.get_connection()) as schema_connection:
            with patch.object(database, "get_connection", return_value=schema_connection):
                database.init_db()
        with closing(database.get_connection()) as connection, connection:
            for debtor_id, country, transferred in ((1, "kz", None), (2, "kz", None), (3, "uz", None), (4, "kz", "2026-01-01"), (5, "uz", "2026-01-01")):
                connection.execute(
                    """INSERT INTO debtors (id, country, created_at, client_name, contract_number,
                    last_missed_payment_date, company, city, court, debt_amount, csi_transferred_at)
                    VALUES (?, ?, '2026-01-01', ?, ?, '2025-01-01', 'Test company', 'City', 'Court', 200000, ?)""",
                    (debtor_id, country, f"Client {debtor_id}", f"010125/1M-{debtor_id}", transferred),
                )
                for payment_date, amount in (("2026-02-28", 999), ("2026-03-01", 10.25), ("2026-03-31", 20.75), ("2026-04-01", 999), ("", 777)):
                    connection.execute("INSERT INTO debtor_received_payments (debtor_id, payment_date, amount) VALUES (?, ?, ?)", (debtor_id, payment_date, amount))
            for record_id, country, category in ((1, "kz", "Претензия"), (2, "kz", "Иск"), (3, "uz", "Претензия"), (4, "uz", "Иск")):
                connection.execute(
                    """INSERT INTO incoming_correspondence (id, country, created_at, updated_at, category,
                    received_date, receive_method, company, client_name, authority_kind, contract_number,
                    response_text, response_date, comment)
                    VALUES (?, ?, '2026-01-01', '2026-01-01', ?, '2026-03-01', 'Почта', 'Company', ?, 'other', ?, 'Отказ', '2026-03-02', ?)""",
                    (record_id, country, category, f"Letter client {record_id}", f"0000{record_id}", '=HYPERLINK("http://example.com")'),
                )
        main.app.dependency_overrides[main.require_app_user] = lambda: {"id": 1, "role": "admin"}
        self.addCleanup(main.app.dependency_overrides.pop, main.require_app_user)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def request_export(self, **changes):
        payload = dict(source="debtors", country="kz", format="xlsx", record_ids=[1], report="table")
        payload.update(changes)
        return self.client.post("/api/exports", json=payload)

    def workbook(self, response):
        self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else "")
        workbook = load_workbook(BytesIO(response.content))
        self.addCleanup(workbook.close)
        return workbook.active

    def test_table_exports_only_selected_rows_with_numbers_and_dates(self):
        sheet = self.workbook(self.request_export(record_ids=[2]))
        self.assertEqual(sheet["D6"].value, "Client 2")
        self.assertEqual(sheet["E6"].value, "010125/1M-2")
        self.assertIsInstance(sheet["A6"].value, datetime)
        self.assertEqual(sheet["A6"].number_format, "dd.mm.yyyy")
        self.assertEqual(sheet["N6"].value, 200000)
        self.assertEqual(sheet["N7"].value, 200000)
        self.assertEqual(sheet["D7"].value, None)
        self.assertEqual(sheet.freeze_panes, "A6")
        self.assertEqual(sheet.auto_filter.ref, "A5:AB6")

    def test_countries_and_csi_are_separate(self):
        for source, country, row_id in (("debtors", "kz", 1), ("debtors", "uz", 3), ("csi", "kz", 4), ("csi", "uz", 5)):
            with self.subTest(source=source, country=country):
                sheet = self.workbook(self.request_export(source=source, country=country, record_ids=[row_id]))
                self.assertEqual(sheet["D6"].value, f"Client {row_id}")
        self.assertEqual(self.request_export(record_ids=[3]).status_code, 409)
        self.assertEqual(self.request_export(record_ids=[4]).status_code, 409)

    def test_payments_use_period_inclusively_and_filter_debtor_ids(self):
        for source, country, row_id in (("debtors", "kz", 1), ("debtors", "uz", 3), ("csi", "kz", 4), ("csi", "uz", 5)):
            with self.subTest(source=source, country=country):
                sheet = self.workbook(self.request_export(source=source, country=country, record_ids=[row_id], report="payments", date_from="2026-03-01", date_to="2026-03-31"))
                self.assertEqual(sheet["A4"].value, "Поступлений: 2")
                self.assertEqual(sheet["B5"].value, 31)
                self.assertEqual(sheet["C8"].value, f"Client {row_id}")
                self.assertEqual(sheet["D8"].value, 10.25)
                self.assertEqual(sheet["D9"].value, 20.75)
                self.assertEqual(sheet["D10"].value, 31)
                self.assertIsInstance(sheet["A8"].value, datetime)
                self.assertEqual(sheet["A8"].number_format, "dd.mm.yyyy")

    def test_correspondence_tabs_and_formula_like_text(self):
        for source, country, row_id in (("incoming_claims", "kz", 1), ("incoming_other", "kz", 2), ("incoming_claims", "uz", 3), ("incoming_other", "uz", 4)):
            with self.subTest(source=source, country=country):
                sheet = self.workbook(self.request_export(source=source, country=country, record_ids=[row_id]))
                self.assertEqual(sheet["D6"].value, f"Letter client {row_id}")
                self.assertEqual(sheet["F6"].value, f"0000{row_id}")
                if source == "incoming_claims":
                    self.assertEqual(sheet["K6"].data_type, "s")
                    self.assertTrue(sheet["K6"].value.startswith("=HYPERLINK"))
        self.assertEqual(self.request_export(source="incoming_claims", record_ids=[2]).status_code, 409)
        self.assertEqual(self.request_export(source="incoming_claims", record_ids=[1], report="payments").status_code, 400)

    def test_empty_filter_selection_exports_zero_rows(self):
        sheet = self.workbook(self.request_export(record_ids=[]))
        self.assertEqual(sheet["A3"].value, "Записей: 0")
        self.assertEqual(sheet["N6"].value, 0)
        self.assertNotIn("Client 1", [cell.value for row in sheet for cell in row])

    def test_no_pagination_limit_and_repeated_ids_not_double_counted(self):
        with closing(database.get_connection()) as connection, connection:
            for debtor_id in range(10, 65):
                connection.execute("INSERT INTO debtors (id,country,created_at,client_name,contract_number,last_missed_payment_date,company,city,court,debt_amount) VALUES (?, 'kz', '2026-01-01', ?, ?, '2025-01-01', 'Company', 'City', 'Court', 10)", (debtor_id, f"Client {debtor_id}", f"test-{debtor_id}"))
        sheet = self.workbook(self.request_export(record_ids=list(range(10, 65)) + [10]))
        self.assertEqual(sheet["A3"].value, "Записей: 55")
        self.assertEqual(sheet["D60"].value, "Client 64")
        self.assertEqual(sheet["N61"].value, 550)

    def test_child_shared_financials_not_double_counted(self):
        report = table_report("debtors", "kz", [
            {"id": 1, "client_name": "Parent", "debt_amount": 100, "received_amount": 10},
            {"id": 2, "parent_debtor_id": 1, "client_name": "Old", "debt_amount": 100, "received_amount": 5},
        ])
        self.assertEqual(report.rows[1]["client_name"], "Parent")
        self.assertIsNone(report.rows[1]["debt_amount"])
        self.assertEqual(report.totals()["debt_amount"], 100)
        self.assertEqual(report.totals()["received_amount"], 15)

    def test_invalid_period_and_stale_rows_rejected(self):
        self.assertEqual(self.request_export(record_ids=[999]).status_code, 409)
        self.assertEqual(self.request_export(report="payments").status_code, 400)
        self.assertEqual(self.request_export(report="payments", date_from="2026-04-01", date_to="2026-03-01").status_code, 400)

    def test_pdf_exports_all_sources(self):
        for source, country, row_id in (("debtors", "kz", 1), ("csi", "uz", 5), ("incoming_claims", "kz", 1), ("incoming_other", "uz", 4)):
            with self.subTest(source=source):
                response = self.request_export(source=source, country=country, record_ids=[row_id], format="pdf")
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(b"%PDF"))
                self.assertIn("application/pdf", response.headers["content-type"])

    def test_wide_table_has_one_landscape_a4_page_for_one_client(self):
        response = self.request_export(format="pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", response.content)), 1)
        media_box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", response.content)
        self.assertIsNotNone(media_box)
        self.assertAlmostEqual(float(media_box[1]), 842, delta=1)
        self.assertAlmostEqual(float(media_box[2]), 595, delta=1)

    def test_wide_table_continues_vertically_without_column_blocks(self):
        rows = [{"id": index, "client_name": f"Client {index}", "contract_number": f"contract-{index}", "debt_amount": 100} for index in range(100)]
        path = render_pdf(table_report("debtors", "kz", rows), self.output)
        # Incremental PDF saves can redefine page objects; the last page-tree count is authoritative.
        self.assertEqual(int(re.findall(rb"/Count\s+(\d+)", path.read_bytes())[-1]), 2)


if __name__ == "__main__":
    unittest.main()
