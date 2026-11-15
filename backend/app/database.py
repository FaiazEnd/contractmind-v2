"""Async SQLAlchemy 2.0 database engine, session factory, and initialization."""

import asyncio
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

_db_initialized = False
_db_init_lock = asyncio.Lock()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    await ensure_db_initialized()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def ensure_db_initialized() -> None:
    """Idempotently initialize tables and seed default playbooks (safe for serverless cold starts)."""
    global _db_initialized
    if _db_initialized:
        return
    async with _db_init_lock:
        if _db_initialized:
            return
        await init_db()
        _db_initialized = True


async def init_db() -> None:
    """Create all tables and seed default playbooks if missing."""
    global _db_initialized
    # Import models to register metadata
    from app.models import audit, contract, user  # noqa: F401
    from app.services.playbook_engine import ensure_default_playbooks

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await ensure_default_playbooks(session)
    _db_initialized = True
