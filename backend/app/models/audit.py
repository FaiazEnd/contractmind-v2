"""Token, latency, and USD cost telemetry ORM model and pricing engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# Pricing per 1,000 tokens (USD) per architectural specification
MODEL_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash-lite": (0.000075, 0.0003),
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "claude-3-5-sonnet": (0.003, 0.015),
    "ollama": (0.0, 0.0),
    "simulator": (0.0, 0.0),
}


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Compute estimated USD cost for an LLM invocation."""
    normalized = (model_name or "").lower()
    if "ollama" in normalized or "qwen" in normalized or "llama" in normalized or "simulator" in normalized:
        return 0.0
    prompt_rate, completion_rate = MODEL_PRICING_PER_1K.get(normalized, (0.000075, 0.0003))
    for key, rates in MODEL_PRICING_PER_1K.items():
        if key in normalized:
            prompt_rate, completion_rate = rates
            break
    cost = (prompt_tokens / 1000.0) * prompt_rate + (completion_tokens / 1000.0) * completion_rate
    return round(cost, 8)


class AuditLog(Base):
    """Records per-agent-node execution tokens, wall-clock latency, and cost telemetry."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
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
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
