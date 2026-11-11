from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.graph import (
    REFUSAL,
    AgentGraph,
    citation_report,
    next_node,
    prefilter,
    router_node,
)
from app.agent.llm import AllModelsRateLimited
from app.agent.state import AgentState, Citation
from app.agent.tools import WebSearchResult, web_sources_from
from app.core.audit_log import default_audit_logger
from app.rag.hybrid_search import HybridSearchResult


def _chunk(chunk_id: str = "chunk-1", dense_score: float = 0.9) -> HybridSearchResult:
    return HybridSearchResult(
        id=chunk_id,
        document_id=str(uuid4()),
        chunk_index=0,
        content=f"Artificial Analysis ranks intelligence and latency for {chunk_id}.",
        filename="artificial_analysis.md",
        similarity_score=0.1,
        dense_score=dense_score,
        page=1,
    )


class _FakeSearch:
    def __init__(self, chunks=None):
        self._chunks = chunks or [_chunk("c-1", 0.9), _chunk("c-2", 0.8)]

    async def search(self, **kwargs):
        return list(self._chunks)


# ---------------------------------------------------------------------------
# Unit tests: prefilter
# ---------------------------------------------------------------------------


def test_prefilter():
    """Deterministic refusal check for length (> 60 words) or code blocks."""
    short = "What is the fastest model on OpenRouter?"
    assert prefilter(short) is False

    long_q = "word " * 61
    assert prefilter(long_q) is True

    code_q = "Can you fix this:\n```python\nprint('hello')\n```"
    assert prefilter(code_q) is True


# ---------------------------------------------------------------------------
# Unit tests: citation_report
# ---------------------------------------------------------------------------


def test_citation_report():
    c1 = Citation(label="S1", filename="f1.md", chunk_id="c1", document_id="d1")
    c2 = Citation(label="S2", filename="f2.md", chunk_id="c2", document_id="d2")
    citations = [c1, c2]

    # Valid citation
    invalid, has_valid = citation_report("Claude Opus leads CursorBench [S1].", citations)
    assert invalid == []
    assert has_valid is True

    # Valid and invalid citation
    invalid, has_valid = citation_report("Models are [S1] and [S99].", citations)
    assert invalid == ["S99"]
    assert has_valid is True

    # No citations, but chunks exist
    invalid, has_valid = citation_report("No citations here.", citations)
    assert invalid == []
    assert has_valid is False

    # No citations, 0 chunks
    invalid, has_valid = citation_report("No citations here.", [])
    assert invalid == []
    assert has_valid is False


# ---------------------------------------------------------------------------
# Unit tests: router_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_node_refuse_intent():
    """When intent is already 'refuse' (e.g. from prefilter), router sets REFUSAL response immediately."""
    state = AgentState(query="code snippet", intent="refuse")
    updated = await router_node(state)
    assert updated.is_complete is True
    assert updated.response == REFUSAL
    assert updated.plan[0].tool == "scope_guardrail"


@pytest.mark.asyncio
async def test_router_node_classifies_benchmark(fake_llm):
    """Router classifies benchmark question and sets 2 plan steps."""
    fake_llm(structured_route="benchmark")
    state = AgentState(query="Which model is cheapest on OpenRouter?")
    updated = await router_node(state)

    assert updated.intent == "benchmark"
    assert "router" in updated.node_history
    assert len(updated.plan) == 2
    assert updated.plan[0].tool == "hybrid_rag_search"
    assert updated.plan[1].tool == "agent"
    assert len(updated.usage) == 1
    assert updated.usage[0].step == "router"


@pytest.mark.asyncio
async def test_router_node_classifies_smalltalk(fake_llm):
    """Router classifies smalltalk / greeting and sets 1 plan step."""
    fake_llm(structured_route="smalltalk")
    state = AgentState(query="hello there")
    updated = await router_node(state)

    assert updated.intent == "smalltalk"
    assert "router" in updated.node_history
    assert len(updated.plan) == 1
    assert updated.plan[0].tool == "google_search"


# ---------------------------------------------------------------------------
# Scenario 1: Model answers at once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_1_model_answers_at_once(fake_llm, monkeypatch):
    """Node order router, preload, agent. 1 audit row (preload). S1..Sn citations. 2 model calls."""
    audit_calls = []
    monkeypatch.setattr(
        default_audit_logger,
        "log_tool_audit",
        AsyncMock(side_effect=lambda **kw: audit_calls.append(kw)),
    )

    fake_llm(
        structured_route="benchmark",
        script=[
            {"text": ["Claude Opus leads CursorBench [S1]."]},
        ],
    )

    search_engine = _FakeSearch([_chunk("c-1", 0.9), _chunk("c-2", 0.8)])
    graph = AgentGraph(search_engine=search_engine)

    state = AgentState(query="Compare GPT and Claude on CursorBench", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert final_state.node_history == ["router", "preload", "agent"]
    assert len(audit_calls) == 1
    assert audit_calls[0]["tool_name"] == "hybrid_rag_search"
    assert len(final_state.citations) == 2
    assert final_state.citations[0].label == "S1"
    assert final_state.citations[1].label == "S2"
    assert final_state.uncited is False
    assert final_state.invalid_citations == []
    assert "Claude Opus leads CursorBench [S1]" in final_state.response


# ---------------------------------------------------------------------------
# Scenario 2: Model calls hybrid_rag_search, then answers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_2_rag_tool_call_then_answers(fake_llm, monkeypatch):
    """Order router, preload, agent, tools, agent. 2 audit rows. Chunks deduplicated."""
    audit_calls = []
    monkeypatch.setattr(
        default_audit_logger,
        "log_tool_audit",
        AsyncMock(side_effect=lambda **kw: audit_calls.append(kw)),
    )

    fake_llm(
        structured_route="benchmark",
        script=[
            {
                "tool_calls": [
                    {
                        "name": "hybrid_rag_search",
                        "args": {"query": "latency benchmark"},
                        "id": "call_1",
                    }
                ]
            },
            {"text": ["The answer is [S1] and [S3]."]},
        ],
    )

    call_count = 0

    class MultiSearch:
        async def search(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [_chunk("c-1", 0.9), _chunk("c-2", 0.8)]
            return [_chunk("c-2", 0.8), _chunk("c-3", 0.7)]

    graph = AgentGraph(search_engine=MultiSearch())
    state = AgentState(query="Compare model latency", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert final_state.node_history == ["router", "preload", "agent", "tools", "agent"]
    assert len(audit_calls) == 2
    assert len(final_state.citations) == 3
    assert [c.label for c in final_state.citations] == ["S1", "S2", "S3"]
    assert final_state.uncited is False


# ---------------------------------------------------------------------------
# Scenario 3: Model calls web_search, then answers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_3_web_search_tool_call_then_answers(fake_llm, monkeypatch):
    """Web search adds webSources, untrusted tool output wrapping, and web_search usage."""
    audit_calls = []
    monkeypatch.setattr(
        default_audit_logger,
        "log_tool_audit",
        AsyncMock(side_effect=lambda **kw: audit_calls.append(kw)),
    )

    fake_llm(
        structured_route="benchmark",
        script=[
            {
                "tool_calls": [
                    {
                        "name": "web_search",
                        "args": {"query": "cursor bench current score"},
                        "id": "call_2",
                    }
                ]
            },
            {"text": ["Claude 3.7 score is 70% according to web search."]},
        ],
    )

    from app.agent.state import WebSource

    async def fake_web_search(query: str):
        return WebSearchResult(
            summary="Claude 3.7 score is 70%",
            queries=["cursor bench score"],
            sources=[
                WebSource(title="CursorBench Leaderboard", url="https://cursorbench.com/lead")
            ],
            model="gemini-2.5-flash",
            usage={"input_tokens": 5, "output_tokens": 10, "total_tokens": 15},
            duration_ms=120,
        )

    monkeypatch.setattr("app.agent.graph.run_web_search", fake_web_search)

    graph = AgentGraph(search_engine=_FakeSearch())
    state = AgentState(query="Cursor bench scores", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert len(final_state.web_sources) == 1
    assert final_state.web_sources[0].url == "https://cursorbench.com/lead"

    tool_msgs = [m for m in final_state.agent_messages if getattr(m, "type", "") == "tool"]
    assert len(tool_msgs) == 1
    assert "<untrusted_tool_output" in tool_msgs[0].content

    web_usage = [u for u in final_state.usage if u.step == "web_search"]
    assert len(web_usage) == 1
    assert web_usage[0].model == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Scenario 4: Model asks for tools 3 times
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_4_tool_rounds_bounded_at_two(fake_llm):
    """Tool calling cut off after 2 rounds; 3rd call has no tools bound, forced final answer."""
    fake_llm(
        structured_route="benchmark",
        script=[
            {
                "tool_calls": [
                    {
                        "name": "hybrid_rag_search",
                        "args": {"query": "round 1 query"},
                        "id": "c1",
                    }
                ]
            },
            {
                "tool_calls": [
                    {
                        "name": "hybrid_rag_search",
                        "args": {"query": "round 2 query"},
                        "id": "c2",
                    }
                ]
            },
            {"text": ["Final answer after 2 tool rounds."]},
        ],
    )

    graph = AgentGraph(search_engine=_FakeSearch())
    state = AgentState(query="benchmark search", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert final_state.tool_rounds == 2
    assert final_state.node_history == [
        "router",
        "preload",
        "agent",
        "tools",
        "agent",
        "tools",
        "agent",
    ]
    assert "Final answer after 2 tool rounds." in final_state.response


# ---------------------------------------------------------------------------
# Scenario 5: Model asks for 3 tools in one round
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_5_max_tools_per_round_capped(fake_llm):
    """When model yields 3 tools in one round, only the first 2 are executed."""
    fake_llm(
        structured_route="benchmark",
        script=[
            {
                "tool_calls": [
                    {"name": "hybrid_rag_search", "args": {"query": "q1"}, "id": "c1"},
                    {"name": "hybrid_rag_search", "args": {"query": "q2"}, "id": "c2"},
                    {"name": "hybrid_rag_search", "args": {"query": "q3"}, "id": "c3"},
                ]
            },
            {"text": ["Answer after capped tools."]},
        ],
    )

    graph = AgentGraph(search_engine=_FakeSearch())
    state = AgentState(query="multi-tool test", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert len(final_state.tool_events) == 3  # 1 preload + 2 executed tool calls
    tool_msgs = [m for m in final_state.agent_messages if getattr(m, "type", "") == "tool"]
    assert len(tool_msgs) == 2
    assert [m.tool_call_id for m in tool_msgs] == ["c1", "c2"]


# ---------------------------------------------------------------------------
# Scenario 6: Unknown tool name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_6_unknown_tool_name(fake_llm):
    """Unknown tool name writes error message, does not execute, run still completes."""
    fake_llm(
        structured_route="benchmark",
        script=[
            {"tool_calls": [{"name": "execute_code", "args": {"code": "print(1)"}, "id": "c1"}]},
            {"text": ["Answer after unknown tool rejection."]},
        ],
    )

    graph = AgentGraph(search_engine=_FakeSearch())
    state = AgentState(query="test unknown tool", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    tool_msgs = [m for m in final_state.agent_messages if getattr(m, "type", "") == "tool"]
    assert len(tool_msgs) == 1
    assert "Unknown tool: execute_code" in tool_msgs[0].content
    assert final_state.tool_events[1].error == "unknown tool"


# ---------------------------------------------------------------------------
# Scenario 7: Invalid arguments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_7_invalid_arguments(fake_llm):
    """Invalid arguments write error message, run still completes."""
    fake_llm(
        structured_route="benchmark",
        script=[
            {"tool_calls": [{"name": "hybrid_rag_search", "args": {"query": "x"}, "id": "c1"}]},
            {"text": ["Answer after invalid args."]},
        ],
    )

    graph = AgentGraph(search_engine=_FakeSearch())
    state = AgentState(query="test invalid args", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    tool_msgs = [m for m in final_state.agent_messages if getattr(m, "type", "") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].content == "Invalid arguments."
    assert final_state.tool_events[1].error == "invalid arguments"


# ---------------------------------------------------------------------------
# Scenario 8: run_web_search raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_8_web_search_failure_handled(fake_llm, monkeypatch):
    """When run_web_search raises, tool message is set and run completes."""
    fake_llm(
        structured_route="benchmark",
        script=[
            {"tool_calls": [{"name": "web_search", "args": {"query": "live news"}, "id": "c1"}]},
            {"text": ["Answer despite web search outage."]},
        ],
    )

    async def fail_web_search(query: str):
        raise RuntimeError("network failure")

    monkeypatch.setattr("app.agent.graph.run_web_search", fail_web_search)

    graph = AgentGraph(search_engine=_FakeSearch())
    state = AgentState(query="test web search failure", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    tool_msgs = [m for m in final_state.agent_messages if getattr(m, "type", "") == "tool"]
    assert len(tool_msgs) == 1
    assert "Web search is unavailable right now." in tool_msgs[0].content


# ---------------------------------------------------------------------------
# Scenario 9: Web source with javascript: URL filtered out
# ---------------------------------------------------------------------------


def test_scenario_9_javascript_url_filtered():
    """web_sources_from filters out javascript: URLs."""
    chunk = {
        "response_metadata": {
            "grounding_metadata": {
                "web_search_queries": ["query"],
                "grounding_chunks": [
                    {"web": {"title": "XSS", "uri": "javascript:alert(1)"}},
                    {"web": {"title": "Valid", "uri": "https://example.com/valid"}},
                ],
            }
        }
    }
    queries, sources = web_sources_from(type("Merged", (), chunk)())
    assert queries == ["query"]
    assert len(sources) == 1
    assert sources[0].url == "https://example.com/valid"


# ---------------------------------------------------------------------------
# Scenario 10: Rate limit during agent turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_10_agent_rate_limit(monkeypatch, fake_llm):
    """AllModelsRateLimited during agent turn sets state.error."""
    fake_llm(structured_route="benchmark")

    async def fail_routing(*args, **kwargs):
        raise AllModelsRateLimited(120.0)

    monkeypatch.setattr("app.agent.graph.call_with_routing", fail_routing)

    graph = AgentGraph(search_engine=_FakeSearch())
    state = AgentState(query="benchmark question", user_id=uuid4())
    final_state = await graph.invoke(state)

    assert "reached its usage limit" in final_state.error
    assert final_state.response == ""


# ---------------------------------------------------------------------------
# next_node helper tests
# ---------------------------------------------------------------------------


def test_next_node():
    state = AgentState(query="test")
    state.intent = "benchmark"
    assert next_node("router", state) == "preload"
    assert next_node("preload", state) == "agent"
    assert next_node("tools", state) == "agent"

    state.pending_tool_calls = [{"name": "web_search", "args": {}}]
    assert next_node("agent", state) == "tools"

    state.pending_tool_calls = []
    assert next_node("agent", state) is None
