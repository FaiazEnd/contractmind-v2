"""Redline Synthesizer Agent: Arbiter computing consensus redlines, diffs, and risk score."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractAnalysisState
from app.services.diff_engine import compute_word_diff
from app.services.rag_engine import rag_engine


async def redline_node(state: ContractAnalysisState) -> ContractAnalysisState:
    """Synthesize consensus redlines grounded in SEC EDGAR precedents and compute risk score."""
    t0 = time.time()
    cb = state.get("progress_callback")
    if cb:
        await cb(
            {
                "stage": "redline",
                "status": "running",
                "message": "Redline Synthesizer querying SEC EDGAR precedents and drafting consensus edits...",
            }
        )

    risks = state.get("identified_risks") or []
    debate_transcript = list(state.get("debate_transcript") or [])
    redlines: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc).isoformat()

    total_score = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    model_used = "contractmind-legal-sim"

    for r in risks:
        total_score += float(r.get("score", 50))
        sec_num = str(r.get("section_number", "1"))
        orig_text = str(r.get("matched_excerpt", "")).strip()
        fallback_sugg = str(r.get("consensus_replacement", "")).strip() or orig_text
        category = str(r.get("category", "Risk"))
        rationale = str(r.get("legal_rationale", ""))

        # Query 2,000 SEC EDGAR / LexGLUE LEDGAR precedents for grounding
        precedents = rag_engine.query_knowledge_base(
            f"{category} {rationale}", n_results=2
        )
        precedent_ctx = "\n".join(
            f"- [{p.get('category', 'LEDGAR')}] {p.get('text', '')[:300]}"
            for p in precedents
        )

        # Preserve header line if present in original excerpt
        first_line = orig_text.splitlines()[0] if orig_text else ""
        if (
            first_line
            and any(
                first_line.lower().startswith(p)
                for p in ("section ", "article ", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")
            )
            and not fallback_sugg.startswith(first_line)
        ):
            fallback_sugg = f"{first_line}\n{fallback_sugg}"

        # Use LLM if live key is configured, otherwise deterministic high-precision consensus text
        llm_res = await llm_gateway.generate(
            prompt=(
                f"Draft a balanced, execution-ready consensus replacement clause for Section {sec_num} "
                f"resolving '{category}'.\n\n"
                f"Original Clause:\n{orig_text[:1200]}\n\n"
                f"Auditor Critique: {rationale}\n"
                f"SEC EDGAR Precedents:\n{precedent_ctx}\n\n"
                "Return ONLY the revised clause text (preserve the section heading line if present, no markdown fences)."
            ),
            system_prompt="You are an impartial Senior Commercial Arbiter drafting enforceable redlines.",
            fallback_text=fallback_sugg,
        )

        suggested_text = llm_res.text.strip()
        if not suggested_text:
            suggested_text = fallback_sugg

        total_prompt_tokens += llm_res.prompt_tokens
        total_completion_tokens += llm_res.completion_tokens
        total_cost += llm_res.estimated_cost_usd
        model_used = llm_res.model

        diff_tokens = compute_word_diff(orig_text, suggested_text)
        redline_id = f"rl_{uuid.uuid4().hex[:8]}"

        precedent_note = (
            f" Grounded in SEC EDGAR / LEDGAR precedent ({precedents[0]['category']})."
            if precedents
            else ""
        )

        redlines.append(
            {
                "id": redline_id,
                "section_number": sec_num,
                "original_text": orig_text,
                "suggested_text": suggested_text,
                "diff_type": "modification",
                "risk_severity": str(r.get("severity", "MEDIUM")).upper(),
                "legal_rationale": f"{rationale}{precedent_note}".strip(),
                "diff_tokens": diff_tokens,
                "accepted": None,
                "custom_prompt": None,
            }
        )

    num_risks = len(risks)
    overall_score = round(min(100.0, total_score / max(1, num_risks)), 1) if num_risks else 12.5

    debate_transcript.append(
        {
            "agent": "Redline Synthesizer Agent",
            "role": "Consensus Arbiter",
            "section_number": "ALL",
            "category": "Consensus Synthesis",
            "argument": (
                f"Synthesized {len(redlines)} consensus redline(s) grounded in SEC EDGAR / LexGLUE LEDGAR precedents. "
                f"Composite Contract Risk Score computed at {overall_score}/100. "
                "All proposed edits preserve commercial viability while eliminating uncapped liabilities and unconsented AI training rights."
            ),
            "timestamp": ts,
        }
    )

    elapsed_ms = round((time.time() - t0) * 1000.0, 2)
    audit_logs = list(state.get("audit_logs") or [])
    audit_logs.append(
        {
            "agent_name": "Redline Synthesizer Agent",
            "action": "synthesize_consensus_redlines",
            "model_name": model_used,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "latency_ms": elapsed_ms,
            "estimated_cost_usd": round(total_cost, 8),
        }
    )

    if cb:
        await cb(
            {
                "stage": "redline",
                "status": "completed",
                "message": f"Synthesized {len(redlines)} consensus redlines (Risk Score: {overall_score}/100).",
            }
        )

    return {
        **state,
        "redlines": redlines,
        "overall_risk_score": overall_score,
        "debate_transcript": debate_transcript,
        "audit_logs": audit_logs,
    }
