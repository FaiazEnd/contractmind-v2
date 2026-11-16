"""Server-Sent Events (SSE) streaming endpoint for real-time 4-agent pipeline progress."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_contract_or_404
from app.database import get_db
from app.services.orchestrator import run_contract_analysis

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/{contract_id}")
async def stream_contract_analysis(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Run analysis while streaming live 4-agent StateGraph events over SSE."""
    contract = await get_contract_or_404(contract_id, db)

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def _cb(ev: dict) -> None:
            await queue.put(ev)

        task = asyncio.create_task(
            run_contract_analysis(db, contract, progress_callback=_cb)
        )

        while not task.done() or not queue.empty():
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=0.25)
                yield {"event": "progress", "data": json.dumps(ev)}
            except asyncio.TimeoutError:
                continue

        exc = task.exception()
        if exc:
            yield {
                "event": "error",
                "data": json.dumps({"status": "failed", "error": str(exc)}),
            }
        else:
            updated = task.result()
            yield {
                "event": "completed",
                "data": json.dumps(
                    {
                        "status": "completed",
                        "contract_id": updated.id,
                        "overall_risk_score": updated.overall_risk_score,
                    }
                ),
            }

    return EventSourceResponse(event_generator())
