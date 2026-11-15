"""StateGraph pipeline orchestrating Auditor -> Opposing Counsel -> Redline Synthesizer -> Obligation Extractor."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.auditor_agent import auditor_node
from app.agents.nodes.obligation_agent import obligation_node
from app.agents.nodes.opposing_agent import opposing_node
from app.agents.nodes.redline_agent import redline_node
from app.agents.state import ContractAgentState
from app.models.audit import AuditLog
from app.models.contract import Contract

NodeFn = Callable[[ContractAgentState], Awaitable[ContractAgentState]]


class StateGraph:
    """Lightweight async StateGraph supporting sequential edges and streaming node events."""

    def __init__(self) -> None:
        self._nodes: Dict[str, NodeFn] = {}
        self._edges: Dict[str, str] = {}
        self._entry_point: Optional[str] = None

    def add_node(self, name: str, fn: NodeFn) -> "StateGraph":
        self._nodes[name] = fn
        if self._entry_point is None:
            self._entry_point = name
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        self._entry_point = name
        return self

    def add_edge(self, src: str, dst: str) -> "StateGraph":
        self._edges[src] = dst
        return self

    def compile(self) -> "CompiledStateGraph":
        order: List[str] = []
        cursor = self._entry_point
        visited = set()
        while cursor and cursor != "__end__" and cursor not in visited:
            if cursor not in self._nodes:
                break
            order.append(cursor)
            visited.add(cursor)
            cursor = self._edges.get(cursor)
        return CompiledStateGraph(self._nodes, order)


class CompiledStateGraph:
    def __init__(self, nodes: Dict[str, NodeFn], order: List[str]) -> None:
        self._nodes = nodes
        self._order = order

    async def ainvoke(self, initial_state: ContractAgentState) -> ContractAgentState:
        state: ContractAgentState = dict(initial_state)  # type: ignore[assignment]
        for node_name in self._order:
            state = await self._nodes[node_name](state)
        return state

    async def astream(self, initial_state: ContractAgentState) -> AsyncGenerator[Tuple[str, ContractAgentState], None]:
        state: ContractAgentState = dict(initial_state)  # type: ignore[assignment]
        for node_name in self._order:
            state = await self._nodes[node_name](state)
            yield node_name, state


def build_contract_graph() -> CompiledStateGraph:
    graph = StateGraph()
    graph.add_node("auditor_node", auditor_node)
    graph.add_node("opposing_node", opposing_node)
    graph.add_node("redline_node", redline_node)
    graph.add_node("obligation_node", obligation_node)
    graph.set_entry_point("auditor_node")
    graph.add_edge("auditor_node", "opposing_node")
    graph.add_edge("opposing_node", "redline_node")
    graph.add_edge("redline_node", "obligation_node")
    graph.add_edge("obligation_node", "__end__")
    return graph.compile()


contract_graph = build_contract_graph()


async def run_contract_analysis(db: AsyncSession, contract: Contract) -> Contract:
    """Execute the 4-node StateGraph pipeline on a Contract and persist results + telemetry."""
    contract.status = "analyzing"
    contract.error_message = None
    await db.commit()

    initial_state: ContractAgentState = {
        "contract_id": contract.id,
        "title": contract.title,
        "playbook_name": contract.playbook_name,
        "raw_text": contract.raw_text,
        "sections": list(contract.extracted_sections or []),
        "identified_risks": [],
        "debate_transcript": [],
        "redlines": [],
        "obligations": [],
        "overall_risk_score": 0.0,
        "risk_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "audit_events": [],
    }

    try:
        final_state = await contract_graph.ainvoke(initial_state)
        contract.identified_risks = list(final_state.get("identified_risks") or [])
        contract.debate_transcript = list(final_state.get("debate_transcript") or [])
        contract.redlines = list(final_state.get("redlines") or [])
        contract.obligations = list(final_state.get("obligations") or [])
        contract.overall_risk_score = float(final_state.get("overall_risk_score") or 0.0)
        contract.risk_summary = dict(
            final_state.get("risk_summary") or {"critical": 0, "high": 0, "medium": 0, "low": 0}
        )
        contract.status = "completed"

        for evt in final_state.get("audit_events") or []:
            db.add(
                AuditLog(
                    contract_id=contract.id,
                    agent_name=str(evt["agent_name"]),
                    action=str(evt["action"]),
                    model_name=str(evt["model_name"]),
                    prompt_tokens=int(evt["prompt_tokens"]),
                    completion_tokens=int(evt["completion_tokens"]),
                    total_tokens=int(evt["total_tokens"]),
                    latency_ms=float(evt["latency_ms"]),
                    estimated_cost_usd=float(evt["estimated_cost_usd"]),
                )
            )
        await db.commit()
        await db.refresh(contract)
        return contract
    except Exception as exc:
        contract.status = "failed"
        contract.error_message = str(exc)
        await db.commit()
        raise
