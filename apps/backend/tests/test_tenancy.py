"""R2-TST-01: one user's documents and audit rows are invisible to another user."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.audit_log import default_audit_logger
from app.core.auth import create_access_token, session_claims
from app.db.models import Document, DocumentChunk, User
from app.db.neon import neon_db
from app.main import app

SECRET_TEXT = "tenancyprobe quorum notes belonging to user A only"


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
async def test_other_users_documents_are_invisible_r2_tst_01():
    user_a, headers_a = await _make_user("Tenant A")
    user_b, headers_b = await _make_user("Tenant B")
    doc = Document(
        id=uuid4(),
        user_id=user_a.id,
        filename="a-private.md",
        mime_type="text/markdown",
        sha256_hash=uuid4().hex,
        total_chunks=1,
        is_seeded=False,
    )
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, content=SECRET_TEXT)
    try:
        await neon_db.create_document_with_chunks(doc, [chunk])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # The owner can read the chunk and sees the document.
            own = await client.get(f"/api/documents/{doc.id}/chunks/{chunk.id}", headers=headers_a)
            assert own.status_code == 200

            # Another user gets 404 for the chunk and does not see the document in the list.
            foreign = await client.get(
                f"/api/documents/{doc.id}/chunks/{chunk.id}", headers=headers_b
            )
            assert foreign.status_code == 404
            listed = await client.get("/api/documents", headers=headers_b)
            assert doc.filename not in [d["filename"] for d in listed.json()["documents"]]

            # Search scoped to that document, and unscoped lexical search, never leak it.
            scoped = await client.post(
                "/api/rag/search",
                json={"query": "tenancyprobe quorum", "documentId": str(doc.id)},
                headers=headers_b,
            )
            assert scoped.status_code == 404
            unscoped = await client.post(
                "/api/rag/search", json={"query": "tenancyprobe quorum"}, headers=headers_b
            )
            assert unscoped.status_code == 200
            assert all(SECRET_TEXT not in r["content"] for r in unscoped.json()["results"])

            # Another user cannot delete it either.
            deleted = await client.delete(f"/api/documents/{doc.id}", headers=headers_b)
            assert deleted.status_code == 404
        rows = await neon_db.search_chunks_lexical("tenancyprobe quorum", user_id=user_b.id)
        assert rows == []
        own_rows = await neon_db.search_chunks_lexical("tenancyprobe quorum", user_id=user_a.id)
        assert [r["content"] for r in own_rows] == [SECRET_TEXT]
    finally:
        await _delete_users(user_a, user_b)


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
