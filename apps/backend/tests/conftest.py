"""Shared pytest fixtures for the NexusAgent backend test suite.

The suite is hermetic by default: tests that require a live Neon PostgreSQL instance are
marked ``@pytest.mark.db`` and skipped when ``NEON_DATABASE_URL`` is missing or unreachable,
so ``uv run pytest`` stays green offline and in CI. When a database *is* configured, one
connection pool is opened for the whole session instead of one per test.
"""

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
def require_db(request):
    """Skip ``db``-marked tests when no live database is available."""
    if request.node.get_closest_marker("db") and not DB_STATE["connected"]:
        pytest.skip("Requires a reachable Neon PostgreSQL instance (set NEON_DATABASE_URL)")
