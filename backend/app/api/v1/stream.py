"""Server-Sent Events (SSE) streaming endpoint for live StateGraph pipeline execution."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import contract_graph
from app.agents.state import ContractAgentState
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract

router = APIRouter()


@router.get("/{contract_id}")
async def stream_contract_analysis(contract_id: str, db: AsyncSession = Depends(get_db)) -> EventSourceResponse:
    """Stream real-time node progress events while running the 4-agent StateGraph pipeline."""
    res = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = res.scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    async def event_generator():
        contract.status = "analyzing"
        await db.commit()

        state: ContractAgentState = {
            "contract_id": contract.id,
            "title": contract.title,
            "playbook_name": contract.playbook_name,
            "raw_text": contract.raw_text,
            "sections": list(contract.extracted_sections or []),
            "identified_risks": [],
            "debate_transcript": [],
            "redlines": [],
            "obligations": [],
            "overall_risk_score": 0.0,
            "risk_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "audit_events": [],
        }

        yield {
            "event": "stage",
            "data": json.dumps({"node": "start", "status": "started", "contract_id": contract.id}),
        }

        final_state = state
        async for node_name, updated_state in contract_graph.astream(state):
            final_state = updated_state
            yield {
                "event": "stage",
                "data": json.dumps(
                    {
                        "node": node_name,
                        "status": "completed",
                        "risks_count": len(updated_state.get("identified_risks") or []),
                        "redlines_count": len(updated_state.get("redlines") or []),
                        "obligations_count": len(updated_state.get("obligations") or []),
                        "overall_risk_score": updated_state.get("overall_risk_score", 0.0),
                    }
                ),
            }

        contract.identified_risks = list(final_state.get("identified_risks") or [])
        contract.debate_transcript = list(final_state.get("debate_transcript") or [])
        contract.redlines = list(final_state.get("redlines") or [])
        contract.obligations = list(final_state.get("obligations") or [])
        contract.overall_risk_score = float(final_state.get("overall_risk_score") or 0.0)
        contract.risk_summary = dict(
            final_state.get("risk_summary") or {"critical": 0, "high": 0, "medium": 0, "low": 0}
        )
        contract.status = "completed"

        for evt in final_state.get("audit_events") or []:
            db.add(
                AuditLog(
                    contract_id=contract.id,
                    agent_name=str(evt["agent_name"]),
                    action=str(evt["action"]),
                    model_name=str(evt["model_name"]),
                    prompt_tokens=int(evt["prompt_tokens"]),
                    completion_tokens=int(evt["completion_tokens"]),
                    total_tokens=int(evt["total_tokens"]),
                    latency_ms=float(evt["latency_ms"]),
                    estimated_cost_usd=float(evt["estimated_cost_usd"]),
                )
            )
        await db.commit()

        yield {
            "event": "complete",
            "data": json.dumps({"contract_id": contract.id, "status": "completed"}),
        }

    return EventSourceResponse(event_generator())
