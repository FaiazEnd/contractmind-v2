"""Tests for 4-Agent StateGraph pipeline, diff engine, telemetry pricing, and fallback gateway."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.graph import contract_graph
from app.models.audit import calculate_cost_usd
from app.services.pdf_processor import process_raw_text
from app.services.sample_contracts import SAMPLE_CONTRACTS


def test_telemetry_pricing_model() -> None:
    assert calculate_cost_usd("ollama", 1000, 1000) == 0.0
    assert calculate_cost_usd("gpt-4o", 1000, 1000) == pytest.approx(0.02, rel=1e-4)
    assert calculate_cost_usd("claude-3-5-sonnet", 1000, 1000) == pytest.approx(0.018, rel=1e-4)
    assert calculate_cost_usd("gemini-3.5-flash-lite", 1000, 1000) == pytest.approx(0.000375, rel=1e-4)


@pytest.mark.asyncio
async def test_four_agent_stategraph_execution() -> None:
    parsed = process_raw_text(SAMPLE_CONTRACTS["saas"]["text"])
    initial_state = {
        "contract_id": "unit-test-saas",
        "title": SAMPLE_CONTRACTS["saas"]["title"],
        "raw_text": parsed["raw_text"],
        "sections": parsed["sections"],
        "playbook_name": "Standard Corporate Playbook",
        "playbook_rules": [],
        "identified_risks": [],
        "debate_transcript": [],
        "redlines": [],
        "obligations": [],
        "risk_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "overall_risk_score": 0.0,
        "audit_logs": [],
        "progress_callback": None,
    }

    final = await contract_graph.ainvoke(initial_state)  # type: ignore[arg-type]
    assert len(final["identified_risks"]) >= 3
    assert len(final["redlines"]) == len(final["identified_risks"])
    assert final["overall_risk_score"] > 0.0
    assert len(final["obligations"]) >= 2
    assert len(final["audit_logs"]) == 4

    agents_logged = {log["agent_name"] for log in final["audit_logs"]}
    assert agents_logged == {
        "Auditor Agent",
        "Opposing Counsel Agent",
        "Redline Synthesizer Agent",
        "Obligation Extractor Agent",
    }
    for rl in final["redlines"]:
        assert rl["diff_tokens"]
        assert rl["accepted"] is None
