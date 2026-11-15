"""Opposing Counsel Agent Node: Counterparty negotiator defending commercial velocity and vendor leverage."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractGraphState


_COUNTERPARTY_DEFENSES: dict[str, str] = {
    "uncapped_indemnification": "Counterparty relies on standard IP and third-party bodily-injury carve-outs to align risk allocation with vendor pricing; we can negotiate a super-cap rather than a bare 1x limit.",
    "consequential_damages_missing": "Maintaining direct-plus-foreseeable remedies protects recovery for willful misconduct or confidentiality breaches without opening speculative claims.",
    "ai_model_training": "Vendor requires telemetry and anonymized pattern retention to preserve service quality and latency SLAs, though we can isolate raw Customer prompts from shared weights.",
    "auto_renewal_trap": "Annual automatic renewals prevent abrupt service interruptions and lock in multi-year unit pricing discounts; a 45-to-60 day notice window balances operational planning.",
    "immediate_termination_no_cure": "Immediate suspension rights are standard for security compromises, AUP violations, or non-payment where a 30-day wait amplifies platform risk.",
    "unlimited_audit_rights": "Broad regulatory inspection rights reflect enterprise compliance expectations; limiting frequency to once annually except for security incidents is an acceptable middle ground.",
    "asymmetric_fee_shifting": "Collection cost recovery deters strategic payment withholding on undisputed invoices; mutual prevailing-party language is acceptable for general litigation.",
    "non_compete_overbreadth": "Exclusivity provisions underwrite dedicated engineering allocation and preferential pricing tiers; narrowing scope to named deliverables preserves commercial intent.",
    "broad_subprocessor_shield": "Cloud-native delivery depends on elastic multi-region subprocessors; advance web-portal RSS notification satisfies transparency without operational bottlenecks.",
    "liquidated_damages_trap": "Pre-agreed remedies establish predictable exit economics when dedicated capacity is reserved exclusively for Customer.",
}


async def opposing_node(state: ContractGraphState) -> ContractGraphState:
    """Challenge Auditor findings from the counterparty commercial perspective."""
    start = time.time()
    risks = state.get("identified_risks") or []
    transcript = list(state.get("debate_transcript") or [])
    now_iso = datetime.now(timezone.utc).isoformat()

    def _fallback_rebuttal() -> str:
        if not risks:
            return "Counterparty accepts the draft terms as balanced market-standard commercial language."
        return (
            f"Opposing Counsel pushes back on {len(risks)} proposed objections: vendor pricing assumes standard commercial risk allocation, "
            "operational continuity carve-outs, and elastic cloud delivery. Propose calibrated middle-ground compromises rather than blanket deletions."
        )

    prompt = (
        f"Contract: {state.get('title', 'Agreement')}\n"
        f"Respond as Counterparty Counsel to these enterprise objections: "
        + "; ".join(f"{r['category']} (Section {r['section_number']})" for r in risks)
    )
    llm_resp = await llm_gateway.generate(
        prompt=prompt,
        system_prompt="You are Opposing Counsel representing the counterparty vendor. Defend commercial efficiency and propose pragmatic compromises in 2 sentences.",
        fallback_fn=_fallback_rebuttal,
    )

    transcript.append(
        {
            "agent": "Opposing Counsel",
            "role": "Counterparty Negotiator",
            "section_number": risks[0]["section_number"] if risks else "General",
            "stance": "Commercial Leverage & Market Terms",
            "message": llm_resp.text,
            "timestamp": now_iso,
        }
    )

    for risk in risks:
        rebuttal = _COUNTERPARTY_DEFENSES.get(
            risk.get("key", ""),
            "Counterparty maintains this clause reflects standard commercial allocation and requests a balanced mutual compromise.",
        )
        transcript.append(
            {
                "agent": "Opposing Counsel",
                "role": "Counterparty Negotiator",
                "section_number": risk["section_number"],
                "stance": "Counter-Proposal",
                "message": f"[Re: {risk['category']}] {rebuttal}",
                "timestamp": now_iso,
            }
        )

    total_latency_ms = round((time.time() - start) * 1000.0, 2)
    audit_records = list(state.get("audit_records") or [])
    audit_records.append(
        {
            "agent_name": "Opposing Counsel",
            "action": "counterparty_negotiation",
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
                "node": "opposing_node",
                "status": "completed",
                "rebuttals": len(risks),
            }
        )

    return {
        **state,
        "debate_transcript": transcript,
        "audit_records": audit_records,
    }
