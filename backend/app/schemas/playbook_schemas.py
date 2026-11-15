"""Playbook and compliance audit schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlaybookRule(BaseModel):
    id: str
    category: str
    standard_requirement: str
    unacceptable_terms: list[str] = Field(default_factory=list)
    preferred_fallback: str
    severity_if_missing: str = "HIGH"


class PlaybookCreate(BaseModel):
    name: str
    description: str = ""
    rules: list[PlaybookRule] = Field(default_factory=list)
    is_default: bool = False


class PlaybookResponse(BaseModel):
    id: str
    name: str
    description: str
    rules: list[PlaybookRule]
    is_default: bool


class RuleComplianceItem(BaseModel):
    rule_id: str
    category: str
    severity: str
    standard_requirement: str
    status: str  # COMPLIANT | REMEDIATED_BY_REDLINE | DEVIATION
    matched_unacceptable_terms: list[str] = Field(default_factory=list)
    remediation_note: str = ""
    preferred_fallback: str = ""


class PlaybookComplianceResult(BaseModel):
    contract_id: str
    playbook_name: str
    adherence_score: float
    verdict: str  # STRONG COMPLIANCE | ACCEPTABLE WITH REDLINES | HIGH DEVIATION / HIGH RISK
    total_rules: int
    compliant_count: int
    remediated_count: int
    deviation_count: int
    checklist: list[RuleComplianceItem] = Field(default_factory=list)
