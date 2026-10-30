import pytest

from app.agent.graph import (
    AgentGraph,
    classify_query_intent,
    planner_node,
)
from app.agent.state import AgentState


def test_classify_query_intent_boundaries():
    """Verify scope guardrail correctly differentiates domain, greetings, and off-topic queries."""
    # Out-of-scope queries
    assert classify_query_intent("weather at 713205") == "out_of_scope"
    assert classify_query_intent("code me a python script to print hello world") == "out_of_scope"
    assert classify_query_intent("what is the recipe for pancakes") == "out_of_scope"
    assert classify_query_intent("who won the football match yesterday") == "out_of_scope"

    # Greetings
    assert classify_query_intent("hi") == "greeting"
    assert classify_query_intent("hello!") == "greeting"
    assert classify_query_intent("who are you") == "greeting"
    assert classify_query_intent("what can you do") == "greeting"

    # Architectural queries
    assert (
        classify_query_intent("Compare Claude Sonnet 3.7 vs GPT-4o on CursorBench")
        == "architectural"
    )
    assert (
        classify_query_intent("Explain Raft consensus commit latency under high write throughput")
        == "architectural"
    )
    assert (
        classify_query_intent("Calculate quorum size and failover time for 5 replicas")
        == "architectural"
    )


@pytest.mark.parametrize(
    "query",
    [
        "best pasta recipe",
        "average storage price of a fridge",
        "what is the last movie",
    ],
)
def test_scope_guardrail_out_of_scope_parametrized(query: str):
    """Verify out-of-scope queries with sub-word false-positive traps are rejected (L-05)."""
    assert classify_query_intent(query) == "out_of_scope"


@pytest.mark.parametrize(
    "query",
    [
        "Raft consensus quorum",
        "compare LLM benchmarks",
        "vector databases",
        "RAG pipeline design",
    ],
)
def test_scope_guardrail_architectural_parametrized(query: str):
    """Verify architectural queries match word boundary regex (L-05)."""
    assert classify_query_intent(query) == "architectural"


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


def test_follow_ups_in_a_conversation_are_not_refused_r2_log_02():
    assert classify_query_intent("explain that in more detail") == "out_of_scope"
    assert classify_query_intent("explain that in more detail", has_history=True) == "architectural"
    assert classify_query_intent("why?", has_history=True) == "architectural"
    # A long off-topic message is still refused, even mid-conversation.
    long_offtopic = "tell me " + "all about the history of pancakes " * 10
    assert classify_query_intent(long_offtopic, has_history=True) == "out_of_scope"


def test_more_architecture_vocabulary_is_in_scope_r2_log_02():
    for query in (
        "How scalable is leader election in Raft?",
        "B-tree vs LSM trade-offs",
        "Postgres vs MySQL isolation levels",
        "What makes an API idempotent?",
        "Kubernetes rate limiting and throttling",
    ):
        assert classify_query_intent(query) == "architectural", query
    assert classify_query_intent("best pasta recipe") == "out_of_scope"
