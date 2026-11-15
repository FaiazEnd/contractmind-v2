"""Obligation Extractor Agent Node: extracts payment, audit, deletion, insurance, SLA, and notice duties."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractAgentState

OBLIGATION_RULES: List[Dict[str, Any]] = [
    {
        "obligation_type": "Payment",
        "pattern": re.compile(r"(?:invoice|net\s+\d+|fee|payment|remit|payable\s+within)", re.IGNORECASE),
        "obligor": "Customer",
        "recipient": "Provider",
        "default_trigger": "Net 30 days from invoice receipt",
        "recurrence": "Recurring (Per Invoice / Annual)",
        "default_penalty": "1.5% monthly late interest or service suspension after notice",
    },
    {
        "obligation_type": "Security Audit",
        "pattern": re.compile(r"(?:soc\s*2|iso\s*27001|audit|security\s+assessment|penetration\s+test)", re.IGNORECASE),
        "obligor": "Provider",
        "recipient": "Customer",
        "default_trigger": "Annually upon 30 days written request",
        "recurrence": "Annual",
        "default_penalty": "Material breach / regulatory remediation obligation",
    },
    {
        "obligation_type": "Data Deletion",
        "pattern": re.compile(r"(?:delet(?:e|ion)|destroy|return\s+(?:all\s+)?customer\s+data|purg(?:e|ing)|retain)", re.IGNORECASE),
        "obligor": "Provider",
        "recipient": "Customer",
        "default_trigger": "Within 30 days of agreement termination",
        "recurrence": "Upon Termination",
        "default_penalty": "Privacy indemnification & injunctive relief",
    },
    {
        "obligation_type": "Insurance",
        "pattern": re.compile(r"(?:insurance|cyber\s+liability|errors\s+and\s+omissions|certificate\s+of\s+insurance|coverage)", re.IGNORECASE),
        "obligor": "Provider",
        "recipient": "Customer",
        "default_trigger": "Maintained continuously; certificate within 15 days of renewal",
        "recurrence": "Annual",
        "default_penalty": "Suspension of onboarding / breach of representation",
    },
    {
        "obligation_type": "Service Credits",
        "pattern": re.compile(r"(?:uptime|sla|service\s+level|availability|service\s+credit|99\.\d+%)", re.IGNORECASE),
        "obligor": "Provider",
        "recipient": "Customer",
        "default_trigger": "Within 30 days following monthly SLA shortfall claim",
        "recurrence": "Monthly SLA Window",
        "default_penalty": "10% to 25% monthly fee service credit or termination right",
    },
    {
        "obligation_type": "Notice Requirements",
        "pattern": re.compile(r"(?:written\s+notice|non-renewal|breach\s+notification|security\s+incident|72\s*hours|subprocessor)", re.IGNORECASE),
        "obligor": "Both Parties",
        "recipient": "Designated Legal Contacts",
        "default_trigger": "72 hours (security incident) / 30 days (renewal or breach)",
        "recurrence": "Event-Driven",
        "default_penalty": "Automatic renewal lock-in or waiver of claim/cure defense",
    },
]

_TIMING_RE = re.compile(
    r"((?:within\s+)?\d+\s*(?:calendar|business)?\s*(?:days?|hours?|months?)|net\s+\d+|annually|monthly|upon\s+termination)",
    re.IGNORECASE,
)


async def obligation_node(state: ContractAgentState) -> ContractAgentState:
    """Extract structured operational obligations from contract sections."""
    t0 = time.time()
    sections: List[Dict[str, Any]] = list(state.get("sections") or [])
    audit_events: List[Dict[str, Any]] = list(state.get("audit_events") or [])
    obligations: List[Dict[str, Any]] = []
    seen_types = set()

    for sec in sections:
        sec_num = str(sec.get("section_number", "1"))
        sec_title = str(sec.get("title", f"Section {sec_num}"))
        sec_text = str(sec.get("text", ""))

        for rule in OBLIGATION_RULES:
            ob_type = rule["obligation_type"]
            if ob_type in seen_types:
                continue
            match = rule["pattern"].search(sec_text)
            if match:
                seen_types.add(ob_type)
                timing_match = _TIMING_RE.search(sec_text)
                trigger = timing_match.group(1).strip() if timing_match else rule["default_trigger"]
                snippet = " ".join(sec_text.split())[:220]
                obligations.append(
                    {
                        "clause_reference": f"Section {sec_num} ({sec_title})",
                        "obligation_type": ob_type,
                        "obligor": rule["obligor"],
                        "recipient": rule["recipient"],
                        "description": snippet,
                        "due_date_or_trigger": trigger,
                        "recurrence": rule["recurrence"],
                        "penalty_for_breach": rule["default_penalty"],
                    }
                )

    llm_res = await llm_gateway.generate(
        prompt=(
            f"Verify {len(obligations)} extracted obligations for '{state.get('title', 'Agreement')}': "
            + ", ".join(o["obligation_type"] for o in obligations)
        ),
        system_instruction="You are the Obligation Extractor Agent producing calendar and compliance matrices.",
        fallback_text=f"Extracted {len(obligations)} structured obligations across 6 operational categories.",
    )

    latency_ms = round((time.time() - t0) * 1000.0, 2)
    audit_events.append(
        {
            "agent_name": "Obligation Extractor Agent",
            "action": "obligation_matrix_extraction",
            "model_name": llm_res.model_name,
            "prompt_tokens": llm_res.prompt_tokens,
            "completion_tokens": llm_res.completion_tokens,
            "total_tokens": llm_res.total_tokens,
            "latency_ms": max(latency_ms, llm_res.latency_ms),
            "estimated_cost_usd": llm_res.estimated_cost_usd,
        }
    )

    state["obligations"] = obligations
    state["audit_events"] = audit_events
    return state
