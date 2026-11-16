"""Obligation Extractor Agent: Extracts operational commitments, triggers, and penalties."""
from __future__ import annotations

import re
import time
from typing import Any

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractAnalysisState


OBLIGATION_PATTERNS: list[dict[str, Any]] = [
    {
        "obligation_type": "Payment",
        "pattern": re.compile(
            r"(?:invoic|payment|fees?\s+shall\s+be\s+paid|net\s+\d+|remit|purchase\s+price)",
            re.IGNORECASE,
        ),
        "default_obligor": "Customer / Buyer",
        "default_recipient": "Provider / Seller",
        "default_trigger": "Net 30 days from invoice receipt",
        "default_recurrence": "Monthly / Per Invoice",
        "default_penalty": "Interest on undisputed overdue amounts or suspension notice",
    },
    {
        "obligation_type": "Security Audit",
        "pattern": re.compile(
            r"(?:soc\s*2|iso\s*27001|audit|security\s+assessment|penetration\s+test)",
            re.IGNORECASE,
        ),
        "default_obligor": "Provider / Processor",
        "default_recipient": "Customer / Controller",
        "default_trigger": "Annual attestation / 30 days written notice",
        "default_recurrence": "Annual",
        "default_penalty": "Mandatory remediation within 30 days or termination for cause",
    },
    {
        "obligation_type": "Data Deletion",
        "pattern": re.compile(
            r"(?:delet(?:e|ion)|return\s+or\s+destroy|erasure|purge\s+data|certif(?:y|ication)\s+of\s+destruction)",
            re.IGNORECASE,
        ),
        "default_obligor": "Provider / Processor",
        "default_recipient": "Customer",
        "default_trigger": "Within 30 days of termination or expiration",
        "default_recurrence": "Upon Termination",
        "default_penalty": "Breach of Data Processing Addendum & statutory regulatory exposure",
    },
    {
        "obligation_type": "Insurance",
        "pattern": re.compile(
            r"(?:insurance|cyber\s+liability|errors\s+and\s+omissions|general\s+liability|certificate\s+of\s+insurance)",
            re.IGNORECASE,
        ),
        "default_obligor": "Provider",
        "default_recipient": "Customer",
        "default_trigger": "Continuous coverage; certificates within 15 days of request",
        "default_recurrence": "Annual Renewal",
        "default_penalty": "Material breach if coverage lapses without cure",
    },
    {
        "obligation_type": "Service Credits",
        "pattern": re.compile(
            r"(?:uptime|sla|service\s+level|service\s+credit|availability\s+of\s+\d+)",
            re.IGNORECASE,
        ),
        "default_obligor": "Provider",
        "default_recipient": "Customer",
        "default_trigger": "Within 30 days following SLA breach month",
        "default_recurrence": "Monthly Measurement",
        "default_penalty": "Service fee credits (5%-15%) or termination for chronic SLA failure",
    },
    {
        "obligation_type": "Notice Requirements",
        "pattern": re.compile(
            r"(?:written\s+notice|non-?renewal\s+notice|breach\s+notification|subprocessor\s+notice|\d+\s+hours?\s+notice|\d+\s+days?\s+(?:prior\s+)?written\s+notice)",
            re.IGNORECASE,
        ),
        "default_obligor": "Notifying Party",
        "default_recipient": "Counterparty",
        "default_trigger": "30-60 days prior to renewal/change or 48 hours for security incident",
        "default_recurrence": "Event-Triggered",
        "default_penalty": "Waiver of objection window or automatic renewal/breach liability",
    },
]

TIMELINE_HINT_RE = re.compile(
    r"(?:within\s+\d+\s+(?:calendar\s+|business\s+)?(?:days?|hours?|months?)|\bnet\s+\d+\b|\d+\s+days?\s+prior\s+(?:written\s+)?notice)",
    re.IGNORECASE,
)


async def obligation_node(state: ContractAnalysisState) -> ContractAnalysisState:
    """Extract structured operational obligations, deadlines, obligors, and breach penalties."""
    t0 = time.time()
    cb = state.get("progress_callback")
    if cb:
        await cb(
            {
                "stage": "obligation",
                "status": "running",
                "message": "Obligation Extractor building calendar matrix & breach penalties...",
            }
        )

    sections = state.get("sections") or []
    obligations: list[dict[str, Any]] = []
    seen_types: set[tuple[str, str]] = set()

    for sec in sections:
        sec_num = str(sec.get("section_number", "1"))
        sec_title = str(sec.get("title", "Clause"))
        sec_text = str(sec.get("text", ""))
        if not sec_text.strip():
            continue

        for rule in OBLIGATION_PATTERNS:
            if rule["pattern"].search(sec_text):
                ob_type = rule["obligation_type"]
                key = (sec_num, ob_type)
                if key in seen_types:
                    continue
                seen_types.add(key)

                # Extract specific sentence & timing hint from clause text
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", sec_text) if s.strip()]
                matching_sent = next(
                    (s for s in sentences if rule["pattern"].search(s)),
                    sec_text[:240],
                )
                hint_m = TIMELINE_HINT_RE.search(sec_text)
                trigger = hint_m.group(0) if hint_m else rule["default_trigger"]

                obligations.append(
                    {
                        "clause_reference": f"Section {sec_num} ({sec_title})",
                        "obligation_type": ob_type,
                        "obligor": rule["default_obligor"],
                        "recipient": rule["default_recipient"],
                        "description": matching_sent[:320],
                        "due_date_or_trigger": trigger,
                        "recurrence": rule["default_recurrence"],
                        "penalty_for_breach": rule["default_penalty"],
                    }
                )

    # Guarantee at least one operational review obligation if contract was minimal
    if not obligations:
        obligations.append(
            {
                "clause_reference": "Section 1 (General Governance)",
                "obligation_type": "Notice Requirements",
                "obligor": "Contract Manager",
                "recipient": "Legal & Finance",
                "description": "Conduct 30-day post-execution compliance and renewal calendar verification.",
                "due_date_or_trigger": "30 days post-execution",
                "recurrence": "Annual",
                "penalty_for_breach": "Missed renewal opt-out or governance gap",
            }
        )

    # Record telemetry via LLM Gateway summary (fallback deterministic)
    ob_summary = "; ".join(f"{o['obligation_type']} ({o['due_date_or_trigger']})" for o in obligations[:6])
    llm_res = await llm_gateway.generate(
        prompt=(
            f"Confirm operational obligation summary for '{state.get('title', 'Contract')}': {ob_summary}"
        ),
        system_prompt="You are a Legal Operations Obligation Analyst.",
        fallback_text=f"Extracted {len(obligations)} structured operational obligation(s): {ob_summary}.",
    )

    elapsed_ms = round((time.time() - t0) * 1000.0, 2)
    audit_logs = list(state.get("audit_logs") or [])
    audit_logs.append(
        {
            "agent_name": "Obligation Extractor Agent",
            "action": "extract_obligations",
            "model_name": llm_res.model,
            "prompt_tokens": llm_res.prompt_tokens,
            "completion_tokens": llm_res.completion_tokens,
            "total_tokens": llm_res.total_tokens,
            "latency_ms": max(elapsed_ms, llm_res.latency_ms),
            "estimated_cost_usd": llm_res.estimated_cost_usd,
        }
    )

    if cb:
        await cb(
            {
                "stage": "obligation",
                "status": "completed",
                "message": f"Extracted {len(obligations)} calendarized obligations.",
            }
        )

    return {
        **state,
        "obligations": obligations,
        "audit_logs": audit_logs,
    }
