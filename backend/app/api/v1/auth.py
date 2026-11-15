"""Optional authentication endpoints for studio workspaces."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.user import User

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = "Enterprise Counsel"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> dict:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id, role=user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role},
    }


@router.post("/login")
async def login_user(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    token = create_access_token(user.id, role=user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role},
    }


@router.get("/me")
async def current_user(user: User = Depends(require_user)) -> dict:
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}
