"""Integration tests for rolling 24-hour chat quotas against Neon PostgreSQL."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.rate_limiter import default_chat_quota
from app.db.models import User
from app.db.neon import neon_db


@pytest.mark.db
@pytest.mark.asyncio
async def test_rolling_24h_quota_enforcement():
    pool = neon_db.get_pool()
    client_ip = f"198.51.100.{uuid4().hex[:2]}"
    device_id = f"dev_{uuid4().hex[:12]}"
    machine_hash = f"mach_{uuid4().hex[:12]}"

    # Create guest 1
    guest1 = await neon_db.create_user(
        User(
            id=uuid4(),
            email=None,
            name="Guest One",
            is_guest=True,
            client_ip=client_ip,
            device_id=device_id,
            machine_hash=machine_hash,
        )
    )

    # 1. Guest makes 5 chats and the 6th returns 429 with Retry-After > 0
    usage_ids = []
    for i in range(5):
        usage_id, remaining = await default_chat_quota.reserve(guest1, client_ip)
        assert usage_id is not None
        assert remaining == (4 - i)
        usage_ids.append(usage_id)

    with pytest.raises(HTTPException) as exc_info:
        await default_chat_quota.reserve(guest1, client_ip)
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers is not None
    assert int(exc_info.value.headers.get("Retry-After", 0)) > 0
    assert "Daily chat limit reached" in exc_info.value.detail

    # 2. A NEW guest with the same machine hash is blocked
    new_guest_same_machine = await neon_db.create_user(
        User(
            id=uuid4(),
            email=None,
            name="Guest Two (Same Machine)",
            is_guest=True,
            client_ip="203.0.113.1",
            device_id=f"dev_{uuid4().hex[:12]}",
            machine_hash=machine_hash,
        )
    )
    with pytest.raises(HTTPException) as exc_info:
        await default_chat_quota.reserve(new_guest_same_machine, "203.0.113.1")
    assert exc_info.value.status_code == 429

    # 3. A NEW guest with the same IP is blocked
    new_guest_same_ip = await neon_db.create_user(
        User(
            id=uuid4(),
            email=None,
            name="Guest Three (Same IP)",
            is_guest=True,
            client_ip=client_ip,
            device_id=f"dev_{uuid4().hex[:12]}",
            machine_hash=f"mach_{uuid4().hex[:12]}",
        )
    )
    with pytest.raises(HTTPException) as exc_info:
        await default_chat_quota.reserve(new_guest_same_ip, client_ip)
    assert exc_info.value.status_code == 429

    # 4. A NEW guest with a different device, machine and IP is allowed
    different_ip = f"198.51.101.{uuid4().hex[:2]}"
    new_guest_different = await neon_db.create_user(
        User(
            id=uuid4(),
            email=None,
            name="Guest Four (Different)",
            is_guest=True,
            client_ip=different_ip,
            device_id=f"dev_{uuid4().hex[:12]}",
            machine_hash=f"mach_{uuid4().hex[:12]}",
        )
    )
    diff_usage_id, diff_remaining = await default_chat_quota.reserve(
        new_guest_different, different_ip
    )
    assert diff_usage_id is not None
    assert diff_remaining == 4

    # 5. A Google user gets 25, and is not affected by guest rows sharing their IP
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

    # 26th chat is blocked
    with pytest.raises(HTTPException) as exc_info:
        await default_chat_quota.reserve(google_user, client_ip)
    assert exc_info.value.status_code == 429

    # 6. After UPDATE chat_usage SET created_at = NOW() - INTERVAL '24 hours 1 second', chats are allowed again
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

    # 7. release_chat gives the chat back
    await default_chat_quota.refund(allowed_usage_id)
    rem, _ = await default_chat_quota.status(guest1, client_ip)
    assert rem == 5
