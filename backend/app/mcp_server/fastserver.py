"""Model Context Protocol (MCP) HTTP/JSON-RPC 2.0 gateway for ContractMind v2.0."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract, Playbook
from app.services.cross_contract_service import analyze_cross_contract_conflicts
from app.services.playbook_engine import ensure_default_playbooks, evaluate_playbook_compliance
from app.services.rag_engine import rag_engine

router = APIRouter()

MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "list_contracts",
        "description": "List all uploaded and demo contracts in ContractMind with risk scores and status.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_contract_analysis",
        "description": "Retrieve identified risks, redlines, and obligations for a contract ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"contract_id": {"type": "string"}},
            "required": ["contract_id"],
        },
    },
    {
        "name": "query_contract_rag",
        "description": "Search contextual clause passages inside a contract via RAG.",
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
        "description": "Evaluate corporate playbook compliance score and remediation status for a contract.",
        "inputSchema": {
            "type": "object",
            "properties": {"contract_id": {"type": "string"}},
            "required": ["contract_id"],
        },
    },
    {
        "name": "analyze_deal_room_conflicts",
        "description": "Audit multiple related contracts for cross-contract contradictions and precedence traps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["contract_ids"],
        },
    },
    {
        "name": "get_telemetry_summary",
        "description": "Return token consumption, latency, and estimated USD cost telemetry.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


async def _dispatch_tool(name: str, args: Dict[str, Any], db: AsyncSession) -> Any:
    if name == "list_contracts":
        res = await db.execute(select(Contract).order_by(desc(Contract.created_at)))
        contracts = res.scalars().all()
        return [
            {
                "id": c.id,
                "title": c.title,
                "status": c.status,
                "overall_risk_score": c.overall_risk_score,
                "risk_summary": c.risk_summary,
            }
            for c in contracts
        ]

    if name == "get_contract_analysis":
        cid = str(args.get("contract_id", ""))
        res = await db.execute(select(Contract).where(Contract.id == cid))
        c = res.scalar_one_or_none()
        if not c:
            raise ValueError(f"Contract '{cid}' not found.")
        return {
            "id": c.id,
            "title": c.title,
            "overall_risk_score": c.overall_risk_score,
            "identified_risks": c.identified_risks,
            "redlines": c.redlines,
            "obligations": c.obligations,
        }

    if name == "query_contract_rag":
        cid = str(args.get("contract_id", ""))
        query = str(args.get("query", ""))
        n_results = int(args.get("n_results", 4))
        res = await db.execute(select(Contract).where(Contract.id == cid))
        c = res.scalar_one_or_none()
        if not c:
            raise ValueError(f"Contract '{cid}' not found.")
        return rag_engine.query_similar(
            contract_id=cid,
            query=query,
            n_results=n_results,
            fallback_sections=list(c.extracted_sections or []),
        )

    if name == "check_playbook_compliance":
        cid = str(args.get("contract_id", ""))
        res = await db.execute(select(Contract).where(Contract.id == cid))
        c = res.scalar_one_or_none()
        if not c:
            raise ValueError(f"Contract '{cid}' not found.")
        await ensure_default_playbooks(db)
        pb_res = await db.execute(select(Playbook).where(Playbook.name == c.playbook_name))
        pb = pb_res.scalar_one_or_none()
        if pb is None:
            pb = (await db.execute(select(Playbook))).scalars().first()
        if pb is None:
            raise ValueError("No playbook configured.")
        return evaluate_playbook_compliance(c, pb)

    if name == "analyze_deal_room_conflicts":
        cids = list(args.get("contract_ids") or [])
        res = await db.execute(select(Contract).where(Contract.id.in_(cids)))
        contracts = list(res.scalars().all())
        return analyze_cross_contract_conflicts(contracts)

    if name == "get_telemetry_summary":
        res = await db.execute(select(AuditLog))
        rows = list(res.scalars().all())
        return {
            "total_records": len(rows),
            "total_tokens": sum(r.total_tokens for r in rows),
            "total_cost_usd": round(sum(r.estimated_cost_usd for r in rows), 8),
        }

    raise ValueError(f"Unknown MCP tool '{name}'.")


@router.get("/tools")
async def list_mcp_tools() -> Dict[str, Any]:
    """REST convenience view of exposed MCP tools."""
    return {"protocol": "mcp-jsonrpc-2.0", "tools": MCP_TOOLS}


@router.post("")
@router.post("/")
async def mcp_jsonrpc_endpoint(request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Handle JSON-RPC 2.0 MCP requests (initialize, tools/list, tools/call)."""
    body = await request.json()
    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params") or {}

    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "contractmind-mcp", "version": "2.0.0"},
                "capabilities": {"tools": {}},
            }
        elif method == "tools/list":
            result = {"tools": MCP_TOOLS}
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments") or {}
            tool_output = await _dispatch_tool(tool_name, tool_args, db)
            result = {
                "content": [{"type": "text", "text": json.dumps(tool_output, default=str)}],
                "isError": False,
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32000, "message": str(exc)},
        }
