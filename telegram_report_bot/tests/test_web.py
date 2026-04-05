from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from employee_report_bot.web import create_app


class WebAppTests(unittest.TestCase):
    def test_landing_page_renders(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            data_dir = base_dir / "data"
            data_dir.mkdir()

            env = {
                "TELEGRAM_BOT_TOKEN": "testtoken",
                "TELEGRAM_BOT_USERNAME": "test_bot",
                "WEB_BASE_URL": "https://example.com",
                "WEB_DOMAIN": "example.com",
                "WEB_SESSION_SECRET": "secret",
                "ADMIN_USER_IDS": "",
                "REPORTS_XLSX_PATH": "data/reports.xlsx",
                "REPORT_TIMEZONE": "Europe/Moscow",
                "DEFAULT_LANGUAGE": "ru",
                "WHISPER_MODEL": "small",
                "WHISPER_DEVICE": "cpu",
                "WHISPER_COMPUTE_TYPE": "int8",
                "DATABASE_URL": "",
            }

            with patch("employee_report_bot.config.ENV_PATH", base_dir / ".env"), patch.dict(
                "os.environ",
                env,
                clear=True,
            ):
                client = TestClient(create_app())
                response = client.get("/")

            self.assertEqual(response.status_code, 200)
            self.assertIn("ServiceTex Control Center", response.text)


if __name__ == "__main__":
    unittest.main()
