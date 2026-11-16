"""Audit log model and Token/Cost Telemetry engine."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    return str(uuid.uuid4())


# Pricing per 1K tokens (USD) per Section 10 Telemetry specification
MODEL_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash-lite": (0.000075, 0.0003),
    "gemini-2.5-flash-lite": (0.000075, 0.0003),
    "gemini-2.5-flash": (0.00015, 0.0006),
    "gemini-2.5-pro": (0.00125, 0.005),
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "ollama": (0.0, 0.0),
    "contractmind-legal-sim": (0.0, 0.0),
}


def calculate_cost_usd(
    model_name: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Calculate USD cost for an LLM invocation based on model pricing table."""
    normalized = (model_name or "").lower().strip()
    if normalized.startswith("ollama") or "qwen" in normalized or "llama" in normalized:
        return 0.0

    prompt_rate, completion_rate = MODEL_PRICING_PER_1K.get(
        normalized, (0.000075, 0.0003)
    )
    cost = (prompt_tokens / 1000.0) * prompt_rate + (
        completion_tokens / 1000.0
    ) * completion_rate
    return round(cost, 8)


class AuditLog(Base):
    """Stores per-agent execution telemetry, token usage, latency, and estimated USD cost."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    contract_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
