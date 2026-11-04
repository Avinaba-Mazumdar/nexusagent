import pytest

from app.agent.graph import (
    REFUSAL,
    AgentGraph,
    prefilter,
    route_after_router,
    router_node,
)
from app.agent.state import AgentState


def test_prefilter_boundaries():
    """Verify prefilter correctly catches queries > 60 words or queries with code fences."""
    # Under limit without code
    assert prefilter("What is the fastest model on OpenRouter?") is False
    assert prefilter("weather in Kolkata") is False

    # Over 60 words
    assert prefilter("word " * 61) is True

    # Code fences
    assert prefilter("```python\nprint('hello')\n```") is True
    assert prefilter("help with ```ts const x = 1; ```") is True


@pytest.mark.asyncio
async def test_router_fast_path_refusal_when_intent_preset():
    """Verify preset 'refuse' intent halts at router node with deterministic REFUSAL."""
    state = AgentState(query="code me a python script to print hello world", intent="refuse")
    updated = await router_node(state)

    assert updated.is_complete is True
    assert updated.response == REFUSAL
    assert len(updated.plan) == 1
    assert updated.plan[0].tool == "scope_guardrail"


@pytest.mark.asyncio
async def test_agent_graph_fast_path_refusal():
    """Verify end-to-end graph execution returns refusal without calling external tools when refused."""
    graph = AgentGraph()
    state = AgentState(
        query="code me a python script to print hello world",
        intent="refuse",
    )

    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert final_state.response == REFUSAL
    assert "retriever" not in final_state.node_history
    assert "chat" not in final_state.node_history


def test_route_after_router_logic():
    """Verify route_after_router redirects to done, chat, or retriever."""
    # Refusal or completed
    assert route_after_router(AgentState(query="q", intent="refuse", is_complete=True)) == "done"
    assert route_after_router(AgentState(query="q", intent="refuse")) == "done"
    assert route_after_router(AgentState(query="q", error="some error")) == "done"

    # Smalltalk
    assert route_after_router(AgentState(query="q", intent="smalltalk")) == "chat"

    # Benchmark
    assert route_after_router(AgentState(query="q", intent="benchmark")) == "retriever"
