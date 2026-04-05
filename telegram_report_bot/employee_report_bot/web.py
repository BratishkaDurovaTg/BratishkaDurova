from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .runtime import AppRuntime, create_runtime
from .telegram_auth import verify_telegram_login


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def create_app() -> FastAPI:
    runtime = create_runtime()
    app = FastAPI(title="ServiceTex Web")
    app.state.runtime = runtime
    app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.add_middleware(
        SessionMiddleware,
        secret_key=runtime.settings.web_session_secret,
        same_site="lax",
        https_only=runtime.settings.web_base_url.startswith("https://"),
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def landing(request: Request) -> Response:
        user = _get_current_user(request)
        if user is not None:
            return RedirectResponse(url="/app", status_code=302)

        return _render(
            request,
            "landing.html",
            runtime,
            user=None,
            page_title="ServiceTex Web",
            auth_error=None,
        )

    @app.get("/auth/telegram", response_class=HTMLResponse)
    async def telegram_auth(request: Request) -> Response:
        raw_payload = dict(request.query_params)
        try:
            user = verify_telegram_login(
                raw_payload,
                bot_token=runtime.settings.telegram_bot_token,
                max_age_seconds=runtime.settings.telegram_auth_max_age_seconds,
            )
        except ValueError as exc:
            return _render(
                request,
                "landing.html",
                runtime,
                user=None,
                page_title="ServiceTex Web",
                auth_error=str(exc),
            )

        request.session["telegram_user"] = user
        return RedirectResponse(url="/app", status_code=302)

    @app.get("/logout")
    async def logout(request: Request) -> Response:
        request.session.clear()
        return RedirectResponse(url="/", status_code=302)

    @app.get("/app", response_class=HTMLResponse)
    async def dashboard(request: Request) -> Response:
        user = _get_current_user(request)
        if user is None:
            return RedirectResponse(url="/", status_code=302)
        is_admin = _is_admin(runtime, user["id"])
        today = datetime.now(runtime.settings.report_timezone).date().isoformat()
        all_projects = runtime.project_store.list_projects()
        all_user_reports = runtime.report_store.get_user_reports(user["id"], limit=None)
        my_project_codes = {report["project_code"] for report in all_user_reports}
        today_total = 0
        parsed_total = 0
        project_cards: list[dict[str, str | int | bool]] = []

        for project_code in all_projects:
            today_reports = runtime.report_store.get_reports_for_date(today, project_code=project_code)
            today_total += len(today_reports)
            project_parsed_total = sum(1 for report in today_reports if report["parse_status"] == "parsed")
            parsed_total += project_parsed_total
            project_cards.append(
                {
                    "code": project_code,
                    "today_total": len(today_reports),
                    "parsed_total": project_parsed_total,
                    "needs_review": len(today_reports) - project_parsed_total,
                    "can_view": is_admin or project_code in my_project_codes,
                }
            )

        project_cards.sort(
            key=lambda project: (not bool(project["can_view"]), str(project["code"])),
        )

        return _render(
            request,
            "dashboard.html",
            runtime,
            user=user,
            page_title="ServiceTex Dashboard",
            is_admin=is_admin,
            today=today,
            today_total=today_total,
            parsed_total=parsed_total,
            review_total=today_total - parsed_total,
            project_cards=project_cards,
            my_reports=all_user_reports[:6],
            my_report_count=len(all_user_reports),
            recent_reports=runtime.report_store.list_recent_reports(limit=8) if is_admin else all_user_reports[:8],
        )

    @app.get("/projects/{project_code}", response_class=HTMLResponse)
    async def project_detail(request: Request, project_code: str) -> Response:
        user = _get_current_user(request)
        if user is None:
            return RedirectResponse(url="/", status_code=302)
        is_admin = _is_admin(runtime, user["id"])
        user_project_codes = {
            report["project_code"] for report in runtime.report_store.get_user_reports(user["id"], limit=None)
        }
        if project_code not in runtime.project_store.list_projects():
            return _render(
                request,
                "error.html",
                runtime,
                user=user,
                page_title="Project Not Found",
                is_admin=is_admin,
                error_title="Проект не найден",
                error_message="Такого проекта нет в базе.",
            )

        if not is_admin and project_code not in user_project_codes:
            return _render(
                request,
                "error.html",
                runtime,
                user=user,
                page_title="Access Denied",
                is_admin=is_admin,
                error_title="Доступ ограничен",
                error_message="Откройте проект, по которому у вас уже есть отчёты, или зайдите как администратор.",
            )

        today = datetime.now(runtime.settings.report_timezone).date().isoformat()
        today_reports = runtime.report_store.get_reports_for_date(today, project_code=project_code)
        recent_reports = runtime.report_store.list_recent_reports(limit=20, project_code=project_code)
        parsed_total = sum(1 for report in today_reports if report["parse_status"] == "parsed")

        return _render(
            request,
            "project.html",
            runtime,
            user=user,
            page_title=f"Project {project_code}",
            is_admin=is_admin,
            project_code=project_code,
            today=today,
            today_reports=today_reports,
            recent_reports=recent_reports,
            parsed_total=parsed_total,
            review_total=len(today_reports) - parsed_total,
        )

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_dashboard(request: Request) -> Response:
        user = _get_current_user(request)
        if user is None:
            return RedirectResponse(url="/", status_code=302)
        is_admin = _is_admin(runtime, user["id"])
        if not is_admin:
            return _render(
                request,
                "error.html",
                runtime,
                user=user,
                page_title="Access Denied",
                is_admin=is_admin,
                error_title="Только для админа",
                error_message="Эта страница доступна только администраторам системы.",
            )

        today = datetime.now(runtime.settings.report_timezone).date().isoformat()
        project_cards: list[dict[str, str | int]] = []
        today_total = 0
        parsed_total = 0

        for project_code in runtime.project_store.list_projects():
            today_reports = runtime.report_store.get_reports_for_date(today, project_code=project_code)
            project_parsed_total = sum(1 for report in today_reports if report["parse_status"] == "parsed")
            today_total += len(today_reports)
            parsed_total += project_parsed_total
            project_cards.append(
                {
                    "code": project_code,
                    "today_total": len(today_reports),
                    "parsed_total": project_parsed_total,
                    "review_total": len(today_reports) - project_parsed_total,
                }
            )

        return _render(
            request,
            "admin.html",
            runtime,
            user=user,
            page_title="Admin Control",
            is_admin=is_admin,
            today=today,
            today_total=today_total,
            parsed_total=parsed_total,
            review_total=today_total - parsed_total,
            project_cards=project_cards,
            recent_reports=runtime.report_store.list_recent_reports(limit=20),
        )

    return app


def _render(
    request: Request,
    template_name: str,
    runtime: AppRuntime,
    *,
    user: dict[str, str | int] | None,
    page_title: str,
    **context,
) -> HTMLResponse:
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "page_title": page_title,
            "brand_name": "ServiceTex",
            "brand_tagline": "project by @BratishkaDurova",
            "user": user,
            "is_admin": False if user is None else _is_admin(runtime, int(user["id"])),
            "telegram_bot_username": runtime.settings.telegram_bot_username,
            "telegram_bot_url": _build_bot_url(runtime.settings.telegram_bot_username),
            "telegram_auth_url": _build_telegram_auth_url(runtime.settings.web_base_url),
            "telegram_login_ready": bool(
                runtime.settings.telegram_bot_username and runtime.settings.web_base_url
            ),
            "web_domain": runtime.settings.web_domain,
            "project_title": "ServiceTex Control Center",
            **context,
        },
    )


def _get_current_user(request: Request) -> dict[str, str | int] | None:
    session_user = request.session.get("telegram_user")
    return session_user if isinstance(session_user, dict) else None


def _is_admin(runtime: AppRuntime, user_id: int) -> bool:
    if not runtime.settings.admin_user_ids:
        return True
    return user_id in runtime.settings.admin_user_ids


def _build_bot_url(bot_username: str) -> str | None:
    if not bot_username:
        return None
    return f"https://t.me/{bot_username}"


def _build_telegram_auth_url(web_base_url: str) -> str:
    base_url = web_base_url.rstrip("/")
    return f"{base_url}/auth/telegram" if base_url else "/auth/telegram"
