from uuid import uuid4

import pytest

from app.agent.graph import (
    AgentGraph,
    grounding_node,
    planner_node,
    synthesizer_node,
)
from app.agent.state import AgentState
from app.rag.hybrid_search import HybridSearchResult


def _chunk(dense_score: float | None = 0.9) -> HybridSearchResult:
    return HybridSearchResult(
        id=str(uuid4()),
        document_id=str(uuid4()),
        chunk_index=0,
        content="Raft needs a quorum.",
        filename="raft.md",
        similarity_score=0.1,
        dense_score=dense_score,
    )


@pytest.mark.asyncio
async def test_planner_node_formulates_plan():
    """Planner classifies intent once and decomposes the query into plan steps."""
    state = AgentState(query="Explain Raft consensus commit latency under high write throughput")
    updated_state = await planner_node(state)

    assert updated_state.intent == "architectural"
    assert "planner" in updated_state.node_history
    assert len(updated_state.plan) >= 2
    assert updated_state.plan[0].tool == "hybrid_rag_search"
    assert updated_state.plan[-1].tool == "synthesizer"
    assert updated_state.canary_token
    # No user-supplied or generated code is ever executed by the agent.
    assert "python_sandbox" not in [s.tool for s in updated_state.plan]


@pytest.mark.asyncio
async def test_planner_respects_preset_intent():
    state = AgentState(query="Explain Raft consensus", intent="greeting")
    assert (await planner_node(state)).intent == "greeting"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chunks", "expected"),
    [([], "none"), ([_chunk(0.2)], "weak"), ([_chunk(0.9)], "grounded")],
)
async def test_grounding_node_reports_retrieval_quality(chunks, expected):
    """The grounding check is a plain function of retrieved chunks and runs exactly once."""
    state = await grounding_node(AgentState(query="q", retrieved_chunks=chunks))
    assert state.grounding == expected
    assert state.grounding_feedback
    assert state.node_history.count("grounding") == 1


@pytest.mark.db
@pytest.mark.asyncio
async def test_agent_graph_invoke_pipeline(fake_llm):
    """Complete DAG executes plan -> retrieve -> grounding -> synthesize."""
    fake_llm(["## Architectural Analysis: Raft\n", "```mermaid\nflowchart TD\n A-->B\n```"])
    state = AgentState(
        query="What is the quorum requirement and commit latency for 5 nodes in Raft?",
        user_id=uuid4(),
    )

    final_state = await AgentGraph().invoke(state)

    assert final_state.is_complete is True
    assert final_state.node_history == ["planner", "retriever", "grounding", "synthesizer"]
    assert all(s.status == "completed" for s in final_state.plan)
    assert "## Architectural Analysis" in final_state.response
    assert len(final_state.mermaid_diagrams) == 1


@pytest.mark.asyncio
async def test_synthesizer_streams_chunks_to_token_sink(fake_llm):
    """LOG-01: tokens reach the sink as the model produces them, not after the full answer."""
    fake_llm(["alpha ", "beta ", "gamma"])
    seen: list[str] = []

    async def sink(text: str) -> None:
        seen.append(text)

    state = AgentState(query="benchmark latency", intent="architectural")
    result = await synthesizer_node(state, {"configurable": {"on_token": sink}})

    assert result.response == "alpha beta gamma"
    assert "".join(seen) == "alpha beta gamma"
    assert len(seen) >= 2


@pytest.mark.asyncio
async def test_synthesizer_failure_sets_error_not_response():
    """LLM failure sets state.error and clears state.response instead of returning the exception."""
    from unittest.mock import patch

    state = AgentState(query="Explain Raft consensus commit latency", user_id=uuid4())
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
        res2 = await synthesizer_node(AgentState(query="Explain Raft consensus", user_id=uuid4()))
        assert (
            res2.error == "The language model is unavailable right now. Please try again shortly."
        )
        assert res2.response == ""


@pytest.mark.asyncio
async def test_multi_turn_history_included_in_llm_messages(fake_llm):
    """Past chat turns are injected into the LLM messages."""
    chain = fake_llm(["Multi-turn synthesized answer"])
    state = AgentState(
        query="What was the second point again?",
        intent="architectural",
        chat_history=[
            {"role": "user", "content": "Tell me about Raft invariants."},
            {"role": "assistant", "content": "1. Election safety. 2. Leader append-only."},
        ],
    )

    res = await synthesizer_node(state)

    assert res.response == "Multi-turn synthesized answer"
    contents = [m.content for m in chain.calls[0]]
    assert "Tell me about Raft invariants." in contents
    assert "1. Election safety. 2. Leader append-only." in contents
    assert "What was the second point again?" in contents


@pytest.mark.asyncio
async def test_prompt_labels_sources_and_requires_label_citations(fake_llm):
    """LOG-05: every chunk shown to the model has a label, and the prompt demands label citations."""
    chain = fake_llm(["ok"])
    state = AgentState(
        query="Explain Raft quorum", intent="architectural", retrieved_chunks=[_chunk(), _chunk()]
    )
    await synthesizer_node(state)

    system_prompt = chain.calls[0][0].content
    assert 'label="S1"' in system_prompt and 'label="S2"' in system_prompt
    assert "[S1]" in system_prompt
