"""Obligation Extractor Agent Node: Operational duties, triggers, recurrence, and breach penalties."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractGraphState


_OBLIGATION_PATTERNS: list[dict[str, Any]] = [
    {
        "obligation_type": "Payment",
        "pattern": re.compile(r"(?:net\s*\d+|pay\s+(?:all\s+)?invoices|within\s+\d+\s+days\s+of\s+invoice|annual\s+fee|subscription\s+fee)", re.IGNORECASE),
        "obligor": "Customer",
        "recipient": "Vendor / Provider",
        "default_trigger": "Net 30 days from invoice date",
        "recurrence": "Monthly / Annual",
        "penalty": "1.5% monthly late interest and potential service suspension",
    },
    {
        "obligation_type": "Security Audit",
        "pattern": re.compile(r"(?:soc\s*2|iso\s*27001|security\s+audit|penetration\s+test|audit\s+rights)", re.IGNORECASE),
        "obligor": "Vendor / Processor",
        "recipient": "Customer",
        "default_trigger": "Within 30 days of annual request",
        "recurrence": "Annual",
        "penalty": "Mandatory remediation plan or termination for material breach",
    },
    {
        "obligation_type": "Data Deletion",
        "pattern": re.compile(r"(?:delete|destroy|return\s+(?:all\s+)?customer\s+data|purge\s+data|data\s+deletion)", re.IGNORECASE),
        "obligor": "Vendor / Processor",
        "recipient": "Customer",
        "default_trigger": "Within 30 days after termination",
        "recurrence": "Upon Termination",
        "penalty": "GDPR/CCPA regulatory liability and breach indemnity",
    },
    {
        "obligation_type": "Insurance",
        "pattern": re.compile(r"(?:cyber\s+liability|commercial\s+general\s+liability|errors\s+and\s+omissions|insurance\s+coverage|certificate\s+of\s+insurance)", re.IGNORECASE),
        "obligor": "Vendor / Provider",
        "recipient": "Customer",
        "default_trigger": "Within 15 days of Effective Date",
        "recurrence": "Annual Renewal",
        "penalty": "Breach of covenant and suspension of SOW awards",
    },
    {
        "obligation_type": "Service Credits",
        "pattern": re.compile(r"(?:service\s+credit|uptime|99\.\d+%\s+availability|sla\s+credit|downtime)", re.IGNORECASE),
        "obligor": "Vendor / Provider",
        "recipient": "Customer",
        "default_trigger": "Within 15 days of monthly SLA claim",
        "recurrence": "Monthly",
        "penalty": "10%-25% monthly fee credit and chronic SLA termination right",
    },
    {
        "obligation_type": "Notice Requirements",
        "pattern": re.compile(r"(?:written\s+notice|prior\s+notice|breach\s+notification|within\s+\d+\s+hours|non-renewal\s+notice)", re.IGNORECASE),
        "obligor": "Both Parties",
        "recipient": "Counterparty Legal Notice Contact",
        "default_trigger": "Within 48 hours (security) / 30 days (renewal/cure)",
        "recurrence": "Event-driven",
        "penalty": "Waiver of claim or automatic term extension",
    },
]


def _extract_trigger(sentence: str, default_trigger: str) -> str:
    m = re.search(
        r"(within\s+\d+\s+(?:calendar\s+|business\s+)?(?:days?|hours?)|net\s*\d+|\d+\s+days\s+prior)",
        sentence,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return default_trigger


def _extract_sentence(text: str, match: re.Match[str]) -> str:
    start = text.rfind(".", 0, match.start())
    start = 0 if start == -1 else start + 1
    end = text.find(".", match.end())
    end = len(text) if end == -1 else end + 1
    return re.sub(r"\s+", " ", text[start:end]).strip()


async def obligation_node(state: ContractGraphState) -> ContractGraphState:
    """Extract structured operational commitments and deadlines into the obligation matrix."""
    start = time.time()
    sections = state.get("sections") or []
    if not sections and state.get("raw_text"):
        sections = [{"section_number": "1", "title": "General Terms", "text": state["raw_text"], "page_number": 1}]

    obligations: list[dict[str, Any]] = []
    seen_types: set[str] = set()

    for sec in sections:
        sec_num = str(sec.get("section_number", "1"))
        sec_title = str(sec.get("title", "General"))
        sec_text = str(sec.get("text", ""))
        for spec in _OBLIGATION_PATTERNS:
            if spec["obligation_type"] in seen_types:
                continue
            m = spec["pattern"].search(sec_text)
            if m:
                seen_types.add(spec["obligation_type"])
                sentence = _extract_sentence(sec_text, m)
                trigger = _extract_trigger(sentence, spec["default_trigger"])
                obligations.append(
                    {
                        "clause_reference": f"Section {sec_num} ({sec_title})",
                        "obligation_type": spec["obligation_type"],
                        "obligor": spec["obligor"],
                        "recipient": spec["recipient"],
                        "description": sentence[:280],
                        "due_date_or_trigger": trigger,
                        "recurrence": spec["recurrence"],
                        "penalty_for_breach": spec["penalty"],
                    }
                )

    def _fallback_ob() -> str:
        return (
            f"Extracted {len(obligations)} operational obligation(s) across Payment, Security Audit, "
            "Data Deletion, Insurance, Service Credits, and Notice Requirements for RFC 5545 calendar sync."
        )

    llm_resp = await llm_gateway.generate(
        prompt=f"Summarize {len(obligations)} extracted contractual obligations for {state.get('title', 'Contract')}.",
        system_prompt="You are the Obligation Extractor Agent. Summarize extracted operational duties in 1 sentence.",
        fallback_fn=_fallback_ob,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    transcript = list(state.get("debate_transcript") or [])
    transcript.append(
        {
            "agent": "Obligation Extractor",
            "role": "Calendar & Penalty Monitor",
            "section_number": "Obligations",
            "stance": f"{len(obligations)} Duties Mapped",
            "message": llm_resp.text,
            "timestamp": now_iso,
        }
    )

    total_latency_ms = round((time.time() - start) * 1000.0, 2)
    audit_records = list(state.get("audit_records") or [])
    audit_records.append(
        {
            "agent_name": "Obligation Extractor",
            "action": "obligation_matrix_extraction",
            "model_name": llm_resp.model_name,
            "prompt_tokens": llm_resp.prompt_tokens,
            "completion_tokens": llm_resp.completion_tokens,
            "total_tokens": llm_resp.total_tokens,
            "latency_ms": max(total_latency_ms, llm_resp.latency_ms),
            "estimated_cost_usd": llm_resp.estimated_cost_usd,
        }
    )

    if state.get("event_emitter"):
        await state["event_emitter"](
            {
                "node": "obligation_node",
                "status": "completed",
                "obligations_extracted": len(obligations),
            }
        )

    return {
        **state,
        "obligations": obligations,
        "debate_transcript": transcript,
        "audit_records": audit_records,
    }
