"""End-to-end integration tests covering all REST endpoints, DOCX Track Changes, Clean DOCX, ICS, Copilot, Deal Room, Playbook, and MCP."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app


def test_full_e2e_workflow() -> None:
    with TestClient(app) as client:
        # 1. Health & UI Studio
        r_health = client.get("/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "healthy"

        r_ui = client.get("/")
        assert r_ui.status_code == 200
        assert "ContractMind" in r_ui.text

        # 2. Load two benchmark deals (MSA + Cloud DPA)
        r_msa = client.post("/api/v1/contracts/demo/msa")
        assert r_msa.status_code == 201
        msa = r_msa.json()
        msa_id = msa["id"]
        assert msa["status"] == "completed"
        assert len(msa["redlines"]) >= 3

        r_dpa = client.post("/api/v1/contracts/demo/cloud_dpa")
        assert r_dpa.status_code == 201
        dpa = r_dpa.json()
        dpa_id = dpa["id"]

        # 3. Filter redlines by severity
        r_crit = client.get(f"/api/v1/analysis/{msa_id}/redlines?risk_severity=CRITICAL")
        assert r_crit.status_code == 200
        assert r_crit.json()["filtered_count"] >= 1

        # 4. Accept first redline, reject second if present
        first_rl_id = msa["redlines"][0]["id"]
        r_accept = client.patch(
            f"/api/v1/analysis/{msa_id}/redlines/{first_rl_id}",
            json={"accepted": True},
        )
        assert r_accept.status_code == 200
        assert r_accept.json()["redline"]["accepted"] is True

        if len(msa["redlines"]) > 1:
            second_rl_id = msa["redlines"][1]["id"]
            r_reject = client.patch(
                f"/api/v1/analysis/{msa_id}/redlines/{second_rl_id}",
                json={"accepted": False},
            )
            assert r_reject.status_code == 200
            assert r_reject.json()["redline"]["accepted"] is False

        # 5. AI Prompt Rewriting on first redline (resets to pending)
        r_regen = client.post(
            f"/api/v1/analysis/{msa_id}/redlines/{first_rl_id}/regenerate",
            json={"custom_prompt": "Cap indemnity at 2x fees and require 30-day cure"},
        )
        assert r_regen.status_code == 200
        regen_rl = r_regen.json()["redline"]
        assert regen_rl["accepted"] is None
        assert "2x" in regen_rl["suggested_text"] or "capped" in regen_rl["suggested_text"].lower()

        # Re-accept for Clean DOCX export verification
        client.patch(
            f"/api/v1/analysis/{msa_id}/redlines/{first_rl_id}",
            json={"accepted": True},
        )

        # 6. Export Track Changes DOCX & verify OpenXML <w:del> and <w:ins>
        r_docx = client.get(f"/api/v1/analysis/{msa_id}/export/docx")
        assert r_docx.status_code == 200
        with zipfile.ZipFile(io.BytesIO(r_docx.content)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "w:del" in doc_xml
            assert "w:ins" in doc_xml
            assert "ContractMind Legal AI" in doc_xml

        # 7. Export Clean DOCX & verify zero <w:del> / <w:ins>
        r_clean = client.get(f"/api/v1/analysis/{msa_id}/export/clean")
        assert r_clean.status_code == 200
        with zipfile.ZipFile(io.BytesIO(r_clean.content)) as zf:
            clean_xml = zf.read("word/document.xml").decode("utf-8")
            assert "<w:del " not in clean_xml
            assert "<w:ins " not in clean_xml

        # 8. Export RFC 5545 .ics calendar
        r_ics = client.get(f"/api/v1/analysis/{msa_id}/export/calendar")
        assert r_ics.status_code == 200
        assert "BEGIN:VCALENDAR" in r_ics.text
        assert "BEGIN:VEVENT" in r_ics.text
        assert "STATUS:CONFIRMED" in r_ics.text

        # 9. Playbook Compliance Check
        r_pb = client.get(f"/api/v1/analysis/{msa_id}/compliance/playbook")
        assert r_pb.status_code == 200
        pb_data = r_pb.json()
        assert 0.0 <= pb_data["adherence_score"] <= 100.0
        assert pb_data["total_rules"] >= 4

        # 10. Grounded Legal AI Copilot
        r_cop = client.post(
            f"/api/v1/copilot/{msa_id}/chat",
            json={"message": "Generate a CFO Risk Summary"},
        )
        assert r_cop.status_code == 200
        cop = r_cop.json()
        assert cop["citations"]
        assert len(cop["precedents"]) >= 1

        # 11. Deal Room Cross-Contract Conflict Analyzer
        r_dr = client.post(
            "/api/v1/analysis/deal-room/conflicts",
            json=[msa_id, dpa_id],
        )
        assert r_dr.status_code == 200
        dr = r_dr.json()
        assert dr["conflict_count"] >= 2
        assert 0.0 <= dr["deal_alignment_score"] <= 100.0

        # 12. MCP JSON-RPC Server
        r_mcp_list = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert r_mcp_list.status_code == 200
        assert len(r_mcp_list.json()["result"]["tools"]) == 6

        r_mcp_call = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "query_legal_precedents",
                    "arguments": {"query": "indemnification cap", "n_results": 2},
                },
            },
        )
        assert r_mcp_call.status_code == 200
        assert len(r_mcp_call.json()["result"]["data"]) == 2

        # 13. Audit Summary & Cleanup
        r_audit = client.get("/api/v1/analysis/audit/summary")
        assert r_audit.status_code == 200
        assert r_audit.json()["total_runs"] >= 8

        assert client.delete(f"/api/v1/contracts/{msa_id}").status_code == 200
        assert client.delete(f"/api/v1/contracts/{dpa_id}").status_code == 200
