from dataclasses import dataclass


@dataclass(slots=True)
class ParsedReport:
    transcript: str
    fact_today: str
    plan_tomorrow: str
    parse_status: str


@dataclass(slots=True)
class EmployeeReport:
    report_date: str
    updated_at: str
    project_code: str
    employee_name: str
    telegram_username: str
    user_id: int
    chat_id: int
    message_id: int
    source: str
    telegram_file_id: str
    transcript: str
    fact_today: str
    plan_tomorrow: str
    parse_status: str
