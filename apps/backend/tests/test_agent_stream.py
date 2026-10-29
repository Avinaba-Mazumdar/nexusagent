import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.db
@pytest.mark.asyncio
async def test_agent_sse_streaming_endpoint():
    """Verify POST /api/agent/stream emits full sequence of structured SSE events."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Obtain guest token
        guest_resp = await client.post("/api/auth/guest")
        assert guest_resp.status_code == 200
        token = guest_resp.json()["tokens"]["accessToken"]

        # Call streaming endpoint
        response = await client.post(
            "/api/agent/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "Synthesize quorum requirements and write throughput for Raft consensus",
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        raw_stream = response.text
        assert "event: start" in raw_stream
        assert "event: plan" in raw_stream
        assert "event: node_start" in raw_stream
        assert "event: critic" in raw_stream
        assert "event: done" in raw_stream

        # Parse SSE done event block
        blocks = raw_stream.split("\n\n")
        done_block = next((b for b in blocks if "event: done" in b), None)
        assert done_block is not None

        data_line = next((l for l in done_block.split("\n") if l.startswith("data:")), None)
        assert data_line is not None

        done_data = json.loads(data_line[5:].strip())
        assert done_data["isComplete"] is True
        assert "## Architectural Analysis" in done_data["response"]
        assert len(done_data["plan"]) >= 2
        assert len(done_data["nodeHistory"]) >= 3
        assert done_data["reflectionScore"] > 0.0


@pytest.mark.asyncio
async def test_stream_inaccessible_document_does_not_consume_quota_log_09(monkeypatch):
    """Regression (LOG-09): invalid or inaccessible documentId returns 404 without consuming quota."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.core.auth import get_current_user
    from app.core.rate_limiter import default_rate_limiter
    from app.db.models import User

    default_rate_limiter.reset_for_test()
    now = datetime.now(UTC)
    user_id = uuid4()
    test_user = User(
        id=user_id,
        email="test-log09@example.com",
        name="LOG-09 Test",
        is_guest=True,
        client_ip="127.0.0.1",
        created_at=now,
        last_seen_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: test_user

    mock_get_doc = AsyncMock(return_value=None)
    monkeypatch.setattr("app.db.neon.NeonDatabase.get_document_by_id", mock_get_doc)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/agent/stream",
                json={
                    "query": "Synthesize quorum requirements",
                    "documentId": str(uuid4()),
                },
            )
            assert resp.status_code == 404
            quota_after = await default_rate_limiter.get_quota(user_id=user_id, is_guest=True)
            assert quota_after == 5
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        default_rate_limiter.reset_for_test()
