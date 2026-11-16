"""Grounded Legal AI Copilot & CFO Briefing Generator endpoint."""

from __future__ import annotations

import time
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

router = APIRouter(prefix="/copilot", tags=["Legal AI Copilot"])


def _build_deterministic_copilot_reply(
    contract: Contract,
    message: str,
    rag_hits: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    lower = message.lower()
    risks = contract.identified_risks or []
    redlines = contract.redlines or []
    obligations = contract.obligations or []
    citations = [f"[Section {h['section_number']}]" for h in rag_hits if h.get("section_number")]
    for r in risks:
        c = f"[Section {r.get('section_number', '1')}]"
        if c not in citations:
            citations.append(c)

    if "cfo" in lower or "brief" in lower or "executive" in lower or "summary" in lower:
        crit = sum(1 for r in risks if r.get("severity") == "CRITICAL")
        high = sum(1 for r in risks if r.get("severity") == "HIGH")
        accepted = sum(1 for rl in redlines if rl.get("accepted") is True)
        top_risks = "; ".join(f"{r['category']} ([Section {r['section_number']}])" for r in risks[:3])
        answer = (
            f"**CFO Executive Risk Briefing — {contract.title}**\n\n"
            f"- **Composite Risk Score:** {contract.overall_risk_score}/100 ({crit} Critical, {high} High exposures)\n"
            f"- **Redline Status:** {accepted}/{len(redlines)} consensus revisions accepted\n"
            f"- **Key Financial & Operational Traps:** {top_risks or 'No material traps detected'}\n"
            f"- **Tracked Obligations:** {len(obligations)} operational duties mapped for calendar compliance.\n\n"
            "**Recommendation:** Do not execute until Critical uncapped liability/AI-training redlines are accepted and baked into the Clean Execution Draft."
        )
        return answer, citations[:5]

    if "pushback" in lower or "email" in lower or "opposing" in lower:
        bullet_lines = "\n".join(
            f"- **[Section {rl.get('section_number', '1')}] ({rl.get('risk_severity', 'HIGH')}):** {rl.get('legal_rationale', '').split(':')[0]} — proposing balanced fallback language."
            for rl in redlines[:4]
        )
        answer = (
            f"**Subject: Commercial Redlines & Consensus Markup — {contract.title}**\n\n"
            "Counsel,\n\n"
            "Thank you for circulating the draft agreement. We have completed our corporate risk review and attach our targeted Track Changes package focused exclusively on market-standard alignment:\n\n"
            f"{bullet_lines or '- Standard commercial cleanups only.'}\n\n"
            "We are aligned on core commercial scope and pricing and look forward to finalizing execution following confirmation of these protective edits.\n\n"
            "Best regards,\nEnterprise Legal Team"
        )
        return answer, citations[:5]

    if "indemn" in lower or "liability" in lower or "uncapped" in lower:
        ind_risks = [r for r in risks if "indemn" in r.get("category", "").lower() or "consequential" in r.get("category", "").lower()]
        if ind_risks:
            details = "\n".join(
                f"- **[Section {r['section_number']}] {r['category']} ({r['severity']}):** \"{r['matched_excerpt']}\" → Recommended mitigation: {r['suggested_mitigation']}"
                for r in ind_risks
            )
            answer = f"**Uncapped Indemnity & Liability Trap Check:**\n\n{details}"
        else:
            passages = "\n".join(f"- [Section {h['section_number']}]: {h['text'][:220]}" for h in rag_hits[:2])
            answer = (
                f"**Liability & Indemnity Audit for {contract.title}:**\n"
                "No uncapped indemnification trap matched our critical signature, though counsel should verify cap multipliers in:\n"
                f"{passages or 'All liability clauses reviewed.'}"
            )
        return answer, citations[:5]

    # General grounded RAG QA
    if rag_hits:
        passages_str = "\n".join(
            f"- **[Section {h['section_number']}: {h['title']}]** {h['text'].split('] ', 1)[-1][:260]}"
            for h in rag_hits[:3]
        )
        matching_redlines = [
            rl for rl in redlines if str(rl.get("section_number")) in {str(h["section_number"]) for h in rag_hits}
        ]
        rl_note = ""
        if matching_redlines:
            rl_note = (
                "\n\n**Related Arbiter Redlines:**\n"
                + "\n".join(
                    f"- [Section {rl['section_number']}] ({rl['risk_severity']}): {rl['suggested_text'][:180]}"
                    for rl in matching_redlines[:2]
                )
            )
        answer = (
            f"Based on the retrieved clauses of **{contract.title}**:\n\n"
            f"{passages_str}{rl_note}"
        )
    else:
        answer = (
            f"Reviewed **{contract.title}** (Composite Risk: {contract.overall_risk_score}/100, {len(redlines)} redlines, "
            f"{len(obligations)} obligations). Ask about specific sections such as indemnification, AI training, termination, or governing law for exact clause citations."
        )
    return answer, citations[:5]


@router.post("/{contract_id}/chat", response_model=CopilotChatResponse)
async def copilot_chat(
    contract_id: str,
    payload: CopilotChatRequest,
    db: AsyncSession = Depends(get_db),
) -> CopilotChatResponse:
    """Grounded Legal AI Copilot using RAG passages, redlines, and negotiation transcript."""
    start = time.time()
    contract = await get_contract_or_404(contract_id, db)

    # Ensure index is populated (helpful after process restarts if in-memory fallback is active)
    if not rag_engine.query_similar(contract_id, payload.message, n_results=1):
        rag_engine.index_contract(contract_id, contract.extracted_sections or [], contract.raw_text or "")

    rag_hits = rag_engine.query_similar(contract_id, payload.message, n_results=4)
    kb_hits = rag_engine.query_knowledge_base(payload.message, n_results=2)

    def _fallback() -> str:
        ans, _ = _build_deterministic_copilot_reply(contract, payload.message, rag_hits)
        return ans

    context_block = "\n".join(h["text"] for h in rag_hits)
    precedent_block = "\n".join(p["text"] for p in kb_hits)
    redline_block = "\n".join(
        f"[Section {r.get('section_number')}] ({r.get('risk_severity')}): {r.get('legal_rationale')} -> Suggested: {r.get('suggested_text')}"
        for r in (contract.redlines or [])[:5]
    )

    llm_resp = await llm_gateway.generate(
        prompt=(
            f"Contract: {contract.title} (Risk Score: {contract.overall_risk_score}/100)\n"
            f"Relevant Contract Passages:\n{context_block}\n\n"
            f"External Legal Precedents & Market Fallbacks:\n{precedent_block}\n\n"
            f"Synthesized Redlines:\n{redline_block}\n\n"
            f"User Question: {payload.message}"
        ),
        system_prompt="You are ContractMind Legal AI Copilot. Answer grounded in the provided contract passages and external legal precedents, citing [Section X] and precedent sources.",
        fallback_fn=_fallback,
    )

    _, default_citations = _build_deterministic_copilot_reply(contract, payload.message, rag_hits)
    for p in kb_hits:
        cit = f"[{p['source']}: {p['category']}]"
        if cit not in default_citations:
            default_citations.append(cit)
    latency_ms = max(round((time.time() - start) * 1000.0, 2), llm_resp.latency_ms)

    db.add(
        AuditLog(
            contract_id=contract.id,
            agent_name="Legal AI Copilot",
            action="grounded_rag_chat",
            model_name=llm_resp.model_name,
            prompt_tokens=llm_resp.prompt_tokens,
            completion_tokens=llm_resp.completion_tokens,
            total_tokens=llm_resp.total_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=llm_resp.estimated_cost_usd,
        )
    )
    await db.commit()

    return CopilotChatResponse(
        contract_id=contract.id,
        answer=llm_resp.text,
        citations=default_citations,
        suggested_followups=[
            "Draft CFO Risk Summary",
            "Draft Pushback Email to Opposing Counsel",
            "Check Uncapped Indemnity & Liability Traps",
        ],
        model_used=llm_resp.model_name,
    )
