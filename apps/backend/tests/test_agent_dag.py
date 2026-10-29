from uuid import uuid4

import pytest

from app.agent.graph import AgentGraph, critic_node, planner_node, route_next_node
from app.agent.state import AgentState


@pytest.mark.asyncio
async def test_planner_node_formulates_plan():
    """Verify planner node decomposes query into structured plan steps."""
    state = AgentState(query="Explain Raft consensus commit latency under high write throughput")
    updated_state = await planner_node(state)

    assert "planner" in updated_state.node_history
    assert len(updated_state.plan) >= 2
    assert updated_state.plan[0].tool == "hybrid_rag_search"
    assert updated_state.plan[-1].tool == "synthesizer"
    # No user-supplied or generated code is ever executed by the agent.
    assert "python_sandbox" not in [s.tool for s in updated_state.plan]


@pytest.mark.db
@pytest.mark.asyncio
async def test_agent_graph_invoke_pipeline():
    """Verify complete DAG pipeline executes plan -> retrieve -> critic -> synthesize."""
    graph = AgentGraph()
    state = AgentState(
        query="What is the quorum requirement and commit latency for 5 nodes in Raft?",
        user_id=uuid4(),
    )

    final_state = await graph.invoke(state)

    assert final_state.is_complete is True
    assert final_state.completed_at is not None
    assert "planner" in final_state.node_history
    assert "retriever" in final_state.node_history
    assert "critic" in final_state.node_history
    assert "synthesizer" in final_state.node_history

    # Verify plan completed
    assert all(s.status == "completed" for s in final_state.plan)

    # Verify reflection score computed
    assert final_state.reflection_score > 0.0
    assert final_state.iteration_count >= 1

    # Verify synthesized response contains markdown and Mermaid sequence diagram
    assert "## Architectural Analysis" in final_state.response
    assert "```mermaid" in final_state.response
    assert len(final_state.mermaid_diagrams) >= 1


@pytest.mark.asyncio
async def test_reflection_critic_and_loop_back_bound():
    """Verify that reflection loop terminates strictly within max_iterations ceiling."""
    state = AgentState(
        query="Obscure query with zero matches",
        retrieved_chunks=[],
        max_iterations=3,  # Capped at 3 for testing
    )

    # First critique on empty context -> low score, triggers needs_replan
    state = await critic_node(state)
    assert state.iteration_count == 1
    assert state.needs_replan is True
    assert route_next_node(state) == "planner"

    # Simulate reaching iteration cap
    state.iteration_count = 3
    state.needs_replan = True
    assert route_next_node(state) == "synthesizer"


@pytest.mark.db
@pytest.mark.asyncio
async def test_agent_stream_steps_generator():
    """Verify stream_steps yields intermediate state at each node execution."""
    graph = AgentGraph()
    state = AgentState(query="Synthesize Raft consensus architecture invariants")

    node_sequence: list[str] = []
    async for node_name, step_state in graph.stream_steps(state):
        node_sequence.append(node_name)
        assert step_state.current_node == node_name

    assert "planner" in node_sequence
    assert "retriever" in node_sequence
    assert "critic" in node_sequence
    assert "synthesizer" in node_sequence
