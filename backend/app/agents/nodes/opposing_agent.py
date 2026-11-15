"""Opposing Counsel Agent Node: defends vendor/counterparty leverage and commercial efficiency."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractAgentState

COUNTERPARTY_DEFENSES: Dict[str, str] = {
    "Uncapped Indemnification": (
        "Counterparty accepts a balanced super-cap for third-party IP claims but rejects open-ended enterprise exposure "
        "unrelated to Provider's core SaaS deliverables; prompt defense control is essential to manage litigation spend."
    ),
    "Consequential Damages Waiver Missing": (
        "Standard commercial pricing assumes predictable unit economics; mutual exclusion of indirect/lost-profit damages "
        "is market-standard provided Provider's fee-based liability ceiling remains intact."
    ),
    "AI Model Training on Proprietary Data": (
        "Counterparty requires aggregated telemetry and anonymized operational diagnostics to maintain model reliability "
        "and SLA uptime, though we can wall off raw proprietary Customer Data from shared foundation model weights."
    ),
    "Auto-Renewal Without Notice Trap": (
        "Multi-quarter capacity reservation and dedicated cloud tenancy justify predictable renewal notice windows; "
        "30-day non-renewal notice with automated reminder is acceptable if annual rate-lock protections apply."
    ),
    "Immediate Termination Without Cure Window": (
        "Counterparty requires immediate suspension/termination rights strictly for severe AUP, security, or payment default "
        "events, while accepting a 30-day cure period for ordinary operational breaches."
    ),
    "Unlimited Audit Rights": (
        "Unrestricted on-site audits expose multi-tenant infrastructure to security and operational disruptions; "
        "annual SOC 2 Type II / ISO 27001 certification delivery should serve as the primary audit mechanism."
    ),
    "Asymmetric Attorney Fee Shifting": (
        "Fee recovery clauses deter frivolous non-payment disputes; converting to a mutual prevailing-party standard "
        "preserves symmetry while maintaining collection discipline."
    ),
    "Non-Compete / Exclusivity Overbreadth": (
        "Dedicated solution engineering investments warrant commercial commitment, though Counterparty agrees to drop "
        "blanket exclusivity covenants in exchange for committed annual volume tiers."
    ),
    "Broad Data Exfiltration / Subprocessor Shield": (
        "Modern cloud architectures rely on elastic hyperscaler subprocessors; advance 30-day email/portal notice is "
        "workable provided Customer objection remedies are limited to good-faith mitigation or pro-rata termination."
    ),
    "Liquidated Damages Penalty Trap": (
        "Committed enterprise discounts are amortized over the full subscription term; while 100% acceleration is waived "
        "for Provider's uncured breach, termination for convenience should settle unpaid committed minimums."
    ),
}


async def opposing_node(state: ContractAgentState) -> ContractAgentState:
    """Review flagged risks from counterparty counsel perspective."""
    t0 = time.time()
    risks: List[Dict[str, Any]] = list(state.get("identified_risks") or [])
    transcript: List[Dict[str, Any]] = list(state.get("debate_transcript") or [])
    audit_events: List[Dict[str, Any]] = list(state.get("audit_events") or [])

    for risk in risks:
        cat = str(risk.get("category", ""))
        defense = COUNTERPARTY_DEFENSES.get(
            cat,
            "Counterparty maintains that standard commercial allocation reflects negotiated enterprise pricing and SLA guarantees.",
        )
        transcript.append(
            {
                "turn_index": len(transcript) + 1,
                "agent_name": "Opposing Counsel Agent",
                "role": "Counterparty Commercial Negotiator",
                "section_number": risk.get("section_number", "1"),
                "risk_category": cat,
                "argument": (
                    f"Rebuttal on Section {risk.get('section_number')} ({cat}): {defense}"
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    llm_res = await llm_gateway.generate(
        prompt=(
            f"Provide counterparty commercial pushback position for {len(risks)} flagged clauses in "
            f"'{state.get('title', 'Agreement')}'."
        ),
        system_instruction="You are Opposing Counsel defending commercial efficiency and vendor leverage.",
        fallback_text=f"Opposing Counsel reviewed {len(risks)} flagged issues and submitted commercial counter-positions.",
    )

    latency_ms = round((time.time() - t0) * 1000.0, 2)
    audit_events.append(
        {
            "agent_name": "Opposing Counsel Agent",
            "action": "adversarial_counter_argument",
            "model_name": llm_res.model_name,
            "prompt_tokens": llm_res.prompt_tokens,
            "completion_tokens": llm_res.completion_tokens,
            "total_tokens": llm_res.total_tokens,
            "latency_ms": max(latency_ms, llm_res.latency_ms),
            "estimated_cost_usd": llm_res.estimated_cost_usd,
        }
    )

    state["debate_transcript"] = transcript
    state["audit_events"] = audit_events
    return state
