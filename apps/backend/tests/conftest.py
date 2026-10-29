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
os.environ["DATABASE_URL"] = ""

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


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset token buckets and sliding-window counters between tests."""
    from app.core.rate_limiter import default_rate_limiter

    default_rate_limiter.reset_for_test()
    yield
    default_rate_limiter.reset_for_test()


@pytest.fixture(autouse=True)
def require_db(request):
    """Skip ``db``-marked tests when no live database is available."""
    if request.node.get_closest_marker("db") and not DB_STATE["connected"]:
        pytest.skip("Requires a reachable Neon PostgreSQL instance (set TEST_DATABASE_URL)")
