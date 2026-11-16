from ed import rep

G = "app/agent/graph.py"
rep(G, "from typing import Any, Literal\n", "from typing import Literal, cast\n")
rep(
    G,
    """from app.agent.llm import (
    AllModelsRateLimited,
    TokenSink,
    _chunk_text,
    _get_llm,
    _stream_llm,
    call_with_routing,
    default_model_router,
    failure_message,
)""",
    """from app.agent.llm import (
    AllModelsRateLimited,
    ChunkStream,
    MarkForwarded,
    TokenSink,
    call_with_routing,
    chunk_text,
    default_model_router,
    failure_message,
    stream_llm,
    with_tools,
)""",
)
rep(G, "from langchain_core.tools import StructuredTool\n", "from langchain_core.tools import StructuredTool\nfrom langchain_google_genai import ChatGoogleGenerativeAI\n")
rep(
    G,
    '''        ", or web_search for facts the documents cannot contain (for example a model released after "
        "the documents were collected)"''',
    '''        ", or web_search for facts the documents cannot contain (for example a model released after "
        + "the documents were collected)"''',
)
rep(
    G,
    "    return {tok for tok in _CONTENT_TOKEN.findall(text.lower()) if tok not in _STOPWORDS}",
    "    found: list[str] = _CONTENT_TOKEN.findall(text.lower())\n    return {tok for tok in found if tok not in _STOPWORDS}",
)

# router
rep(
    G,
    """    async def _execute_route(llm: Any) -> Any:
        wrapper = llm.with_structured_output(RouteDecision, include_raw=True)
        return await wrapper.ainvoke(messages)

    try:
        raw_result, model = await call_with_routing(
            default_model_router,
            prefer_lite=True,
            run=_execute_route,
        )
        if isinstance(raw_result, dict):
            decision: RouteDecision = raw_result.get("parsed") or RouteDecision(route="benchmark")
            raw_chunk = raw_result.get("raw")
        else:
            decision = raw_result
            raw_chunk = None

        state.intent = decision.route
        usage_meta = getattr(raw_chunk, "usage_metadata", None) or {}
        state.usage.append(
            UsageRecord(
                step="router",
                model=model,
                input_tokens=usage_meta.get("input_tokens", 0) or 0,
                output_tokens=usage_meta.get("output_tokens", 0) or 0,
                total_tokens=usage_meta.get("total_tokens", 0) or 0,
            )
        )""",
    """    async def _execute_route(llm: ChatGoogleGenerativeAI, _mark: MarkForwarded) -> object:
        wrapper = llm.with_structured_output(RouteDecision, include_raw=True)
        return await wrapper.ainvoke(messages)

    try:
        raw_result, model = await call_with_routing(
            default_model_router,
            prefer_lite=True,
            run=_execute_route,
        )
        decision = RouteDecision(route="benchmark")
        raw_chunk: object = None
        if isinstance(raw_result, dict):
            # include_raw=True returns {"parsed": RouteDecision | None, "raw": AIMessage, ...}.
            result = cast(dict[str, object], raw_result)
            parsed = result.get("parsed")
            if isinstance(parsed, RouteDecision):
                decision = parsed
            raw_chunk = result.get("raw")
        elif isinstance(raw_result, RouteDecision):
            decision = raw_result

        state.intent = decision.route
        state.usage.append(usage_record("router", model, raw_chunk))""",
)

# chat
rep(
    G,
    """    async def _execute_chat(llm: Any, mark_forwarded: Callable[[], None]) -> Any:""",
    """    async def _execute_chat(llm: ChatGoogleGenerativeAI, mark_forwarded: MarkForwarded) -> AIMessage:""",
)
rep(
    G,
    """            tool_llm = (
                llm.bind_tools([{"google_search": {}}]) if settings.WEB_SEARCH_ENABLED else llm
            )
            merged = await _stream_llm(tool_llm, messages, tracked)""",
    """            tool_llm: ChunkStream = (
                with_tools(llm, [{"google_search": {}}]) if settings.WEB_SEARCH_ENABLED else llm
            )
            merged = await stream_llm(tool_llm, messages, tracked)""",
)
rep(
    G,
    """                "Model %s failed with google_search tool (%s), retrying without tools",
                getattr(llm, "model", "unknown"),
                exc,
            )
            started = time.perf_counter()
            merged = await _stream_llm(llm, messages, tracked)""",
    """                "Model %s failed with google_search tool (%s), retrying without tools",
                llm.model,
                exc,
            )
            started = time.perf_counter()
            merged = await stream_llm(llm, messages, tracked)""",
)
rep(G, "        state.response = scrub_sensitive_information(_chunk_text(merged))\n        state.model = model\n\n        queries,", "        state.response = scrub_sensitive_information(chunk_text(merged))\n        state.model = model\n\n        queries,")
rep(
    G,
    """        usage_meta = getattr(merged, "usage_metadata", None) or {}
        state.usage.append(
            UsageRecord(
                step="chat",
                model=model,
                input_tokens=usage_meta.get("input_tokens", 0) or 0,
                output_tokens=usage_meta.get("output_tokens", 0) or 0,
                total_tokens=usage_meta.get("total_tokens", 0) or 0,
            )
        )""",
    """        state.usage.append(usage_record("chat", model, merged))""",
)

# agent
rep(
    G,
    """    async def _execute(llm: Any, mark_forwarded: Callable[[], None]) -> Any:""",
    """    async def _execute(llm: ChatGoogleGenerativeAI, mark_forwarded: MarkForwarded) -> AIMessage:""",
)
rep(
    G,
    """        bound_llm = llm.bind_tools(tools) if (allow_tools and tools) else llm
        return await _stream_llm(bound_llm, state.agent_messages, tracked)""",
    """        bound_llm: ChunkStream = with_tools(llm, tools) if (allow_tools and tools) else llm
        return await stream_llm(bound_llm, state.agent_messages, tracked)""",
)
rep(
    G,
    """    usage_meta = getattr(merged, "usage_metadata", None) or {}
    state.usage.append(
        UsageRecord(
            step="agent",
            model=model,
            input_tokens=usage_meta.get("input_tokens", 0) or 0,
            output_tokens=usage_meta.get("output_tokens", 0) or 0,
            total_tokens=usage_meta.get("total_tokens", 0) or 0,
        )
    )

    state.agent_messages.append(merged)
    calls = list(getattr(merged, "tool_calls", None) or [])""",
    """    state.usage.append(usage_record("agent", model, merged))

    state.agent_messages.append(merged)
    calls = list(merged.tool_calls)""",
)
rep(G, "    state.response = scrub_sensitive_information(_chunk_text(merged))\n    state.model = model\n    review_grounding", "    state.response = scrub_sensitive_information(chunk_text(merged))\n    state.model = model\n    review_grounding")

# usage helper, placed before router_node
rep(
    G,
    "async def router_node(",
    '''def usage_record(step: str, model: str, message: object) -> UsageRecord:
    """Token counts from a model reply's ``usage_metadata`` (zero when it has none)."""
    meta = cast(object, getattr(message, "usage_metadata", None))
    counts = cast(dict[str, object], meta) if isinstance(meta, dict) else {}

    def count(key: str) -> int:
        value = counts.get(key)
        return value if isinstance(value, int) else 0

    return UsageRecord(
        step=step,
        model=model,
        input_tokens=count("input_tokens"),
        output_tokens=count("output_tokens"),
        total_tokens=count("total_tokens"),
    )


async def router_node(''',
)

# AgentGraph
rep(
    G,
    """        self.search_engine = search_engine or default_hybrid_search_engine
        self.tools = build_tools(self.search_engine)
        self.graph = self._build_graph()""",
    """        self.search_engine: HybridSearchEngine = search_engine or default_hybrid_search_engine
        self.tools: list[StructuredTool] = build_tools(self.search_engine)
        self.graph: CompiledStateGraph[AgentState] = self._build_graph()""",
)
rep(G, "    def _build_graph(self):\n", "    def _build_graph(self) -> CompiledStateGraph[AgentState]:\n")
rep(G, "from langgraph.graph import END, StateGraph\n", "from langgraph.graph import END, CompiledStateGraph, StateGraph\n")
rep(G, '    "_get_llm",\n', "")
print("ok")
