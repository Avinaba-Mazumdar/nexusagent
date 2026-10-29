from uuid import uuid4

import pytest

from app.agent.graph import AgentGraph, critic_node, planner_node, synthesizer_node
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
async def test_critic_visits_exactly_once_no_loop_back():
    """Verify that critic runs once without looping back even with zero retrieved chunks (L-08, D-5)."""
    state = AgentState(
        query="Obscure query with zero matches",
        retrieved_chunks=[],
    )

    state = await critic_node(state)
    assert state.iteration_count == 1
    assert state.needs_replan is False
    assert state.is_grounded is False
    assert "Weak grounding" in state.reflection_feedback
    assert state.node_history.count("critic") == 1


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


@pytest.mark.asyncio
async def test_synthesizer_synthesis_failure_sets_error_not_response():
    """Verify that LLM failure sets state.error and clears state.response instead of returning exception as answer."""
    from unittest.mock import patch

    from app.agent.graph import synthesizer_node

    state = AgentState(
        query="Explain Raft consensus commit latency under high write throughput",
        user_id=uuid4(),
    )
    with patch("app.agent.graph.settings.GEMINI_API_KEY", ""):
        res = await synthesizer_node(state)
        assert res.error == "Answer generation is not configured on this server."
        assert res.response == ""

    with (
        patch("app.agent.graph.settings.GEMINI_API_KEY", "fake-key"),
        patch(
            "app.agent.graph.ChatGoogleGenerativeAI",
            side_effect=RuntimeError("Google API quota exhausted"),
        ),
    ):
        state2 = AgentState(
            query="Explain Raft consensus commit latency under high write throughput",
            user_id=uuid4(),
        )
        res2 = await synthesizer_node(state2)
        assert (
            res2.error == "The language model is unavailable right now. Please try again shortly."
        )
        assert res2.response == ""


@pytest.mark.asyncio
async def test_multi_turn_history_included_in_llm_messages():
    """Verify synthesizer_node injects past chat history turns into LLM messages (L-06)."""
    from unittest.mock import AsyncMock, MagicMock, patch

    captured_messages = []

    mock_llm = MagicMock()

    async def fake_ainvoke(messages, *args, **kwargs):
        captured_messages.extend(messages)
        res = MagicMock()
        res.content = "Multi-turn synthesized answer"
        return res

    mock_llm.with_fallbacks.return_value.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    mock_llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)

    state = AgentState(
        query="What was the second point again?",
        chat_history=[
            {"role": "user", "content": "Tell me about Raft invariants."},
            {"role": "assistant", "content": "1. Election safety. 2. Leader append-only."},
        ],
    )

    with (
        patch("app.agent.graph.settings.GEMINI_API_KEY", "test-key"),
        patch("app.agent.graph.ChatGoogleGenerativeAI", return_value=mock_llm),
    ):
        res = await synthesizer_node(state)
        assert res.response == "Multi-turn synthesized answer"
        msg_contents = [m.content for m in captured_messages]
        assert "Tell me about Raft invariants." in msg_contents
        assert "1. Election safety. 2. Leader append-only." in msg_contents
        assert "What was the second point again?" in msg_contents
