"""Model Context Protocol (MCP) HTTP/JSON-RPC 2.0 gateway exposing ContractMind legal tools."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.contract import Contract, Playbook
from app.services.calendar_service import generate_obligations_ics
from app.services.cross_contract_service import analyze_deal_room_conflicts
from app.services.orchestrator import run_contract_analysis
from app.services.playbook_engine import evaluate_playbook_compliance
from app.services.rag_engine import rag_engine

router = APIRouter(prefix="/mcp", tags=["mcp"])


MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "analyze_contract",
        "description": "Run the 4-agent ContractMind StateGraph pipeline on a stored contract ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"contract_id": {"type": "string"}},
            "required": ["contract_id"],
        },
    },
    {
        "name": "query_contract_rag",
        "description": "Query contextual RAG passages from a specific ingested contract.",
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
        "name": "query_legal_precedents",
        "description": "Search the 2,000-clause SEC EDGAR / LexGLUE LEDGAR legal knowledge base.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "n_results": {"type": "integer", "default": 2},
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_playbook_compliance",
        "description": "Evaluate a contract against its assigned corporate Playbook rules.",
        "inputSchema": {
            "type": "object",
            "properties": {"contract_id": {"type": "string"}},
            "required": ["contract_id"],
        },
    },
    {
        "name": "detect_deal_room_conflicts",
        "description": "Analyze 2+ contracts in a Deal Room for cross-contract contradictions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["contract_ids"],
        },
    },
    {
        "name": "export_obligations_ics",
        "description": "Generate RFC 5545 iCalendar (.ics) events for a contract's obligations.",
        "inputSchema": {
            "type": "object",
            "properties": {"contract_id": {"type": "string"}},
            "required": ["contract_id"],
        },
    },
]


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    method: str
    params: dict[str, Any] | None = None


@router.get("/tools")
async def list_mcp_tools() -> dict[str, Any]:
    """Convenience GET endpoint listing available MCP tools."""
    return {"server": "ContractMind MCP v2.0", "tools": MCP_TOOLS}


@router.post("")
@router.post("/")
async def mcp_jsonrpc_endpoint(
    req: JSONRPCRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Handle Model Context Protocol JSON-RPC 2.0 requests."""
    params = req.params or {}

    if req.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "contractmind-mcp", "version": "2.0.0"},
                "capabilities": {"tools": {}},
            },
        }

    if req.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {"tools": MCP_TOOLS},
        }

    if req.method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            output = await _dispatch_tool(tool_name, args, db)
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "result": {
                    "content": [{"type": "text", "text": str(output)}]
                    if isinstance(output, str)
                    else [{"type": "json", "json": output}],
                    "data": output,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32000, "message": str(exc)},
            }

    return {
        "jsonrpc": "2.0",
        "id": req.id,
        "error": {"code": -32601, "message": f"Method '{req.method}' not found"},
    }


async def _dispatch_tool(
    tool_name: str, args: dict[str, Any], db: AsyncSession
) -> Any:
    if tool_name == "query_legal_precedents":
        return rag_engine.query_knowledge_base(
            query=str(args.get("query", "")),
            n_results=int(args.get("n_results", 2)),
        )

    if tool_name == "query_contract_rag":
        return rag_engine.query_similar(
            contract_id=str(args.get("contract_id", "")),
            query=str(args.get("query", "")),
            n_results=int(args.get("n_results", 4)),
        )

    if tool_name == "analyze_contract":
        cid = str(args.get("contract_id", ""))
        res = await db.execute(select(Contract).where(Contract.id == cid))
        contract = res.scalars().first()
        if not contract:
            raise ValueError(f"Contract '{cid}' not found")
        updated = await run_contract_analysis(db, contract)
        return {
            "contract_id": updated.id,
            "overall_risk_score": updated.overall_risk_score,
            "risk_summary": updated.risk_summary,
            "redline_count": len(updated.redlines or []),
        }

    if tool_name == "check_playbook_compliance":
        cid = str(args.get("contract_id", ""))
        res = await db.execute(select(Contract).where(Contract.id == cid))
        contract = res.scalars().first()
        if not contract:
            raise ValueError(f"Contract '{cid}' not found")
        pb_res = await db.execute(
            select(Playbook).where(Playbook.name == contract.playbook_name)
        )
        pb = pb_res.scalars().first()
        return evaluate_playbook_compliance(contract, pb)

    if tool_name == "detect_deal_room_conflicts":
        cids = list(args.get("contract_ids") or [])
        res = await db.execute(select(Contract).where(Contract.id.in_(cids)))
        contracts = list(res.scalars().all())
        if len(contracts) < 2:
            raise ValueError("Provide at least 2 valid contract IDs")
        return analyze_deal_room_conflicts(contracts)

    if tool_name == "export_obligations_ics":
        cid = str(args.get("contract_id", ""))
        res = await db.execute(select(Contract).where(Contract.id == cid))
        contract = res.scalars().first()
        if not contract:
            raise ValueError(f"Contract '{cid}' not found")
        return generate_obligations_ics(contract)

    raise ValueError(f"Unknown MCP tool '{tool_name}'")
