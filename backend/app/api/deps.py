"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.contract import Contract


async def get_contract_or_404(
    contract_id: str, db: AsyncSession = Depends(get_db)
) -> Contract:
    res = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = res.scalars().first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{contract_id}' not found",
        )
    return contract
