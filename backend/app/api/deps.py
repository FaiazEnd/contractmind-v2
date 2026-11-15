"""Shared FastAPI dependencies."""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User


async def get_optional_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return authenticated user if Bearer token is present and valid, else None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    res = await db.execute(select(User).where(User.id == payload["sub"]))
    return res.scalar_one_or_none()


async def require_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
