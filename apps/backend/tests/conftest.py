"""Shared pytest fixtures for the NexusAgent backend test suite.

The suite is hermetic by default: tests that require a live Neon PostgreSQL instance are
marked ``@pytest.mark.db`` and skipped when ``TEST_DATABASE_URL`` is missing or unreachable,
so ``uv run pytest`` stays green offline and in CI. When a database *is* configured, one
connection pool is opened for the whole session instead of one per test.
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
# db-marked tests only ever touch a dedicated database (e.g. a Neon branch per CI run).
os.environ["NEON_DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.db.neon import neon_db

DB_STATE = {"connected": False}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "db: integration test requiring a reachable Neon PostgreSQL instance",
    )


@pytest.fixture(scope="session", autouse=True)
async def neon_pool():
    """Open a single Neon connection pool for the session and close it at teardown."""
    DB_STATE["connected"] = await neon_db.connect()
    try:
        yield
    finally:
        if DB_STATE["connected"]:
            await neon_db.disconnect()


class FakeBucketDb:
    """In-memory stand-in for the rate-limit methods of NeonDatabase (per-user counter)."""

    def __init__(self):
        self.tokens: dict[UUID, int] = {}

    async def consume_rate_limit(self, user_id, default_tokens=5, cost=1):
        left = self.tokens.get(user_id, default_tokens)
        if left < cost:
            return None
        self.tokens[user_id] = left - cost
        return left - cost

    async def get_or_create_rate_limit(self, user_id, default_tokens=5):
        return SimpleNamespace(
            tokens_remaining=self.tokens.setdefault(user_id, default_tokens),
            last_replenished_at=datetime.now(UTC),
        )

    async def refund_rate_limit(self, user_id):
        self.tokens[user_id] = self.tokens.get(user_id, 0) + 1


class FakeChain:
    """Stand-in for the Gemini chain: ``astream`` yields the given text pieces as chunks."""

    def __init__(self, pieces):
        self.pieces = list(pieces)
        self.calls = []

    async def astream(self, messages):
        self.calls.append(messages)
        for piece in self.pieces:
            yield SimpleNamespace(content=piece)


@pytest.fixture
def fake_llm(monkeypatch):
    """Return ``use(pieces) -> FakeChain``: route synthesis to a canned streamed answer."""

    def use(pieces):
        chain = FakeChain(pieces)
        monkeypatch.setattr("app.agent.graph.settings.GEMINI_API_KEY", "test-key")
        monkeypatch.setattr("app.agent.graph._get_llm", lambda api_key, model: chain)
        return chain

    return use


@pytest.fixture
def fake_rate_db(monkeypatch):
    """Back the default rate limiter with an in-memory bucket store (no Neon needed)."""
    from app.core.rate_limiter import default_rate_limiter

    db = FakeBucketDb()
    monkeypatch.setattr(default_rate_limiter, "db", db)
    return db


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset token buckets and sliding-window counters between tests."""
    from app.agent.graph import _get_llm, default_model_router
    from app.core.rate_limiter import default_rate_limiter

    _get_llm.cache_clear()
    default_model_router.reset()
    default_rate_limiter.reset_for_test()
    yield
    _get_llm.cache_clear()
    default_model_router.reset()
    default_rate_limiter.reset_for_test()


@pytest.fixture(autouse=True)
def require_db(request):
    """Skip ``db``-marked tests when no live database is available."""
    if request.node.get_closest_marker("db") and not DB_STATE["connected"]:
        pytest.skip("Requires a reachable Neon PostgreSQL instance (set TEST_DATABASE_URL)")
