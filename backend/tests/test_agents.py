"""End-to-end tests for 4-agent StateGraph, REST endpoints, DOCX/ICS exports, Deal Room, Playbook & MCP."""

from __future__ import annotations

import io
import zipfile
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import init_db
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def _setup_db() -> None:
    await init_db()


@pytest.mark.asyncio
async def test_full_contractmind_lifecycle() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        h = await client.get("/health")
        assert h.status_code == 200
        assert h.json()["status"] == "healthy"

        # 2. Load MSA and Cloud DPA demos (auto-runs 4-Agent StateGraph)
        r_msa = await client.post("/api/v1/contracts/demo/msa")
        assert r_msa.status_code == 200
        msa = r_msa.json()
        assert msa["status"] == "completed"
        assert msa["overall_risk_score"] > 0
        assert len(msa["redlines"]) >= 3
        assert len(msa["debate_transcript"]) >= 4
        assert len(msa["obligations"]) >= 2

        r_dpa = await client.post("/api/v1/contracts/demo/cloud_dpa")
        assert r_dpa.status_code == 200
        dpa = r_dpa.json()

        msa_id = msa["id"]
        dpa_id = dpa["id"]
        redline_0 = msa["redlines"][0]["id"]
        redline_1 = msa["redlines"][1]["id"]

        # 3. Clause-level Accept / Reject decisions via PATCH
        p1 = await client.patch(f"/api/v1/analysis/{msa_id}/redlines/{redline_0}", json={"accepted": True})
        assert p1.status_code == 200
        assert p1.json()["redline"]["accepted"] is True

        p2 = await client.patch(f"/api/v1/analysis/{msa_id}/redlines/{redline_1}", json={"accepted": False})
        assert p2.status_code == 200
        assert p2.json()["redline"]["accepted"] is False

        # 4. Filtered redlines query
        f_acc = await client.get(f"/api/v1/analysis/{msa_id}/redlines?decision=ACCEPTED")
        assert f_acc.status_code == 200
        assert f_acc.json()["filtered_count"] == 1

        # 5. On-demand AI Prompt Rewriting
        regen = await client.post(
            f"/api/v1/analysis/{msa_id}/redlines/{redline_1}/regenerate",
            json={"custom_prompt": "Cap at 24 months fees with mutual reciprocal carve-out"},
        )
        assert regen.status_code == 200
        regen_rl = regen.json()["redline"]
        assert regen_rl["accepted"] is None
        assert "twenty-four (24) months" in regen_rl["suggested_text"] or "mutual" in regen_rl["suggested_text"].lower()
        assert len(regen_rl["diff_tokens"]) > 0

        # Re-reject redline_1 so DOCX export tests both accepted and rejected handling
        await client.patch(f"/api/v1/analysis/{msa_id}/redlines/{redline_1}", json={"accepted": False})

        # 6. Track Changes DOCX export (verify OpenXML <w:del> and <w:ins> tags)
        docx_resp = await client.get(f"/api/v1/analysis/{msa_id}/export/docx")
        assert docx_resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(docx_resp.content)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "<w:del " in doc_xml or "w:del " in doc_xml
            assert "<w:ins " in doc_xml or "w:ins " in doc_xml
            assert "ACCEPTED" in doc_xml
            assert "REJECTED" in doc_xml

        # 7. Clean Executable DOCX export (no Track Changes markup tags)
        clean_resp = await client.get(f"/api/v1/analysis/{msa_id}/export/clean")
        assert clean_resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(clean_resp.content)) as zf:
            clean_xml = zf.read("word/document.xml").decode("utf-8")
            assert "<w:del " not in clean_xml
            assert "<w:ins " not in clean_xml

        # 8. RFC 5545 iCalendar export
        ics_resp = await client.get(f"/api/v1/analysis/{msa_id}/export/calendar")
        assert ics_resp.status_code == 200
        ics_text = ics_resp.text
        assert "BEGIN:VCALENDAR" in ics_text
        assert "BEGIN:VEVENT" in ics_text
        assert "[ContractMind]" in ics_text

        # 9. Playbook compliance score
        comp = await client.get(f"/api/v1/analysis/{msa_id}/compliance/playbook")
        assert comp.status_code == 200
        comp_json = comp.json()
        assert 0.0 <= comp_json["adherence_score"] <= 100.0
        assert comp_json["verdict"] in {
            "STRONG COMPLIANCE",
            "ACCEPTABLE WITH REDLINES",
            "HIGH DEVIATION / HIGH RISK",
        }

        # 10. Deal Room Cross-Contract Contradiction Audit (MSA vs Cloud DPA)
        dr = await client.post("/api/v1/analysis/deal-room/conflicts", json=[msa_id, dpa_id])
        assert dr.status_code == 200
        dr_json = dr.json()
        assert dr_json["conflict_count"] >= 2
        assert 0.0 <= dr_json["deal_alignment_score"] <= 100.0

        # 11. Grounded Legal AI Copilot
        cop = await client.post(
            f"/api/v1/copilot/{msa_id}/chat",
            json={"message": "Generate a CFO Risk Summary for uncapped indemnification"},
        )
        assert cop.status_code == 200
        cop_json = cop.json()
        assert len(cop_json["citations"]) >= 1
        assert "Risk" in cop_json["answer"]

        # 12. MCP JSON-RPC 2.0 server
        mcp_tools = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert mcp_tools.status_code == 200
        assert len(mcp_tools.json()["result"]["tools"]) >= 4

        # 13. Audit telemetry summary
        tel = await client.get("/api/v1/analysis/audit/summary")
        assert tel.status_code == 200
        assert tel.json()["total_calls"] >= 8
        assert tel.json()["total_tokens"] > 0

        # 14. Delete contracts & purge telemetry
        del1 = await client.delete(f"/api/v1/contracts/{msa_id}")
        assert del1.status_code == 200
        del2 = await client.delete(f"/api/v1/contracts/{dpa_id}")
        assert del2.status_code == 200

        reset = await client.delete("/api/v1/analysis/audit/reset")
        assert reset.status_code == 200
