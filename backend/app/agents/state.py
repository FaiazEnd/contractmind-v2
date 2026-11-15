"""Shared StateGraph state schema for ContractMind multi-agent execution."""

from typing import Any, Dict, List, TypedDict


class ContractAgentState(TypedDict, total=False):
    contract_id: str
    title: str
    playbook_name: str
    raw_text: str
    sections: List[Dict[str, Any]]
    identified_risks: List[Dict[str, Any]]
    debate_transcript: List[Dict[str, Any]]
    redlines: List[Dict[str, Any]]
    obligations: List[Dict[str, Any]]
    overall_risk_score: float
    risk_summary: Dict[str, int]
    audit_events: List[Dict[str, Any]]
