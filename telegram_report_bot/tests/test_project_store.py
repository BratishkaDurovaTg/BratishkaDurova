from __future__ import annotations

import unittest

from employee_report_bot.project_store import ProjectStore


class ProjectStoreNormalizeProjectCodeTests(unittest.TestCase):
    def test_normalizes_to_uppercase_without_spaces(self) -> None:
        self.assertEqual(ProjectStore.normalize_project_code(" s150 "), "S150")

    def test_keeps_hyphen_and_underscore(self) -> None:
        self.assertEqual(ProjectStore.normalize_project_code("crm_stage-2"), "CRM_STAGE-2")

    def test_rejects_invalid_characters(self) -> None:
        self.assertEqual(ProjectStore.normalize_project_code("project!"), "")


if __name__ == "__main__":
    unittest.main()
