"""Contract, redline, copilot, and deal-room schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class SectionSchema(BaseModel):
    section_number: str
    title: str
    text: str
    page_number: int = 1


class DiffTokenSchema(BaseModel):
    type: str  # "equal" | "delete" | "insert"
    text: str


class RedlineItemSchema(BaseModel):
    id: str
    section_number: str
    original_text: str
    suggested_text: str
    diff_type: str = "modification"
    risk_severity: str = "MEDIUM"
    legal_rationale: str = ""
    diff_tokens: list[DiffTokenSchema] = Field(default_factory=list)
    accepted: Optional[bool] = None
    custom_prompt: Optional[str] = None


class RedlineDecisionRequest(BaseModel):
    accepted: Optional[bool] = None


class RedlineRegenerateRequest(BaseModel):
    custom_prompt: str = Field(..., min_length=3, max_length=2000)


class ContractSummaryResponse(BaseModel):
    id: str
    title: str
    original_filename: str
    status: str
    playbook_name: str
    overall_risk_score: float
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    redline_count: int = 0
    obligation_count: int = 0
    created_at: datetime
    updated_at: datetime


class ContractDetailResponse(BaseModel):
    id: str
    title: str
    original_filename: str
    status: str
    error_message: Optional[str] = None
    raw_text: str
    playbook_name: str
    overall_risk_score: float
    extracted_sections: list[dict[str, Any]] = Field(default_factory=list)
    identified_risks: list[dict[str, Any]] = Field(default_factory=list)
    debate_transcript: list[dict[str, Any]] = Field(default_factory=list)
    redlines: list[dict[str, Any]] = Field(default_factory=list)
    obligations: list[dict[str, Any]] = Field(default_factory=list)
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list)


class CopilotChatResponse(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    precedents: list[dict[str, Any]] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)
    model_used: str = "contractmind-legal-sim"


class DealRoomConflictRequest(BaseModel):
    contract_ids: list[str] = Field(..., min_length=2)


class LLMConfigRequest(BaseModel):
    provider: str
    model: str
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
