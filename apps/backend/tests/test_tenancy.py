"""R2-TST-01: one user's documents and audit rows are invisible to another user."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.audit_log import default_audit_logger
from app.core.auth import create_access_token, session_claims
from app.db.models import User
from app.db.neon import neon_db
from app.main import app


async def _make_user(name: str) -> tuple[User, dict[str, str]]:
    user = await neon_db.create_user(
        User(id=uuid4(), name=name, is_guest=True, device_id=uuid4().hex)
    )
    token, _ = create_access_token(session_claims(user))
    return user, {"Authorization": f"Bearer {token}"}


async def _delete_users(*users: User) -> None:
    async with neon_db.get_pool().acquire() as conn:
        for user in users:
            await conn.execute("DELETE FROM users WHERE id = $1;", user.id)


@pytest.mark.db
@pytest.mark.asyncio
async def test_audit_logs_only_return_the_callers_rows_r2_tst_01():
    user_a, headers_a = await _make_user("Auditor A")
    user_b, headers_b = await _make_user("Auditor B")
    try:
        await default_audit_logger.log_tool_audit(
            tool_name="only_a", input_args={}, output_summary={}, duration_ms=1, user_id=user_a.id
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            a_logs = await client.get("/api/agent/audit-logs", headers=headers_a)
            b_logs = await client.get("/api/agent/audit-logs", headers=headers_b)
        assert "only_a" in [row["tool_name"] for row in a_logs.json()["logs"]]
        assert "only_a" not in [row["tool_name"] for row in b_logs.json()["logs"]]
    finally:
        await _delete_users(user_a, user_b)
