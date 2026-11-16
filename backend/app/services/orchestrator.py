"""Shared orchestration service connecting Contract records, RAG indexing, StateGraph, and AuditLogs."""
from __future__ import annotations

from typing import Any, Callable, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import contract_graph
from app.models.audit import AuditLog
from app.models.contract import Contract, Playbook
from app.services.rag_engine import rag_engine


async def run_contract_analysis(
    db: AsyncSession,
    contract: Contract,
    progress_callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
) -> Contract:
    """Execute the 4-agent StateGraph pipeline on a Contract and persist results + AuditLogs."""
    contract.status = "analyzing"
    contract.error_message = None
    await db.commit()

    try:
        # Ensure RAG index exists for this contract & knowledge base
        sections = contract.extracted_sections or []
        if sections:
            rag_engine.index_contract(contract.id, sections)
        rag_engine.index_knowledge_base()

        # Load assigned Playbook rules
        pb_res = await db.execute(
            select(Playbook).where(Playbook.name == contract.playbook_name)
        )
        playbook = pb_res.scalars().first()
        if not playbook:
            pb_res = await db.execute(select(Playbook).where(Playbook.is_default.is_(True)))
            playbook = pb_res.scalars().first()

        initial_state = {
            "contract_id": contract.id,
            "title": contract.title,
            "raw_text": contract.raw_text,
            "sections": sections,
            "playbook_name": contract.playbook_name,
            "playbook_rules": playbook.rules if playbook else [],
            "identified_risks": [],
            "debate_transcript": [],
            "redlines": [],
            "obligations": [],
            "risk_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "overall_risk_score": 0.0,
            "audit_logs": [],
            "progress_callback": progress_callback,
        }

        final_state = await contract_graph.ainvoke(initial_state)  # type: ignore[arg-type]

        contract.identified_risks = final_state.get("identified_risks", [])
        contract.debate_transcript = final_state.get("debate_transcript", [])
        contract.redlines = final_state.get("redlines", [])
        contract.obligations = final_state.get("obligations", [])
        contract.risk_summary = final_state.get(
            "risk_summary", {"critical": 0, "high": 0, "medium": 0, "low": 0}
        )
        contract.overall_risk_score = float(
            final_state.get("overall_risk_score", 0.0)
        )
        contract.status = "completed"

        for log_entry in final_state.get("audit_logs", []):
            db.add(
                AuditLog(
                    contract_id=contract.id,
                    agent_name=log_entry["agent_name"],
                    action=log_entry["action"],
                    model_name=log_entry["model_name"],
                    prompt_tokens=log_entry["prompt_tokens"],
                    completion_tokens=log_entry["completion_tokens"],
                    total_tokens=log_entry["total_tokens"],
                    latency_ms=log_entry["latency_ms"],
                    estimated_cost_usd=log_entry["estimated_cost_usd"],
                )
            )

        await db.commit()
        await db.refresh(contract)
        return contract
    except Exception as exc:
        contract.status = "failed"
        contract.error_message = str(exc)
        await db.commit()
        raise
