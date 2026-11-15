"""Contract and Playbook SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Contract(Base):
    """Represents an ingested commercial contract and its multi-agent analysis artifacts."""

    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    playbook_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Standard Corporate Playbook"
    )
    overall_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extracted_sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    identified_risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    debate_transcript: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    redlines: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    obligations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risk_summary: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0},
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class Playbook(Base):
    """Corporate legal playbook defining standard terms, unacceptable clauses, and fallbacks."""

    __tablename__ = "playbooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
