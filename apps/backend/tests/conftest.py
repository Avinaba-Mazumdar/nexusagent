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

os.environ.setdefault("ENVIRONMENT", "test")

_test_url = os.environ.get("TEST_DATABASE_URL", "")
_env_file = Path(__file__).resolve().parents[1] / ".env.local"
_prod_url = (dotenv_values(_env_file).get("NEON_DATABASE_URL") or "") if _env_file.exists() else ""

if "neon.tech" in _test_url:
    if not _prod_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is a Neon URL, but apps/backend/.env.local has no NEON_DATABASE_URL, "
            "so it cannot be proven that this is not the production database."
        )
    if neon_endpoint(_test_url) == neon_endpoint(_prod_url):
        raise RuntimeError(
            "TEST_DATABASE_URL points at the production Neon database. "
            "Use the test branch URL instead (roadmap.md H10)."
        )

# db-marked tests only ever touch a dedicated database (e.g. a Neon branch per CI run).
os.environ["NEON_DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessageChunk

from app.config import REPO_ROOT
from app.db.neon import neon_db

DB_STATE = {"connected": False}


async def _apply_schema(neon_db):
    schema_sql = (REPO_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    pool = neon_db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "db: integration test requiring a reachable Neon PostgreSQL instance",
    )


@pytest.fixture(scope="session", autouse=True)
async def neon_pool():
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


class FakeUsageDb:
    """In-memory stand-in for the chat usage methods of NeonDatabase."""

    def __init__(self):
        self.rows: list[dict[str, Any]] = []

    def _matches(
        self,
        row: dict[str, Any],
        user_id: UUID,
        device_hash: str | None,
        machine_hash: str | None,
        client_ip: str | None,
        now: datetime,
    ) -> bool:
        if now - row["created_at"] >= timedelta(hours=24):
            return False
        if row["user_id"] == user_id:
            return True
        if device_hash is not None and row["device_hash"] == device_hash:
            return True
        if machine_hash is not None and row["machine_hash"] == machine_hash:
            return True
        return bool(client_ip is not None and row["client_ip"] == client_ip)

    async def reserve_chat(
        self,
        *,
        user_id: UUID,
        device_hash: str | None = None,
        machine_hash: str | None = None,
        client_ip: str | None = None,
        limit: int,
    ) -> tuple[UUID | None, int, datetime | None]:
        now = datetime.now(UTC)
        matching = [
            r
            for r in self.rows
            if self._matches(r, user_id, device_hash, machine_hash, client_ip, now)
        ]
        used = len(matching)
        oldest = min((r["created_at"] for r in matching), default=None)
        if used >= limit:
            return None, 0, oldest
        usage_id = uuid4()
        self.rows.append(
            {
                "id": usage_id,
                "user_id": user_id,
                "device_hash": device_hash,
                "machine_hash": machine_hash,
                "client_ip": client_ip,
                "created_at": now,
            }
        )
        return usage_id, limit - used - 1, oldest or now

    async def count_chats(
        self,
        *,
        user_id: UUID,
        device_hash: str | None = None,
        machine_hash: str | None = None,
        client_ip: str | None = None,
    ) -> tuple[int, datetime | None]:
        now = datetime.now(UTC)
        matching = [
            r
            for r in self.rows
            if self._matches(r, user_id, device_hash, machine_hash, client_ip, now)
        ]
        oldest = min((r["created_at"] for r in matching), default=None)
        return len(matching), oldest

    async def release_chat(self, usage_id: UUID) -> None:
        self.rows = [r for r in self.rows if r["id"] != usage_id]


class FakeChunk(AIMessageChunk):
    def __init__(
        self,
        content: str = "",
        usage_metadata: dict[str, Any] | None = None,
        response_metadata: dict[str, Any] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ):
        usage = None
        if usage_metadata:
            usage = {
                "input_tokens": usage_metadata.get("input_tokens", 0),
                "output_tokens": usage_metadata.get("output_tokens", 0),
                "total_tokens": usage_metadata.get("total_tokens", 0),
            }
        super().__init__(
            content=content,
            usage_metadata=usage,
            response_metadata=response_metadata or {},
            tool_calls=tool_calls or [],
            **kwargs,
        )


def _check_tool_replies(messages) -> None:
    """Gemini rejects a request whose function responses do not match its function calls."""
    msgs = list(messages or [])
    for i, msg in enumerate(msgs):
        calls = getattr(msg, "tool_calls", None) or []
        if getattr(msg, "type", "") != "ai" or not calls:
            continue
        replies = set()
        for follower in msgs[i + 1 :]:
            if getattr(follower, "type", "") != "tool":
                break
            replies.add(follower.tool_call_id)
        if replies != {c.get("id") for c in calls}:
            raise ValueError("function responses do not match function calls")


class FakeChain:
    """Stand-in for the Gemini chain: ``astream`` yields the given text pieces or scripted turns as chunks,
    and supports ``with_structured_output`` and ``bind_tools``."""

    def __init__(
        self,
        pieces=None,
        *,
        script: list[dict[str, Any]] | None = None,
        structured_route: str = "benchmark",
        usage_metadata: dict[str, Any] | None = None,
        response_metadata: dict[str, Any] | None = None,
    ):
        self.pieces = list(pieces or [])
        self.script = script if script is not None else None
        self.structured_route = structured_route
        self.usage_metadata = (
            {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
            if usage_metadata is None
            else usage_metadata
        )
        self.response_metadata = response_metadata or {}
        self.calls = []
        self.model = "fake-gemini"
        self._tools_bound = []

    def bind_tools(self, tools):
        new_chain = FakeChain(
            self.pieces,
            script=self.script,
            structured_route=self.structured_route,
            usage_metadata=self.usage_metadata,
            response_metadata=self.response_metadata,
        )
        new_chain.calls = self.calls
        new_chain._tools_bound = list(tools)
        return new_chain

    def with_structured_output(self, schema, include_raw=False):
        chain = self

        class StructuredOutputWrapper:
            async def ainvoke(self, messages):
                chain.calls.append(messages)
                from app.agent.graph import RouteDecision

                parsed = RouteDecision(route=chain.structured_route)  # type: ignore
                raw = FakeChunk(
                    content="",
                    usage_metadata=chain.usage_metadata,
                    response_metadata=chain.response_metadata,
                )
                if include_raw:
                    return {"parsed": parsed, "raw": raw}
                return parsed

        return StructuredOutputWrapper()

    async def ainvoke(self, messages):
        _check_tool_replies(messages)
        self.calls.append(messages)
        return FakeChunk(
            content="".join(self.pieces),
            usage_metadata=self.usage_metadata,
            response_metadata=self.response_metadata,
        )

    async def astream(self, messages):
        _check_tool_replies(messages)
        self.calls.append(messages)
        if self.script is not None:
            if not self.script:
                yield FakeChunk(
                    content="",
                    usage_metadata=self.usage_metadata,
                    response_metadata=self.response_metadata,
                )
                return
            turn = self.script.pop(0)
            if "tool_calls" in turn:
                tool_calls = turn["tool_calls"]
                yield FakeChunk(
                    content="",
                    usage_metadata=self.usage_metadata,
                    response_metadata=self.response_metadata,
                    tool_calls=tool_calls,
                )
                return
            elif "text" in turn:
                text_pieces = turn["text"]
                if not text_pieces:
                    yield FakeChunk(
                        content="",
                        usage_metadata=self.usage_metadata,
                        response_metadata=self.response_metadata,
                    )
                    return
                for i, piece in enumerate(text_pieces):
                    chunk_usage = self.usage_metadata if i == len(text_pieces) - 1 else None
                    chunk_resp = self.response_metadata if i == len(text_pieces) - 1 else None
                    yield FakeChunk(
                        content=piece,
                        usage_metadata=chunk_usage,
                        response_metadata=chunk_resp,
                    )
                return

        if not self.pieces:
            yield FakeChunk(
                content="",
                usage_metadata=self.usage_metadata,
                response_metadata=self.response_metadata,
            )
            return

        for i, piece in enumerate(self.pieces):
            chunk_usage = self.usage_metadata if i == len(self.pieces) - 1 else None
            chunk_resp = self.response_metadata if i == len(self.pieces) - 1 else None
            yield FakeChunk(
                content=piece,
                usage_metadata=chunk_usage,
                response_metadata=chunk_resp,
            )


@pytest.fixture
def fake_llm(monkeypatch):
    """Return ``use(...) -> FakeChain``: route synthesis to a canned streamed answer."""

    def use(
        pieces=None,
        *,
        script=None,
        structured_route="benchmark",
        usage_metadata=None,
        response_metadata=None,
    ):
        chain = FakeChain(
            pieces,
            script=script,
            structured_route=structured_route,
            usage_metadata=usage_metadata,
            response_metadata=response_metadata,
        )
        monkeypatch.setattr("app.agent.graph.settings.GEMINI_API_KEY", "test-key")
        monkeypatch.setattr("app.agent.llm.settings.GEMINI_API_KEY", "test-key")
        monkeypatch.setattr("app.agent.graph._get_llm", lambda api_key, model: chain)
        monkeypatch.setattr("app.agent.llm._get_llm", lambda api_key, model: chain)
        return chain

    return use


@pytest.fixture
def fake_rate_db(monkeypatch):
    """Back the default chat quota with an in-memory usage store (no Neon needed)."""
    from app.core.rate_limiter import default_chat_quota

    db = FakeUsageDb()
    monkeypatch.setattr(default_chat_quota, "db", db)
    return db


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset chat quotas and sliding-window counters between tests."""
    from app.agent.llm import _get_llm, default_model_router
    from app.core.rate_limiter import default_chat_quota
    from app.main import mcp_global_limiter, mcp_rate_limiter

    _get_llm.cache_clear()
    default_model_router.reset()
    default_chat_quota.reset_for_test()
    mcp_rate_limiter.reset_for_test()
    mcp_global_limiter.reset_for_test()
    yield
    _get_llm.cache_clear()
    default_model_router.reset()
    default_chat_quota.reset_for_test()
    mcp_rate_limiter.reset_for_test()
    mcp_global_limiter.reset_for_test()


@pytest.fixture(autouse=True)
def require_db(request):
    """Skip ``db``-marked tests when no live database is available."""
    if request.node.get_closest_marker("db") and not DB_STATE["connected"]:
        pytest.skip("Requires a reachable Neon PostgreSQL instance (set TEST_DATABASE_URL)")
