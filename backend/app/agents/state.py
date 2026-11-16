"""Shared StateGraph state definition for ContractMind multi-agent pipeline."""
from __future__ import annotations

from typing import Any, Callable, Coroutine, TypedDict


class ContractAnalysisState(TypedDict, total=False):
    contract_id: str
    title: str
    raw_text: str
    sections: list[dict[str, Any]]
    playbook_name: str
    playbook_rules: list[dict[str, Any]]

    identified_risks: list[dict[str, Any]]
    debate_transcript: list[dict[str, Any]]
    redlines: list[dict[str, Any]]
    obligations: list[dict[str, Any]]
    risk_summary: dict[str, int]
    overall_risk_score: float

    audit_logs: list[dict[str, Any]]
    progress_callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None
