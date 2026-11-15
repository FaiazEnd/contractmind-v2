"""Corporate Playbook management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.contract import Playbook
from app.schemas.playbook_schemas import PlaybookCreate, PlaybookResponse

router = APIRouter(prefix="/playbooks", tags=["Playbooks"])


@router.get("", response_model=list[PlaybookResponse])
@router.get("/", response_model=list[PlaybookResponse], include_in_schema=False)
async def list_playbooks(db: AsyncSession = Depends(get_db)) -> list[Playbook]:
    res = await db.execute(select(Playbook).order_by(Playbook.is_default.desc(), Playbook.name.asc()))
    return list(res.scalars().all())


@router.post("", response_model=PlaybookResponse)
@router.post("/", response_model=PlaybookResponse, include_in_schema=False)
async def create_playbook(payload: PlaybookCreate, db: AsyncSession = Depends(get_db)) -> Playbook:
    existing = (await db.execute(select(Playbook).where(Playbook.name == payload.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Playbook '{payload.name}' already exists")
    pb = Playbook(
        name=payload.name,
        description=payload.description,
        rules=[r.model_dump() for r in payload.rules],
        is_default=payload.is_default,
    )
    db.add(pb)
    await db.commit()
    await db.refresh(pb)
    return pb
