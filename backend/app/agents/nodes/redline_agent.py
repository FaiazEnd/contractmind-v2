"""Redline Synthesizer Agent Node: Consensus arbiter, word-level diff builder, and composite risk scorer."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractGraphState
from app.services.diff_engine import compute_diff_tokens


async def redline_node(state: ContractGraphState) -> ContractGraphState:
    """Synthesize consensus redlines, compute diff tokens, and score composite risk."""
    start = time.time()
    risks = state.get("identified_risks") or []
    redlines: list[dict[str, Any]] = []

    risk_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    total_score = 0.0

    for risk in risks:
        sev = str(risk.get("severity", "MEDIUM")).upper()
        sev_key = sev.lower()
        if sev_key in risk_summary:
            risk_summary[sev_key] += 1
        total_score += float(risk.get("score", 50.0))

        original_text = risk.get("matched_excerpt", "")
        suggested_text = risk.get("suggested_mitigation", "")
        diff_tokens = compute_diff_tokens(original_text, suggested_text)

        redlines.append(
            {
                "id": f"redline-{uuid.uuid4().hex[:8]}",
                "section_number": str(risk.get("section_number", "1")),
                "original_text": original_text,
                "suggested_text": suggested_text,
                "diff_type": "modification",
                "risk_severity": sev,
                "legal_rationale": f"{risk.get('category', 'Policy Risk')}: {risk.get('legal_rationale', '')}",
                "diff_tokens": diff_tokens,
                "accepted": None,
                "custom_prompt": None,
            }
        )

    num_risks = len(risks)
    overall_score = round(min(100.0, total_score / max(1, num_risks)), 1) if num_risks > 0 else 0.0

    def _fallback_arbiter() -> str:
        if not redlines:
            return "Consensus Arbiter confirms zero redlines required; contract scores 0.0/100 residual risk."
        return (
            f"Redline Synthesizer reconciled Auditor objections and Counterparty commercial positions into {len(redlines)} "
            f"consensus clause modification(s). Composite Risk Severity scored at {overall_score}/100."
        )

    llm_resp = await llm_gateway.generate(
        prompt=f"Synthesize arbiter summary for {len(redlines)} redlines with composite risk score {overall_score}/100.",
        system_prompt="You are the Redline Synthesizer Arbiter. State the consensus resolution concisely in 2 sentences.",
        fallback_fn=_fallback_arbiter,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    transcript = list(state.get("debate_transcript") or [])
    transcript.append(
        {
            "agent": "Redline Synthesizer",
            "role": "Consensus Arbiter & Diff Builder",
            "section_number": "Summary",
            "stance": f"Consensus Reached (Risk {overall_score}/100)",
            "message": llm_resp.text,
            "timestamp": now_iso,
        }
    )

    total_latency_ms = round((time.time() - start) * 1000.0, 2)
    audit_records = list(state.get("audit_records") or [])
    audit_records.append(
        {
            "agent_name": "Redline Synthesizer",
            "action": "consensus_redline_synthesis",
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
                "node": "redline_node",
                "status": "completed",
                "redlines_generated": len(redlines),
                "overall_risk_score": overall_score,
            }
        )

    return {
        **state,
        "redlines": redlines,
        "overall_risk_score": overall_score,
        "risk_summary": risk_summary,
        "debate_transcript": transcript,
        "audit_records": audit_records,
    }
