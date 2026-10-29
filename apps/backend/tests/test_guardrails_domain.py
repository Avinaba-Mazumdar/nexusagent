import pytest
from app.agent.graph import (
    AgentGraph,
    classify_query_intent,
    is_architectural_query,
    is_out_of_scope,
    planner_node,
)
from app.agent.state import AgentState


def test_classify_query_intent_boundaries():
    """Verify scope guardrail correctly differentiates domain, greetings, and off-topic queries."""
    # Out-of-scope queries
    assert classify_query_intent("weather at 713205") == "out_of_scope"
    assert is_out_of_scope("weather at 713205") is True

    assert classify_query_intent("code me a python script to print hello world") == "out_of_scope"
    assert is_out_of_scope("code me a python script to print hello world") is True

    assert classify_query_intent("what is the recipe for pancakes") == "out_of_scope"
    assert classify_query_intent("who won the football match yesterday") == "out_of_scope"

    # Greetings
    assert classify_query_intent("hi") == "greeting"
    assert classify_query_intent("hello!") == "greeting"
    assert classify_query_intent("who are you") == "greeting"
    assert classify_query_intent("what can you do") == "greeting"

    # Architectural queries
    assert classify_query_intent("Compare Claude Sonnet 3.7 vs GPT-4o on CursorBench") == "architectural"
    assert is_architectural_query("Compare Claude Sonnet 3.7 vs GPT-4o on CursorBench") is True

    assert classify_query_intent("Explain Raft consensus commit latency under high write throughput") == "architectural"
    assert is_architectural_query("Explain Raft consensus commit latency under high write throughput") is True

    assert classify_query_intent("Calculate quorum size and failover time for 5 replicas") == "architectural"


@pytest.mark.asyncio
async def test_planner_intercepts_out_of_scope_query():
    """Verify out-of-scope queries are halted at planner node with deterministic refusal."""
    state = AgentState(query="weather at 713205")
    updated = await planner_node(state)

    assert updated.is_complete is True
    assert "Scope Guardrail: Out-of-Domain Request" in updated.response
    assert "Autonomous Systems Architecture" in updated.response
    assert len(updated.plan) == 1
    assert updated.plan[0].tool == "scope_guardrail"


@pytest.mark.asyncio
async def test_agent_graph_fast_path_refusal():
    """Verify end-to-end graph execution returns refusal without calling external models."""
    graph = AgentGraph()
    state = AgentState(query="code me a python script to print 'hello world'")

    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert "Scope Guardrail: Out-of-Domain Request" in final_state.response
    # Fast-path must not invoke the retriever
    assert "retriever" not in final_state.node_history
