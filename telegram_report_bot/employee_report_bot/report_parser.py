from __future__ import annotations

import re

from .models import ParsedReport


FACT_MARKER_RE = re.compile(
    r"\b(?:факт(?:\s+за\s+сегодня)?|за\s+сегодня|сделал(?:а)?\s+за\s+сегодня)\b\s*[:\-]?",
    re.IGNORECASE,
)
PLAN_MARKER_RE = re.compile(
    r"\b(?:план(?:\s+на\s+завтра)?|на\s+завтра|завтра)\b\s*[:\-]?",
    re.IGNORECASE,
)


def parse_report(raw_text: str) -> ParsedReport:
    transcript = _cleanup_text(raw_text)
    if not transcript:
        return ParsedReport(
            transcript="",
            fact_today="",
            plan_tomorrow="",
            parse_status="empty",
        )

    fact_match = FACT_MARKER_RE.search(transcript)
    plan_match = PLAN_MARKER_RE.search(transcript)

    fact_today = ""
    plan_tomorrow = ""
    parse_status = "transcript_only"

    if fact_match and plan_match:
        if fact_match.start() <= plan_match.start():
            fact_today = _cleanup_text(transcript[fact_match.end() : plan_match.start()])
            plan_tomorrow = _cleanup_text(transcript[plan_match.end() :])
        else:
            plan_tomorrow = _cleanup_text(transcript[plan_match.end() : fact_match.start()])
            fact_today = _cleanup_text(transcript[fact_match.end() :])
        parse_status = "parsed"
    elif fact_match:
        fact_today = _cleanup_text(transcript[fact_match.end() :])
        parse_status = "fact_only"
    elif plan_match:
        fact_today = _cleanup_text(transcript[: plan_match.start()])
        plan_tomorrow = _cleanup_text(transcript[plan_match.end() :])
        parse_status = "plan_split"
    else:
        fact_today = transcript

    if not fact_today and transcript:
        fact_today = transcript

    if parse_status == "parsed" and not plan_tomorrow:
        parse_status = "fact_only"

    return ParsedReport(
        transcript=transcript,
        fact_today=fact_today,
        plan_tomorrow=plan_tomorrow,
        parse_status=parse_status,
    )


def _cleanup_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value.strip(" .,:;-")
