"""Contract, redline action, deal room, copilot, and LLM config schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class SectionItem(BaseModel):
    section_number: str
    title: str
    text: str
    page_number: int = 1


class ContractListItem(BaseModel):
    id: str
    title: str
    original_filename: str
    status: str
    playbook_name: str
    overall_risk_score: float
    risk_summary: dict[str, int]
    redline_count: int = 0
    accepted_count: int = 0
    obligation_count: int = 0
    created_at: datetime
    updated_at: datetime


class ContractDetail(BaseModel):
    id: str
    title: str
    original_filename: str
    file_path: str
    status: str
    error_message: str | None = None
    raw_text: str
    playbook_name: str
    overall_risk_score: float
    extracted_sections: list[dict[str, Any]]
    identified_risks: list[dict[str, Any]]
    debate_transcript: list[dict[str, Any]]
    redlines: list[dict[str, Any]]
    obligations: list[dict[str, Any]]
    risk_summary: dict[str, int]
    created_at: datetime
    updated_at: datetime


class RedlineDecisionRequest(BaseModel):
    accepted: bool | None = None


class RedlineRegenerateRequest(BaseModel):
    custom_prompt: str = Field(..., min_length=3, max_length=2000)


class DealRoomConflictRequest(BaseModel):
    contract_ids: list[str] = Field(..., min_length=2)


class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list)


class CopilotChatResponse(BaseModel):
    contract_id: str
    answer: str
    citations: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    model_used: str = "simulator"


class LLMConfigRequest(BaseModel):
    provider: str = "simulator"
    model: str = "gemini-3.5-flash-lite"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
