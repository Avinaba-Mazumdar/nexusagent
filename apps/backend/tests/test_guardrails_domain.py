from uuid import uuid4

import pytest

from app.agent.graph import REFUSAL, AgentGraph, route_after_router
from app.agent.state import AgentState
from app.rag.hybrid_search import HybridSearchResult


def _chunk(dense_score: float | None = 0.9) -> HybridSearchResult:
    return HybridSearchResult(
        id=str(uuid4()),
        document_id=str(uuid4()),
        chunk_index=0,
        content="Artificial Analysis ranks intelligence and latency.",
        filename="artificial_analysis.md",
        similarity_score=0.1,
        dense_score=dense_score,
        page=1,
    )


@pytest.mark.asyncio
async def test_guardrail_refuses_off_topic_queries(fake_llm):
    """The agent must immediately refuse unrelated non-benchmark queries with REFUSAL."""
    fake_llm(["I can help with coding."])
    graph = AgentGraph()

    off_topic_queries = [
        "How do I cook a good lasagna?",
        "Write a quicksort implementation in Rust",
        "Who won the 2024 presidential election?",
        "Debug this Python memory leak",
        "Explain quantum computing fundamentals",
    ]

    for query in off_topic_queries:
        state = AgentState(query=query, user_id=uuid4(), intent="refuse")
        final_state = await graph.invoke(state)

        assert final_state.is_complete is True
        assert final_state.response == REFUSAL
        assert final_state.node_history == ["router"]
        assert len(final_state.plan) == 1
        assert final_state.plan[0].tool == "scope_guardrail"


@pytest.mark.asyncio
async def test_guardrail_refuses_code_snippets():
    """Queries containing markdown code blocks are refused without invoking the model."""
    graph = AgentGraph()
    state = AgentState(
        query="Can you fix this:\n```python\nprint('hello')\n```",
        user_id=uuid4(),
    )
    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert final_state.response == REFUSAL
    assert "retriever" not in final_state.node_history
    assert "chat" not in final_state.node_history


def test_route_after_router_logic():
    """Verify route_after_router redirects to done, chat, or preload."""
    # Refusal or completed
    assert route_after_router(AgentState(query="q", intent="refuse", is_complete=True)) == "done"
    assert route_after_router(AgentState(query="q", intent="refuse")) == "done"
    assert route_after_router(AgentState(query="q", error="some error")) == "done"

    # Smalltalk
    assert route_after_router(AgentState(query="q", intent="smalltalk")) == "chat"

    # Benchmark
    assert route_after_router(AgentState(query="q", intent="benchmark")) == "preload"
