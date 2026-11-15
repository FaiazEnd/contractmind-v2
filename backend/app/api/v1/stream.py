"""Server-Sent Events (SSE) streaming endpoint for live 4-agent StateGraph execution."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_contract_or_404, run_pipeline_for_contract
from app.database import get_db

router = APIRouter(prefix="/stream", tags=["Streaming"])


@router.get("/{contract_id}")
async def stream_contract_analysis(contract_id: str, db: AsyncSession = Depends(get_db)) -> EventSourceResponse:
    """Stream real-time node progress events while executing the 4-agent StateGraph."""
    contract = await get_contract_or_404(contract_id, db)

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def _emit(event: dict) -> None:
            await queue.put(event)

        async def _runner() -> None:
            try:
                await _emit({"node": "pipeline", "status": "started", "contract_id": contract_id})
                updated = await run_pipeline_for_contract(contract, db, event_emitter=_emit)
                await _emit(
                    {
                        "node": "pipeline",
                        "status": "completed",
                        "overall_risk_score": updated.overall_risk_score,
                        "redline_count": len(updated.redlines or []),
                        "obligation_count": len(updated.obligations or []),
                    }
                )
            except Exception as exc:
                await _emit({"node": "pipeline", "status": "error", "detail": str(exc)})
            finally:
                await queue.put(None)

        task = asyncio.create_task(_runner())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield {"event": "agent_update", "data": json.dumps(item)}
        await task

    return EventSourceResponse(event_generator())
