"""Apply ordered SQL files from migrations/ exactly once, under an advisory lock."""

import logging
from pathlib import Path

from app.db.neon import NeonDatabase

logger = logging.getLogger("nexusagent.db.migrations")

_CANDIDATE_DIR = Path(__file__).resolve().parents[4] / "migrations"
MIGRATIONS_DIR = _CANDIDATE_DIR if _CANDIDATE_DIR.is_dir() else Path("migrations").resolve()
LOCK_KEY = 815_000_001  # arbitrary constant shared by all instances


async def apply_migrations(db: NeonDatabase, directory: Path = MIGRATIONS_DIR) -> list[str]:
    files = sorted(directory.glob("*.sql"))
    applied_now: list[str] = []
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1);", LOCK_KEY)
        try:
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW());"
            )
            done = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations;")}
            for f in files:
                if f.stem in done:
                    continue
                async with conn.transaction():
                    await conn.execute(f.read_text(encoding="utf-8"))
                    await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1);", f.stem)
                applied_now.append(f.stem)
                logger.info("Applied migration %s", f.name)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1);", LOCK_KEY)
    return applied_now

