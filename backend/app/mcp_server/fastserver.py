"""Model Context Protocol (MCP) HTTP/JSON-RPC 2.0 server exposing ContractMind tools."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.contract import Contract, Playbook
from app.services.cross_contract_service import analyze_deal_room_conflicts
from app.services.playbook_engine import evaluate_playbook_compliance
from app.services.rag_engine import rag_engine

mcp_router = APIRouter(tags=["MCP Server"])

MCP_TOOLS = [
    {
        "name": "list_contracts",
        "description": "List all analyzed contracts in the ContractMind workspace.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "query_contract_rag",
        "description": "Search contract sections via Contextual RAG semantic/cosine retrieval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_id": {"type": "string"},
                "query": {"type": "string"},
                "n_results": {"type": "integer", "default": 4},
            },
            "required": ["contract_id", "query"],
        },
    },
    {
        "name": "check_playbook_compliance",
        "description": "Audit a contract against its assigned corporate playbook and compute adherence score.",
        "inputSchema": {
            "type": "object",
            "properties": {"contract_id": {"type": "string"}},
            "required": ["contract_id"],
        },
    },
    {
        "name": "audit_deal_room_conflicts",
        "description": "Run Deal Room cross-contract contradiction audit across 2+ contracts.",
        "inputSchema": {
            "type": "object",
            "properties": {"contract_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["contract_ids"],
        },
    },
]


@mcp_router.post("/mcp")
async def mcp_jsonrpc_endpoint(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Handle MCP JSON-RPC 2.0 initialize, tools/list, and tools/call requests."""
    body = await request.json()
    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "contractmind-mcp", "version": "2.0.0"},
                "capabilities": {"tools": {}},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments") or {}

        if tool_name == "list_contracts":
            rows = (await db.execute(select(Contract).order_by(Contract.created_at.desc()))).scalars().all()
            payload = [
                {"id": c.id, "title": c.title, "status": c.status, "risk_score": c.overall_risk_score}
                for c in rows
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "json", "json": payload}]}}

        if tool_name == "query_contract_rag":
            cid = args.get("contract_id", "")
            query = args.get("query", "")
            n_res = int(args.get("n_results", 4))
            hits = rag_engine.query_similar(cid, query, n_results=n_res)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "json", "json": hits}]}}

        if tool_name == "check_playbook_compliance":
            cid = args.get("contract_id", "")
            contract = (await db.execute(select(Contract).where(Contract.id == cid))).scalar_one_or_none()
            if not contract:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Contract not found"}}
            pb = (
                await db.execute(select(Playbook).where(Playbook.name == contract.playbook_name))
            ).scalar_one_or_none()
            if not pb:
                pb = (await db.execute(select(Playbook).where(Playbook.is_default.is_(True)))).scalar_one_or_none()
            res = evaluate_playbook_compliance(contract, pb)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "json", "json": res.model_dump()}]}}

        if tool_name == "audit_deal_room_conflicts":
            cids = args.get("contract_ids") or []
            rows = (await db.execute(select(Contract).where(Contract.id.in_(cids)))).scalars().all()
            if len(rows) < 2:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Need at least 2 contracts"}}
            res = analyze_deal_room_conflicts(list(rows))
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "json", "json": res}]}}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unsupported method: {method}"}}
