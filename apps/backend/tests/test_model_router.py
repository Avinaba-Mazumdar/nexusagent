"""Free-tier model routing: a model that hits its quota is skipped until the quota comes back."""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_google_genai.chat_models import GoogleModelNotFoundError, GoogleRateLimitError

from app.agent.graph import answer_node, default_model_router
from app.agent.model_router import PACIFIC, ModelRouter, rate_limit_cooldown
from app.agent.state import AgentState


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

    async def astream(self, messages):
        self.calls += 1
        for piece in self.pieces:
            yield SimpleNamespace(content=piece)
        if self.error:
            raise self.error


@pytest.fixture
def models(monkeypatch):
    """Route synthesis through fake models keyed by name: ``use({"m1": _Model(...), ...})``."""

    def use(fakes: dict[str, _Model]):
        monkeypatch.setattr("app.agent.graph.settings.GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(default_model_router, "models", list(fakes))
        monkeypatch.setattr("app.agent.graph._get_llm", lambda api_key, model: fakes[model])
        return fakes

    return use


def _state() -> AgentState:
    return AgentState(query="Explain Raft quorum", user_id=uuid4(), intent="benchmark")


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
    sent: list[str] = []

    async def on_token(text: str) -> None:
        sent.append(text)

    result = await answer_node(_state(), {"configurable": {"on_token": on_token}})
    assert sent == ["Partial "]
    assert result.error and result.response == ""
    assert fakes["m2"].calls == 0  # one answer never mixes two models


@pytest.mark.asyncio
async def test_all_models_limited_reports_when_to_retry(models):
    models({"m1": _Model(error=rate_limited(delay="120s")), "m2": _Model(error=rate_limited())})
    result = await answer_node(_state())
    assert result.response == ""
    assert result.error is not None
    assert "reached its usage limit" in result.error
    assert "about 1 minute" in result.error


@pytest.mark.asyncio
async def test_server_error_model_hands_over_and_stays_skipped(models, monkeypatch):
    from types import SimpleNamespace

    from langchain_google_genai.chat_models import ServerError

    clock = SimpleNamespace(t=1000.0)
    monkeypatch.setattr(default_model_router, "_clock", lambda: clock.t)

    server_err = ServerError(503, {"error": "model overloaded"})
    models({"m1": _Model(error=server_err), "m2": _Model(["Answer from m2."])})

    first = await answer_node(_state())
    assert (first.response, first.model, first.error) == ("Answer from m2.", "m2", None)
    assert default_model_router.candidates() == ["m2"]

    # Advance clock by 31s: m1 is back
    clock.t = 1031.0
    assert default_model_router.candidates() == ["m1", "m2"]


@pytest.mark.asyncio
async def test_no_switch_after_text_reached_the_client_on_server_error(models):
    from langchain_google_genai.chat_models import ServerError

    server_err = ServerError(500, {"error": "internal error"})
    fakes = models({"m1": _Model(["Partial "], error=server_err), "m2": _Model(["Never used."])})
    sent: list[str] = []

    async def on_token(text: str) -> None:
        sent.append(text)

    result = await answer_node(_state(), {"configurable": {"on_token": on_token}})
    assert sent == ["Partial "]
    assert result.error and result.response == ""
    assert fakes["m2"].calls == 0
