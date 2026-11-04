from uuid import uuid4

import pytest

from app.agent.graph import (
    REFUSAL,
    AgentGraph,
    answer_node,
    grounding_node,
    prefilter,
    router_node,
)
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


def test_prefilter():
    """Deterministic refusal check for length (> 60 words) or code blocks."""
    short = "What is the fastest model on OpenRouter?"
    assert prefilter(short) is False

    long_q = "word " * 61
    assert prefilter(long_q) is True

    code_q = "Can you fix this:\n```python\nprint('hello')\n```"
    assert prefilter(code_q) is True


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
    assert updated.plan[1].tool == "answer"
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
    assert updated.plan[0].tool == "chat"


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
async def test_agent_graph_invoke_benchmark_pipeline(fake_llm):
    """Complete DAG executes router -> retriever -> grounding -> answer for benchmark."""
    fake_llm(
        ["Claude Opus leads CursorBench with 4.0 score [S1]."],
        structured_route="benchmark",
    )
    state = AgentState(
        query="Compare GPT and Claude on CursorBench",
        user_id=uuid4(),
    )

    final_state = await AgentGraph().invoke(state)

    assert final_state.is_complete is True
    assert final_state.node_history == ["router", "retriever", "grounding", "answer"]
    assert all(s.status == "completed" for s in final_state.plan)
    assert "Claude Opus leads CursorBench" in final_state.response
    assert len(final_state.usage) >= 2  # router + answer


@pytest.mark.asyncio
async def test_agent_graph_invoke_smalltalk_pipeline(fake_llm):
    """Complete DAG executes router -> chat for smalltalk."""
    fake_llm(
        ["Hello! How can I help you today?"],
        structured_route="smalltalk",
        response_metadata={
            "grounding_metadata": {
                "web_search_queries": ["weather Kolkata"],
                "grounding_chunks": [
                    {"web": {"title": "Kolkata Weather", "uri": "https://weather.com/kolkata"}}
                ],
            }
        },
    )
    state = AgentState(
        query="What is the weather in Kolkata?",
        user_id=uuid4(),
    )

    final_state = await AgentGraph().invoke(state)

    assert final_state.is_complete is True
    assert final_state.node_history == ["router", "chat"]
    assert all(s.status == "completed" for s in final_state.plan)
    assert "Hello!" in final_state.response
    assert final_state.web_search_queries == ["weather Kolkata"]
    assert len(final_state.web_sources) == 1
    assert final_state.web_sources[0].url == "https://weather.com/kolkata"


@pytest.mark.asyncio
async def test_answer_node_streams_chunks_to_token_sink(fake_llm):
    """Tokens reach the sink as the model produces them."""
    fake_llm(["alpha ", "beta ", "gamma"])
    seen: list[str] = []

    async def sink(text: str) -> None:
        seen.append(text)

    state = AgentState(query="benchmark latency", intent="benchmark")
    result = await answer_node(state, {"configurable": {"on_token": sink}})

    assert result.response == "alpha beta gamma"
    assert "".join(seen) == "alpha beta gamma"
    assert len(seen) >= 2


@pytest.mark.asyncio
async def test_answer_failure_sets_error_not_response():
    """LLM failure sets state.error and clears state.response instead of returning the exception."""
    from unittest.mock import patch

    state = AgentState(query="OpenRouter throughput", user_id=uuid4())
    with patch("app.agent.graph.settings.GEMINI_API_KEY", ""):
        res = await answer_node(state)
        assert res.error == "Answer generation is not configured on this server."
        assert res.response == ""

    with (
        patch("app.agent.graph.settings.GEMINI_API_KEY", "fake-key"),
        patch(
            "app.agent.graph.ChatGoogleGenerativeAI",
            side_effect=RuntimeError("Google API quota exhausted"),
        ),
    ):
        res2 = await answer_node(AgentState(query="OpenRouter throughput", user_id=uuid4()))
        assert (
            res2.error == "The language model is unavailable right now. Please try again shortly."
        )
        assert res2.response == ""


@pytest.mark.asyncio
async def test_multi_turn_history_included_in_llm_messages(fake_llm):
    """Past chat turns are injected into the LLM messages."""
    chain = fake_llm(["Multi-turn answer"])
    state = AgentState(
        query="What was the second point again?",
        intent="benchmark",
        chat_history=[
            {"role": "user", "content": "Tell me about Artificial Analysis."},
            {"role": "assistant", "content": "1. Quality index. 2. Latency metrics."},
        ],
    )

    res = await answer_node(state)

    assert res.response == "Multi-turn answer"
    contents = [m.content for m in chain.calls[0]]
    assert "Tell me about Artificial Analysis." in contents
    assert "1. Quality index. 2. Latency metrics." in contents
    assert "What was the second point again?" in contents


@pytest.mark.asyncio
async def test_prompt_labels_sources_and_requires_label_citations(fake_llm):
    """Every chunk shown to the model has a label, and the prompt demands label citations."""
    chain = fake_llm(["ok"])
    state = AgentState(
        query="Explain CursorBench", intent="benchmark", retrieved_chunks=[_chunk(), _chunk()]
    )
    await answer_node(state)

    system_prompt = chain.calls[0][0].content
    assert 'label="S1"' in system_prompt and 'label="S2"' in system_prompt
    assert "[S1]" in system_prompt
