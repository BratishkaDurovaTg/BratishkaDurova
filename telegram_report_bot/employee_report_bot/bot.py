from __future__ import annotations

import asyncio
import html
import logging
import tempfile
import uuid
from datetime import datetime, tzinfo
from pathlib import Path

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import load_settings
from .excel_store import ExcelReportStore
from .models import EmployeeReport
from .postgres_store import PostgresProjectStore, PostgresReportStore
from .project_store import ProjectStore
from .report_parser import parse_report
from .transcriber import AudioTranscriber


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BUTTON_CHOOSE_PROJECT = "📁 Выбрать проект"
BUTTON_SEND_REPORT = "🎤 Отправить отчёт"
BUTTON_MY_PROJECT = "📌 Мой проект"
BUTTON_HELP = "ℹ️ Помощь"
BUTTON_BACK = "⬅️ Назад"

USER_PROJECT_KEY = "selected_project"
ADMIN_PROJECT_KEY = "admin_project"
ADMIN_ADD_PROJECT_KEY = "admin_awaiting_project_code"


class EmployeeReportBot:
    def __init__(self) -> None:
        self.settings = load_settings()
        if self.settings.database_url:
            self.project_store = PostgresProjectStore(
                self.settings.database_url,
                snapshot_path=self.settings.projects_path,
            )
            self.store = PostgresReportStore(
                self.settings.database_url,
                snapshot_path=self.settings.reports_xlsx_path,
            )
        else:
            self.store = ExcelReportStore(self.settings.reports_xlsx_path)
            self.project_store = ProjectStore(self.settings.projects_path)
        self.transcriber = AudioTranscriber(
            model_name=self.settings.whisper_model,
            device=self.settings.whisper_device,
            compute_type=self.settings.whisper_compute_type,
            language=self.settings.default_language,
        )

    def build_application(self) -> Application:
        application = Application.builder().token(self.settings.telegram_bot_token).build()
        application.bot_data["report_bot"] = self

        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CallbackQueryHandler(handle_admin_callback, pattern=r"^admin:"))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE, handle_audio_report))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
        application.add_error_handler(handle_error)
        return application


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    await message.reply_text(
        _format_welcome_message(context.user_data.get(USER_PROJECT_KEY)),
        reply_markup=_build_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    bot: EmployeeReportBot = context.application.bot_data["report_bot"]

    await message.reply_text(
        _format_help_message(
            context.user_data.get(USER_PROJECT_KEY),
            bot.project_store.list_projects(),
        ),
        reply_markup=_build_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    bot: EmployeeReportBot = context.application.bot_data["report_bot"]
    if not _is_admin(update, bot):
        return

    selected_project = context.user_data.get(ADMIN_PROJECT_KEY)
    await message.reply_text(
        _format_admin_menu_text(selected_project),
        reply_markup=_build_admin_keyboard(selected_project),
        parse_mode=ParseMode.HTML,
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    bot: EmployeeReportBot = context.application.bot_data["report_bot"]
    if not _is_admin(update, bot):
        return

    action = (query.data or "").removeprefix("admin:")
    selected_project = context.user_data.get(ADMIN_PROJECT_KEY)

    if action == "menu":
        await _safe_edit_callback_message(
            query,
            _format_admin_menu_text(selected_project),
            reply_markup=_build_admin_keyboard(selected_project),
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "select_project":
        await _safe_edit_callback_message(
            query,
            _format_admin_project_picker_text(selected_project),
            reply_markup=_build_admin_project_keyboard(bot.project_store.list_projects()),
            parse_mode=ParseMode.HTML,
        )
        return

    if action.startswith("project:"):
        project_code = action.split(":", 1)[1]
        context.user_data[ADMIN_PROJECT_KEY] = project_code
        context.user_data[ADMIN_ADD_PROJECT_KEY] = False
        await _safe_edit_callback_message(
            query,
            _format_admin_project_selected_text(project_code),
            reply_markup=_build_admin_keyboard(project_code),
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "add_project":
        context.user_data[ADMIN_ADD_PROJECT_KEY] = True
        await _safe_edit_callback_message(
            query,
            _format_admin_add_project_prompt(),
            reply_markup=_build_admin_add_project_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if action in {"summary", "list", "excel"} and not selected_project:
        await _safe_edit_callback_message(
            query,
            _format_admin_project_picker_text(selected_project=None),
            reply_markup=_build_admin_project_keyboard(bot.project_store.list_projects()),
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "summary":
        summary = await asyncio.to_thread(_build_today_summary, bot, selected_project)
        await _safe_edit_callback_message(
            query,
            summary,
            reply_markup=_build_admin_keyboard(selected_project),
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "list":
        listing = await asyncio.to_thread(_build_today_report_list, bot, selected_project)
        await _safe_edit_callback_message(
            query,
            listing,
            reply_markup=_build_admin_keyboard(selected_project),
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "excel":
        await _send_excel_file(query, context, bot, selected_project)
        return

    await _safe_edit_callback_message(
        query,
        _format_admin_menu_text(selected_project),
        reply_markup=_build_admin_keyboard(selected_project),
        parse_mode=ParseMode.HTML,
    )


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return

    text = message.text.strip()
    bot: EmployeeReportBot = context.application.bot_data["report_bot"]
    selected_project = context.user_data.get(USER_PROJECT_KEY)
    available_projects = bot.project_store.list_projects()

    if _is_admin(update, bot) and context.user_data.get(ADMIN_ADD_PROJECT_KEY):
        if _is_cancel_text(text):
            context.user_data[ADMIN_ADD_PROJECT_KEY] = False
            await message.reply_text(
                _format_admin_menu_text(context.user_data.get(ADMIN_PROJECT_KEY)),
                reply_markup=_build_admin_keyboard(context.user_data.get(ADMIN_PROJECT_KEY)),
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            project_code, created = bot.project_store.add_project(text)
        except ValueError as exc:
            await message.reply_text(
                f"⚠️ <b>Не удалось добавить проект.</b>\n\n{html.escape(str(exc))}\n\n"
                "Введите код ещё раз или отправьте <b>отмена</b>.",
                parse_mode=ParseMode.HTML,
            )
            return

        context.user_data[ADMIN_ADD_PROJECT_KEY] = False
        context.user_data[ADMIN_PROJECT_KEY] = project_code
        await message.reply_text(
            _format_admin_project_added_text(project_code, created),
            reply_markup=_build_admin_keyboard(project_code),
            parse_mode=ParseMode.HTML,
        )
        return

    if text == BUTTON_CHOOSE_PROJECT:
        await message.reply_text(
            _format_project_picker_message(selected_project, available_projects),
            reply_markup=_build_project_keyboard(available_projects),
            parse_mode=ParseMode.HTML,
        )
        return

    if text in available_projects:
        context.user_data[USER_PROJECT_KEY] = text
        await message.reply_text(
            _format_project_selected_message(text),
            reply_markup=_build_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if text == BUTTON_BACK:
        await message.reply_text(
            _format_welcome_message(selected_project),
            reply_markup=_build_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if text == BUTTON_MY_PROJECT:
        await message.reply_text(
            _format_current_project_message(selected_project),
            reply_markup=_build_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if text == BUTTON_HELP:
        await message.reply_text(
            _format_help_message(selected_project, available_projects),
            reply_markup=_build_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if text == BUTTON_SEND_REPORT:
        if not selected_project:
            await message.reply_text(
                _format_project_required_message(),
                reply_markup=_build_project_keyboard(available_projects),
                parse_mode=ParseMode.HTML,
            )
            return

        await message.reply_text(
            _format_report_prompt_message(selected_project),
            reply_markup=_build_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if not selected_project:
        await message.reply_text(
            _format_project_required_message(),
            reply_markup=_build_project_keyboard(available_projects),
            parse_mode=ParseMode.HTML,
        )
        return

    report = _build_report(
        update=update,
        transcript=text,
        source="text",
        telegram_file_id="",
        report_timezone=bot.settings.report_timezone,
        project_code=selected_project,
    )
    await asyncio.to_thread(bot.store.upsert_report, report)
    await message.reply_text(
        _format_success_message(report),
        reply_markup=_build_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def handle_audio_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    bot: EmployeeReportBot = context.application.bot_data["report_bot"]
    selected_project = context.user_data.get(USER_PROJECT_KEY)
    available_projects = bot.project_store.list_projects()
    if not selected_project:
        await message.reply_text(
            _format_project_required_message(),
            reply_markup=_build_project_keyboard(available_projects),
            parse_mode=ParseMode.HTML,
        )
        return

    attachment = message.voice or message.audio or message.video_note
    if attachment is None:
        await message.reply_text(
            "⚠️ <b>Не нашёл аудио во входящем сообщении.</b>",
            reply_markup=_build_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    source = "voice"
    extension = ".ogg"
    if message.audio:
        source = "audio"
        extension = _guess_extension(message.audio.file_name)
    elif message.video_note:
        source = "video_note"
        extension = ".mp4"

    status_message = await message.reply_text(
        _format_processing_message(selected_project),
        parse_mode=ParseMode.HTML,
    )
    local_path: Path | None = None

    try:
        local_path = await _download_attachment(
            context=context,
            file_id=attachment.file_id,
            download_dir=bot.settings.download_dir,
            extension=extension,
        )
        transcript = await asyncio.to_thread(bot.transcriber.transcribe, local_path)
        if not transcript:
            await _safe_update_status_message(
                status_message,
                "⚠️ <b>Не удалось распознать речь.</b>\n\nПопробуйте записать голосовое чуть громче и короче.",
                parse_mode=ParseMode.HTML,
            )
            return

        report = _build_report(
            update=update,
            transcript=transcript,
            source=source,
            telegram_file_id=attachment.file_id,
            report_timezone=bot.settings.report_timezone,
            project_code=selected_project,
        )
        await asyncio.to_thread(bot.store.upsert_report, report)
        await _safe_update_status_message(
            status_message,
            _format_success_message(report),
            parse_mode=ParseMode.HTML,
        )
    finally:
        if local_path is not None:
            local_path.unlink(missing_ok=True)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot error", exc_info=context.error)
    effective_message = getattr(update, "effective_message", None)
    if effective_message is not None:
        await effective_message.reply_text(
            "⚠️ <b>Что-то пошло не так.</b>\n\nПопробуйте ещё раз чуть позже.",
            reply_markup=_build_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )


async def _send_excel_file(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    bot: EmployeeReportBot,
    project_code: str,
) -> None:
    if query.message is None:
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        export_path = Path(tmp_dir) / f"reports_{project_code}.xlsx"
        await asyncio.to_thread(bot.store.export_reports, export_path, project_code)

        with export_path.open("rb") as file_handle:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file_handle,
                filename=export_path.name,
                caption=f"📤 Excel по проекту {project_code}.",
            )

    await _safe_edit_callback_message(
        query,
        _format_admin_file_sent_text(project_code),
        reply_markup=_build_admin_keyboard(project_code),
        parse_mode=ParseMode.HTML,
    )


async def _download_attachment(
    context: ContextTypes.DEFAULT_TYPE,
    file_id: str,
    download_dir: Path,
    extension: str,
) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    telegram_file = await context.bot.get_file(file_id)
    local_path = download_dir / f"{uuid.uuid4().hex}{extension}"
    await telegram_file.download_to_drive(custom_path=str(local_path))
    return local_path


async def _safe_edit_callback_message(
    query,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    try:
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except BadRequest as exc:
        error_text = str(exc).lower()
        if "message is not modified" in error_text:
            return
        raise


async def _safe_update_status_message(
    status_message: Message,
    text: str,
    parse_mode: str | None = None,
) -> None:
    try:
        await status_message.edit_text(text, parse_mode=parse_mode)
    except BadRequest as exc:
        error_text = str(exc).lower()
        if "message can't be edited" in error_text or "message to edit not found" in error_text:
            await status_message.reply_text(text, parse_mode=parse_mode)
            return
        if "message is not modified" in error_text:
            return
        raise


def _build_report(
    update: Update,
    transcript: str,
    source: str,
    telegram_file_id: str,
    report_timezone: tzinfo,
    project_code: str,
) -> EmployeeReport:
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    if user is None or chat is None or message is None:
        raise ValueError("Telegram update does not have enough data to build a report.")

    now = datetime.now(report_timezone)
    parsed = parse_report(transcript)
    username = f"@{user.username}" if user.username else ""

    return EmployeeReport(
        report_date=now.date().isoformat(),
        updated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        project_code=project_code,
        employee_name=user.full_name,
        telegram_username=username,
        user_id=user.id,
        chat_id=chat.id,
        message_id=message.message_id,
        source=source,
        telegram_file_id=telegram_file_id,
        transcript=parsed.transcript,
        fact_today=parsed.fact_today,
        plan_tomorrow=parsed.plan_tomorrow,
        parse_status=parsed.parse_status,
    )


def _build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BUTTON_CHOOSE_PROJECT), KeyboardButton(BUTTON_SEND_REPORT)],
            [KeyboardButton(BUTTON_MY_PROJECT), KeyboardButton(BUTTON_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def _build_project_keyboard(project_codes: list[str]) -> ReplyKeyboardMarkup:
    rows = _build_project_button_rows(project_codes, inline=False)
    rows.append([KeyboardButton(BUTTON_BACK)])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        input_field_placeholder="Выберите проект",
    )


def _build_admin_keyboard(selected_project: str | None) -> InlineKeyboardMarkup:
    project_label = selected_project or "не выбран"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"📁 Проект: {project_label}", callback_data="admin:select_project")],
            [
                InlineKeyboardButton("📊 Сводка", callback_data="admin:summary"),
                InlineKeyboardButton("📋 Отчёты", callback_data="admin:list"),
            ],
            [InlineKeyboardButton("📤 Excel", callback_data="admin:excel")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin:menu")],
        ]
    )


def _build_admin_project_keyboard(project_codes: list[str]) -> InlineKeyboardMarkup:
    rows = _build_project_button_rows(project_codes, inline=True)
    rows.append([InlineKeyboardButton("➕ Добавить проект", callback_data="admin:add_project")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin:menu")])
    return InlineKeyboardMarkup(rows)


def _build_admin_add_project_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Назад", callback_data="admin:select_project")]]
    )


def _is_admin(update: Update, bot: EmployeeReportBot) -> bool:
    user = update.effective_user
    if user is None:
        return False
    if not bot.settings.admin_user_ids:
        return True
    return user.id in bot.settings.admin_user_ids


def _build_today_summary(bot: EmployeeReportBot, project_code: str) -> str:
    today = datetime.now(bot.settings.report_timezone).date().isoformat()
    reports = bot.store.get_reports_for_date(today, project_code=project_code)
    if not reports:
        return (
            "🛡 <b>Сводка</b>\n\n"
            f"📁 Проект: <b>{html.escape(project_code)}</b>\n"
            f"🗓 Дата: <b>{today}</b>\n\n"
            "⚠️ За сегодня пока нет ни одного отчёта."
        )

    parsed_count = sum(1 for report in reports if report["parse_status"] == "parsed")
    review_count = len(reports) - parsed_count

    return (
        "🛡 <b>Сводка</b>\n\n"
        f"📁 Проект: <b>{html.escape(project_code)}</b>\n"
        f"🗓 Дата: <b>{today}</b>\n\n"
        f"✅ Отчётов: <b>{len(reports)}</b>\n"
        f"✅ Разобрано факт/план: <b>{parsed_count}</b>\n"
        f"⚠️ Нужна проверка: <b>{review_count}</b>"
    )


def _build_today_report_list(bot: EmployeeReportBot, project_code: str) -> str:
    today = datetime.now(bot.settings.report_timezone).date().isoformat()
    reports = bot.store.get_reports_for_date(today, project_code=project_code)
    if not reports:
        return (
            "📋 <b>Отчёты</b>\n\n"
            f"📁 Проект: <b>{html.escape(project_code)}</b>\n"
            f"🗓 Дата: <b>{today}</b>\n\n"
            "⚠️ За сегодня пока нет ни одного отчёта."
        )

    lines = [
        "📋 <b>Отчёты за сегодня</b>",
        "",
        f"📁 Проект: <b>{html.escape(project_code)}</b>",
        f"🗓 Дата: <b>{today}</b>",
    ]
    for index, report in enumerate(reports, start=1):
        employee_label = report["employee_name"] or report["telegram_username"] or report["user_id"]
        fact = html.escape(_shorten(report["fact_today"] or "не найден", 80))
        plan = html.escape(_shorten(report["plan_tomorrow"] or "не найден", 80))
        status = html.escape(report["parse_status"])
        lines.extend(
            [
                "",
                f"<b>{index}. {html.escape(employee_label)}</b>",
                f"✅ Сегодня: {fact}",
                f"🔜 Завтра: {plan}",
                f"📌 Статус: {status}",
            ]
        )

    return "\n".join(lines)


def _format_welcome_message(selected_project: str | None) -> str:
    project_label = html.escape(selected_project or "не выбран")
    return (
        "<b>ServiceTex</b>\n"
        "<i>Project by @BratishkaDurova</i>\n\n"
        "Учет работы сотрудников через голосовые сообщения.\n\n"
        f"📁 <b>Проект:</b> {project_label}\n"
        "🎤 <b>Отчёт:</b> что сделали сегодня и что будете делать завтра\n\n"
        "Выберите действие в меню ниже."
    )


def _format_help_message(selected_project: str | None, project_codes: list[str]) -> str:
    project_label = html.escape(selected_project or "не выбран")
    project_list = " / ".join(project_codes)
    return (
        "ℹ️ <b>Как пользоваться ботом</b>\n\n"
        f"📁 Текущий проект: <b>{project_label}</b>\n\n"
        "1. Нажмите <b>Выбрать проект</b>\n"
        f"2. Выберите один из проектов: <b>{html.escape(project_list)}</b>\n"
        "3. Нажмите <b>Отправить отчёт</b>\n"
        "4. Отправьте голосовое сообщение\n\n"
        "Лучший формат голосового:\n"
        "✅ Факт за сегодня: ...\n"
        "🔜 План на завтра: ..."
    )


def _format_project_picker_message(selected_project: str | None, project_codes: list[str]) -> str:
    current = html.escape(selected_project or "не выбран")
    project_lines = "\n".join(f"• <b>{html.escape(code)}</b>" for code in project_codes)
    return (
        "📁 <b>Выберите проект</b>\n\n"
        f"Текущий проект: <b>{current}</b>\n\n"
        "Доступные проекты:\n"
        f"{project_lines}"
    )


def _format_project_selected_message(project_code: str) -> str:
    return (
        "✅ <b>Проект выбран</b>\n\n"
        f"📁 Проект: <b>{html.escape(project_code)}</b>\n\n"
        "🎤 Теперь отправьте голосовое сообщение.\n"
        "Я сохраню:\n"
        "✅ Что сделано сегодня\n"
        "🔜 Что будете делать завтра"
    )


def _format_current_project_message(selected_project: str | None) -> str:
    if selected_project:
        return (
            "📌 <b>Текущий проект</b>\n\n"
            f"📁 Сейчас выбран: <b>{html.escape(selected_project)}</b>\n\n"
            "🎤 Можно сразу отправлять отчёт."
        )

    return (
        "📌 <b>Текущий проект</b>\n\n"
        "⚠️ Проект пока не выбран.\n"
        "Сначала нажмите <b>Выбрать проект</b>."
    )


def _format_project_required_message() -> str:
    return (
        "⚠️ <b>Сначала выберите проект</b>\n\n"
        "Нажмите нужный проект ниже, а затем отправьте голосовое сообщение."
    )


def _format_report_prompt_message(project_code: str) -> str:
    return (
        "🎤 <b>Можно отправлять отчёт</b>\n\n"
        f"📁 Проект: <b>{html.escape(project_code)}</b>\n\n"
        "Скажите в одном сообщении:\n"
        "✅ что сделали сегодня\n"
        "🔜 что будете делать завтра"
    )


def _format_processing_message(project_code: str) -> str:
    return (
        "🎤 <b>Сообщение получено</b>\n\n"
        f"📁 Проект: <b>{html.escape(project_code)}</b>\n"
        "⏳ Скачиваю и расшифровываю голосовое..."
    )


def _format_success_message(report: EmployeeReport) -> str:
    fact_preview = html.escape(_shorten(report.fact_today) or "не найден")
    plan_preview = html.escape(_shorten(report.plan_tomorrow) or "не найден")
    note = ""
    if report.parse_status != "parsed":
        note = (
            "\n\n⚠️ Для более точного разбора начните голосовое словами:\n"
            "«Факт за сегодня» и «План на завтра»."
        )

    return (
        "✅ <b>Факт за сегодня сохранён</b>\n\n"
        f"📁 Проект: <b>{html.escape(report.project_code)}</b>\n"
        f"🗓 Дата: <b>{report.report_date}</b>\n\n"
        f"✅ <b>Что сделано сегодня:</b>\n{fact_preview}\n\n"
        f"🔜 <b>Что будете делать завтра:</b>\n{plan_preview}"
        f"{note}"
    )


def _format_admin_menu_text(selected_project: str | None) -> str:
    project_label = html.escape(selected_project or "не выбран")
    return (
        "🛡 <b>Админ-панель</b>\n\n"
        f"📁 Проект: <b>{project_label}</b>\n\n"
        "Выберите действие ниже."
    )


def _format_admin_project_picker_text(selected_project: str | None) -> str:
    current = html.escape(selected_project or "не выбран")
    return (
        "📁 <b>Какой проект хотите открыть?</b>\n\n"
        f"Текущий выбор: <b>{current}</b>\n\n"
        "Выберите проект для админ-панели или добавьте новый."
    )


def _format_admin_project_selected_text(project_code: str) -> str:
    return (
        "✅ <b>Проект для админ-панели выбран</b>\n\n"
        f"📁 Проект: <b>{html.escape(project_code)}</b>\n\n"
        "Теперь можно открыть сводку, список отчётов или Excel."
    )


def _format_admin_file_sent_text(project_code: str) -> str:
    return (
        "📤 <b>Excel отправлен</b>\n\n"
        f"📁 Проект: <b>{html.escape(project_code)}</b>\n\n"
        "Файл уже лежит в этом чате."
    )


def _format_admin_add_project_prompt() -> str:
    return (
        "➕ <b>Добавление проекта</b>\n\n"
        "Введите код нового проекта сообщением.\n\n"
        "Например: <b>S205</b>\n\n"
        "Чтобы отменить, отправьте <b>отмена</b>."
    )


def _format_admin_project_added_text(project_code: str, created: bool) -> str:
    if created:
        return (
            "✅ <b>Проект добавлен</b>\n\n"
            f"📁 Новый проект: <b>{html.escape(project_code)}</b>\n\n"
            "Он уже доступен в меню сотрудника и в админке."
        )

    return (
        "ℹ️ <b>Проект уже существует</b>\n\n"
        f"📁 Проект: <b>{html.escape(project_code)}</b>\n\n"
        "Я просто выбрал его как текущий для админ-панели."
    )


def _guess_extension(file_name: str | None) -> str:
    if not file_name or "." not in file_name:
        return ".mp3"
    return Path(file_name).suffix or ".mp3"


def _shorten(value: str, limit: int = 160) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _build_project_button_rows(project_codes: list[str], inline: bool) -> list[list[KeyboardButton | InlineKeyboardButton]]:
    rows: list[list[KeyboardButton | InlineKeyboardButton]] = []
    for index in range(0, len(project_codes), 2):
        chunk = project_codes[index : index + 2]
        if inline:
            rows.append(
                [InlineKeyboardButton(code, callback_data=f"admin:project:{code}") for code in chunk]
            )
        else:
            rows.append([KeyboardButton(code) for code in chunk])
    return rows


def _is_cancel_text(text: str) -> bool:
    return text.strip().lower() in {"отмена", "cancel", BUTTON_BACK.lower()}


def run() -> None:
    report_bot = EmployeeReportBot()
    application = report_bot.build_application()
    logger.info("Bot is starting")
    application.run_polling()
