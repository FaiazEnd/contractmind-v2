"""Token, cost, and latency telemetry model + pricing calculator."""

import uuid
from datetime import datetime, timezone
from typing import Dict, Tuple

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Pricing per 1,000 tokens (USD) aligned with Section 10 specification
MODEL_PRICING_PER_1K: Dict[str, Tuple[float, float]] = {
    "gemini-3.5-flash-lite": (0.000075, 0.0003),
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "claude-3-5-sonnet": (0.003, 0.015),
    "ollama": (0.0, 0.0),
    "qwen3.5:4b": (0.0, 0.0),
    "llama3.2": (0.0, 0.0),
    "deterministic-simulator": (0.0, 0.0),
}


def calculate_token_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for a model invocation from prompt and completion token counts."""
    normalized = (model_name or "deterministic-simulator").lower()
    prompt_rate, completion_rate = (0.0, 0.0)
    for key, rates in MODEL_PRICING_PER_1K.items():
        if key in normalized:
            prompt_rate, completion_rate = rates
            break
    cost = (prompt_tokens / 1000.0) * prompt_rate + (completion_tokens / 1000.0) * completion_rate
    return round(cost, 8)


class AuditLog(Base):
    """Telemetry record capturing per-node latency, tokens, and estimated USD cost."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="deterministic-simulator")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
