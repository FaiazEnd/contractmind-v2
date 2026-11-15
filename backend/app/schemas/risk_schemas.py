"""Pydantic schemas for risk findings, debate turns, LLM config, and telemetry."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class IdentifiedRisk(BaseModel):
    id: str
    category: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    score: float
    section_number: str
    section_title: str
    matched_excerpt: str
    legal_rationale: str
    suggested_mitigation: str


class DebateTurn(BaseModel):
    turn_index: int
    agent_name: str
    role: str
    section_number: str
    risk_category: str
    argument: str
    timestamp: str


class LLMConfigRequest(BaseModel):
    default_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None


class LLMConfigStatus(BaseModel):
    default_provider: str
    providers: Dict[str, Dict[str, object]]


class AuditSummaryResponse(BaseModel):
    total_records: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_estimated_cost_usd: float
    avg_latency_ms: float
    by_agent: List[Dict[str, object]] = Field(default_factory=list)
    by_model: List[Dict[str, object]] = Field(default_factory=list)
