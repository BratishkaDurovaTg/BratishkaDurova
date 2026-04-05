from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, load_settings
from .excel_store import ExcelReportStore
from .postgres_store import PostgresProjectStore, PostgresReportStore
from .project_store import ProjectStore


@dataclass(slots=True)
class AppRuntime:
    settings: Settings
    project_store: ProjectStore | PostgresProjectStore
    report_store: ExcelReportStore | PostgresReportStore


def create_runtime() -> AppRuntime:
    settings = load_settings()
    if settings.database_url:
        project_store = PostgresProjectStore(
            settings.database_url,
            snapshot_path=settings.projects_path,
        )
        report_store = PostgresReportStore(
            settings.database_url,
            snapshot_path=settings.reports_xlsx_path,
        )
    else:
        report_store = ExcelReportStore(settings.reports_xlsx_path)
        project_store = ProjectStore(settings.projects_path)

    return AppRuntime(
        settings=settings,
        project_store=project_store,
        report_store=report_store,
    )
