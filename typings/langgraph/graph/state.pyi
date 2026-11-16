"""Type stub for the part of ``langgraph.graph.state`` that NexusAgent uses.

langgraph is a namespace package (no top-level ``__init__.py``), so type checkers ignore its
``py.typed`` marker and see the library as untyped. This stub declares the builder and compiled
graph API exactly as ``app/agent/graph.py`` calls it.
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Hashable, Mapping
from typing import Literal, Self

from langchain_core.runnables import RunnableConfig

class CompiledStateGraph[StateT]:
    async def ainvoke(self, input: StateT, config: RunnableConfig | None = None) -> object:
        """The final state; a dict of field values for a pydantic state schema."""
        ...
    def astream(
        self,
        input: StateT,
        config: RunnableConfig | None = None,
        *,
        stream_mode: Literal["values", "updates"] = "values",
    ) -> AsyncIterator[dict[str, object]]:
        """With ``stream_mode="updates"``, one ``{node name: state update}`` dict per finished node."""
        ...

class StateGraph[StateT]:
    def __init__(self, state_schema: type[StateT]) -> None: ...
    def add_node(self, node: str, action: Callable[..., Awaitable[StateT]]) -> Self: ...
    def add_edge(self, start_key: str, end_key: str) -> Self: ...
    def set_entry_point(self, key: str) -> Self: ...
    def add_conditional_edges(
        self,
        source: str,
        path: Callable[[StateT], Hashable],
        path_map: Mapping[Hashable, str],
    ) -> Self: ...
    def compile(self) -> CompiledStateGraph[StateT]: ...
