from __future__ import annotations

import unittest

from employee_report_bot.report_parser import parse_report


class ReportParserTests(unittest.TestCase):
    def test_parses_fact_and_plan_sections(self) -> None:
        parsed = parse_report(
            "Факт за сегодня: закрыл две задачи. План на завтра: проверить сервер."
        )

        self.assertEqual(parsed.parse_status, "parsed")
        self.assertEqual(parsed.fact_today, "закрыл две задачи")
        self.assertEqual(parsed.plan_tomorrow, "проверить сервер")

    def test_falls_back_to_fact_when_no_markers(self) -> None:
        parsed = parse_report("созвонился с клиентом и отправил макеты")

        self.assertEqual(parsed.parse_status, "transcript_only")
        self.assertEqual(parsed.fact_today, "созвонился с клиентом и отправил макеты")
        self.assertEqual(parsed.plan_tomorrow, "")

    def test_extracts_plan_and_keeps_prefix_as_fact(self) -> None:
        parsed = parse_report("закрыл тесты завтра доделаю отчёт")

        self.assertEqual(parsed.parse_status, "plan_split")
        self.assertEqual(parsed.fact_today, "закрыл тесты")
        self.assertEqual(parsed.plan_tomorrow, "доделаю отчёт")


if __name__ == "__main__":
    unittest.main()
