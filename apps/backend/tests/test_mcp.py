"""MCP v2 protocol tests.

All HTTP tests authenticate with a guest Bearer token: the MCP gateway reaches
the production database, so unauthenticated access is rejected by
design (covered offline in test_security_hardening.py).
"""

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.mcp.server import handle_jsonrpc_request


@asynccontextmanager
async def _auth_client():
    """ASGI client pre-authenticated with a guest Bearer token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        guest = await client.post("/api/auth/guest", json={})
        client.headers["Authorization"] = f"Bearer {guest.json()['tokens']['accessToken']}"
        yield client


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


@pytest.mark.db
@pytest.mark.asyncio
async def test_mcp_sse_handshake_endpoint():
    """Verify GET /api/mcp/sse emits the standard endpoint event."""
    async with _auth_client() as client:
        res = await client.get("/api/mcp/sse?once=true")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")
        assert "event: endpoint" in res.text
        assert "/api/mcp/messages?sessionId=" in res.text


@pytest.mark.asyncio
async def test_stdio_jsonrpc_dispatcher():
    """Verify stdio JSON-RPC handler processes requests and errors correctly."""
    # Ping
    ping_res = await handle_jsonrpc_request({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert ping_res["result"] == {}

    # Method not found
    bad_res = await handle_jsonrpc_request({"jsonrpc": "2.0", "id": 2, "method": "unknown/method"})
    assert bad_res["error"]["code"] == -32601
