"""RFC 5545 iCalendar (.ics) obligation deadlines sync engine."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


DAYS_RE = re.compile(r"(\d+)\s*(?:calendar\s+|business\s+)?days?", re.IGNORECASE)
MONTHS_RE = re.compile(r"(\d+)\s*months?", re.IGNORECASE)


def _ics_escape(value: str) -> str:
    """Escape text values according to RFC 5545."""
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _compute_deadline(trigger: str, base_dt: datetime, offset_index: int) -> datetime:
    """Derive a concrete target deadline from a contract trigger string."""
    txt = (trigger or "").lower()
    m_days = DAYS_RE.search(txt)
    if m_days:
        days = min(365, max(1, int(m_days.group(1))))
        return base_dt + timedelta(days=days)
    m_months = MONTHS_RE.search(txt)
    if m_months:
        months = min(36, max(1, int(m_months.group(1))))
        return base_dt + timedelta(days=30 * months)
    if "quarter" in txt:
        return base_dt + timedelta(days=90)
    if "annual" in txt or "year" in txt:
        return base_dt + timedelta(days=365)
    if "month" in txt:
        return base_dt + timedelta(days=30)
    return base_dt + timedelta(days=14 + (offset_index * 7))


def generate_obligations_ics(contract: Any) -> str:
    """Generate RFC 5545 .ics calendar payload for all extracted contract obligations."""
    title = getattr(contract, "title", "Contract Agreement")
    contract_id = getattr(contract, "id", "unknown")
    obligations: list[dict[str, Any]] = list(getattr(contract, "obligations", None) or [])

    now_utc = datetime.now(timezone.utc)
    dtstamp = now_utc.strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ContractMind v2.0//Legal Obligations Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(title)} - Obligations",
    ]

    if not obligations:
        # Provide a baseline contract review milestone so the .ics file is always valid
        obligations = [
            {
                "clause_reference": "General",
                "obligation_type": "Contract Review",
                "obligor": "Legal Counsel",
                "recipient": "Business Stakeholder",
                "description": f"Initial post-execution compliance check for {title}.",
                "due_date_or_trigger": "30 days post-execution",
                "recurrence": "One-time",
                "penalty_for_breach": "Operational governance review",
            }
        ]

    for idx, ob in enumerate(obligations):
        category = ob.get("obligation_type", "Obligation")
        obligor = ob.get("obligor", "Party")
        recipient = ob.get("recipient", "Counterparty")
        trigger = ob.get("due_date_or_trigger", "30 days")
        recurrence = ob.get("recurrence", "One-time")
        penalty = ob.get("penalty_for_breach", "Standard breach remedies")
        citation = ob.get("clause_reference", "Contract Clause")
        description_body = ob.get("description", "")

        due_dt = _compute_deadline(trigger, now_utc, idx)
        dtstart = due_dt.strftime("%Y%m%dT090000Z")
        dtend = due_dt.strftime("%Y%m%dT100000Z")

        summary = f"[ContractMind] {category} ({obligor}): {trigger}"
        desc = (
            f"Contract: {title}\n"
            f"Clause Citation: {citation}\n"
            f"Obligor: {obligor}\n"
            f"Recipient: {recipient}\n"
            f"Due Date / Trigger: {trigger}\n"
            f"Recurrence: {recurrence}\n"
            f"Penalty for Breach: {penalty}\n"
            f"Details: {description_body}"
        )
        uid = f"{contract_id}-{idx}-{uuid.uuid4().hex[:8]}@contractmind.ai"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{dtstart}",
                f"DTEND:{dtend}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"DESCRIPTION:{_ics_escape(desc)}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
