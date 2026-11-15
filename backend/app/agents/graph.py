"""StateGraph Multi-Agent Orchestrator executing Auditor -> Opposing -> Redline -> Obligation sequentially."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.agents.nodes.auditor_agent import auditor_node
from app.agents.nodes.obligation_agent import obligation_node
from app.agents.nodes.opposing_agent import opposing_node
from app.agents.nodes.redline_agent import redline_node
from app.agents.state import ContractGraphState


NodeFn = Callable[[ContractGraphState], Awaitable[ContractGraphState]]
END = "__end__"


class StateGraph:
    """Lightweight async StateGraph orchestrator for sequential multi-agent legal execution."""

    def __init__(self, _state_schema: Any = ContractGraphState) -> None:
        self._nodes: dict[str, NodeFn] = {}
        self._edges: dict[str, str] = {}
        self._entry_point: str | None = None

    def add_node(self, name: str, fn: NodeFn) -> None:
        self._nodes[name] = fn

    def add_edge(self, source: str, target: str) -> None:
        self._edges[source] = target

    def set_entry_point(self, name: str) -> None:
        self._entry_point = name

    def compile(self) -> "CompiledGraph":
        if not self._entry_point or self._entry_point not in self._nodes:
            raise ValueError("StateGraph entry point is missing or invalid.")
        return CompiledGraph(self._nodes, self._edges, self._entry_point)


class CompiledGraph:
    """Executable compiled StateGraph."""

    def __init__(self, nodes: dict[str, NodeFn], edges: dict[str, str], entry_point: str) -> None:
        self._nodes = nodes
        self._edges = edges
        self._entry_point = entry_point

    async def ainvoke(self, initial_state: ContractGraphState) -> ContractGraphState:
        state = dict(initial_state)
        current: str | None = self._entry_point
        visited = 0
        while current and current != END:
            if visited > 32:
                raise RuntimeError("Cycle detected in StateGraph execution.")
            visited += 1
            node_fn = self._nodes[current]
            state = await node_fn(state)  # type: ignore[arg-type]
            current = self._edges.get(current, END)
        return state  # type: ignore[return-value]


def build_contract_graph() -> CompiledGraph:
    """Construct and compile the canonical 4-agent ContractMind StateGraph."""
    workflow = StateGraph(ContractGraphState)
    workflow.add_node("auditor_node", auditor_node)
    workflow.add_node("opposing_node", opposing_node)
    workflow.add_node("redline_node", redline_node)
    workflow.add_node("obligation_node", obligation_node)

    workflow.set_entry_point("auditor_node")
    workflow.add_edge("auditor_node", "opposing_node")
    workflow.add_edge("opposing_node", "redline_node")
    workflow.add_edge("redline_node", "obligation_node")
    workflow.add_edge("obligation_node", END)

    return workflow.compile()


contract_graph = build_contract_graph()
