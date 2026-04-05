from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    telegram_bot_username: str
    database_url: str | None
    admin_user_ids: set[int]
    web_base_url: str
    web_domain: str
    web_session_secret: str
    telegram_auth_max_age_seconds: int
    reports_xlsx_path: Path
    projects_path: Path
    download_dir: Path
    report_timezone: ZoneInfo
    default_language: str
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str


def load_settings() -> Settings:
    load_dotenv(ENV_PATH)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and set the bot token."
        )

    timezone_name = os.getenv("REPORT_TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        report_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown REPORT_TIMEZONE value: {timezone_name}") from exc

    reports_xlsx_raw = os.getenv("REPORTS_XLSX_PATH", "data/reports.xlsx").strip() or "data/reports.xlsx"
    reports_xlsx_path = (BASE_DIR / reports_xlsx_raw).resolve()
    projects_path = reports_xlsx_path.parent / "projects.json"
    download_dir = reports_xlsx_path.parent / "downloads"

    return Settings(
        telegram_bot_token=token,
        telegram_bot_username=os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@"),
        database_url=os.getenv("DATABASE_URL", "").strip() or None,
        admin_user_ids=_parse_admin_user_ids(os.getenv("ADMIN_USER_IDS", "")),
        web_base_url=_normalize_web_base_url(os.getenv("WEB_BASE_URL", "")),
        web_domain=_resolve_web_domain(
            os.getenv("WEB_DOMAIN", ""),
            os.getenv("WEB_BASE_URL", ""),
        ),
        web_session_secret=os.getenv("WEB_SESSION_SECRET", "").strip() or f"{token}:web",
        telegram_auth_max_age_seconds=_parse_positive_int(
            os.getenv("TELEGRAM_AUTH_MAX_AGE_SECONDS", "86400"),
            default=86400,
        ),
        reports_xlsx_path=reports_xlsx_path,
        projects_path=projects_path,
        download_dir=download_dir,
        report_timezone=report_timezone,
        default_language=os.getenv("DEFAULT_LANGUAGE", "ru").strip() or "ru",
        whisper_model=os.getenv("WHISPER_MODEL", "small").strip() or "small",
        whisper_device=os.getenv("WHISPER_DEVICE", "cpu").strip() or "cpu",
        whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip() or "int8",
    )


def _parse_admin_user_ids(raw_value: str) -> set[int]:
    admin_user_ids: set[int] = set()
    if not raw_value.strip():
        return admin_user_ids

    for chunk in raw_value.split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            admin_user_ids.add(int(value))
        except ValueError as exc:
            raise ValueError(
                "ADMIN_USER_IDS must contain comma-separated Telegram numeric user ids."
            ) from exc

    return admin_user_ids


def _normalize_web_base_url(raw_value: str) -> str:
    return raw_value.strip().rstrip("/")


def _resolve_web_domain(raw_domain: str, raw_base_url: str) -> str:
    domain = raw_domain.strip().lower()
    if domain:
        return domain

    base_url = _normalize_web_base_url(raw_base_url)
    if not base_url:
        return ""

    return (urlparse(base_url).hostname or "").lower()


def _parse_positive_int(raw_value: str, default: int) -> int:
    try:
        value = int((raw_value or "").strip())
    except ValueError:
        return default
    return value if value > 0 else default
