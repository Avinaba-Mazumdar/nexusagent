"""MCP v2 protocol tests.

All HTTP tests authenticate with a guest Bearer token: the MCP gateway reaches
the production database, so unauthenticated access is rejected by
design (covered offline in test_security_hardening.py).
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_user
from app.core.rate_limiter import default_rate_limiter
from app.db.models import User
from app.main import app
from app.mcp.server import handle_jsonrpc_request
from app.routes.mcp import SESSIONS, McpSession


@asynccontextmanager
async def _auth_client():
    """ASGI client pre-authenticated with a guest Bearer token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        guest = await client.post("/api/auth/guest", json={})
        client.headers["Authorization"] = f"Bearer {guest.json()['tokens']['accessToken']}"
        yield client


@pytest.mark.asyncio
async def test_mcp_notification_returns_202_empty_body():
    """Verify MCP notification (no id) returns HTTP 202 with an empty body (L-23)."""
    now = datetime.now(UTC)
    mock_user = User(
        id=uuid4(),
        email="guest@example.com",
        hashed_password=None,
        name="Guest",
        avatar_url=None,
        is_guest=True,
        client_ip="127.0.0.1",
        device_id="dev-guest",
        created_at=now,
        last_seen_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/mcp/v1",
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
            )
            assert res.status_code == 202
            assert res.text == ""
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.db
@pytest.mark.asyncio
async def test_mcp_initialize_endpoint():
    """Verify MCP initialize handshake returns protocolVersion 2024-11-05 and capabilities."""
    async with _auth_client() as client:
        res = await client.post(
            "/api/mcp/v1",
            json={
                "jsonrpc": "2.0",
                "id": "init-1",
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "init-1"
        assert data["result"]["protocolVersion"] == "2024-11-05"
        assert data["result"]["serverInfo"]["name"] == "nexusagent-mcp"
        assert "tools" in data["result"]["capabilities"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_mcp_tools_list_endpoint():
    """Verify MCP tools/list returns hybrid_rag_search."""
    async with _auth_client() as client:
        res = await client.post(
            "/api/mcp/v1",
            json={
                "jsonrpc": "2.0",
                "id": "list-1",
                "method": "tools/list",
            },
        )
        assert res.status_code == 200
        data = res.json()
        tool_names = [t["name"] for t in data["result"]["tools"]]
        assert "hybrid_rag_search" in tool_names


@pytest.mark.asyncio
async def test_code_execution_is_not_exposed():
    """Regression (audit S-01): no MCP tool or HTTP route executes user-supplied code."""
    tools = await handle_jsonrpc_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert "python_sandbox" not in [t["name"] for t in tools["result"]["tools"]]

    call = await handle_jsonrpc_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "python_sandbox", "arguments": {"code": "print(1)"}},
        }
    )
    assert call["result"]["isError"] is True
    assert "Unknown tool" in call["result"]["content"][0]["text"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/sandbox/run", json={"code": "print(1)"})
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_sql_audit_tool_is_not_exposed():
    """Regression (audit S-02): no MCP tool runs arbitrary SQL."""
    tools = await handle_jsonrpc_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert "mcp_sql_audit" not in [t["name"] for t in tools["result"]["tools"]]
    call = await handle_jsonrpc_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "mcp_sql_audit", "arguments": {"query": "SELECT 1"}},
        }
    )
    assert call["result"]["isError"] is True


@pytest.mark.db
@pytest.mark.asyncio
async def test_mcp_resources_list_and_read():
    """Verify MCP resources/list and resources/read."""
    async with _auth_client() as client:
        # List resources
        list_res = await client.post(
            "/api/mcp/v1",
            json={"jsonrpc": "2.0", "id": "res-1", "method": "resources/list"},
        )
        assert list_res.status_code == 200
        res_list = list_res.json()["result"]["resources"]
        assert len(res_list) >= 2
        first_uri = res_list[0]["uri"]

        # Read resource
        read_res = await client.post(
            "/api/mcp/v1",
            json={
                "jsonrpc": "2.0",
                "id": "res-2",
                "method": "resources/read",
                "params": {"uri": first_uri},
            },
        )
        assert read_res.status_code == 200
        contents = read_res.json()["result"]["contents"]
        assert len(contents) > 0
        assert contents[0]["uri"] == first_uri
        assert len(contents[0]["text"]) > 10


@pytest.mark.asyncio
async def test_mcp_read_unknown_resource_returns_invalid_params():
    """Verify resources/read with unknown URI returns INVALID_PARAMS error (L-15)."""
    now = datetime.now(UTC)
    mock_user = User(
        id=uuid4(),
        email="guest@example.com",
        hashed_password=None,
        name="Guest",
        avatar_url=None,
        is_guest=True,
        client_ip="127.0.0.1",
        device_id="dev-guest",
        created_at=now,
        last_seen_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/mcp/v1",
                json={
                    "jsonrpc": "2.0",
                    "id": "bad-res",
                    "method": "resources/read",
                    "params": {"uri": "benchmark://nope"},
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert data["id"] == "bad-res"
            assert "error" in data
            assert data["error"]["code"] == -32602  # INVALID_PARAMS
            assert data["error"]["message"] == "Unknown resource"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_mcp_sse_handshake_endpoint():
    """GET /api/mcp/sse emits the endpoint event first and frees its session on close."""
    from app.routes.mcp import mcp_sse_endpoint

    class _Request:
        async def is_disconnected(self) -> bool:
            return True

    SESSIONS.clear()
    response = await mcp_sse_endpoint(_Request(), current_user=User(id=uuid4(), name="g"))
    assert "text/event-stream" in response.media_type
    first = await response.body_iterator.__anext__()
    assert "event: endpoint" in first
    assert "/api/mcp/messages?sessionId=" in first
    await response.body_iterator.aclose()
    assert not SESSIONS


@pytest.mark.asyncio
async def test_stdio_jsonrpc_dispatcher():
    """Verify stdio JSON-RPC handler processes requests and errors correctly."""
    # Ping
    ping_res = await handle_jsonrpc_request({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert ping_res["result"] == {}

    # Method not found
    bad_res = await handle_jsonrpc_request({"jsonrpc": "2.0", "id": 2, "method": "unknown/method"})
    assert bad_res["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_mcp_session_owner_isolation():
    """Verify MCP SSE sessions are isolated to their owner (audit S-15)."""
    owner_user_id = uuid4()
    other_user_id = uuid4()

    session_id = f"test-sess-{uuid4().hex[:8]}"
    SESSIONS[session_id] = McpSession(owner_id=owner_user_id, queue=asyncio.Queue())

    now = datetime.now(UTC)
    attacker_user = User(
        id=other_user_id,
        email="attacker@example.com",
        hashed_password=None,
        name="Attacker",
        avatar_url=None,
        is_guest=True,
        client_ip="127.0.0.1",
        device_id="dev-attacker",
        created_at=now,
        last_seen_at=now,
    )

    app.dependency_overrides[get_current_user] = lambda: attacker_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                f"/api/mcp/messages?sessionId={session_id}",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            )
            assert res.status_code == 404
            assert "Session ID not found" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        SESSIONS.pop(session_id, None)


@pytest.mark.asyncio
async def test_mcp_tools_call_guest_quota_enforcement(monkeypatch, fake_rate_db):
    """Verify guest tools/call is rate-limited to 5 calls per hour (SEC-01)."""
    default_rate_limiter.reset_for_test()
    now = datetime.now(UTC)
    guest_user = User(
        id=uuid4(),
        email="guest-sec01@example.com",
        hashed_password=None,
        name="Guest",
        avatar_url=None,
        is_guest=True,
        client_ip="127.0.0.1",
        device_id="dev-sec01",
        created_at=now,
        last_seen_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: guest_user

    embed_mock = AsyncMock(return_value=[0.1] * 768)

    async def fake_search(*args, **kwargs):
        await embed_mock("test")
        return []

    monkeypatch.setattr("app.mcp.registry.default_hybrid_search_engine.search", fake_search)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for i in range(5):
                res = await client.post(
                    "/api/mcp/v1",
                    json={
                        "jsonrpc": "2.0",
                        "id": f"call-{i}",
                        "method": "tools/call",
                        "params": {"name": "hybrid_rag_search", "arguments": {"query": "cost"}},
                    },
                )
                assert res.status_code == 200
                data = res.json()
                assert "result" in data
                assert data.get("error") is None

            # 6th call must be blocked by quota with JSON-RPC -32000 error
            res6 = await client.post(
                "/api/mcp/v1",
                json={
                    "jsonrpc": "2.0",
                    "id": "call-5",
                    "method": "tools/call",
                    "params": {"name": "hybrid_rag_search", "arguments": {"query": "cost"}},
                },
            )
            assert res6.status_code == 200
            data6 = res6.json()
            assert "error" in data6
            assert data6["error"]["code"] == -32000
            assert "Quota exhausted" in data6["error"]["message"]
            assert embed_mock.call_count == 5
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        default_rate_limiter.reset_for_test()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[1, 2], "ping", 7, None])
async def test_stdio_rejects_non_object_payloads(payload):
    """LOG-10: batches and scalars get INVALID_REQUEST instead of crashing the read loop."""
    res = await handle_jsonrpc_request(payload)
    assert res["error"]["code"] == -32600
