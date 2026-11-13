"""Free-tier model routing: a model that hits its quota is skipped until the quota comes back."""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_google_genai.chat_models import GoogleModelNotFoundError, GoogleRateLimitError

from app.agent.graph import answer_node, build_agent_messages, chat_node, default_model_router
from app.agent.model_router import PACIFIC, ModelRouter, rate_limit_cooldown
from app.agent.state import AgentState
from app.agent.tools import web_search_model_router
from app.config import settings


class _GoogleError(Exception):
    """Stand-in for google.genai's ClientError: the parsed error body is in ``details``."""

    def __init__(self, details: dict):
        super().__init__("429 RESOURCE_EXHAUSTED")
        self.details = details


def rate_limited(
    quota_id: str = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier", delay="41s"
):
    body = {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": quota_id}],
                },
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay},
            ],
        }
    }
    try:
        raise _GoogleError(body)
    except _GoogleError as cause:
        try:
            raise GoogleRateLimitError("Error calling model (RESOURCE_EXHAUSTED)") from cause
        except GoogleRateLimitError as exc:
            return exc


def test_hosted_gemma_models_sit_between_lite_and_full_flash_in_both_routers():
    assert settings.GEMMA_MODELS == ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]
    lite = [m for m in settings.GEMINI_MODELS if "lite" in m]
    full = [m for m in settings.GEMINI_MODELS if "lite" not in m]
    assert settings.TEXT_MODELS == [*lite, *settings.GEMMA_MODELS, *full]
    assert default_model_router.models == settings.TEXT_MODELS
    assert web_search_model_router.models == settings.TEXT_MODELS


def test_per_minute_limit_uses_the_advised_retry_delay():
    assert rate_limit_cooldown(rate_limited(delay="41s"), now=0.0) == 41.0


def test_per_day_limit_waits_until_midnight_pacific():
    now = datetime(2026, 10, 30, 22, 0, tzinfo=PACIFIC).timestamp()
    exc = rate_limited(quota_id="GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    assert rate_limit_cooldown(exc, now) == pytest.approx(2 * 3600)


def test_cooling_model_is_skipped_until_its_cooldown_ends():
    clock = SimpleNamespace(t=1000.0)
    router = ModelRouter(["a", "b"], clock=lambda: clock.t)

    router.mark_rate_limited("a", rate_limited(delay="30s"))
    assert router.candidates() == ["b"]
    assert router.next_available_at() == 1030.0

    clock.t = 1031.0
    assert router.candidates() == ["a", "b"]


def test_prefer_lite_sorts_lite_models_first():
    models = [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
    ]
    router = ModelRouter(models)
    assert router.candidates(prefer_lite=False) == models
    assert router.candidates(prefer_lite=True) == [
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-2.5-pro",
    ]


class _Model:
    """Fake chat model: raises ``error`` (optionally after streaming ``pieces``) or streams them."""

    def __init__(self, pieces=(), error: BaseException | None = None):
        self.pieces, self.error, self.calls = list(pieces), error, 0

    def bind_tools(self, tools):
        return self

    async def astream(self, messages):
        self.calls += 1
        for piece in self.pieces:
            yield SimpleNamespace(content=piece, type="ai")
        if self.error:
            raise self.error


@pytest.fixture
def models(monkeypatch):
    """Route synthesis through fake models keyed by name: ``use({"m1": _Model(...), ...})``."""

    def use(fakes: dict[str, _Model]):
        monkeypatch.setattr("app.agent.graph.settings.GEMINI_API_KEY", "test-key")
        monkeypatch.setattr("app.agent.llm.settings.GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(default_model_router, "models", list(fakes))
        monkeypatch.setattr("app.agent.graph._get_llm", lambda api_key, model: fakes[model])
        monkeypatch.setattr("app.agent.llm._get_llm", lambda api_key, model: fakes[model])
        return fakes

    return use


def _state() -> AgentState:
    state = AgentState(query="Explain Raft quorum", user_id=uuid4(), intent="benchmark")
    build_agent_messages(state, "")
    return state


@pytest.mark.asyncio
async def test_rate_limited_model_hands_over_and_stays_skipped(models):
    fakes = models({"m1": _Model(error=rate_limited()), "m2": _Model(["Answer from m2."])})

    first = await answer_node(_state())
    assert (first.response, first.model, first.error) == ("Answer from m2.", "m2", None)

    second = await answer_node(_state())
    assert second.model == "m2"
    assert fakes["m1"].calls == 1  # not retried while it cools down


@pytest.mark.asyncio
async def test_inaccessible_model_is_skipped(models):
    models({"gone": _Model(error=GoogleModelNotFoundError("404")), "ok": _Model(["Fine."])})
    result = await answer_node(_state())
    assert (result.response, result.model) == ("Fine.", "ok")


@pytest.mark.asyncio
async def test_no_switch_after_text_reached_the_client(models):
    fakes = models(
        {"m1": _Model(["Partial "], error=rate_limited()), "m2": _Model(["Never used."])}
    )
    result = await answer_node(_state())
    assert result.model is None
    assert fakes["m2"].calls == 0
    assert result.error


@pytest.mark.asyncio
async def test_all_models_limited_reports_when_to_retry(models):
    models({"m1": _Model(error=rate_limited(delay="60s"))})
    result = await answer_node(_state())
    assert result.error and "about 1 minute" in result.error


@pytest.mark.asyncio
async def test_server_error_model_hands_over_and_stays_skipped(models):
    from google.genai.errors import ServerError

    fakes = models({"m1": _Model(error=ServerError(500, {})), "m2": _Model(["Answer from m2."])})
    first = await answer_node(_state())
    assert (first.response, first.model, first.error) == ("Answer from m2.", "m2", None)

    second = await answer_node(_state())
    assert second.model == "m2"
    assert fakes["m1"].calls == 1


@pytest.mark.asyncio
async def test_timed_out_model_hands_over_and_stays_skipped(models):
    import httpx

    fakes = models(
        {"m1": _Model(error=httpx.ReadTimeout("timed out")), "m2": _Model(["Answer from m2."])}
    )
    first = await answer_node(_state())
    assert (first.response, first.model, first.error) == ("Answer from m2.", "m2", None)

    second = await answer_node(_state())
    assert second.model == "m2"
    assert fakes["m1"].calls == 1


@pytest.mark.asyncio
async def test_no_switch_after_text_reached_the_client_on_server_error(models):
    from google.genai.errors import ServerError

    fakes = models(
        {"m1": _Model(["Partial "], error=ServerError(500, {})), "m2": _Model(["Never used."])}
    )
    result = await answer_node(_state())
    assert result.model is None
    assert fakes["m2"].calls == 0
    assert result.error


@pytest.mark.asyncio
async def test_chat_node_falls_back_when_google_search_rate_limited(models):
    class _ToolFailingModel(_Model):
        def bind_tools(self, tools):
            return _Model(error=rate_limited())

    models({"m1": _ToolFailingModel(pieces=["Fallback answer without tools."])})
    state = AgentState(query="hello", user_id=uuid4(), intent="smalltalk")
    result = await chat_node(state)
    assert result.response == "Fallback answer without tools."
    assert result.error is None


@pytest.mark.asyncio
@pytest.mark.parametrize("make_error", ["timeout", "server"])
async def test_chat_node_moves_on_instead_of_retrying_without_tools(models, make_error):
    import httpx
    from google.genai.errors import ServerError

    error = httpx.ReadTimeout("timed out") if make_error == "timeout" else ServerError(500, {})

    class _HangingWithTools(_Model):
        def bind_tools(self, tools):
            self.tool_model = _Model(error=error)
            return self.tool_model

    fakes = models({"m1": _HangingWithTools(["Should not be used."]), "m2": _Model(["Hi!"])})
    state = AgentState(query="hello", user_id=uuid4(), intent="smalltalk")
    result = await chat_node(state)
    assert (result.response, result.model, result.error) == ("Hi!", "m2", None)
    assert fakes["m1"].tool_model.calls == 1
    assert fakes["m1"].calls == 0  # no same-model retry without tools


def test_timed_out_model_cools_down_longer_than_server_error():
    from app.agent.model_router import OVERLOADED_COOLDOWN_SECONDS, TIMEOUT_COOLDOWN_SECONDS

    clock = SimpleNamespace(t=0.0)
    router = ModelRouter(["slow", "busy"], clock=lambda: clock.t)
    router.mark_timed_out("slow")
    router.mark_overloaded("busy")

    clock.t = OVERLOADED_COOLDOWN_SECONDS + 1
    assert router.candidates() == ["busy"]
    clock.t = TIMEOUT_COOLDOWN_SECONDS + 1
    assert router.candidates() == ["slow", "busy"]


class _SlowModel(_Model):
    """Waits ``delay`` seconds before its first chunk, then streams ``pieces``."""

    def __init__(self, pieces=(), delay: float = 0.0, gap: float = 0.0):
        super().__init__(pieces)
        self.delay, self.gap = delay, gap

    async def astream(self, messages):
        import asyncio

        from langchain_core.messages import AIMessageChunk

        self.calls += 1
        await asyncio.sleep(self.delay)
        for piece in self.pieces:
            yield AIMessageChunk(content=piece)
            await asyncio.sleep(self.gap)


@pytest.mark.asyncio
async def test_model_silent_past_first_token_deadline_is_skipped(models, monkeypatch):
    monkeypatch.setattr("app.agent.llm.settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS", 0.05)
    fakes = models({"slow": _SlowModel(["Too late."], delay=5), "fast": _Model(["Hi!"])})

    state = AgentState(query="hello", user_id=uuid4(), intent="smalltalk")
    result = await chat_node(state)
    assert (result.response, result.model, result.error) == ("Hi!", "fast", None)

    # The stalled model is benched, so the next request goes straight to the fast one.
    # The tool bind and the tool-less retry each miss the deadline, so the slow model is called twice.
    assert default_model_router.candidates() == ["fast"]
    assert fakes["slow"].calls == 2


@pytest.mark.asyncio
async def test_first_token_timeout_is_not_reported_as_a_quota_limit(models, monkeypatch):
    """A slow start is a 30s in-memory skip. It is not a shared outage and not an exhausted quota."""
    monkeypatch.setattr("app.agent.llm.settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS", 0.05)
    default_model_router.reset()
    recorded: list[tuple] = []
    monkeypatch.setattr(default_model_router, "on_cooldown", lambda *args: recorded.append(args))
    models(
        {
            "slow": _SlowModel(["Too late."], delay=5),
            "also": _SlowModel(["Also late."], delay=5),
        }
    )

    result = await chat_node(AgentState(query="hello", user_id=uuid4(), intent="smalltalk"))

    assert result.error is not None
    assert "usage limit" not in result.error
    assert "taking too long" in result.error
    assert recorded == []
    default_model_router.reset()


@pytest.mark.asyncio
async def test_first_token_deadline_does_not_cut_off_a_streaming_answer(models, monkeypatch):
    monkeypatch.setattr("app.agent.llm.settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS", 0.05)
    models({"m1": _SlowModel(["Long ", "answer."], delay=0.01, gap=0.1)})
    result = await answer_node(_state())
    assert (result.response, result.model, result.error) == ("Long answer.", "m1", None)


def test_text_models_try_lite_then_gemma_then_full_flash():
    from app.config import Settings

    s = Settings(
        GEMINI_MODELS=[
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
            "gemini-flash-lite-latest",
        ],
        GEMMA_MODELS=["gemma-4-31b-it", "gemma-4-26b-a4b-it"],
    )
    assert s.TEXT_MODELS == [
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
    ]
