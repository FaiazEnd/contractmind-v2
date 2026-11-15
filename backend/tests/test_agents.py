"""Tests for Multi-Agent StateGraph pipeline, exports, calendar, playbook, and Deal Room."""

import io
import sys
from pathlib import Path

import pytest
from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.graph import contract_graph
from app.models.contract import Contract, Playbook
from app.services.calendar_service import generate_ics_calendar
from app.services.cross_contract_service import analyze_cross_contract_conflicts
from app.services.demo_contracts import DEMO_CONTRACTS
from app.services.export_service import export_clean_docx, export_to_docx
from app.services.pdf_processor import process_text_document
from app.services.playbook_engine import DEFAULT_PLAYBOOKS, evaluate_playbook_compliance


@pytest.mark.asyncio
async def test_stategraph_4_node_pipeline():
    parsed = process_text_document(DEMO_CONTRACTS["msa"]["text"])
    initial = {
        "contract_id": "test-msa-1",
        "title": DEMO_CONTRACTS["msa"]["title"],
        "playbook_name": "Standard Corporate Playbook",
        "raw_text": parsed["raw_text"],
        "sections": parsed["sections"],
        "identified_risks": [],
        "debate_transcript": [],
        "redlines": [],
        "obligations": [],
        "overall_risk_score": 0.0,
        "risk_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "audit_events": [],
    }
    out = await contract_graph.ainvoke(initial)

    assert len(out["identified_risks"]) >= 6
    assert len(out["redlines"]) == len(out["identified_risks"])
    assert len(out["debate_transcript"]) >= len(out["identified_risks"]) * 3
    assert len(out["obligations"]) >= 4
    assert 0.0 < out["overall_risk_score"] <= 100.0
    assert len(out["audit_events"]) == 4
    for rl in out["redlines"]:
        assert any(tok["type"] in ("del", "ins") for tok in rl["diff_tokens"])


@pytest.mark.asyncio
async def test_docx_track_changes_clean_export_and_ics_calendar():
    parsed = process_text_document(DEMO_CONTRACTS["msa"]["text"])
    out = await contract_graph.ainvoke(
        {
            "contract_id": "test-export-1",
            "title": "Test MSA Agreement",
            "playbook_name": "Standard Corporate Playbook",
            "raw_text": parsed["raw_text"],
            "sections": parsed["sections"],
            "identified_risks": [],
            "debate_transcript": [],
            "redlines": [],
            "obligations": [],
            "overall_risk_score": 0.0,
            "risk_summary": {},
            "audit_events": [],
        }
    )
    redlines = out["redlines"]
    redlines[0]["accepted"] = True
    if len(redlines) > 1:
        redlines[1]["accepted"] = False

    contract = Contract(
        id="test-export-1",
        title="Test MSA Agreement",
        original_filename="test_msa.pdf",
        raw_text=parsed["raw_text"],
        playbook_name="Standard Corporate Playbook",
        overall_risk_score=out["overall_risk_score"],
        extracted_sections=parsed["sections"],
        identified_risks=out["identified_risks"],
        debate_transcript=out["debate_transcript"],
        redlines=redlines,
        obligations=out["obligations"],
        risk_summary=out["risk_summary"],
    )

    tracked_bytes = export_to_docx(contract)
    tracked_doc = Document(io.BytesIO(tracked_bytes))
    xml_str = tracked_doc.element.xml
    assert "w:del" in xml_str
    assert "w:ins" in xml_str
    assert "ContractMind Legal AI" in xml_str

    clean_bytes = export_clean_docx(contract)
    clean_doc = Document(io.BytesIO(clean_bytes))
    clean_xml = clean_doc.element.xml
    assert "w:del" not in clean_xml
    assert "w:ins" not in clean_xml
    assert "CLEAN EXECUTION DRAFT" in "\n".join(p.text for p in clean_doc.paragraphs)

    ics = generate_ics_calendar(contract)
    assert "BEGIN:VCALENDAR" in ics
    assert "BEGIN:VEVENT" in ics
    assert "STATUS:CONFIRMED" in ics
    assert "[ContractMind]" in ics


@pytest.mark.asyncio
async def test_playbook_compliance_and_deal_room_conflicts():
    msa_parsed = process_text_document(DEMO_CONTRACTS["msa"]["text"])
    out = await contract_graph.ainvoke(
        {
            "contract_id": "msa-1",
            "title": DEMO_CONTRACTS["msa"]["title"],
            "playbook_name": "Standard Corporate Playbook",
            "raw_text": msa_parsed["raw_text"],
            "sections": msa_parsed["sections"],
            "identified_risks": [],
            "debate_transcript": [],
            "redlines": [],
            "obligations": [],
            "overall_risk_score": 0.0,
            "risk_summary": {},
            "audit_events": [],
        }
    )
    msa = Contract(
        id="msa-1",
        title=DEMO_CONTRACTS["msa"]["title"],
        original_filename="msa.pdf",
        raw_text=msa_parsed["raw_text"],
        playbook_name="Standard Corporate Playbook",
        overall_risk_score=out["overall_risk_score"],
        extracted_sections=msa_parsed["sections"],
        redlines=out["redlines"],
    )
    dpa = Contract(
        id="dpa-1",
        title=DEMO_CONTRACTS["cloud_dpa"]["title"],
        original_filename="dpa.pdf",
        raw_text=DEMO_CONTRACTS["cloud_dpa"]["text"],
        playbook_name="Standard Corporate Playbook",
    )

    pb = Playbook(**DEFAULT_PLAYBOOKS[0])
    report = evaluate_playbook_compliance(msa, pb)
    assert 0.0 <= report["adherence_score"] <= 100.0
    assert report["remediated_count"] >= 1

    conflicts = analyze_cross_contract_conflicts([msa, dpa])
    assert conflicts["contract_count"] == 2
    assert len(conflicts["conflicts"]) >= 2
    assert any("Governing Law" in c["conflict_type"] for c in conflicts["conflicts"])
