"""Sequential 4-Agent StateGraph pipeline orchestrator."""
from __future__ import annotations

from typing import Awaitable, Callable

from app.agents.nodes.auditor_agent import auditor_node
from app.agents.nodes.obligation_agent import obligation_node
from app.agents.nodes.opposing_agent import opposing_node
from app.agents.nodes.redline_agent import redline_node
from app.agents.state import ContractAnalysisState


NodeFn = Callable[[ContractAnalysisState], Awaitable[ContractAnalysisState]]


class StateGraph:
    """Minimal, deterministic async StateGraph supporting sequential node execution."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeFn] = {}
        self._edges: dict[str, str] = {}
        self._entry_point: str | None = None

    def add_node(self, name: str, fn: NodeFn) -> None:
        self._nodes[name] = fn

    def add_edge(self, source: str, target: str) -> None:
        self._edges[source] = target

    def set_entry_point(self, name: str) -> None:
        self._entry_point = name

    def compile(self) -> "CompiledStateGraph":
        return CompiledStateGraph(self._nodes, self._edges, self._entry_point)


class CompiledStateGraph:
    def __init__(
        self,
        nodes: dict[str, NodeFn],
        edges: dict[str, str],
        entry_point: str | None,
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._entry_point = entry_point

    async def ainvoke(self, initial_state: ContractAnalysisState) -> ContractAnalysisState:
        state = dict(initial_state)
        current = self._entry_point
        visited: set[str] = set()
        while current and current != "END":
            if current in visited:
                raise RuntimeError(f"Cycle detected in StateGraph at node '{current}'")
            visited.add(current)
            node_fn = self._nodes[current]
            state = await node_fn(state)  # type: ignore[arg-type]
            current = self._edges.get(current, "END")
        return state  # type: ignore[return-value]


def build_contract_graph() -> CompiledStateGraph:
    """Construct the 4-persona ContractMind StateGraph."""
    graph = StateGraph()
    graph.add_node("auditor", auditor_node)
    graph.add_node("opposing", opposing_node)
    graph.add_node("redline", redline_node)
    graph.add_node("obligation", obligation_node)

    graph.set_entry_point("auditor")
    graph.add_edge("auditor", "opposing")
    graph.add_edge("opposing", "redline")
    graph.add_edge("redline", "obligation")
    graph.add_edge("obligation", "END")
    return graph.compile()


contract_graph = build_contract_graph()
