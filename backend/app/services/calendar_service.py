"""RFC 5545 iCalendar (.ics) generation engine for contractual obligation deadlines."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


def _escape_ics(value: str) -> str:
    text = str(value or "")
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\r\n", "\\n").replace("\n", "\\n")
    return text


def _fold_line(line: str) -> str:
    """Fold RFC 5545 content lines to <= 75 octets."""
    if len(line) <= 75:
        return line
    parts = [line[:75]]
    idx = 75
    while idx < len(line):
        parts.append(" " + line[idx : idx + 74])
        idx += 74
    return "\r\n".join(parts)


def _infer_due_date(trigger: str, base_date: datetime) -> datetime:
    text = (trigger or "").lower()
    # Explicit ISO date YYYY-MM-DD
    iso_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        try:
            return datetime(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    # Relative day counts e.g. "within 30 days", "net 45", "15 business days"
    day_match = re.search(r"(\d+)\s*(?:calendar\s+|business\s+)?days?", text)
    if day_match:
        days = max(1, min(3650, int(day_match.group(1))))
        return base_date + timedelta(days=days)

    net_match = re.search(r"net\s*(\d+)", text)
    if net_match:
        return base_date + timedelta(days=int(net_match.group(1)))

    if "hour" in text:
        return base_date + timedelta(days=1)
    if "month" in text:
        m_match = re.search(r"(\d+)\s*months?", text)
        months = int(m_match.group(1)) if m_match else 1
        return base_date + timedelta(days=30 * months)
    if "annual" in text or "year" in text:
        return base_date + timedelta(days=365)

    return base_date + timedelta(days=30)


def generate_ics_calendar(contract: Any) -> str:
    """Build an RFC 5545 .ics calendar payload from a Contract's extracted obligations."""
    now = datetime.now(timezone.utc)
    dtstamp = now.strftime("%Y%m%dT%H%M%SZ")
    base_date = getattr(contract, "created_at", None) or now
    if base_date.tzinfo is None:
        base_date = base_date.replace(tzinfo=timezone.utc)

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ContractMind v2.0//Legal Obligation Sync//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics(getattr(contract, 'title', 'ContractMind Obligations'))}",
    ]

    obligations = getattr(contract, "obligations", None) or []
    for idx, ob in enumerate(obligations):
        category = ob.get("obligation_type", "Contractual Duty")
        obligor = ob.get("obligor", "Party")
        recipient = ob.get("recipient", "Counterparty")
        trigger = ob.get("due_date_or_trigger", "Upon Notice")
        recurrence = ob.get("recurrence", "One-time")
        penalty = ob.get("penalty_for_breach", "Contractual remedies")
        clause_ref = ob.get("clause_reference", "General")
        desc_body = ob.get("description", "")

        due_dt = _infer_due_date(trigger, base_date + timedelta(days=idx))
        dt_start = due_dt.strftime("%Y%m%d")
        dt_end = (due_dt + timedelta(days=1)).strftime("%Y%m%d")

        summary = f"[ContractMind] {category} ({obligor}): {trigger}"
        description = (
            f"Contract: {getattr(contract, 'title', 'Contract')}\n"
            f"Clause Reference: {clause_ref}\n"
            f"Obligor: {obligor}\n"
            f"Recipient: {recipient}\n"
            f"Due Date / Trigger: {trigger}\n"
            f"Recurrence: {recurrence}\n"
            f"Penalty for Breach: {penalty}\n"
            f"Details: {desc_body}"
        )

        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@contractmind.ai",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;VALUE=DATE:{dt_start}",
            f"DTEND;VALUE=DATE:{dt_end}",
            _fold_line(f"SUMMARY:{_escape_ics(summary)}"),
            _fold_line(f"DESCRIPTION:{_escape_ics(description)}"),
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ]
        lines.extend(event_lines)

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
