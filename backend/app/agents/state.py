"""Shared StateGraph state schema for the 4-agent ContractMind negotiation pipeline."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypedDict


class ContractGraphState(TypedDict, total=False):
    contract_id: str
    title: str
    raw_text: str
    playbook_name: str
    playbook_rules: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    identified_risks: list[dict[str, Any]]
    debate_transcript: list[dict[str, Any]]
    redlines: list[dict[str, Any]]
    obligations: list[dict[str, Any]]
    overall_risk_score: float
    risk_summary: dict[str, int]
    audit_records: list[dict[str, Any]]
    event_emitter: Callable[[dict[str, Any]], Awaitable[None]] | None
