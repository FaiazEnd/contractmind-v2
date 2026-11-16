"""Playbook definition and compliance audit schemas."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class PlaybookRuleSchema(BaseModel):
    category: str
    standard_requirement: str
    unacceptable_terms: list[str] = Field(default_factory=list)
    preferred_fallback: str = ""
    severity_if_missing: str = "HIGH"


class PlaybookCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str = ""
    rules: list[PlaybookRuleSchema] = Field(default_factory=list)
    is_default: bool = False


class PlaybookResponseSchema(BaseModel):
    id: str
    name: str
    description: str
    rules: list[dict[str, Any]]
    is_default: bool


class PlaybookComplianceResultSchema(BaseModel):
    contract_id: str
    playbook_name: str
    adherence_score: float
    status_verdict: str
    passed_rules: int
    total_rules: int
    rule_checks: list[dict[str, Any]] = Field(default_factory=list)
