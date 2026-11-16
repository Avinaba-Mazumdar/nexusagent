"""Shared pytest fixtures for the NexusAgent backend test suite.

The suite is hermetic by default: tests that require a live Neon PostgreSQL instance are
marked ``@pytest.mark.db`` and skipped when ``TEST_DATABASE_URL`` is missing or unreachable,
so ``uv run pytest`` stays green offline and in CI. When a database *is* configured, one
connection pool is opened for the whole session instead of one per test.
"""

import os
from pathlib import Path

from dotenv import dotenv_values

from tests.db_guard import neon_endpoint

_ = os.environ.setdefault("ENVIRONMENT", "test")

_test_url = os.environ.get("TEST_DATABASE_URL", "")
_env_file = Path(__file__).resolve().parents[1] / ".env.local"
_prod_url = (dotenv_values(_env_file).get("NEON_DATABASE_URL") or "") if _env_file.exists() else ""

if "neon.tech" in _test_url:
    if not _prod_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is a Neon URL, but apps/backend/.env.local has no NEON_DATABASE_URL, "
            + "so it cannot be proven that this is not the production database."
        )
    if neon_endpoint(_test_url) == neon_endpoint(_prod_url):
        raise RuntimeError(
            "TEST_DATABASE_URL points at the production Neon database. "
            + "Use the test branch URL instead (roadmap.md H10)."
        )

# db-marked tests only ever touch a dedicated database (e.g. a Neon branch per CI run).
os.environ["NEON_DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")

from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal, NotRequired, Protocol, TypedDict, cast, override
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.messages.tool import ToolCall

from app.config import REPO_ROOT
from app.core.quota_policy import (
    QuotaDecision,
    QuotaLimits,
    UsageCounts,
    after_reserving,
    decide,
)
from app.db.neon import NeonDatabase, neon_db
from app.rag.hybrid_search import (
    DEFAULT_DENSE_WEIGHT,
    DEFAULT_RRF_K,
    DEFAULT_SPARSE_WEIGHT,
    HybridSearchEngine,
    HybridSearchResult,
)

DB_STATE = {"connected": False}


async def _apply_schema(db: NeonDatabase) -> None:
    schema_sql = (REPO_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    pool = db.get_pool()
    async with pool.acquire() as conn:
        _ = await conn.execute(schema_sql)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "db: integration test requiring a reachable Neon PostgreSQL instance",
    )


@pytest.fixture(scope="session", autouse=True)
async def neon_pool() -> AsyncIterator[None]:
    """Open a single Neon connection pool for the session and close it at teardown."""
    DB_STATE["connected"] = await neon_db.connect()
    if DB_STATE["connected"]:
        # A fresh database (for example the CI service container) has no schema yet; applying is idempotent.
        await _apply_schema(neon_db)
    try:
        yield
    finally:
        if DB_STATE["connected"]:
            await neon_db.disconnect()


class UsageRow(TypedDict):
    id: UUID
    user_id: UUID
    device_hash: str | None
    client_ip: str | None
    created_at: datetime


class FakeUsageDb:
    """In-memory stand-in for the chat usage methods of NeonDatabase (same buckets, same policy)."""

    def __init__(self) -> None:
        self.rows: list[UsageRow] = []

    def _counts(
        self, user_id: UUID, device_hash: str | None, client_ip: str | None, now: datetime
    ) -> UsageCounts:
        recent = [r for r in self.rows if now - r["created_at"] < timedelta(hours=24)]
        mine = [
            r
            for r in recent
            if r["user_id"] == user_id
            or (device_hash is not None and r["device_hash"] == device_hash)
        ]
        guests = [r for r in recent if r["device_hash"] is not None]
        network = [r for r in guests if client_ip is not None and r["client_ip"] == client_ip]

        def oldest(rows: list[UsageRow]) -> datetime | None:
            return min((r["created_at"] for r in rows), default=None)

        return UsageCounts(
            user=len(mine),
            user_oldest=oldest(mine),
            network=len(network),
            network_oldest=oldest(network),
            guests=len(guests),
            guests_oldest=oldest(guests),
            total=len(recent),
            total_oldest=oldest(recent),
        )

    async def reserve_chat(
        self,
        *,
        user_id: UUID,
        device_hash: str | None = None,
        client_ip: str | None = None,
        limits: QuotaLimits,
    ) -> tuple[UUID | None, QuotaDecision]:
        now = datetime.now(UTC)
        decision = decide(self._counts(user_id, device_hash, client_ip, now), limits)
        if decision.blocked_by is not None:
            return None, decision
        usage_id = uuid4()
        self.rows.append(
            {
                "id": usage_id,
                "user_id": user_id,
                "device_hash": device_hash,
                "client_ip": client_ip,
                "created_at": now,
            }
        )
        return usage_id, after_reserving(decision, now)

    async def count_chats(
        self,
        *,
        user_id: UUID,
        device_hash: str | None = None,
        client_ip: str | None = None,
        limits: QuotaLimits,
    ) -> QuotaDecision:
        return decide(self._counts(user_id, device_hash, client_ip, datetime.now(UTC)), limits)

    async def release_chat(self, usage_id: UUID) -> None:
        self.rows = [r for r in self.rows if r["id"] != usage_id]


class FakeChunk(AIMessageChunk):
    def __init__(
        self,
        content: str = "",
        usage_metadata: Mapping[str, int] | None = None,
        response_metadata: Mapping[str, object] | None = None,
        tool_calls: list[ToolCall] | None = None,
    ):
        usage: UsageMetadata | None = None
        if usage_metadata:
            usage = {
                "input_tokens": usage_metadata.get("input_tokens", 0),
                "output_tokens": usage_metadata.get("output_tokens", 0),
                "total_tokens": usage_metadata.get("total_tokens", 0),
            }
        super().__init__(
            content=content,
            usage_metadata=usage,
            response_metadata=dict(response_metadata or {}),
            tool_calls=tool_calls or [],
        )


def _check_tool_replies(messages: Sequence[BaseMessage]) -> None:
    """Gemini rejects a request whose function responses do not match its function calls."""
    msgs = list(messages)
    for i, msg in enumerate(msgs):
        if not isinstance(msg, AIMessage) or not msg.tool_calls:
            continue
        replies: set[str] = set()
        for follower in msgs[i + 1 :]:
            if not isinstance(follower, ToolMessage):
                break
            replies.add(follower.tool_call_id)
        if replies != {c.get("id") for c in msg.tool_calls}:
            raise ValueError("function responses do not match function calls")


type SearchResults = Callable[[str, int], Sequence[HybridSearchResult]]


class StaticSearch(HybridSearchEngine):
    """A search engine with canned results; it never touches the database or the embedding API.

    ``results`` is a fixed list, or a function of the query and the call number (1, 2, ...).
    Every query is recorded in ``queries``.
    """

    def __init__(self, results: Sequence[HybridSearchResult] | SearchResults) -> None:
        super().__init__()
        self.results: Sequence[HybridSearchResult] | SearchResults = results
        self.queries: list[str] = []

    @override
    async def search(
        self,
        query: str,
        document_id: UUID | None = None,
        limit: int = 5,
        dense_weight: float = DEFAULT_DENSE_WEIGHT,
        sparse_weight: float = DEFAULT_SPARSE_WEIGHT,
        rrf_k: int = DEFAULT_RRF_K,
        candidate_pool_multiplier: int = 3,
        use_embeddings: bool = True,
    ) -> list[HybridSearchResult]:
        self.queries.append(query)
        if callable(self.results):
            return list(self.results(query, len(self.queries)))
        return list(self.results)


Route = Literal["smalltalk", "benchmark", "refuse"]


class ScriptTurn(TypedDict):
    """One scripted model reply: either tool calls or streamed text pieces."""

    tool_calls: NotRequired[list[ToolCall]]
    text: NotRequired[list[str]]


DEFAULT_USAGE: dict[str, int] = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}


class _StructuredOutput:
    """``with_structured_output(RouteDecision)`` of a FakeChain."""

    def __init__(self, chain: FakeChain, include_raw: bool) -> None:
        self.chain: FakeChain = chain
        self.include_raw: bool = include_raw

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> object:
        self.chain.calls.append(messages)
        from app.agent.graph import RouteDecision

        parsed = RouteDecision(route=self.chain.structured_route)
        raw = FakeChunk(
            content="",
            usage_metadata=self.chain.usage_metadata,
            response_metadata=self.chain.response_metadata,
        )
        if self.include_raw:
            return {"parsed": parsed, "raw": raw}
        return parsed


class FakeChain:
    """Stand-in for the Gemini chain: ``astream`` yields the given text pieces or scripted turns as chunks,
    and supports ``with_structured_output`` and ``bind_tools``."""

    def __init__(
        self,
        pieces: Sequence[str] | None = None,
        *,
        script: list[ScriptTurn] | None = None,
        structured_route: Route = "benchmark",
        usage_metadata: dict[str, int] | None = None,
        response_metadata: dict[str, object] | None = None,
    ):
        self.pieces: list[str] = list(pieces or [])
        self.script: list[ScriptTurn] | None = script
        self.structured_route: Route = structured_route
        self.usage_metadata: dict[str, int] = (
            DEFAULT_USAGE if usage_metadata is None else usage_metadata
        )
        self.response_metadata: dict[str, object] = response_metadata or {}
        self.calls: list[Sequence[BaseMessage]] = []
        self.model: str = "fake-gemini"
        self.tools_bound: list[object] = []

    def bind_tools(self, tools: Sequence[object]) -> FakeChain:
        new_chain = FakeChain(
            self.pieces,
            script=self.script,
            structured_route=self.structured_route,
            usage_metadata=self.usage_metadata,
            response_metadata=self.response_metadata,
        )
        new_chain.calls = self.calls
        new_chain.tools_bound = list(tools)
        return new_chain

    def with_structured_output(
        self, _schema: object, include_raw: bool = False
    ) -> _StructuredOutput:
        return _StructuredOutput(self, include_raw)

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> FakeChunk:
        _check_tool_replies(messages)
        self.calls.append(messages)
        return FakeChunk(
            content="".join(self.pieces),
            usage_metadata=self.usage_metadata,
            response_metadata=self.response_metadata,
        )

    def _final(self, content: str = "") -> FakeChunk:
        return FakeChunk(
            content=content,
            usage_metadata=self.usage_metadata,
            response_metadata=self.response_metadata,
        )

    def _pieces(self, pieces: list[str]) -> Iterator[FakeChunk]:
        """Stream ``pieces``; only the last chunk carries usage and response metadata."""
        if not pieces:
            yield self._final()
            return
        for i, piece in enumerate(pieces):
            last = i == len(pieces) - 1
            yield FakeChunk(
                content=piece,
                usage_metadata=self.usage_metadata if last else None,
                response_metadata=self.response_metadata if last else None,
            )

    async def astream(self, messages: Sequence[BaseMessage]) -> AsyncIterator[FakeChunk]:
        _check_tool_replies(messages)
        self.calls.append(messages)
        if self.script is not None:
            if not self.script:
                yield self._final()
                return
            turn = self.script.pop(0)
            if "tool_calls" in turn:
                yield FakeChunk(
                    content="",
                    usage_metadata=self.usage_metadata,
                    response_metadata=self.response_metadata,
                    tool_calls=turn["tool_calls"],
                )
                return
            if "text" in turn:
                for chunk in self._pieces(turn["text"]):
                    yield chunk
                return

        for chunk in self._pieces(self.pieces):
            yield chunk


class FakeLLM(Protocol):
    """The ``fake_llm`` fixture: route every model call to a new FakeChain."""

    def __call__(
        self,
        pieces: Sequence[str] | None = None,
        *,
        script: list[ScriptTurn] | None = None,
        structured_route: Route = "benchmark",
        usage_metadata: dict[str, int] | None = None,
        response_metadata: dict[str, object] | None = None,
    ) -> FakeChain: ...


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """Return ``use(...) -> FakeChain``: route synthesis to a canned streamed answer."""

    def use(
        pieces: Sequence[str] | None = None,
        *,
        script: list[ScriptTurn] | None = None,
        structured_route: Route = "benchmark",
        usage_metadata: dict[str, int] | None = None,
        response_metadata: dict[str, object] | None = None,
    ) -> FakeChain:
        chain = FakeChain(
            pieces,
            script=script,
            structured_route=structured_route,
            usage_metadata=usage_metadata,
            response_metadata=response_metadata,
        )
        monkeypatch.setattr("app.agent.graph.settings.GEMINI_API_KEY", "test-key")
        monkeypatch.setattr("app.agent.llm.settings.GEMINI_API_KEY", "test-key")

        def fake_get_llm(_api_key: str, _model: str) -> FakeChain:
            return chain

        monkeypatch.setattr("app.agent.llm.get_llm", fake_get_llm)
        return chain

    return use


type AuditCalls = list[dict[str, object]]


@pytest.fixture
def audit_calls(monkeypatch: pytest.MonkeyPatch) -> AuditCalls:
    """Record ``log_tool_audit`` calls (their keyword arguments) instead of writing audit rows."""
    from app.core.audit_log import default_audit_logger

    calls: AuditCalls = []

    async def log_tool_audit(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(default_audit_logger, "log_tool_audit", log_tool_audit)
    return calls


@pytest.fixture
def fake_rate_db(monkeypatch: pytest.MonkeyPatch) -> FakeUsageDb:
    """Back the default chat quota with an in-memory usage store (no Neon needed)."""
    from app.core.rate_limiter import default_chat_quota

    db = FakeUsageDb()
    monkeypatch.setattr(default_chat_quota, "db", db)
    return db


@pytest.fixture(autouse=True)
def reset_rate_limiters() -> Iterator[None]:
    """Reset chat quotas and sliding-window counters between tests."""
    from app.agent.llm import default_model_router, get_llm
    from app.agent.tools import web_search_model_router
    from app.core.rate_limiter import default_chat_quota, mcp_embedding_budget
    from app.main import mcp_global_limiter, mcp_rate_limiter

    get_llm.cache_clear()
    default_model_router.reset()
    web_search_model_router.reset()
    default_chat_quota.reset_for_test()
    mcp_embedding_budget.reset_for_test()
    mcp_rate_limiter.reset_for_test()
    mcp_global_limiter.reset_for_test()
    yield
    get_llm.cache_clear()
    default_model_router.reset()
    web_search_model_router.reset()
    default_chat_quota.reset_for_test()
    mcp_embedding_budget.reset_for_test()
    mcp_rate_limiter.reset_for_test()
    mcp_global_limiter.reset_for_test()


@pytest.fixture(autouse=True)
def require_db(request: pytest.FixtureRequest) -> None:
    """Skip ``db``-marked tests when no live database is available."""
    item = cast(pytest.Item, request.node)
    if item.get_closest_marker("db") and not DB_STATE["connected"]:
        pytest.skip("Requires a reachable Neon PostgreSQL instance (set TEST_DATABASE_URL)")


@pytest.fixture
def web_search_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable Google Search grounding and the web_search tool (off by default)."""
    from app.config import settings

    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)
