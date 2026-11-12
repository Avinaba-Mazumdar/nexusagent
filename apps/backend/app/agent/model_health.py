"""Persist model cooldowns in Neon so they survive restarts and are shared between processes.

The router never waits on the database: it decides from its in-memory cooldowns. A failure is
written in a background task, and ``sync_cooldowns`` pulls in failures recorded by other processes
(for example local dev and production, which share one database) at startup and every few seconds.
"""

import asyncio
import contextlib
import logging
from collections.abc import Iterable
from datetime import UTC, datetime

import asyncpg

from app.agent.model_router import ModelRouter
from app.db.neon import DatabaseUnavailable, neon_db

logger = logging.getLogger("nexusagent.agent.model_health")

SYNC_INTERVAL_SECONDS = 30.0
_DB_ERRORS = (asyncpg.PostgresError, DatabaseUnavailable, OSError, TimeoutError)

_pending_writes: set[asyncio.Task] = set()


def persist_cooldown(scope: str, model: str, reason: str, retry_at: float, error: str) -> None:
    """Record a model failure in the database without blocking the caller."""
    if neon_db.pool is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_write(scope, model, reason, retry_at, error))
    _pending_writes.add(task)
    task.add_done_callback(_pending_writes.discard)


async def _write(scope: str, model: str, reason: str, retry_at: float, error: str) -> None:
    try:
        await neon_db.upsert_model_cooldown(
            scope=scope,
            model=model,
            reason=reason,
            error=error,
            retry_after=datetime.fromtimestamp(retry_at, UTC),
        )
    except _DB_ERRORS as exc:
        logger.warning("Could not save the cooldown for %s/%s: %s", scope, model, exc)


async def sync_cooldowns(routers: Iterable[ModelRouter]) -> None:
    """Load every still-active cooldown from the database into the matching router."""
    if neon_db.pool is None:
        return
    try:
        rows = await neon_db.list_active_model_cooldowns()
    except _DB_ERRORS as exc:
        logger.warning("Could not load model cooldowns: %s", exc)
        return
    by_scope: dict[str, dict[str, float]] = {}
    for row in rows:
        by_scope.setdefault(row["scope"], {})[row["model"]] = row["retry_after"].timestamp()
    for router in routers:
        router.load_cooldowns(by_scope.get(router.scope, {}))


async def sync_cooldowns_forever(
    routers: list[ModelRouter], interval: float = SYNC_INTERVAL_SECONDS
) -> None:
    while True:
        await asyncio.sleep(interval)
        await sync_cooldowns(routers)


async def flush_pending_writes() -> None:
    """Let in-flight cooldown writes finish (used at shutdown)."""
    if _pending_writes:
        with contextlib.suppress(Exception):
            await asyncio.wait(list(_pending_writes), timeout=5)
