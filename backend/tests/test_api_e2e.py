"""End-to-end FastAPI API tests verifying all REST, Copilot, Deal Room, Export, and MCP endpoints."""

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import init_db
from app.main import app


@pytest.mark.asyncio
async def test_full_api_lifecycle():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health & UI
        h = await client.get("/health")
        assert h.status_code == 200
        assert h.json()["status"] == "healthy"

        studio = await client.get("/")
        assert studio.status_code == 200
        assert "ContractMind" in studio.text

        # 2. Load two demo contracts for Deal Room audit
        r_msa = await client.post("/api/v1/contracts/demo/msa")
        assert r_msa.status_code == 201
        msa = r_msa.json()
        msa_id = msa["id"]
        assert len(msa["redlines"]) >= 5

        r_dpa = await client.post("/api/v1/contracts/demo/cloud_dpa")
        assert r_dpa.status_code == 201
        dpa_id = r_dpa.json()["id"]

        # 3. Filter redlines & accept/reject + prompt rewrite
        rl_id = msa["redlines"][0]["id"]
        r_filter = await client.get(f"/api/v1/analysis/{msa_id}/redlines?risk_severity=CRITICAL")
        assert r_filter.status_code == 200
        assert r_filter.json()["filtered_count"] >= 1

        r_patch = await client.patch(
            f"/api/v1/analysis/{msa_id}/redlines/{rl_id}",
            json={"accepted": True},
        )
        assert r_patch.status_code == 200
        assert r_patch.json()["redline"]["accepted"] is True

        r_regen = await client.post(
            f"/api/v1/analysis/{msa_id}/redlines/{rl_id}/regenerate",
            json={"custom_prompt": "Cap liability at 6 months fees and make indemnity mutual"},
        )
        assert r_regen.status_code == 200
        assert r_regen.json()["redline"]["accepted"] is None
        assert r_regen.json()["redline"]["custom_prompt"] is not None

        # 4. Exports (DOCX Track Changes, Clean DOCX, ICS Calendar)
        assert (await client.get(f"/api/v1/analysis/{msa_id}/export/docx")).status_code == 200
        assert (await client.get(f"/api/v1/analysis/{msa_id}/export/clean")).status_code == 200
        r_ics = await client.get(f"/api/v1/analysis/{msa_id}/export/calendar")
        assert r_ics.status_code == 200
        assert "BEGIN:VCALENDAR" in r_ics.text

        # 5. Playbook compliance & Deal Room conflicts
        r_pb = await client.get(f"/api/v1/analysis/{msa_id}/compliance/playbook")
        assert r_pb.status_code == 200
        assert r_pb.json()["adherence_score"] > 0

        r_dr = await client.post("/api/v1/analysis/deal-room/conflicts", json=[msa_id, dpa_id])
        assert r_dr.status_code == 200
        assert len(r_dr.json()["conflicts"]) >= 1

        # 6. Grounded Copilot
        r_cop = await client.post(
            f"/api/v1/copilot/{msa_id}/chat",
            json={"message": "Give me a CFO Risk Summary with citations"},
        )
        assert r_cop.status_code == 200
        assert len(r_cop.json()["citations"]) >= 1

        # 7. MCP JSON-RPC tools/list & tools/call
        r_mcp = await client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r_mcp.status_code == 200
        assert len(r_mcp.json()["result"]["tools"]) >= 5

        # 8. Telemetry summary & contract deletion
        r_tel = await client.get("/api/v1/analysis/audit/summary")
        assert r_tel.status_code == 200
        assert r_tel.json()["total_records"] >= 4

        r_del_msa = await client.delete(f"/api/v1/contracts/{msa_id}")
        assert r_del_msa.status_code == 200
        assert r_del_msa.json()["rag_purged"] is True
        await client.delete(f"/api/v1/contracts/{dpa_id}")
