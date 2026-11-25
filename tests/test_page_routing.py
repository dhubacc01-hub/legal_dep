import hashlib
import json
import re
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import main


class PageRoutingTests(unittest.TestCase):
    def setUp(self):
        user = dict(id=1, username="test", full_name="Test", role="lawyer", must_change_password=0,
                    is_active=1, created_at="2026-11-25", updated_at="2026-11-25")
        self.enterContext(patch.object(main, "get_optional_current_user", return_value=user))
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def test_switching_pages_keeps_context_table_scripts_and_active_link_separate(self):
        for path, page, table, script in (
            ("/court-cases", "courts", "incoming-tbody", "court_cases.js"),
            ("/", "debtors", "debtors-tbody", "app.js"),
            ("/csi", "csi", "debtors-tbody", "app.js"),
            ("/incoming-correspondence", "incoming", "incoming-tbody", "incoming_correspondence.js"),
            ("/court-cases", "courts", "incoming-tbody", "court_cases.js"),
            ("/", "debtors", "debtors-tbody", "app.js"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.text
                context = json.loads(re.search(r"window\.__APP_CONTEXT__\s*=\s*(.*?);", html)[1])
                self.assertEqual(context["page"], page)
                self.assertIn(f'id="{table}"', html)
                other_table = "debtors-tbody" if table == "incoming-tbody" else "incoming-tbody"
                self.assertNotIn(f'id="{other_table}"', html)
                self.assertEqual(re.findall(r'<a class="nav-tab active" href="([^"]+)"', html), [path])
                self.assertIn(f"/static/{script}?v=", html)
                if page in {"debtors", "csi"}:
                    self.assertNotIn("/static/court_cases.js", html)
                elif page == "courts":
                    self.assertNotIn("/static/app.js", html)
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_csi_has_writ_headers_without_changing_debtors_headers(self):
        for path in ("/csi", "/", "/csi"):
            with self.subTest(path=path):
                html = self.client.get(path).text
                headers = re.findall(r"<th>(.*?)</th>", html)
                expected = (["Выдача исполнительного листа", "Направление исполнительного листа"]
                            if path == "/csi" else ["Генерация претензии", "Генерация иска"])
                self.assertEqual(headers[-3:-1], expected)
                self.assertEqual("/static/csi_documents.js?v=" in html, path == "/csi")
                self.assertEqual('id="csi-writ-form"' in html, path == "/csi")

    def test_assets_have_content_fingerprints_and_are_served_with_query_parameters(self):
        response = self.client.get("/court-cases")
        urls = re.findall(r'(?:src|href)="([^"]+/static/[^" ]+)"', response.text)
        self.assertEqual(len(urls), 5)
        for url in urls:
            parsed = urlparse(url)
            path = main.BASE_DIR / parsed.path.lstrip("/")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            self.assertEqual(parse_qs(parsed.query), {"v": [expected]})
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_login_html_is_not_cached(self):
        with patch.object(main, "get_optional_current_user", return_value=None):
            response = self.client.get("/")
        self.assertIn('id="login-form"', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
