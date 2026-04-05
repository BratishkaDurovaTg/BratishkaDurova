from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping


ALLOWED_LOGIN_FIELDS = (
    "auth_date",
    "first_name",
    "id",
    "last_name",
    "photo_url",
    "username",
)


def verify_telegram_login(
    payload: Mapping[str, str],
    *,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> dict[str, str | int]:
    received_hash = (payload.get("hash") or "").strip()
    if not received_hash:
        raise ValueError("Missing Telegram login hash.")

    auth_date_raw = (payload.get("auth_date") or "").strip()
    if not auth_date_raw:
        raise ValueError("Missing Telegram login auth_date.")

    try:
        auth_date = int(auth_date_raw)
    except ValueError as exc:
        raise ValueError("Invalid Telegram login auth_date.") from exc

    if int(time.time()) - auth_date > max_age_seconds:
        raise ValueError("Telegram login data has expired.")

    normalized_payload = {
        key: str(value)
        for key, value in payload.items()
        if key in ALLOWED_LOGIN_FIELDS and value not in (None, "")
    }
    data_check_string = "\n".join(
        f"{key}={normalized_payload[key]}"
        for key in sorted(normalized_payload)
    )

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Telegram login signature mismatch.")

    user_id_raw = (payload.get("id") or "").strip()
    if not user_id_raw:
        raise ValueError("Missing Telegram user id.")

    try:
        user_id = int(user_id_raw)
    except ValueError as exc:
        raise ValueError("Invalid Telegram user id.") from exc

    return {
        "id": user_id,
        "first_name": (payload.get("first_name") or "").strip(),
        "last_name": (payload.get("last_name") or "").strip(),
        "username": (payload.get("username") or "").strip(),
        "photo_url": (payload.get("photo_url") or "").strip(),
        "auth_date": auth_date,
    }
