from __future__ import annotations

import hashlib
import hmac
import time
import unittest

from employee_report_bot.telegram_auth import verify_telegram_login


def _build_payload(bot_token: str, **overrides: str) -> dict[str, str]:
    payload = {
        "id": "123456789",
        "first_name": "Nikita",
        "username": "bratishka",
        "auth_date": str(int(time.time())),
    }
    payload.update(overrides)
    data_check_string = "\n".join(
        f"{key}={payload[key]}"
        for key in sorted(payload)
        if payload[key] not in ("", None)
    )
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    payload["hash"] = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return payload


class TelegramAuthTests(unittest.TestCase):
    def test_accepts_valid_payload(self) -> None:
        payload = _build_payload("bot-token")

        result = verify_telegram_login(payload, bot_token="bot-token")

        self.assertEqual(result["id"], 123456789)
        self.assertEqual(result["username"], "bratishka")

    def test_rejects_tampered_payload(self) -> None:
        payload = _build_payload("bot-token")
        payload["username"] = "evil"

        with self.assertRaises(ValueError):
            verify_telegram_login(payload, bot_token="bot-token")

    def test_rejects_expired_payload(self) -> None:
        payload = _build_payload(
            "bot-token",
            auth_date=str(int(time.time()) - 200000),
        )

        with self.assertRaises(ValueError):
            verify_telegram_login(payload, bot_token="bot-token", max_age_seconds=86400)


if __name__ == "__main__":
    unittest.main()
