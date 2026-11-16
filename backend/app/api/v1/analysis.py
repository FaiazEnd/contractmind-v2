"""Analysis, Redline decisions, Prompt Rewriting, Export, Deal Room, Playbook Compliance, and Telemetry endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agents.llm_client import llm_gateway
from app.api.deps import get_contract_or_404
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract, Playbook
from app.schemas.contract_schemas import (
    LLMConfigRequest,
    RedlineDecisionRequest,
    RedlineRegenerateRequest,
)
from app.services.calendar_service import generate_obligations_ics
from app.services.cross_contract_service import analyze_deal_room_conflicts
from app.services.diff_engine import compute_word_diff
from app.services.export_service import export_clean_docx, export_to_docx
from app.services.orchestrator import run_contract_analysis
from app.services.playbook_engine import evaluate_playbook_compliance
from app.services.rag_engine import rag_engine

router = APIRouter(prefix="/analysis", tags=["analysis"])


# ---------------------------------------------------------------------------
# Static routes (declared before /{contract_id}/... to avoid path collisions)
# ---------------------------------------------------------------------------


@router.get("/audit/summary")
async def get_audit_summary(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return aggregated token, latency, cost telemetry, and recent audit logs."""
    logs_res = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()))
    logs = logs_res.scalars().all()

    contracts_res = await db.execute(select(Contract))
    contracts = contracts_res.scalars().all()

    total_prompt = sum(l.prompt_tokens for l in logs)
    total_completion = sum(l.completion_tokens for l in logs)
    total_tokens = sum(l.total_tokens for l in logs)
    total_cost = round(sum(l.estimated_cost_usd for l in logs), 6)
    avg_latency = (
        round(sum(l.latency_ms for l in logs) / len(logs), 2) if logs else 0.0
    )

    return {
        "analyzed_contracts": len([c for c in contracts if c.status == "completed"]),
        "total_contracts": len(contracts),
        "total_runs": len(logs),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "average_latency_ms": avg_latency,
        "total_cost_usd": total_cost,
        "active_engine": llm_gateway.get_status()["active_model"],
        "rag_backend": rag_engine.backend_name,
        "recent_logs": [
            {
                "id": l.id,
                "contract_id": l.contract_id,
                "agent_name": l.agent_name,
                "action": l.action,
                "model_name": l.model_name,
                "prompt_tokens": l.prompt_tokens,
                "completion_tokens": l.completion_tokens,
                "total_tokens": l.total_tokens,
                "latency_ms": l.latency_ms,
                "estimated_cost_usd": l.estimated_cost_usd,
                "timestamp": l.timestamp.isoformat(),
            }
            for l in logs[:50]
        ],
    }


@router.delete("/audit/reset")
async def reset_audit_telemetry(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Purge all audit telemetry records."""
    await db.execute(delete(AuditLog))
    await db.commit()
    return {"reset": True, "message": "All audit telemetry logs purged."}


@router.get("/llm/config")
async def get_llm_config() -> dict[str, Any]:
    """Return active multi-provider LLM status and available models."""
    return llm_gateway.get_status()


@router.post("/llm/config")
async def update_llm_config(payload: LLMConfigRequest) -> dict[str, Any]:
    """Update active LLM provider, model, or session API credentials."""
    return llm_gateway.update_config(
        provider=payload.provider,
        model=payload.model,
        gemini_api_key=payload.gemini_api_key,
        openai_api_key=payload.openai_api_key,
        anthropic_api_key=payload.anthropic_api_key,
        ollama_base_url=payload.ollama_base_url,
    )


@router.post("/deal-room/conflicts")
async def deal_room_conflicts(
    payload: Union[list[str], dict[str, Any]] = Body(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Evaluate 2+ contracts for cross-contract contradictions and precedence traps."""
    if isinstance(payload, list):
        contract_ids = payload
    else:
        contract_ids = payload.get("contract_ids") or []

    if len(contract_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least 2 contracts for Deal Room cross-contract analysis.",
        )

    res = await db.execute(select(Contract).where(Contract.id.in_(contract_ids)))
    contracts = res.scalars().all()
    if len(contracts) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find at least 2 matching contracts.",
        )

    return analyze_deal_room_conflicts(list(contracts))


# ---------------------------------------------------------------------------
# Contract-scoped analysis, redlines, compliance, and export routes
# ---------------------------------------------------------------------------


@router.post("/{contract_id}/trigger")
async def trigger_analysis(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger the 4-agent StateGraph orchestrator on an uploaded contract."""
    contract = await get_contract_or_404(contract_id, db)
    updated = await run_contract_analysis(db, contract)
    return {
        "contract_id": updated.id,
        "status": updated.status,
        "overall_risk_score": updated.overall_risk_score,
        "risk_summary": updated.risk_summary,
        "redline_count": len(updated.redlines or []),
        "obligation_count": len(updated.obligations or []),
    }


@router.get("/{contract_id}/redlines")
async def get_redlines(
    contract_id: str,
    risk_severity: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve contract redlines with optional risk_severity and decision filters."""
    contract = await get_contract_or_404(contract_id, db)
    all_redlines: list[dict[str, Any]] = list(contract.redlines or [])

    severity_counts = {"ALL": len(all_redlines), "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    decision_counts = {"ALL": len(all_redlines), "PENDING": 0, "ACCEPTED": 0, "REJECTED": 0}

    for rl in all_redlines:
        sev = str(rl.get("risk_severity", "MEDIUM")).upper()
        if sev in severity_counts:
            severity_counts[sev] += 1
        acc = rl.get("accepted")
        if acc is True:
            decision_counts["ACCEPTED"] += 1
        elif acc is False:
            decision_counts["REJECTED"] += 1
        else:
            decision_counts["PENDING"] += 1

    filtered = all_redlines
    if risk_severity and risk_severity.upper() != "ALL":
        target_sev = risk_severity.upper()
        filtered = [
            rl for rl in filtered if str(rl.get("risk_severity", "")).upper() == target_sev
        ]

    if decision and decision.upper() != "ALL":
        dec = decision.upper()
        if dec == "ACCEPTED":
            filtered = [rl for rl in filtered if rl.get("accepted") is True]
        elif dec == "REJECTED":
            filtered = [rl for rl in filtered if rl.get("accepted") is False]
        elif dec == "PENDING":
            filtered = [rl for rl in filtered if rl.get("accepted") is None]

    return {
        "contract_id": contract_id,
        "total": len(all_redlines),
        "filtered_count": len(filtered),
        "severity_counts": severity_counts,
        "decision_counts": decision_counts,
        "redlines": filtered,
    }


@router.patch("/{contract_id}/redlines/{redline_id}")
async def update_redline_decision(
    contract_id: str,
    redline_id: str,
    payload: RedlineDecisionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Accept, reject, or reset a specific clause redline decision."""
    contract = await get_contract_or_404(contract_id, db)
    redlines = [dict(rl) for rl in (contract.redlines or [])]

    updated_rl = None
    for rl in redlines:
        if rl.get("id") == redline_id:
            rl["accepted"] = payload.accepted
            updated_rl = rl
            break

    if updated_rl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Redline '{redline_id}' not found on contract '{contract_id}'",
        )

    contract.redlines = redlines
    flag_modified(contract, "redlines")
    await db.commit()
    await db.refresh(contract)

    return {"contract_id": contract_id, "redline": updated_rl}


@router.post("/{contract_id}/redlines/accept-all")
async def accept_all_pending_redlines(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Accept all pending redlines in a single action."""
    contract = await get_contract_or_404(contract_id, db)
    redlines = [dict(rl) for rl in (contract.redlines or [])]
    changed = 0
    for rl in redlines:
        if rl.get("accepted") is None:
            rl["accepted"] = True
            changed += 1

    contract.redlines = redlines
    flag_modified(contract, "redlines")
    await db.commit()
    return {"contract_id": contract_id, "accepted_count": changed, "redlines": redlines}


@router.post("/{contract_id}/redlines/{redline_id}/regenerate")
async def regenerate_redline(
    contract_id: str,
    redline_id: str,
    payload: RedlineRegenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Rewrite a specific redline using lawyer's custom prompt instructions and recompute diff tokens."""
    contract = await get_contract_or_404(contract_id, db)
    redlines = [dict(rl) for rl in (contract.redlines or [])]
    transcript = [dict(t) for t in (contract.debate_transcript or [])]

    target = None
    for rl in redlines:
        if rl.get("id") == redline_id:
            target = rl
            break

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Redline '{redline_id}' not found",
        )

    orig_text = str(target.get("original_text", ""))
    prev_sugg = str(target.get("suggested_text", ""))
    custom_prompt = payload.custom_prompt.strip()
    sec_num = str(target.get("section_number", "1"))

    precedents = rag_engine.query_knowledge_base(
        f"{custom_prompt} {orig_text[:200]}", n_results=2
    )
    precedent_note = precedents[0]["text"][:240] if precedents else ""

    # Deterministic fallback rewrite incorporating the lawyer's custom prompt directives
    first_line = orig_text.splitlines()[0] if orig_text else f"Section {sec_num}"
    fallback_rewrite = _synthesize_custom_rewrite(
        first_line=first_line,
        prev_sugg=prev_sugg,
        custom_prompt=custom_prompt,
    )

    llm_res = await llm_gateway.generate(
        prompt=(
            f"Rewrite Section {sec_num} following the lawyer's explicit instruction.\n"
            f"Lawyer Instruction: {custom_prompt}\n"
            f"Original Text:\n{orig_text}\n\n"
            f"Previous Draft:\n{prev_sugg}\n\n"
            f"Precedent Context: {precedent_note}\n\n"
            "Return ONLY the updated clause text."
        ),
        system_prompt="You are Senior Legal Counsel revising contract redlines per partner instructions.",
        fallback_text=fallback_rewrite,
    )

    new_suggested = llm_res.text.strip() or fallback_rewrite
    target["suggested_text"] = new_suggested
    target["diff_tokens"] = compute_word_diff(orig_text, new_suggested)
    target["accepted"] = None  # Reset decision to Pending
    target["custom_prompt"] = custom_prompt
    target["legal_rationale"] = (
        f"Regenerated per Counsel instruction: \"{custom_prompt}\". "
        + (f"Precedent alignment: {precedents[0]['category']}." if precedents else "")
    ).strip()

    transcript.append(
        {
            "agent": "Redline Synthesizer Agent",
            "role": "Interactive Counsel Rewriter",
            "section_number": sec_num,
            "category": "Custom Prompt Rewrite",
            "argument": (
                f"Rewrote Section {sec_num} per partner directive: '{custom_prompt}'. "
                "Decision reset to Pending for verification."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    db.add(
        AuditLog(
            contract_id=contract_id,
            agent_name="Redline Synthesizer Agent",
            action="regenerate_custom_redline",
            model_name=llm_res.model,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            total_tokens=llm_res.total_tokens,
            latency_ms=llm_res.latency_ms,
            estimated_cost_usd=llm_res.estimated_cost_usd,
        )
    )

    contract.redlines = redlines
    contract.debate_transcript = transcript
    flag_modified(contract, "redlines")
    flag_modified(contract, "debate_transcript")
    await db.commit()
    await db.refresh(contract)

    return {"contract_id": contract_id, "redline": target}


def _synthesize_custom_rewrite(
    first_line: str, prev_sugg: str, custom_prompt: str
) -> str:
    """Deterministic fallback rewrite reflecting common partner negotiation directives."""
    lower = custom_prompt.lower()
    additions: list[str] = []
    if "2x" in lower or "two times" in lower or "cap" in lower:
        additions.append("Aggregate liability under this clause shall be strictly capped at two times (2x) annual fees paid.")
    if "15 day" in lower or "14 day" in lower or "cure" in lower:
        additions.append("Any termination right requires thirty (30) days prior written notice and a cure opportunity.")
    if "mutual" in lower or "bilateral" in lower:
        additions.append("All obligations, waivers, and fee-shifting remedies herein shall apply mutually and symmetrically to both parties.")
    if "delete" in lower or "ai" in lower or "train" in lower:
        additions.append("Provider is strictly prohibited from training, fine-tuning, or evaluating any AI or ML models on Customer Data.")
    if "delaware" in lower or "new york" in lower or "jurisdiction" in lower:
        gov = "Delaware" if "delaware" in lower else "New York"
        additions.append(f"This provision shall be governed exclusively by the laws of the State of {gov}.")

    if not additions:
        additions.append(
            f"Revised per Counsel Directive ({custom_prompt}): obligations shall be mutual, commercially reasonable, capped at twelve (12) months of fees, and subject to thirty (30) days written notice."
        )

    body = prev_sugg
    if first_line and body.startswith(first_line):
        body_rest = body[len(first_line) :].strip()
        return f"{first_line}\n{body_rest} {' '.join(additions)}".strip()
    return f"{first_line}\n{' '.join(additions)}".strip()


@router.get("/{contract_id}/export/docx")
async def download_redlined_docx(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download .docx with native Word OpenXML Track Changes."""
    contract = await get_contract_or_404(contract_id, db)
    content = export_to_docx(contract)
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in contract.title)[:60]
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_title}_TrackChanges.docx"'
        },
    )


@router.get("/{contract_id}/export/clean")
async def download_clean_docx(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download clean execution-ready .docx with accepted redlines baked in."""
    contract = await get_contract_or_404(contract_id, db)
    content = export_clean_docx(contract)
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in contract.title)[:60]
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_title}_CleanExecution.docx"'
        },
    )


@router.get("/{contract_id}/export/calendar")
async def download_calendar_ics(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download RFC 5545 .ics calendar file containing all contract obligation deadlines."""
    contract = await get_contract_or_404(contract_id, db)
    ics_payload = generate_obligations_ics(contract)
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in contract.title)[:60]
    return Response(
        content=ics_payload,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_title}_Obligations.ics"'
        },
    )


@router.get("/{contract_id}/compliance/playbook")
async def check_playbook_compliance(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Audit contract text and redlines against its assigned corporate Playbook."""
    contract = await get_contract_or_404(contract_id, db)
    pb_res = await db.execute(
        select(Playbook).where(Playbook.name == contract.playbook_name)
    )
    playbook = pb_res.scalars().first()
    if not playbook:
        pb_res = await db.execute(select(Playbook).where(Playbook.is_default.is_(True)))
        playbook = pb_res.scalars().first()

    return evaluate_playbook_compliance(contract, playbook)
