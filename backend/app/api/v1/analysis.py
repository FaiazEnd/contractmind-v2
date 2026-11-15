"""Multi-agent analysis trigger, redline decisions, prompt rewriting, exports, Deal Room, compliance, and telemetry."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agents.llm_client import llm_gateway
from app.api.deps import get_contract_or_404, run_pipeline_for_contract
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract, Playbook
from app.schemas.contract_schemas import (
    ContractDetail,
    DealRoomConflictRequest,
    LLMConfigRequest,
    RedlineDecisionRequest,
    RedlineRegenerateRequest,
)
from app.schemas.playbook_schemas import PlaybookComplianceResult
from app.services.calendar_service import generate_ics_calendar
from app.services.cross_contract_service import analyze_deal_room_conflicts
from app.services.diff_engine import compute_diff_tokens
from app.services.export_service import export_clean_docx, export_to_docx
from app.services.playbook_engine import evaluate_playbook_compliance

router = APIRouter(prefix="/analysis", tags=["Analysis & Exports"])


# ---------------------------------------------------------------------------
# Static routes registered before parameterized /{contract_id} routes
# ---------------------------------------------------------------------------


@router.post("/deal-room/conflicts")
async def deal_room_conflicts(
    payload: list[str] | DealRoomConflictRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run multi-document contradiction audit across selected contracts."""
    contract_ids = payload if isinstance(payload, list) else payload.contract_ids
    if len(contract_ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 contracts for Deal Room conflict audit")

    res = await db.execute(select(Contract).where(Contract.id.in_(contract_ids)))
    contracts = list(res.scalars().all())
    if len(contracts) < 2:
        raise HTTPException(status_code=404, detail="At least 2 matching contracts are required")

    return analyze_deal_room_conflicts(contracts)


@router.get("/audit/summary")
async def audit_summary(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Aggregate token, latency, and USD cost telemetry across all agent executions."""
    totals_q = await db.execute(
        select(
            func.count(AuditLog.id),
            func.coalesce(func.sum(AuditLog.prompt_tokens), 0),
            func.coalesce(func.sum(AuditLog.completion_tokens), 0),
            func.coalesce(func.sum(AuditLog.total_tokens), 0),
            func.coalesce(func.sum(AuditLog.estimated_cost_usd), 0.0),
            func.coalesce(func.avg(AuditLog.latency_ms), 0.0),
        )
    )
    row = totals_q.one()
    contract_count = (await db.execute(select(func.count(Contract.id)))).scalar_one()

    recent_q = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(30))
    logs = [
        {
            "id": l.id,
            "contract_id": l.contract_id,
            "agent_name": l.agent_name,
            "action": l.action,
            "model_name": l.model_name,
            "prompt_tokens": l.prompt_tokens,
            "completion_tokens": l.completion_tokens,
            "total_tokens": l.total_tokens,
            "latency_ms": round(float(l.latency_ms), 2),
            "estimated_cost_usd": round(float(l.estimated_cost_usd), 6),
            "timestamp": l.timestamp.isoformat(),
        }
        for l in recent_q.scalars().all()
    ]

    by_agent_q = await db.execute(
        select(
            AuditLog.agent_name,
            func.count(AuditLog.id),
            func.coalesce(func.sum(AuditLog.total_tokens), 0),
            func.coalesce(func.avg(AuditLog.latency_ms), 0.0),
            func.coalesce(func.sum(AuditLog.estimated_cost_usd), 0.0),
        ).group_by(AuditLog.agent_name)
    )
    by_agent = [
        {
            "agent_name": a,
            "calls": int(cnt),
            "total_tokens": int(tok),
            "avg_latency_ms": round(float(lat), 2),
            "cost_usd": round(float(cost), 6),
        }
        for a, cnt, tok, lat, cost in by_agent_q.all()
    ]

    return {
        "total_calls": int(row[0]),
        "total_prompt_tokens": int(row[1]),
        "total_completion_tokens": int(row[2]),
        "total_tokens": int(row[3]),
        "total_cost_usd": round(float(row[4]), 6),
        "avg_latency_ms": round(float(row[5]), 2),
        "analyzed_contracts": int(contract_count),
        "active_provider": llm_gateway.provider,
        "active_model": llm_gateway.model,
        "by_agent": by_agent,
        "recent_logs": logs,
    }


@router.delete("/audit/reset")
async def reset_audit_logs(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Purge all audit telemetry records."""
    await db.execute(delete(AuditLog))
    await db.commit()
    return {"status": "reset", "message": "All audit telemetry logs purged"}


@router.get("/llm/config")
async def get_llm_config() -> dict[str, Any]:
    """Retrieve active LLM provider configuration and safe credential flags."""
    return llm_gateway.get_config()


@router.post("/llm/config")
async def update_llm_config(payload: LLMConfigRequest) -> dict[str, Any]:
    """Update runtime LLM provider, model, and API credentials."""
    return llm_gateway.update_config(
        provider=payload.provider,
        model=payload.model,
        gemini_api_key=payload.gemini_api_key,
        openai_api_key=payload.openai_api_key,
        anthropic_api_key=payload.anthropic_api_key,
        ollama_base_url=payload.ollama_base_url,
        ollama_model=payload.ollama_model,
    )


# ---------------------------------------------------------------------------
# Contract-scoped analysis, redline decisioning, rewriting, compliance, exports
# ---------------------------------------------------------------------------


@router.post("/{contract_id}/trigger", response_model=ContractDetail)
async def trigger_analysis(contract_id: str, db: AsyncSession = Depends(get_db)) -> Contract:
    """Trigger the 4-agent StateGraph orchestrator on an uploaded contract."""
    contract = await get_contract_or_404(contract_id, db)
    return await run_pipeline_for_contract(contract, db)


@router.get("/{contract_id}/redlines")
async def get_redlines(
    contract_id: str,
    risk_severity: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve clause redlines with optional risk_severity and decision filters."""
    contract = await get_contract_or_404(contract_id, db)
    all_redlines = list(contract.redlines or [])

    filtered = all_redlines
    if risk_severity and risk_severity.upper() != "ALL":
        sev_target = risk_severity.upper()
        filtered = [r for r in filtered if str(r.get("risk_severity", "")).upper() == sev_target]

    if decision and decision.upper() != "ALL":
        dec_target = decision.upper()
        if dec_target == "ACCEPTED":
            filtered = [r for r in filtered if r.get("accepted") is True]
        elif dec_target == "REJECTED":
            filtered = [r for r in filtered if r.get("accepted") is False]
        elif dec_target == "PENDING":
            filtered = [r for r in filtered if r.get("accepted") is None]

    return {
        "contract_id": contract_id,
        "total_count": len(all_redlines),
        "filtered_count": len(filtered),
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
    redlines = [dict(r) for r in (contract.redlines or [])]

    target_item = None
    for item in redlines:
        if item.get("id") == redline_id:
            item["accepted"] = payload.accepted
            target_item = item
            break

    if target_item is None:
        raise HTTPException(status_code=404, detail=f"Redline '{redline_id}' not found")

    contract.redlines = redlines
    contract.updated_at = datetime.now(timezone.utc)
    flag_modified(contract, "redlines")
    await db.commit()
    await db.refresh(contract)
    return {"status": "updated", "redline": target_item}


def _rewrite_clause_deterministically(original_text: str, current_suggested: str, custom_prompt: str) -> str:
    """Produce a prompt-responsive legal clause revision when external LLMs are offline."""
    p = custom_prompt.lower()
    base = current_suggested or original_text
    additions: list[str] = []

    if "24" in p or "2x" in p or "super-cap" in p or "supercap" in p:
        base = base.replace("twelve (12) months", "twenty-four (24) months").replace("one times (1x)", "two times (2x)")
        additions.append("with a super-cap of two times (2x) annual fees for confirmed confidentiality or data security breaches")
    if "mutual" in p or "reciprocal" in p:
        if "mutually" not in base.lower() and "each party" not in base.lower():
            additions.append("applied on a strictly mutual and reciprocal basis to both Parties")
    if "45" in p:
        base = base.replace("thirty (30) days", "forty-five (45) days")
    if "60" in p:
        base = base.replace("thirty (30) days", "sixty (60) days")
    if "15" in p:
        base = base.replace("thirty (30) days", "fifteen (15) days")
    if "strict" in p or "prohibit" in p or "zero" in p or "ban" in p:
        additions.append("with zero retention, zero secondary reuse, and mandatory audit certification upon written request")
    if "carve" in p or "gdpr" in p or "soc2" in p:
        additions.append("subject to full GDPR/CCPA compliance and annual SOC 2 Type II attestation")

    if not additions:
        # Incorporate custom instruction cleanly in legal drafting style
        cleaned_instr = custom_prompt.strip().rstrip(".")
        return f"{base.rstrip('.')} — revised per counsel instruction ({cleaned_instr})."

    return f"{base.rstrip('.')}, {'; '.join(additions)}."


@router.post("/{contract_id}/redlines/{redline_id}/regenerate")
async def regenerate_redline(
    contract_id: str,
    redline_id: str,
    payload: RedlineRegenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Rewrite a specific redline using a custom lawyer prompt, recompute diffs, and reset decision to pending."""
    start = time.time()
    contract = await get_contract_or_404(contract_id, db)
    redlines = [dict(r) for r in (contract.redlines or [])]

    target_idx = None
    for idx, item in enumerate(redlines):
        if item.get("id") == redline_id:
            target_idx = idx
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail=f"Redline '{redline_id}' not found")

    item = redlines[target_idx]
    original_text = item.get("original_text", "")
    current_suggested = item.get("suggested_text", "")
    custom_prompt = payload.custom_prompt.strip()

    llm_resp = await llm_gateway.generate(
        prompt=(
            f"Original clause:\n{original_text}\n\n"
            f"Current redline:\n{current_suggested}\n\n"
            f"Counsel rewrite instruction:\n{custom_prompt}\n\n"
            "Return ONLY the revised replacement clause text."
        ),
        system_prompt="You are an elite commercial contracts partner. Rewrite the clause strictly adhering to counsel's instruction.",
        fallback_fn=lambda: _rewrite_clause_deterministically(original_text, current_suggested, custom_prompt),
    )

    new_suggested = llm_resp.text.strip()
    new_diff_tokens = compute_diff_tokens(original_text, new_suggested)

    item["suggested_text"] = new_suggested
    item["diff_tokens"] = new_diff_tokens
    item["accepted"] = None
    item["custom_prompt"] = custom_prompt
    item["legal_rationale"] = f"{item.get('legal_rationale', '').split(' [Custom Rewrite:')[0]} [Custom Rewrite: {custom_prompt}]"
    redlines[target_idx] = item

    transcript = list(contract.debate_transcript or [])
    transcript.append(
        {
            "agent": "Redline Synthesizer",
            "role": "On-Demand Counsel Rewrite",
            "section_number": item.get("section_number", "1"),
            "stance": "Custom Prompt Regenerated",
            "message": f"Regenerated Section {item.get('section_number', '1')} redline per counsel instruction: \"{custom_prompt}\"",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    contract.redlines = redlines
    contract.debate_transcript = transcript
    contract.updated_at = datetime.now(timezone.utc)
    flag_modified(contract, "redlines")
    flag_modified(contract, "debate_transcript")

    latency_ms = max(round((time.time() - start) * 1000.0, 2), llm_resp.latency_ms)
    db.add(
        AuditLog(
            contract_id=contract.id,
            agent_name="Redline Synthesizer",
            action="custom_prompt_rewrite",
            model_name=llm_resp.model_name,
            prompt_tokens=llm_resp.prompt_tokens,
            completion_tokens=llm_resp.completion_tokens,
            total_tokens=llm_resp.total_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=llm_resp.estimated_cost_usd,
        )
    )

    await db.commit()
    await db.refresh(contract)
    return {"status": "regenerated", "redline": item, "debate_transcript": contract.debate_transcript}


@router.get("/{contract_id}/export/docx")
async def download_track_changes_docx(contract_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Download .docx with native Word OpenXML Track Changes."""
    contract = await get_contract_or_404(contract_id, db)
    content = export_to_docx(contract)
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in contract.title)[:50]
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_stem}_track_changes.docx"'},
    )


@router.get("/{contract_id}/export/clean")
async def download_clean_docx(
    contract_id: str,
    include_pending: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download clean executable .docx with accepted redlines baked in and zero diff markup."""
    contract = await get_contract_or_404(contract_id, db)
    content = export_clean_docx(contract, include_pending=include_pending)
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in contract.title)[:50]
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_stem}_clean_executable.docx"'},
    )


@router.get("/{contract_id}/export/calendar")
async def download_ics_calendar(contract_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Download RFC 5545 .ics calendar file containing all extracted obligation deadlines."""
    contract = await get_contract_or_404(contract_id, db)
    ics_payload = generate_ics_calendar(contract)
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in contract.title)[:50]
    return Response(
        content=ics_payload,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_stem}_obligations.ics"'},
    )


@router.get("/{contract_id}/compliance/playbook", response_model=PlaybookComplianceResult)
async def check_playbook_compliance(
    contract_id: str,
    playbook_name: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> PlaybookComplianceResult:
    """Audit contract text & redlines against assigned corporate playbook and return adherence score."""
    contract = await get_contract_or_404(contract_id, db)
    target_name = playbook_name or contract.playbook_name
    pb = (await db.execute(select(Playbook).where(Playbook.name == target_name))).scalar_one_or_none()
    if not pb:
        pb = (await db.execute(select(Playbook).where(Playbook.is_default.is_(True)))).scalar_one_or_none()
    if not pb:
        raise HTTPException(status_code=404, detail="No playbook found in database")

    return evaluate_playbook_compliance(contract, pb)
