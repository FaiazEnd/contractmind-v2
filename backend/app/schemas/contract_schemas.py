"""Pydantic schemas for contracts, sections, redlines, copilot, and deal room."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SectionItem(BaseModel):
    section_number: str
    title: str
    text: str
    page_number: int = 1


class DiffToken(BaseModel):
    type: str  # "equal" | "del" | "ins"
    text: str


class RedlineItem(BaseModel):
    id: str
    section_number: str
    original_text: str
    suggested_text: str
    diff_type: str = "modification"
    risk_severity: str = "MEDIUM"
    legal_rationale: str = ""
    diff_tokens: List[Dict[str, str]] = Field(default_factory=list)
    accepted: Optional[bool] = None
    custom_prompt: Optional[str] = None


class RedlineDecisionUpdate(BaseModel):
    accepted: Optional[bool] = None


class RedlineRegenerateRequest(BaseModel):
    custom_prompt: str = Field(..., min_length=3, max_length=2000)


class ContractListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    original_filename: str
    status: str
    playbook_name: str
    overall_risk_score: float
    risk_summary: Dict[str, int]
    created_at: datetime
    updated_at: datetime


class ContractDetail(ContractListItem):
    file_path: str = ""
    error_message: Optional[str] = None
    raw_text: str = ""
    extracted_sections: List[Dict[str, Any]] = Field(default_factory=list)
    identified_risks: List[Dict[str, Any]] = Field(default_factory=list)
    debate_transcript: List[Dict[str, Any]] = Field(default_factory=list)
    redlines: List[Dict[str, Any]] = Field(default_factory=list)
    obligations: List[Dict[str, Any]] = Field(default_factory=list)


class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: List[Dict[str, str]] = Field(default_factory=list)


class CopilotChatResponse(BaseModel):
    answer: str
    citations: List[str] = Field(default_factory=list)
    retrieved_passages: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_followups: List[str] = Field(default_factory=list)
    model_used: str = "deterministic-simulator"


class DealRoomConflictRequest(BaseModel):
    contract_ids: List[str] = Field(..., min_length=2)
