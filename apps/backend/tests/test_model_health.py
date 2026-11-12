"""Model cooldowns are written to the database on failure and loaded back into the routers."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent import model_health
from app.agent.model_router import ModelRouter
from app.db.neon import neon_db


class _FakeCooldownDb:
    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}

    async def upsert_model_cooldown(self, *, scope, model, reason, error, retry_after):
        self.rows[(scope, model)] = {
            "scope": scope,
            "model": model,
            "reason": reason,
            "error": error,
            "retry_after": retry_after,
        }

    async def list_active_model_cooldowns(self):
        now = datetime.now(UTC)
        return [r for r in self.rows.values() if r["retry_after"] > now]


@pytest.fixture
def fake_db(monkeypatch):
    db = _FakeCooldownDb()
    monkeypatch.setattr(neon_db, "pool", object())
    monkeypatch.setattr(neon_db, "upsert_model_cooldown", db.upsert_model_cooldown)
    monkeypatch.setattr(neon_db, "list_active_model_cooldowns", db.list_active_model_cooldowns)
    return db


def test_router_reports_each_cooldown_to_the_listener():
    seen = []
    router = ModelRouter(
        ["a"], clock=lambda: 100.0, scope="chat", on_cooldown=lambda *args: seen.append(args)
    )
    router.mark_timed_out("a", TimeoutError("slow"))
    assert seen == [("chat", "a", "timed_out", 400.0, "slow")]


def test_listener_failure_does_not_break_routing():
    def boom(*args):
        raise RuntimeError("db down")

    router = ModelRouter(["a", "b"], scope="chat", on_cooldown=boom)
    router.mark_overloaded("a")
    assert router.candidates() == ["b"]


def test_loaded_cooldown_never_shortens_a_local_one():
    clock = SimpleNamespace(t=0.0)
    router = ModelRouter(["a", "b"], clock=lambda: clock.t)
    router.mark_timed_out("a")  # until 300
    router.load_cooldowns({"a": 50.0, "b": 120.0})
    clock.t = 100.0
    assert router.candidates() == []
    clock.t = 200.0
    assert router.candidates() == ["b"]


@pytest.mark.asyncio
async def test_failure_is_saved_and_loaded_into_a_fresh_router(fake_db):
    writer = ModelRouter(["m1", "m2"], scope="chat", on_cooldown=model_health.persist_cooldown)
    writer.mark_unavailable("m1", RuntimeError("404 not found"))
    await asyncio.sleep(0)  # let the background write run
    await model_health.flush_pending_writes()

    row = fake_db.rows[("chat", "m1")]
    assert row["reason"] == "unavailable" and "404" in row["error"]

    # A restarted process (or another server sharing the database) picks the cooldown up.
    fresh_chat = ModelRouter(["m1", "m2"], scope="chat")
    fresh_search = ModelRouter(["m1", "m2"], scope="web_search")
    await model_health.sync_cooldowns([fresh_chat, fresh_search])
    assert fresh_chat.candidates() == ["m2"]
    assert fresh_search.candidates() == ["m1", "m2"]  # scopes are independent


def test_persist_is_a_no_op_without_a_database(monkeypatch):
    monkeypatch.setattr(neon_db, "pool", None)
    model_health.persist_cooldown("chat", "m1", "overloaded", 0.0, "")  # must not raise


@pytest.mark.db
@pytest.mark.asyncio
async def test_cooldown_round_trip_against_neon():
    model = f"test-model-{uuid4().hex[:8]}"
    later = datetime.now(UTC) + timedelta(minutes=10)
    sooner = datetime.now(UTC) + timedelta(minutes=1)
    try:
        await neon_db.upsert_model_cooldown(
            scope="chat", model=model, reason="timed_out", error="slow", retry_after=later
        )
        # A shorter cooldown recorded afterwards must not cut the existing one short.
        await neon_db.upsert_model_cooldown(
            scope="chat", model=model, reason="overloaded", error="503", retry_after=sooner
        )
        rows = {r["model"]: r for r in await neon_db.list_active_model_cooldowns()}
        assert abs((rows[model]["retry_after"] - later).total_seconds()) < 1
        count = await neon_db.get_pool().fetchval(
            "SELECT failure_count FROM model_cooldowns WHERE scope = 'chat' AND model = $1", model
        )
        assert count == 2
    finally:
        await neon_db.get_pool().execute("DELETE FROM model_cooldowns WHERE model = $1", model)
