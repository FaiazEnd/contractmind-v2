"""Shared API dependencies and contract pipeline orchestration helper."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import contract_graph
from app.core.security import decode_access_token
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract, Playbook
from app.models.user import User
from app.services.rag_engine import rag_engine


async def get_optional_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Resolve authenticated user if Bearer token is provided; returns None for guest studio access."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    user_id = decode_access_token(token)
    if not user_id:
        return None
    res = await db.execute(select(User).where(User.id == user_id))
    return res.scalar_one_or_none()


async def get_contract_or_404(contract_id: str, db: AsyncSession) -> Contract:
    """Fetch a Contract by ID or raise HTTP 404."""
    res = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found")
    return contract


async def run_pipeline_for_contract(
    contract: Contract,
    db: AsyncSession,
    event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> Contract:
    """Execute the 4-agent StateGraph pipeline on a Contract and persist results + AuditLogs."""
    # Ensure RAG index exists
    rag_engine.index_contract(contract.id, contract.extracted_sections or [], contract.raw_text or "")

    # Load assigned playbook rules
    pb = (
        await db.execute(select(Playbook).where(Playbook.name == contract.playbook_name))
    ).scalar_one_or_none()
    if not pb:
        pb = (await db.execute(select(Playbook).where(Playbook.is_default.is_(True)))).scalar_one_or_none()

    contract.status = "analyzing"
    contract.error_message = None
    await db.commit()

    try:
        final_state = await contract_graph.ainvoke(
            {
                "contract_id": contract.id,
                "title": contract.title,
                "raw_text": contract.raw_text or "",
                "playbook_name": contract.playbook_name,
                "playbook_rules": (pb.rules if pb else []),
                "sections": contract.extracted_sections or [],
                "identified_risks": [],
                "debate_transcript": [],
                "redlines": [],
                "obligations": [],
                "overall_risk_score": 0.0,
                "risk_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "audit_records": [],
                "event_emitter": event_emitter,
            }
        )

        contract.identified_risks = final_state.get("identified_risks", [])
        contract.debate_transcript = final_state.get("debate_transcript", [])
        contract.redlines = final_state.get("redlines", [])
        contract.obligations = final_state.get("obligations", [])
        contract.overall_risk_score = float(final_state.get("overall_risk_score", 0.0))
        contract.risk_summary = final_state.get("risk_summary", {"critical": 0, "high": 0, "medium": 0, "low": 0})
        contract.status = "completed"
        contract.updated_at = datetime.now(timezone.utc)

        for rec in final_state.get("audit_records", []):
            db.add(
                AuditLog(
                    contract_id=contract.id,
                    agent_name=rec["agent_name"],
                    action=rec["action"],
                    model_name=rec["model_name"],
                    prompt_tokens=rec["prompt_tokens"],
                    completion_tokens=rec["completion_tokens"],
                    total_tokens=rec["total_tokens"],
                    latency_ms=rec["latency_ms"],
                    estimated_cost_usd=rec["estimated_cost_usd"],
                )
            )

        await db.commit()
        await db.refresh(contract)
        return contract
    except Exception as exc:
        contract.status = "error"
        contract.error_message = str(exc)
        await db.commit()
        raise
