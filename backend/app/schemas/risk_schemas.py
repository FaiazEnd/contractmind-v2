"""Risk, redline, diff token, and debate transcript Pydantic schemas."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


SeverityLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]


class DiffToken(BaseModel):
    type: Literal["equal", "del", "ins"]
    text: str


class IdentifiedRisk(BaseModel):
    id: str
    category: str
    severity: SeverityLevel
    score: float
    section_number: str
    section_title: str = ""
    matched_excerpt: str
    legal_rationale: str
    suggested_mitigation: str


class RedlineItem(BaseModel):
    id: str
    section_number: str
    original_text: str
    suggested_text: str
    diff_type: str = "modification"
    risk_severity: SeverityLevel
    legal_rationale: str
    diff_tokens: list[DiffToken] = Field(default_factory=list)
    accepted: bool | None = None
    custom_prompt: str | None = None


class DebateTurn(BaseModel):
    agent: str
    role: str
    section_number: str = "General"
    stance: str = ""
    message: str
    timestamp: str = ""


class RiskSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
