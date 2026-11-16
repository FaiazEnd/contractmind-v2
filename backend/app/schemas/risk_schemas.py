"""Risk assessment and debate transcript schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RiskFindingSchema(BaseModel):
    id: str
    category: str
    severity: str
    score: float
    section_number: str
    section_title: str = ""
    matched_excerpt: str = ""
    legal_rationale: str = ""
    suggested_mitigation: str = ""


class DebateTurnSchema(BaseModel):
    agent: str
    role: str
    section_number: str = ""
    category: str = ""
    argument: str
    timestamp: str = ""


class RiskSummarySchema(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    overall_risk_score: float = 0.0
    findings: list[RiskFindingSchema] = Field(default_factory=list)
