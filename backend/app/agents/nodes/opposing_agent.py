"""Opposing Counsel Agent: Counterparty negotiator defending commercial vendor terms."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractAnalysisState


OPPOSING_DEFENSES: dict[str, str] = {
    "Uncapped Indemnification": (
        "Counterparty requires broad indemnification coverage for customer-supplied content and unauthorized integrations to keep base subscription pricing competitive without raising risk premiums."
    ),
    "Consequential Damages Waiver Missing": (
        "Certain direct operational losses and regulatory exposure from misuse cannot be arbitrarily waived where vendor bears asymmetric platform uptime commitments."
    ),
    "AI Model Training on Proprietary Data": (
        "Aggregated telemetry and de-identified interaction patterns enable latency tuning and automated anomaly detection that directly benefit enterprise accuracy."
    ),
    "Auto-Renewal Without Notice Trap": (
        "Standard multi-year renewal schedules preserve locked-in volume discount tiers and guarantee dedicated cloud capacity provisioning."
    ),
    "Immediate Termination Without Cure Window": (
        "Immediate suspension and termination rights are necessary strictly to prevent ongoing security compromises, payment default, or statutory violations."
    ),
    "Unlimited Audit Rights": (
        "Broad audit inspection rights reflect standard regulatory oversight expectations across regulated financial and healthcare deployments."
    ),
    "Asymmetric Attorney Fee Shifting": (
        "Fee recovery protects the service provider against uncollected invoices and frivolous collection disputes."
    ),
    "Non-Compete / Exclusivity Overbreadth": (
        "Exclusivity and non-compete protections safeguard substantial bespoke R&D and co-investment commitments made for this transaction."
    ),
    "Broad Data Exfiltration / Subprocessor Shield": (
        "Global cloud infrastructure relies on elastic multi-region subprocessors and automated failover; requiring individual pre-approvals degrades SLA availability."
    ),
    "Liquidated Damages Penalty Trap": (
        "Committed term pricing amortizes upfront onboarding engineering; early termination recovery reflects committed infrastructure reservations."
    ),
}


async def opposing_node(state: ContractAnalysisState) -> ContractAnalysisState:
    """Review flagged risks from counterparty counsel perspective and append arguments."""
    t0 = time.time()
    cb = state.get("progress_callback")
    if cb:
        await cb(
            {
                "stage": "opposing",
                "status": "running",
                "message": "Opposing Counsel Agent formulating counterparty negotiation rebuttal...",
            }
        )

    risks = state.get("identified_risks") or []
    debate_transcript = list(state.get("debate_transcript") or [])
    ts = datetime.now(timezone.utc).isoformat()

    risk_summary_lines = "\n".join(
        f"- Section {r['section_number']}: {r['category']}" for r in risks
    ) or "No major risks raised."

    fallback_rebuttal = (
        f"Opposing Counsel acknowledges the {len(risks)} objection(s) raised by Auditor Agent. "
        "From a commercial standpoint, our baseline draft reflects standard market risk allocation, volume discount pricing, and cloud scalability requirements. "
        "We are prepared to accept balanced mutual caps and structured 30-day notice mechanisms provided operational flexibility and fee certainty remain intact."
    )

    llm_res = await llm_gateway.generate(
        prompt=(
            f"You are Opposing Counsel negotiating '{state.get('title', 'Contract')}'.\n"
            f"Auditor objected to:\n{risk_summary_lines}\n\n"
            "Write a concise 3-sentence commercial counter-position defending counterparty leverage while signaling room for compromise."
        ),
        system_prompt="You are sharp, pragmatic Counterparty Commercial Legal Counsel.",
        fallback_text=fallback_rebuttal,
    )

    debate_transcript.append(
        {
            "agent": "Opposing Counsel Agent",
            "role": "Counterparty Negotiator",
            "section_number": "ALL",
            "category": "Commercial Counter-Position",
            "argument": llm_res.text,
            "timestamp": ts,
        }
    )

    for r in risks:
        cat = r["category"]
        defense = OPPOSING_DEFENSES.get(
            cat,
            "Standard commercial draft reflects market-rate pricing and operational efficiency.",
        )
        debate_transcript.append(
            {
                "agent": "Opposing Counsel Agent",
                "role": "Counterparty Negotiator",
                "section_number": r["section_number"],
                "category": cat,
                "argument": (
                    f"Rebuttal on Section {r['section_number']} ({cat}): {defense} "
                    "Counterparty will compromise only if mutual procedural safeguards are preserved."
                ),
                "timestamp": ts,
            }
        )

    elapsed_ms = round((time.time() - t0) * 1000.0, 2)
    audit_logs = list(state.get("audit_logs") or [])
    audit_logs.append(
        {
            "agent_name": "Opposing Counsel Agent",
            "action": "counterparty_rebuttal",
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
                "stage": "opposing",
                "status": "completed",
                "message": "Opposing Counsel counter-arguments logged.",
            }
        )

    return {
        **state,
        "debate_transcript": debate_transcript,
        "audit_logs": audit_logs,
    }
