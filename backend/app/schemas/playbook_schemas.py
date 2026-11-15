"""Pydantic schemas for corporate playbooks and compliance evaluations."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PlaybookRule(BaseModel):
    category: str
    standard_requirement: str
    unacceptable_terms: List[str] = Field(default_factory=list)
    preferred_fallback: str
    severity_if_missing: str = "HIGH"


class PlaybookCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str = ""
    rules: List[PlaybookRule] = Field(default_factory=list)
    is_default: bool = False


class PlaybookUpdate(BaseModel):
    description: Optional[str] = None
    rules: Optional[List[PlaybookRule]] = None
    is_default: Optional[bool] = None


class PlaybookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    rules: List[Dict[str, Any]]
    is_default: bool


class PlaybookRuleCheck(BaseModel):
    category: str
    severity_if_missing: str
    status: str  # "COMPLIANT" | "REMEDIATED_BY_REDLINE" | "NON_COMPLIANT"
    matched_unacceptable_terms: List[str] = Field(default_factory=list)
    remediated_by_redline_id: Optional[str] = None
    finding: str
    preferred_fallback: str


class PlaybookComplianceReport(BaseModel):
    contract_id: str
    playbook_name: str
    adherence_score: float
    verdict: str  # "STRONG COMPLIANCE" | "ACCEPTABLE WITH REDLINES" | "HIGH DEVIATION / HIGH RISK"
    total_rules: int
    compliant_count: int
    remediated_count: int
    non_compliant_count: int
    rule_checks: List[PlaybookRuleCheck]
