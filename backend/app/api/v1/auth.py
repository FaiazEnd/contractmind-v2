"""Authentication endpoints for optional enterprise workspace sign-in."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = "Enterprise Counsel"


class AuthLoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register_user(
    payload: AuthRegisterRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user_id": user.id}


@router.post("/token")
async def login_for_token(
    payload: AuthLoginRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalars().first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user_id": user.id}


@router.get("/me")
async def get_workspace_profile() -> dict:
    return {
        "workspace": "ContractMind Legal Studio v2.0",
        "role": "Senior Commercial Counsel",
        "authenticated": True,
    }
