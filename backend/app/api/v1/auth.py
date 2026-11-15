"""Authentication endpoints for optional legal workspace user sessions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


class AuthCredentials(BaseModel):
    email: str
    password: str
    full_name: str = "Lead Counsel"


@router.post("/register")
async def register(payload: AuthCredentials, db: AsyncSession = Depends(get_db)) -> dict:
    existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "full_name": user.full_name}}


@router.post("/login")
async def login(payload: AuthCredentials, db: AsyncSession = Depends(get_db)) -> dict:
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "full_name": user.full_name}}


@router.get("/me")
async def me(user: User | None = Depends(get_optional_user)) -> dict:
    if not user:
        return {"authenticated": False, "role": "guest_counsel"}
    return {"authenticated": True, "id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}
