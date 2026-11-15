"""SQLAlchemy models for Contracts and Corporate Playbooks."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Contract(Base):
    """Commercial contract artifact, analysis results, redlines, and obligations."""

    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    playbook_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Standard Corporate Playbook"
    )
    overall_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extracted_sections: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    identified_risks: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    debate_transcript: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    redlines: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    obligations: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    risk_summary: Mapped[Dict[str, int]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0},
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class Playbook(Base):
    """Corporate legal playbook defining standard terms, unacceptable clauses, and fallbacks."""

    __tablename__ = "playbooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rules: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
