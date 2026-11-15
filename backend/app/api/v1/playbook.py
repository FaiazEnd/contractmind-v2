"""Corporate Playbook CRUD endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.contract import Playbook
from app.schemas.playbook_schemas import PlaybookCreate, PlaybookResponse, PlaybookUpdate
from app.services.playbook_engine import ensure_default_playbooks

router = APIRouter()


@router.get("/", response_model=List[PlaybookResponse])
async def list_playbooks(db: AsyncSession = Depends(get_db)) -> List[Playbook]:
    """List all configured corporate legal playbooks."""
    await ensure_default_playbooks(db)
    res = await db.execute(select(Playbook))
    return list(res.scalars().all())


@router.post("/", response_model=PlaybookResponse, status_code=status.HTTP_201_CREATED)
async def create_playbook(payload: PlaybookCreate, db: AsyncSession = Depends(get_db)) -> Playbook:
    """Create a custom corporate legal playbook."""
    existing = await db.execute(select(Playbook).where(Playbook.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Playbook with this name already exists.")

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


@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(playbook_id: str, db: AsyncSession = Depends(get_db)) -> Playbook:
    res = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = res.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found.")
    return pb


@router.patch("/{playbook_id}", response_model=PlaybookResponse)
async def update_playbook(
    playbook_id: str,
    payload: PlaybookUpdate,
    db: AsyncSession = Depends(get_db),
) -> Playbook:
    res = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = res.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found.")
    if payload.description is not None:
        pb.description = payload.description
    if payload.rules is not None:
        pb.rules = [r.model_dump() for r in payload.rules]
    if payload.is_default is not None:
        pb.is_default = payload.is_default
    await db.commit()
    await db.refresh(pb)
    return pb


@router.delete("/{playbook_id}")
async def delete_playbook(playbook_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    res = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = res.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found.")
    await db.delete(pb)
    await db.commit()
    return {"status": "deleted", "playbook_id": playbook_id}
