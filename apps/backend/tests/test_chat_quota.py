"""Integration tests for rolling 24-hour chat quotas against Neon PostgreSQL."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import settings
from app.core.rate_limiter import BLOCKED_DETAIL, default_chat_quota
from app.db.models import User
from app.db.neon import neon_db


def _network() -> str:
    """A client network no other run has used, so reruns against one database stay independent."""
    return f"2001:db8:{uuid4().hex[:4]}:{uuid4().hex[:4]}::/64"


async def _guest(client_ip: str, machine_hash: str | None = None) -> User:
    return await neon_db.create_user(
        User(
            id=uuid4(),
            email=None,
            name="Guest",
            is_guest=True,
            client_ip=client_ip,
            device_id=f"dev_{uuid4().hex[:12]}",
            machine_hash=machine_hash or f"mach_{uuid4().hex[:12]}",
        )
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_rolling_24h_quota_enforcement():
    pool = neon_db.get_pool()
    client_ip = _network()
    machine_hash = f"mach_{uuid4().hex[:12]}"
    guest1 = await _guest(client_ip, machine_hash)

    # 1. A guest makes 5 chats and the 6th returns 429 with Retry-After > 0
    for i in range(5):
        usage_id, remaining = await default_chat_quota.reserve(guest1, client_ip)
        assert usage_id is not None
        assert remaining == (4 - i)

    with pytest.raises(HTTPException) as exc_info:
        await default_chat_quota.reserve(guest1, client_ip)
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers is not None
    assert int(exc_info.value.headers.get("Retry-After", 0)) > 0
    assert exc_info.value.detail == BLOCKED_DETAIL["user"]

    # 2. The fingerprint is not a quota key: a new guest with the same one is not blocked
    other_network = _network()
    same_machine = await _guest(other_network, machine_hash)
    usage_id, remaining = await default_chat_quota.reserve(same_machine, other_network)
    assert usage_id is not None
    assert remaining == 4

    # 3. Guests on one network share the network bucket, not one guest's bucket
    per_network = settings.GUEST_QUOTA_PER_NETWORK
    per_guest = settings.GUEST_QUOTA_DEFAULT
    used = per_guest
    while used < per_network:
        neighbour = await _guest(client_ip)
        for _ in range(min(per_guest, per_network - used)):
            usage_id, _remaining = await default_chat_quota.reserve(neighbour, client_ip)
            assert usage_id is not None
            used += 1

    late_neighbour = await _guest(client_ip)
    with pytest.raises(HTTPException) as exc_info:
        await default_chat_quota.reserve(late_neighbour, client_ip)
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == BLOCKED_DETAIL["network"]

    # 4. A Google user gets 25 and is not affected by guest rows sharing their network
    google_user = await neon_db.upsert_google_user(
        google_sub=f"sub_{uuid4().hex[:12]}",
        email=f"user_{uuid4().hex[:8]}@example.com",
        name="Google User",
        client_ip=client_ip,
    )
    for i in range(25):
        g_usage_id, g_remaining = await default_chat_quota.reserve(google_user, client_ip)
        assert g_usage_id is not None
        assert g_remaining == (24 - i)

    with pytest.raises(HTTPException) as exc_info:
        await default_chat_quota.reserve(google_user, client_ip)
    assert exc_info.value.status_code == 429

    # 5. Once a guest's chats are over 24 hours old they count for nothing
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE chat_usage
            SET created_at = NOW() - INTERVAL '24 hours 1 second'
            WHERE user_id = $1;
            """,
            guest1.id,
        )

    allowed_usage_id, allowed_remaining = await default_chat_quota.reserve(guest1, client_ip)
    assert allowed_usage_id is not None
    assert allowed_remaining == 4

    # 6. release_chat gives the chat back
    await default_chat_quota.refund(allowed_usage_id)
    rem, _ = await default_chat_quota.status(guest1, client_ip)
    assert rem == 5


@pytest.mark.db
@pytest.mark.asyncio
async def test_service_wide_guest_ceiling(monkeypatch):
    """With the guest ceiling at the current guest total, the next guest chat is refused."""
    pool = neon_db.get_pool()
    async with pool.acquire() as conn:
        guests_today = await conn.fetchval(
            "SELECT COUNT(*) FROM chat_usage "
            "WHERE created_at > NOW() - INTERVAL '24 hours' AND device_hash IS NOT NULL;"
        )
    monkeypatch.setattr(settings, "GUEST_CHATS_PER_DAY", guests_today + 1)

    client_ip = _network()
    first = await _guest(client_ip)
    usage_id, _remaining = await default_chat_quota.reserve(first, client_ip)
    assert usage_id is not None

    elsewhere = _network()
    second = await _guest(elsewhere)
    with pytest.raises(HTTPException) as exc_info:
        await default_chat_quota.reserve(second, elsewhere)
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == BLOCKED_DETAIL["guests"]
