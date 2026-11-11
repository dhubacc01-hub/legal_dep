import sqlite3
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import database, main


class CsiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.addCleanup(self.connection.close)
        with patch.object(database, "get_connection", return_value=self.connection):
            database.init_db()
        self.enterContext(patch.object(main, "get_connection", return_value=self.connection))
        self.enterContext(patch.dict(main.app.dependency_overrides, {
            main.require_app_user: lambda: {"id": 1, "role": "admin"},
        }))
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def add_debtor(self, country="uz", payout=100, received=0, marker=None, category=main.DEFAULT_CATEGORY):
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO debtors (
                    country, created_at, category, client_name, contract_number,
                    last_missed_payment_date, company, city, court, debt_amount,
                    claim_sent, lawsuit_sent, lawsuit_accepted, decision_exists,
                    decision, decision_payout, received_amount, csi_transferred_at
                ) VALUES (?, '2026-01-01', ?, 'Test client', '010125/1M-1',
                    '2025-01-01', 'Company', 'City', 'Court', 200000,
                    1, 1, 1, 1, ?, ?, ?, ?)
                """,
                (country, category, main.DECISION_SATISFY, payout, received, marker),
            )
        return cursor.lastrowid

    def update(self, debtor_id, **fields):
        response = self.client.patch(f"/api/debtors/{debtor_id}", json=fields)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def save_payments(self, debtor_id, *amounts):
        response = self.client.put(f"/api/debtors/{debtor_id}/received-payments", json={
            "payments": [{"payment_date": "2026-03-01", "amount": amount} for amount in amounts],
        })
        self.assertEqual(response.status_code, 200, response.text)

    def csi_record(self, debtor_id, country="uz"):
        response = self.client.get("/api/csi-debtors", params={"country": country})
        self.assertEqual(response.status_code, 200, response.text)
        return next(row for row in response.json() if row["id"] == debtor_id)

    def test_work_then_close_on_full_payment_or_overpayment(self):
        for country in ("kz", "uz"):
            with self.subTest(country=country):
                debtor_id = self.add_debtor(country=country)
                transferred = self.update(debtor_id, category=main.CATEGORY_TRANSFER_TO_CSI)
                marker = transferred["csi_transferred_at"]
                self.assertTrue(marker)
                self.assertIn(main.CSI_CATEGORY_IN_WORK, transferred["category_options"])
                self.assertNotIn(main.CSI_CATEGORY_CLOSED, transferred["category_options"])

                working = self.update(debtor_id, category=main.CSI_CATEGORY_IN_WORK)
                self.assertEqual(working["category"], main.CSI_CATEGORY_IN_WORK)
                self.assertEqual(working["csi_transferred_at"], marker)

                self.save_payments(debtor_id, 60, 39.99)
                self.assertEqual(self.csi_record(debtor_id, country)["category"], main.CSI_CATEGORY_IN_WORK)
                for last_payment in (40, 50):
                    self.save_payments(debtor_id, 60, last_payment)
                    closed = self.csi_record(debtor_id, country)
                    self.assertEqual(closed["category"], main.CSI_CATEGORY_CLOSED)
                    self.assertEqual(closed["category_options"], [main.CSI_CATEGORY_CLOSED])
                    self.assertTrue(closed["category_is_auto"])
                    self.assertTrue(closed["category_is_locked"])
                    self.assertEqual(closed["csi_transferred_at"], marker)
                    debtors = self.client.get("/api/debtors", params={"country": country}).json()
                    self.assertNotIn(debtor_id, [row["id"] for row in debtors])

                self.save_payments(debtor_id, 60)
                self.assertEqual(self.csi_record(debtor_id, country)["category"], main.CSI_CATEGORY_IN_WORK)

    def test_existing_paid_record_and_payout_corrections(self):
        marker = "2026-02-01T00:00:00"
        debtor_id = self.add_debtor(received=100, marker=marker, category=main.CATEGORY_TRANSFER_TO_CSI)
        self.assertEqual(self.csi_record(debtor_id)["category"], main.CSI_CATEGORY_CLOSED)

        denied = self.client.patch(f"/api/debtors/{debtor_id}", json={"category": "Не должник"})
        self.assertEqual(denied.status_code, 400)
        updated = self.update(debtor_id, decision_payout=100.01)
        self.assertEqual(updated["category"], main.CATEGORY_TRANSFER_TO_CSI)
        updated = self.update(debtor_id, decision_payout=99.99)
        self.assertEqual(updated["category"], main.CSI_CATEGORY_CLOSED)
        self.assertEqual(updated["csi_transferred_at"], marker)

    def test_zero_payout_does_not_close_case(self):
        debtor_id = self.add_debtor(payout=0, marker="2026-02-01", category=main.CATEGORY_TRANSFER_TO_CSI)
        self.assertEqual(self.csi_record(debtor_id)["category"], main.CATEGORY_TRANSFER_TO_CSI)
        self.save_payments(debtor_id, 100)
        self.assertEqual(self.csi_record(debtor_id)["category"], main.CATEGORY_TRANSFER_TO_CSI)

    def test_csi_categories_cannot_be_manually_set_outside_csi(self):
        debtor_id = self.add_debtor(received=100)
        for category in (main.CSI_CATEGORY_IN_WORK, main.CSI_CATEGORY_CLOSED):
            response = self.client.patch(f"/api/debtors/{debtor_id}", json={"category": category})
            self.assertEqual(response.status_code, 400)
        row = self.client.get("/api/debtors?country=uz").json()[0]
        self.assertEqual(row["category"], main.CATEGORY_DEBT_CLOSED)
        self.assertNotIn(main.CSI_CATEGORY_IN_WORK, row["category_options"])

    def test_unpaid_case_can_still_return_to_debtors(self):
        debtor_id = self.add_debtor(marker="2026-02-01", category=main.CSI_CATEGORY_IN_WORK)
        denied = self.client.patch(f"/api/debtors/{debtor_id}", json={"category": main.CSI_CATEGORY_CLOSED})
        self.assertEqual(denied.status_code, 400)
        row = self.update(debtor_id, category="Не должник")
        self.assertEqual(row["category"], "Не должник")
        self.assertIsNone(row["csi_transferred_at"])
        self.assertEqual(self.client.get("/api/csi-debtors?country=uz").json(), [])
