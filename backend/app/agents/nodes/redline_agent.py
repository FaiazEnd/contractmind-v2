"""Redline Synthesizer Agent Node: consensus drafting, diff tokens, composite risk scoring, and prompt regeneration."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractAgentState
from app.services.diff_engine import compute_word_diff


async def redline_node(state: ContractAgentState) -> ContractAgentState:
    """Synthesize balanced consensus redlines, diff tokens, and composite risk score."""
    t0 = time.time()
    risks: List[Dict[str, Any]] = list(state.get("identified_risks") or [])
    transcript: List[Dict[str, Any]] = list(state.get("debate_transcript") or [])
    audit_events: List[Dict[str, Any]] = list(state.get("audit_events") or [])

    redlines: List[Dict[str, Any]] = []
    risk_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    total_score = 0.0

    for idx, risk in enumerate(risks, start=1):
        sev = str(risk.get("severity", "MEDIUM")).upper()
        sev_key = sev.lower() if sev.lower() in risk_summary else "medium"
        risk_summary[sev_key] += 1
        total_score += float(risk.get("score", 50.0))

        original_text = str(risk.get("original_text") or risk.get("matched_excerpt") or "").strip()
        suggested_text = str(risk.get("consensus_template") or "").strip()
        diff_tokens = compute_word_diff(original_text, suggested_text)

        redline_id = f"rl-{idx}-{uuid.uuid4().hex[:6]}"
        redlines.append(
            {
                "id": redline_id,
                "section_number": str(risk.get("section_number", "1")),
                "original_text": original_text,
                "suggested_text": suggested_text,
                "diff_type": "modification",
                "risk_severity": sev,
                "legal_rationale": f"{risk.get('category')}: {risk.get('legal_rationale')}",
                "diff_tokens": diff_tokens,
                "accepted": None,
                "custom_prompt": None,
            }
        )

        transcript.append(
            {
                "turn_index": len(transcript) + 1,
                "agent_name": "Redline Synthesizer Agent",
                "role": "Consensus Arbiter",
                "section_number": risk.get("section_number", "1"),
                "risk_category": risk.get("category", "Clause"),
                "argument": (
                    f"Consensus Arbiter Ruling (Section {risk.get('section_number')}): Synthesized balanced redline "
                    f"[{redline_id}] reconciling enterprise risk ({sev}) with commercial viability."
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    num_risks = len(risks)
    overall_score = round(min(100.0, total_score / max(1, num_risks)), 1) if num_risks > 0 else 0.0

    llm_res = await llm_gateway.generate(
        prompt=(
            f"Synthesize executive arbiter summary for {num_risks} consensus redlines "
            f"(Composite Score {overall_score}/100)."
        ),
        system_instruction="You are the Redline Synthesizer Agent (Consensus Arbiter).",
        fallback_text=(
            f"Synthesized {len(redlines)} consensus redlines with composite risk score {overall_score}/100."
        ),
    )

    latency_ms = round((time.time() - t0) * 1000.0, 2)
    audit_events.append(
        {
            "agent_name": "Redline Synthesizer Agent",
            "action": "consensus_redline_synthesis",
            "model_name": llm_res.model_name,
            "prompt_tokens": llm_res.prompt_tokens,
            "completion_tokens": llm_res.completion_tokens,
            "total_tokens": llm_res.total_tokens,
            "latency_ms": max(latency_ms, llm_res.latency_ms),
            "estimated_cost_usd": llm_res.estimated_cost_usd,
        }
    )

    state["redlines"] = redlines
    state["overall_risk_score"] = overall_score
    state["risk_summary"] = risk_summary
    state["debate_transcript"] = transcript
    state["audit_events"] = audit_events
    return state


async def regenerate_redline_with_prompt(
    redline: Dict[str, Any],
    custom_prompt: str,
    contract_title: str,
) -> Dict[str, Any]:
    """Rewrite a single clause redline on demand from an attorney's custom instruction."""
    t0 = time.time()
    original_text = str(redline.get("original_text", ""))
    current_suggested = str(redline.get("suggested_text", ""))
    section_num = str(redline.get("section_number", "1"))

    # Construct deterministic tailored fallback respecting the attorney's instruction keywords
    instruction_lower = custom_prompt.lower()
    tailored_fallback = current_suggested
    if "cap" in instruction_lower or "limit" in instruction_lower or "month" in instruction_lower:
        tailored_fallback = (
            f"{current_suggested} Notwithstanding the foregoing, aggregate liability under Section {section_num} "
            "shall be strictly capped as instructed: not exceeding six (6) months of fees paid or payable, "
            "with mutual waiver of indirect damages."
        )
    elif "mutual" in instruction_lower or "reciprocal" in instruction_lower:
        tailored_fallback = (
            f"All obligations, remedies, and protective covenants in Section {section_num} shall apply on a strictly "
            f"mutual and reciprocal basis between Customer and Provider. {current_suggested}"
        )
    elif "delete" in instruction_lower or "remove" in instruction_lower or "strike" in instruction_lower:
        tailored_fallback = (
            f"[Clause struck in its entirety pursuant to counsel directive: '{custom_prompt.strip()}'. "
            "Standard statutory default rules shall govern.]"
        )
    else:
        tailored_fallback = (
            f"{current_suggested} [Counsel Revision Directive Applied: {custom_prompt.strip()}]"
        )

    llm_prompt = (
        f"Rewrite the contract clause in Section {section_num} of '{contract_title}' strictly following this instruction.\n"
        f"Attorney Instruction: {custom_prompt}\n"
        f"Original Clause:\n{original_text}\n\n"
        f"Prior Redline Draft:\n{current_suggested}\n\n"
        "Return ONLY the revised legal clause text ready to replace the section."
    )
    llm_res = await llm_gateway.generate(
        prompt=llm_prompt,
        system_instruction="You are a senior M&A and commercial contracts partner drafting precise redline text.",
        fallback_text=tailored_fallback,
    )

    new_suggested = llm_res.text.strip()
    new_diff_tokens = compute_word_diff(original_text, new_suggested)

    updated = {
        **redline,
        "suggested_text": new_suggested,
        "diff_tokens": new_diff_tokens,
        "accepted": None,
        "custom_prompt": custom_prompt,
        "legal_rationale": f"{redline.get('legal_rationale', '')} | Custom rewrite: {custom_prompt}".strip(" |"),
    }

    latency_ms = round((time.time() - t0) * 1000.0, 2)
    audit_meta = {
        "agent_name": "Redline Synthesizer Agent",
        "action": "custom_prompt_redline_rewrite",
        "model_name": llm_res.model_name,
            "prompt_tokens": llm_res.prompt_tokens,
            "completion_tokens": llm_res.completion_tokens,
            "total_tokens": llm_res.total_tokens,
            "latency_ms": max(latency_ms, llm_res.latency_ms),
            "estimated_cost_usd": llm_res.estimated_cost_usd,
    }
    return {"redline": updated, "audit": audit_meta}
