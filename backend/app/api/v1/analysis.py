"""Analysis, Redlines, Export, Compliance, Deal Room, Telemetry, and LLM Config endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_contract_analysis
from app.agents.llm_client import llm_gateway
from app.agents.nodes.redline_agent import regenerate_redline_with_prompt
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract, Playbook
from app.schemas.contract_schemas import (
    ContractDetail,
    DealRoomConflictRequest,
    RedlineDecisionUpdate,
    RedlineRegenerateRequest,
)
from app.schemas.playbook_schemas import PlaybookComplianceReport
from app.schemas.risk_schemas import AuditSummaryResponse, LLMConfigRequest, LLMConfigStatus
from app.services.calendar_service import generate_ics_calendar
from app.services.cross_contract_service import analyze_cross_contract_conflicts
from app.services.export_service import export_clean_docx, export_to_docx
from app.services.playbook_engine import ensure_default_playbooks, evaluate_playbook_compliance

router = APIRouter()


async def _get_contract_or_404(db: AsyncSession, contract_id: str) -> Contract:
    res = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = res.scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    return contract


# ---------------------------------------------------------------------------
# Static telemetry, LLM config, and Deal Room routes (must precede /{id} routes)
# ---------------------------------------------------------------------------


@router.get("/audit/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Return aggregated token, latency, and USD cost telemetry across all agent runs."""
    res = await db.execute(select(AuditLog))
    rows = list(res.scalars().all())
    if not rows:
        return {
            "total_records": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_estimated_cost_usd": 0.0,
            "avg_latency_ms": 0.0,
            "by_agent": [],
            "by_model": [],
        }

    total_prompt = sum(r.prompt_tokens for r in rows)
    total_completion = sum(r.completion_tokens for r in rows)
    total_tokens = sum(r.total_tokens for r in rows)
    total_cost = round(sum(r.estimated_cost_usd for r in rows), 8)
    avg_latency = round(sum(r.latency_ms for r in rows) / len(rows), 2)

    by_agent_map: Dict[str, Dict[str, Any]] = {}
    by_model_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        a = by_agent_map.setdefault(
            r.agent_name,
            {"agent_name": r.agent_name, "calls": 0, "total_tokens": 0, "total_cost_usd": 0.0, "latencies": []},
        )
        a["calls"] += 1
        a["total_tokens"] += r.total_tokens
        a["total_cost_usd"] = round(a["total_cost_usd"] + r.estimated_cost_usd, 8)
        a["latencies"].append(r.latency_ms)

        m = by_model_map.setdefault(
            r.model_name,
            {"model_name": r.model_name, "calls": 0, "total_tokens": 0, "total_cost_usd": 0.0},
        )
        m["calls"] += 1
        m["total_tokens"] += r.total_tokens
        m["total_cost_usd"] = round(m["total_cost_usd"] + r.estimated_cost_usd, 8)

    by_agent = [
        {
            "agent_name": v["agent_name"],
            "calls": v["calls"],
            "total_tokens": v["total_tokens"],
            "total_cost_usd": v["total_cost_usd"],
            "avg_latency_ms": round(sum(v["latencies"]) / len(v["latencies"]), 2),
        }
        for v in by_agent_map.values()
    ]

    return {
        "total_records": len(rows),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "total_estimated_cost_usd": total_cost,
        "avg_latency_ms": avg_latency,
        "by_agent": by_agent,
        "by_model": list(by_model_map.values()),
    }


@router.delete("/audit/reset")
async def reset_audit_telemetry(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Purge all audit telemetry records."""
    count_res = await db.execute(select(func.count()).select_from(AuditLog))
    deleted_count = int(count_res.scalar() or 0)
    await db.execute(delete(AuditLog))
    await db.commit()
    return {"status": "reset", "deleted_records": deleted_count}


@router.get("/llm/config", response_model=LLMConfigStatus)
async def get_llm_config() -> Dict[str, Any]:
    """Get multi-provider LLM credentials status (secrets masked)."""
    return llm_gateway.get_status()


@router.post("/llm/config", response_model=LLMConfigStatus)
async def update_llm_config(payload: LLMConfigRequest) -> Dict[str, Any]:
    """Update multi-provider LLM credentials and default provider at runtime."""
    llm_gateway.update_config(payload.model_dump(exclude_none=True))
    return llm_gateway.get_status()


@router.post("/deal-room/conflicts")
async def deal_room_conflicts(
    payload: Union[List[str], DealRoomConflictRequest] = Body(...),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Audit multiple selected contracts for cross-contract contradictions and precedence traps."""
    contract_ids = payload if isinstance(payload, list) else payload.contract_ids
    if len(contract_ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two contract IDs for Deal Room conflict audit.")

    res = await db.execute(select(Contract).where(Contract.id.in_(contract_ids)))
    contracts = list(res.scalars().all())
    if len(contracts) < 2:
        raise HTTPException(status_code=404, detail="Fewer than two matching contracts found.")

    return analyze_cross_contract_conflicts(contracts)


# ---------------------------------------------------------------------------
# Contract-scoped analysis, redlines, exports, and playbook compliance
# ---------------------------------------------------------------------------


@router.post("/{contract_id}/trigger", response_model=ContractDetail)
async def trigger_analysis(contract_id: str, db: AsyncSession = Depends(get_db)) -> Contract:
    """Trigger the 4-node multi-agent StateGraph pipeline on a contract."""
    contract = await _get_contract_or_404(db, contract_id)
    return await run_contract_analysis(db, contract)


@router.get("/{contract_id}/redlines")
async def get_redlines(
    contract_id: str,
    risk_severity: Optional[str] = Query(default=None),
    decision: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve redlines for a contract with optional risk_severity and decision filters."""
    contract = await _get_contract_or_404(db, contract_id)
    all_redlines: List[Dict[str, Any]] = list(contract.redlines or [])
    filtered = all_redlines

    if risk_severity and risk_severity.upper() != "ALL":
        sev_upper = risk_severity.upper()
        filtered = [r for r in filtered if str(r.get("risk_severity", "")).upper() == sev_upper]

    if decision and decision.upper() != "ALL":
        dec_upper = decision.upper()
        if dec_upper == "ACCEPTED":
            filtered = [r for r in filtered if r.get("accepted") is True]
        elif dec_upper == "REJECTED":
            filtered = [r for r in filtered if r.get("accepted") is False]
        elif dec_upper == "PENDING":
            filtered = [r for r in filtered if r.get("accepted") is None]

    return {
        "contract_id": contract.id,
        "total": len(all_redlines),
        "filtered_count": len(filtered),
        "redlines": filtered,
    }


@router.patch("/{contract_id}/redlines/{redline_id}")
async def update_redline_decision(
    contract_id: str,
    redline_id: str,
    payload: RedlineDecisionUpdate,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Accept, reject, or reset to pending a specific clause redline."""
    contract = await _get_contract_or_404(db, contract_id)
    redlines = [dict(r) for r in (contract.redlines or [])]

    updated_item = None
    for idx, rl in enumerate(redlines):
        if rl.get("id") == redline_id:
            rl["accepted"] = payload.accepted
            redlines[idx] = rl
            updated_item = rl
            break

    if updated_item is None:
        raise HTTPException(status_code=404, detail="Redline not found.")

    contract.redlines = redlines
    await db.commit()
    await db.refresh(contract)
    return {"status": "updated", "redline": updated_item}


@router.post("/{contract_id}/redlines/{redline_id}/regenerate")
async def regenerate_redline(
    contract_id: str,
    redline_id: str,
    payload: RedlineRegenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Rewrite a specific redline using a custom attorney prompt, recompute diffs, and log transcript."""
    contract = await _get_contract_or_404(db, contract_id)
    redlines = [dict(r) for r in (contract.redlines or [])]
    transcript = [dict(t) for t in (contract.debate_transcript or [])]

    target_idx = next((i for i, r in enumerate(redlines) if r.get("id") == redline_id), None)
    if target_idx is None:
        raise HTTPException(status_code=404, detail="Redline not found.")

    result = await regenerate_redline_with_prompt(
        redline=redlines[target_idx],
        custom_prompt=payload.custom_prompt,
        contract_title=contract.title,
    )
    new_redline = result["redline"]
    audit_meta = result["audit"]

    redlines[target_idx] = new_redline
    transcript.append(
        {
            "turn_index": len(transcript) + 1,
            "agent_name": "Redline Synthesizer Agent",
            "role": "Counsel-Directed Rewrite",
            "section_number": new_redline.get("section_number", "1"),
            "risk_category": "Custom Instruction",
            "argument": (
                f"Rewrote redline [{redline_id}] in Section {new_redline.get('section_number')} "
                f"per counsel prompt: \"{payload.custom_prompt}\". Decision reset to Pending Review."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    contract.redlines = redlines
    contract.debate_transcript = transcript
    db.add(
        AuditLog(
            contract_id=contract.id,
            agent_name=audit_meta["agent_name"],
            action=audit_meta["action"],
            model_name=audit_meta["model_name"],
            prompt_tokens=audit_meta["prompt_tokens"],
            completion_tokens=audit_meta["completion_tokens"],
            total_tokens=audit_meta["total_tokens"],
            latency_ms=audit_meta["latency_ms"],
            estimated_cost_usd=audit_meta["estimated_cost_usd"],
        )
    )
    await db.commit()
    await db.refresh(contract)
    return {"status": "regenerated", "redline": new_redline, "debate_transcript": contract.debate_transcript}


@router.get("/{contract_id}/export/docx")
async def export_docx_track_changes(contract_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Download .docx with native Word Track Changes (w:del / w:ins)."""
    contract = await _get_contract_or_404(db, contract_id)
    docx_bytes = export_to_docx(contract)
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in contract.title)[:60]
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_stem}_track_changes.docx"'},
    )


@router.get("/{contract_id}/export/clean")
async def export_docx_clean(contract_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Download clean executable .docx with accepted/recommended redlines baked in."""
    contract = await _get_contract_or_404(db, contract_id)
    docx_bytes = export_clean_docx(contract)
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in contract.title)[:60]
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_stem}_clean_executable.docx"'},
    )


@router.get("/{contract_id}/export/calendar")
async def export_ics_calendar(contract_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Download RFC 5545 .ics calendar sync file for extracted contract obligations."""
    contract = await _get_contract_or_404(db, contract_id)
    ics_payload = generate_ics_calendar(contract)
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in contract.title)[:60]
    return Response(
        content=ics_payload.encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_stem}_obligations.ics"'},
    )


@router.get("/{contract_id}/compliance/playbook", response_model=PlaybookComplianceReport)
async def check_playbook_compliance(
    contract_id: str,
    playbook_name: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Audit contract adherence and redline remediation against assigned corporate playbook."""
    contract = await _get_contract_or_404(db, contract_id)
    await ensure_default_playbooks(db)

    target_name = playbook_name or contract.playbook_name or "Standard Corporate Playbook"
    res = await db.execute(select(Playbook).where(Playbook.name == target_name))
    playbook = res.scalar_one_or_none()
    if playbook is None:
        res_def = await db.execute(select(Playbook).where(Playbook.is_default.is_(True)))
        playbook = res_def.scalar_one_or_none()
    if playbook is None:
        res_any = await db.execute(select(Playbook))
        playbook = res_any.scalars().first()
    if playbook is None:
        raise HTTPException(status_code=404, detail="No playbooks configured.")

    return evaluate_playbook_compliance(contract, playbook)
