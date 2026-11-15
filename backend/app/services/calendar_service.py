"""RFC 5545 iCalendar (.ics) Obligation Deadlines Sync Engine."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def _escape_ics(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold_ics_line(line: str) -> str:
    """Fold content lines at 75 octets per RFC 5545 Section 3.1."""
    if len(line) <= 75:
        return line
    parts = [line[:75]]
    idx = 75
    while idx < len(line):
        parts.append(" " + line[idx : idx + 74])
        idx += 74
    return "\r\n".join(parts)


def _compute_deadline(trigger_text: str, offset_index: int) -> datetime:
    """Compute a target UTC datetime from trigger wording such as '30 days' or explicit dates."""
    now = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    text = (trigger_text or "").lower()

    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    if iso_match:
        try:
            return datetime(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
                9,
                0,
                0,
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    days_match = re.search(r"(\d+)\s*(?:calendar|business)?\s*days?", text)
    if days_match:
        days = max(1, min(365, int(days_match.group(1))))
        return now + timedelta(days=days)

    hours_match = re.search(r"(\d+)\s*hours?", text)
    if hours_match:
        hours = max(1, min(720, int(hours_match.group(1))))
        return now + timedelta(hours=hours)

    if "annual" in text or "year" in text:
        return now + timedelta(days=365)
    if "quarter" in text:
        return now + timedelta(days=90)
    if "month" in text:
        return now + timedelta(days=30)

    return now + timedelta(days=14 + (offset_index * 7))


def generate_ics_calendar(contract: Any) -> str:
    """Generate a valid RFC 5545 .ics calendar payload for extracted contract obligations."""
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    obligations: List[Dict[str, Any]] = list(getattr(contract, "obligations", []) or [])

    if not obligations:
        obligations = [
            {
                "clause_reference": "General",
                "obligation_type": "Contract Review Milestone",
                "obligor": "Legal Counsel",
                "recipient": "Deal Stakeholders",
                "description": f"Final execution and compliance verification for {contract.title}.",
                "due_date_or_trigger": "14 days from review",
                "recurrence": "One-time",
                "penalty_for_breach": "Delayed deal closing",
            }
        ]

    lines: List[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ContractMind v2.0//Legal Intelligence Studio//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics(contract.title)} Obligations",
    ]

    for idx, ob in enumerate(obligations):
        category = str(ob.get("obligation_type", "Obligation"))
        obligor = str(ob.get("obligor", "Party"))
        recipient = str(ob.get("recipient", "Counterparty"))
        trigger = str(ob.get("due_date_or_trigger", "Upon execution"))
        recurrence = str(ob.get("recurrence", "One-time"))
        penalty = str(ob.get("penalty_for_breach") or "Standard contractual remedies")
        clause_ref = str(ob.get("clause_reference", "N/A"))
        desc_body = str(ob.get("description", ""))

        start_dt = _compute_deadline(trigger, idx)
        end_dt = start_dt + timedelta(hours=1)

        summary = f"[ContractMind] {category} ({obligor}): {trigger}"
        description = (
            f"Contract: {contract.title}\n"
            f"Clause Citation: {clause_ref}\n"
            f"Obligor: {obligor}\n"
            f"Recipient: {recipient}\n"
            f"Due Date / Trigger: {trigger}\n"
            f"Recurrence: {recurrence}\n"
            f"Breach Penalty: {penalty}\n\n"
            f"Details: {desc_body}"
        )

        uid = f"cm-{contract.id}-{idx}-{uuid.uuid4().hex[:8]}@contractmind.ai"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%SZ')}",
                _fold_ics_line(f"SUMMARY:{_escape_ics(summary)}"),
                _fold_ics_line(f"DESCRIPTION:{_escape_ics(description)}"),
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
