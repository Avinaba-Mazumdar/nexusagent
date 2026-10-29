import pytest

from app.db.migrations import MIGRATIONS_DIR, apply_migrations


def test_migrations_directory_exists():
    assert MIGRATIONS_DIR.is_dir(), f"Migrations dir not found: {MIGRATIONS_DIR}"
    files = list(MIGRATIONS_DIR.glob("*.sql"))
    assert len(files) >= 1, "At least core schema migration must exist"


@pytest.mark.db
@pytest.mark.asyncio
async def test_apply_migrations_idempotent():
    from app.db.neon import neon_db

    await neon_db.connect()
    try:
        await apply_migrations(neon_db)
        # Second run with same directory should find all migrations already in schema_migrations
        second = await apply_migrations(neon_db)
        assert second == [], "Second migration application must return empty list"
    finally:
        await neon_db.disconnect()
