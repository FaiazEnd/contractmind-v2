"""Playbook management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.contract import Playbook
from app.schemas.playbook_schemas import PlaybookCreateSchema, PlaybookResponseSchema

router = APIRouter(prefix="/playbook", tags=["playbook"])


@router.get("/", response_model=list[PlaybookResponseSchema])
async def list_playbooks(db: AsyncSession = Depends(get_db)) -> list[PlaybookResponseSchema]:
    res = await db.execute(select(Playbook).order_by(Playbook.is_default.desc(), Playbook.name.asc()))
    playbooks = res.scalars().all()
    return [
        PlaybookResponseSchema(
            id=pb.id,
            name=pb.name,
            description=pb.description,
            rules=pb.rules or [],
            is_default=pb.is_default,
        )
        for pb in playbooks
    ]


@router.post("/", response_model=PlaybookResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_playbook(
    payload: PlaybookCreateSchema, db: AsyncSession = Depends(get_db)
) -> PlaybookResponseSchema:
    existing = await db.execute(select(Playbook).where(Playbook.name == payload.name))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Playbook '{payload.name}' already exists",
        )
    pb = Playbook(
        name=payload.name,
        description=payload.description,
        rules=[r.model_dump() for r in payload.rules],
        is_default=payload.is_default,
    )
    db.add(pb)
    await db.commit()
    await db.refresh(pb)
    return PlaybookResponseSchema(
        id=pb.id,
        name=pb.name,
        description=pb.description,
        rules=pb.rules or [],
        is_default=pb.is_default,
    )
