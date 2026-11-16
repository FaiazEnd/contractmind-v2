"""Grounded Legal AI Copilot & CFO Briefing Generator endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_client import llm_gateway
from app.api.deps import get_contract_or_404
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.schemas.contract_schemas import CopilotChatRequest, CopilotChatResponse
from app.services.rag_engine import rag_engine

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/{contract_id}/chat", response_model=CopilotChatResponse)
async def copilot_chat(
    contract_id: str,
    payload: CopilotChatRequest,
    db: AsyncSession = Depends(get_db),
) -> CopilotChatResponse:
    """Answer legal inquiries grounded in contract RAG chunks, redlines, debate, and SEC EDGAR precedents."""
    contract = await get_contract_or_404(contract_id, db)
    question = payload.message.strip()

    # Ensure RAG is indexed for this contract
    if contract.extracted_sections:
        rag_engine.index_contract(contract.id, contract.extracted_sections)
    rag_engine.index_knowledge_base()

    passages = rag_engine.query_similar(contract.id, question, n_results=4)
    precedents = rag_engine.query_knowledge_base(question, n_results=2)

    citations = []
    for p in passages:
        sec_num = p.get("section_number")
        if sec_num:
            tag = f"[Section {sec_num}]"
            if tag not in citations:
                citations.append(tag)
    if not citations and contract.extracted_sections:
        citations = [
            f"[Section {s.get('section_number', '1')}]"
            for s in contract.extracted_sections[:2]
        ]

    fallback_answer = _build_grounded_fallback_answer(
        contract=contract,
        question=question,
        passages=passages,
        precedents=precedents,
        citations=citations,
    )

    context_block = "\n".join(p.get("text", "")[:400] for p in passages)
    redline_summary = "\n".join(
        f"- [Section {r.get('section_number')}] ({r.get('risk_severity')}): {r.get('legal_rationale')}"
        for r in (contract.redlines or [])[:5]
    )
    precedent_block = "\n".join(
        f"- {pr.get('category')}: {pr.get('text', '')[:250]}" for pr in precedents
    )

    llm_res = await llm_gateway.generate(
        prompt=(
            f"Contract: {contract.title} (Risk Score: {contract.overall_risk_score}/100)\n"
            f"Question: {question}\n\n"
            f"Relevant Contract Passages:\n{context_block}\n\n"
            f"Synthesized Redlines:\n{redline_summary}\n\n"
            f"SEC EDGAR / LEDGAR Precedents:\n{precedent_block}\n\n"
            "Provide a clear, executive-ready legal answer citing exact section references like [Section X]."
        ),
        system_prompt="You are ContractMind Legal AI Copilot. Always ground answers in retrieved contract sections and precedents.",
        fallback_text=fallback_answer,
    )

    db.add(
        AuditLog(
            contract_id=contract.id,
            agent_name="Legal AI Copilot",
            action="grounded_copilot_chat",
            model_name=llm_res.model,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            total_tokens=llm_res.total_tokens,
            latency_ms=llm_res.latency_ms,
            estimated_cost_usd=llm_res.estimated_cost_usd,
        )
    )
    await db.commit()

    return CopilotChatResponse(
        answer=llm_res.text,
        citations=citations,
        precedents=precedents,
        suggested_prompts=[
            "Generate a 3-bullet CFO Risk Summary for executive sign-off",
            "Draft a firm pushback email to Opposing Counsel",
            "Check for uncapped indemnity or AI training traps",
        ],
        model_used=llm_res.model,
    )


def _build_grounded_fallback_answer(
    contract: Contract,
    question: str,
    passages: list[dict[str, Any]],
    precedents: list[dict[str, Any]],
    citations: list[str],
) -> str:
    q = question.lower()
    risks = contract.identified_risks or []
    redlines = contract.redlines or []
    obligations = contract.obligations or []
    cite_str = ", ".join(citations) if citations else "[Section 1]"
    prec_cat = precedents[0]["category"] if precedents else "Commercial Standards"
    prec_excerpt = precedents[0]["text"][:220] if precedents else ""

    if "cfo" in q or "brief" in q or "executive" in q:
        crit = sum(1 for r in risks if str(r.get("severity", "")).upper() == "CRITICAL")
        high = sum(1 for r in risks if str(r.get("severity", "")).upper() == "HIGH")
        return (
            f"**CFO Executive Risk Briefing — {contract.title}**\n\n"
            f"• **Composite Risk Posture:** {contract.overall_risk_score}/100 ({crit} Critical, {high} High risks flagged across {cite_str}).\n"
            f"• **Balance Sheet Exposure:** Key financial traps identified include "
            + (", ".join(r["category"] for r in risks[:3]) or "standard commercial terms")
            + f". {len(redlines)} consensus redline(s) have been drafted to cap liability and prevent unbudgeted penalties.\n"
            f"• **Operational Commitments:** {len(obligations)} calendarized obligation(s) extracted (payment, audit, deletion, and notice windows).\n"
            f"• **SEC EDGAR Benchmark ({prec_cat}):** {prec_excerpt}"
        )

    if "email" in q or "pushback" in q or "opposing" in q:
        bullet_issues = "\n".join(
            f"- **Section {r.get('section_number')} ({r.get('risk_severity')}):** {r.get('legal_rationale')}"
            for r in redlines[:4]
        ) or "- Align liability caps and termination cure windows with mutual market standards."
        return (
            f"**Subject:** Proposed Legal Revisions — {contract.title}\n\n"
            "Dear Counterparty Counsel,\n\n"
            f"Thank you for sharing the draft {contract.title}. Following our multi-agent compliance review ({cite_str}), "
            "we can proceed to execution once the following critical points are harmonized:\n\n"
            f"{bullet_issues}\n\n"
            f"Our attached redlines incorporate balanced market language aligned with SEC EDGAR precedent ({prec_cat}). "
            "Please let us know if you are available for a brief call to finalize.\n\nBest regards,\nEnterprise Legal Counsel"
        )

    if "indemn" in q or "uncapped" in q or "trap" in q or "ai" in q:
        matched = [
            r
            for r in risks
            if any(k in r["category"].lower() for k in ("indemn", "ai", "damages", "trap", "penalty"))
        ]
        if matched:
            details = "\n".join(
                f"• **[Section {r['section_number']}] {r['category']} ({r['severity']}):** {r['legal_rationale']} Mitigation: {r['suggested_mitigation']}"
                for r in matched
            )
        else:
            details = f"• Reviewed {cite_str}: No uncapped indemnity trap matched, though standard cap verification is advised."
        return (
            f"**Trap & Exposure Audit ({cite_str})**\n\n{details}\n\n"
            f"**Relevant SEC EDGAR Precedent ({prec_cat}):** {prec_excerpt}"
        )

    top_passage = passages[0]["text"][:320] if passages else (contract.raw_text or "")[:320]
    return (
        f"**Grounded Analysis ({cite_str})**\n\n"
        f"Based on the contract text (`{top_passage}...`), our review identified **{len(risks)} risk(s)** "
        f"with a composite score of **{contract.overall_risk_score}/100** and **{len(redlines)} consensus redline(s)**.\n\n"
        f"**SEC EDGAR / LEDGAR Precedent ({prec_cat}):** {prec_excerpt}"
    )
