from __future__ import annotations

import json
import re
from pathlib import Path


DEFAULT_PROJECT_CODES = ("S1", "S77", "S150", "S50")
PROJECT_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,19}$")


class ProjectStore:
    def __init__(self, projects_path: Path) -> None:
        self._projects_path = projects_path
        self._projects_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def list_projects(self) -> list[str]:
        return self._load_projects()

    def add_project(self, project_code: str) -> tuple[str, bool]:
        normalized_code = self.normalize_project_code(project_code)
        if not normalized_code:
            raise ValueError(
                "Код проекта должен содержать только латинские буквы, цифры, '-' или '_' и быть не длиннее 20 символов."
            )

        projects = self._load_projects()
        if normalized_code in projects:
            return normalized_code, False

        projects.append(normalized_code)
        self._save_projects(projects)
        return normalized_code, True

    def _ensure_file(self) -> None:
        if self._projects_path.exists():
            projects = self._load_projects()
            if projects:
                return
        self._save_projects(list(DEFAULT_PROJECT_CODES))

    def _load_projects(self) -> list[str]:
        if not self._projects_path.exists():
            return list(DEFAULT_PROJECT_CODES)

        try:
            payload = json.loads(self._projects_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return list(DEFAULT_PROJECT_CODES)

        if not isinstance(payload, list):
            return list(DEFAULT_PROJECT_CODES)

        projects: list[str] = []
        for item in payload:
            if not isinstance(item, str):
                continue
            normalized = self.normalize_project_code(item)
            if normalized and normalized not in projects:
                projects.append(normalized)

        return projects or list(DEFAULT_PROJECT_CODES)

    def _save_projects(self, projects: list[str]) -> None:
        self._projects_path.write_text(
            json.dumps(projects, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def normalize_project_code(project_code: str) -> str:
        normalized = re.sub(r"\s+", "", (project_code or "").strip().upper())
        if not normalized or not PROJECT_CODE_RE.fullmatch(normalized):
            return ""
        return normalized
