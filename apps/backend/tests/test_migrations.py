import pytest

from app.db.migrations import MIGRATIONS_DIR, apply_migrations


def test_migrations_directory_exists():
    assert MIGRATIONS_DIR.is_dir(), f"Migrations dir not found: {MIGRATIONS_DIR}"
    files = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
    assert files == [
        "20260901000000_core_schema.sql",
        "20261103000000_document_constraints.sql",
        "20261103000100_constraints_and_cleanup.sql",
    ]


@pytest.mark.db
@pytest.mark.asyncio
async def test_apply_migrations_idempotent():
    from app.db.neon import neon_db

    # The session fixture owns the pool: never connect/disconnect it from a test.
    await apply_migrations(neon_db)
    # Second run with same directory should find all migrations already in schema_migrations
    second = await apply_migrations(neon_db)
    assert second == [], "Second migration application must return empty list"
