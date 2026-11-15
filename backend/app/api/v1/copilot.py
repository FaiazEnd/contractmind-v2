"""Grounded Legal AI Copilot & CFO Briefing Generator endpoint."""

from __future__ import annotations

import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_client import llm_gateway
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.schemas.contract_schemas import CopilotChatRequest, CopilotChatResponse
from app.services.rag_engine import rag_engine

router = APIRouter()


def _build_grounded_fallback(contract: Contract, message: str, passages: List[Dict[str, Any]]) -> str:
    msg_lower = message.lower()
    risks = list(contract.identified_risks or [])
    redlines = list(contract.redlines or [])
    obligations = list(contract.obligations or [])

    if "cfo" in msg_lower or "executive" in msg_lower or "summary" in msg_lower:
        crit = sum(1 for r in risks if str(r.get("severity", "")).upper() == "CRITICAL")
        high = sum(1 for r in risks if str(r.get("severity", "")).upper() == "HIGH")
        lines = [
            f"### CFO Executive Risk Brief: {contract.title}",
            f"- **Composite Risk Score:** {contract.overall_risk_score}/100 ({crit} Critical, {high} High severity findings).",
            f"- **Financial & Operational Exposure:** {len(redlines)} consensus redlines synthesized; {len(obligations)} binding post-execution obligations tracked.",
            "- **Top Financial Risks:**",
        ]
        for r in risks[:4]:
            lines.append(
                f"  - **[Section {r.get('section_number', '1')}] {r.get('category')} ({r.get('severity')}):** {r.get('legal_rationale')}"
            )
        lines.append("- **Recommendation:** Do not execute until Critical redlines (indemnity cap, AI training ban, and consequential damages waiver) are accepted into the clean draft.")
        return "\n".join(lines)

    if "email" in msg_lower or "pushback" in msg_lower or "opposing" in msg_lower:
        top_refs = ", ".join(f"Section {r.get('section_number')}" for r in risks[:3]) or "Key Commercial Sections"
        bullets = "\n".join(
            f"- **Section {r.get('section_number')} ({r.get('category')}):** {r.get('suggested_mitigation')}"
            for r in risks[:4]
        )
        return (
            f"**Subject:** Proposed Consensus Redlines — {contract.title}\n\n"
            f"Dear Counterparty Counsel,\n\n"
            f"Thank you for sharing the draft of **{contract.title}**. We completed our playbook review and circulated a "
            f"tracked-changes markup addressing {top_refs}.\n\n"
            f"Our key commercial alignment items are:\n{bullets}\n\n"
            f"All revisions align with mutual market-standard risk allocation. Please let us know if you would like to walk through these updates on a brief call.\n\n"
            f"Best regards,\nEnterprise Legal Counsel"
        )

    if "indemn" in msg_lower or "liability" in msg_lower or "trap" in msg_lower:
        matching = [
            r for r in risks
            if "indemn" in str(r.get("category", "")).lower() or "damage" in str(r.get("category", "")).lower()
        ]
        if matching:
            details = "\n".join(
                f"- **[Section {m.get('section_number')}] {m.get('category')} ({m.get('severity')}):** {m.get('legal_rationale')} "
                f"Recommended cap/fix: {m.get('suggested_mitigation')}"
                for m in matching
            )
            return f"### Indemnity & Liability Trap Audit\n{details}"

    # General RAG-grounded clause answer
    if passages:
        top = passages[0]
        sec_cite = f"[Section {top.get('section_number', '1')}]"
        other_cites = ", ".join(f"[Section {p.get('section_number')}]" for p in passages[1:3])
        return (
            f"Based on {sec_cite} ({top.get('title', 'Clause')}): {top.get('text', '')[:420]}\n\n"
            + (f"Related provisions appear in {other_cites}. " if other_cites else "")
            + f"Across this agreement, ContractMind identified {len(risks)} risk findings and generated {len(redlines)} consensus redlines."
        )

    return (
        f"ContractMind reviewed **{contract.title}** ({len(contract.extracted_sections or [])} sections, "
        f"{len(risks)} risks, {len(redlines)} redlines). Ask about a specific clause, indemnity exposure, or request a CFO Risk Summary."
    )


@router.post("/{contract_id}/chat", response_model=CopilotChatResponse)
async def copilot_chat(
    contract_id: str,
    payload: CopilotChatRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Grounded Legal AI Copilot answering contract questions with RAG clause citations."""
    t0 = time.time()
    res = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = res.scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    passages = rag_engine.query_similar(
        contract_id=contract.id,
        query=payload.message,
        n_results=4,
        fallback_sections=list(contract.extracted_sections or []),
    )
    citations = []
    for p in passages:
        cite = f"[Section {p.get('section_number', '1')}]"
        if cite not in citations:
            citations.append(cite)

    context_blob = "\n\n".join(p.get("text", "") for p in passages)
    redline_summary = "\n".join(
        f"- Section {r.get('section_number')}: {r.get('legal_rationale')}"
        for r in (contract.redlines or [])[:5]
    )

    fallback_answer = _build_grounded_fallback(contract, payload.message, passages)
    llm_res = await llm_gateway.generate(
        prompt=(
            f"Contract Title: {contract.title}\n"
            f"User Question: {payload.message}\n\n"
            f"Retrieved Clause Passages:\n{context_blob}\n\n"
            f"Synthesized Redlines:\n{redline_summary}\n\n"
            "Answer thoroughly with explicit [Section X] citations."
        ),
        system_instruction="You are ContractMind Legal AI Copilot. Ground every claim in provided sections and cite [Section X].",
        fallback_text=fallback_answer,
    )

    latency_ms = round((time.time() - t0) * 1000.0, 2)
    db.add(
        AuditLog(
            contract_id=contract.id,
            agent_name="Legal AI Copilot",
            action="rag_grounded_copilot_chat",
            model_name=llm_res.model_name,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            total_tokens=llm_res.total_tokens,
            latency_ms=max(latency_ms, llm_res.latency_ms),
            estimated_cost_usd=llm_res.estimated_cost_usd,
        )
    )
    await db.commit()

    return {
        "answer": llm_res.text,
        "citations": citations or ["[Section 1]"],
        "retrieved_passages": passages,
        "suggested_followups": [
            "Generate a CFO Risk Summary for executive sign-off",
            "Draft a pushback email to opposing counsel for Critical redlines",
            "Audit uncapped indemnity and consequential damages exposure",
        ],
        "model_used": llm_res.model_name,
    }
