import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from app.mcp.server import mcp
from app.rag.hybrid_search import HybridSearchResult


@asynccontextmanager
async def connected_client():
    async with (
        create_client_server_memory_streams() as (client_stream, server_stream),
        ClientSession(client_stream[0], client_stream[1]) as client,
    ):
        server_task = asyncio.create_task(
            mcp._lowlevel_server.run(
                server_stream[0],
                server_stream[1],
                mcp._lowlevel_server.create_initialization_options(),
            )
        )
        await client.initialize()
        try:
            yield client
        finally:
            server_task.cancel()


@pytest.mark.asyncio
async def test_list_tools():
    async with connected_client() as client:
        tools_result = await client.list_tools()
        tool_names = [tool.name for tool in tools_result.tools]
        assert "search" in tool_names
        assert "fetch" in tool_names


@pytest.mark.asyncio
async def test_search_tool(monkeypatch):
    fake_results = [
        HybridSearchResult(
            id="chunk-1",
            document_id="doc-1",
            filename="benchmarks.md",
            header_path=["Overview", "Evals"],
            content="Benchmark eval details",
            similarity_score=0.9,
            chunk_index=0,
            metadata={"page": 1},
        ),
        HybridSearchResult(
            id="chunk-2",
            document_id="doc-2",
            filename="cursorbench.md",
            header_path=["Results"],
            content="CursorBench performance metrics",
            similarity_score=0.85,
            chunk_index=1,
            metadata={"page": 2},
        ),
    ]

    audit_calls = []

    async def fake_log_tool_audit(**kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr("app.mcp.server.default_audit_logger.log_tool_audit", fake_log_tool_audit)

    with (
        patch("app.mcp.server._db", new_callable=AsyncMock),
        patch(
            "app.mcp.server.default_hybrid_search_engine.search",
            new_callable=AsyncMock,
        ) as mock_search,
    ):
        mock_search.return_value = fake_results
        async with connected_client() as client:
            result = await client.call_tool("search", {"query": "gpt"})
            assert not result.is_error
            data = json.loads(result.content[0].text)
            assert "results" in data
            assert len(data["results"]) == 2
            first = data["results"][0]
            assert first["id"] == "doc-1:chunk-1"
            assert first["title"] == "benchmarks.md - Overview > Evals"
            assert "doc=doc-1&chunk=chunk-1" in first["url"]

    assert len(audit_calls) == 1
    assert audit_calls[0]["tool_name"] == "mcp.search"
    assert audit_calls[0]["mcp_server"] == "mcp-public"


@pytest.mark.asyncio
async def test_fetch_tool_not_found():
    with (
        patch("app.mcp.server._db", new_callable=AsyncMock),
        patch(
            "app.mcp.server.neon_db.get_document_chunk",
            new_callable=AsyncMock,
        ) as mock_chunk,
    ):
        mock_chunk.return_value = None
        async with connected_client() as client:
            result = await client.call_tool(
                "fetch",
                {"id": "00000000-0000-0000-0000-000000000001:00000000-0000-0000-0000-000000000002"},
            )
            assert result.is_error


@pytest.mark.asyncio
async def test_fetch_tool_invalid_id():
    async with connected_client() as client:
        result = await client.call_tool("fetch", {"id": "invalid-format"})
        assert result.is_error


@pytest.mark.asyncio
async def test_fetch_tool_success(monkeypatch):
    fake_chunk = MagicMock(content="Passage full text content", metadata={"page": 3})
    fake_doc = MagicMock(filename="benchmarks.md")

    audit_calls = []

    async def fake_log_tool_audit(**kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr("app.mcp.server.default_audit_logger.log_tool_audit", fake_log_tool_audit)

    with (
        patch("app.mcp.server._db", new_callable=AsyncMock),
        patch(
            "app.mcp.server.neon_db.get_document_chunk",
            new_callable=AsyncMock,
        ) as mock_chunk,
        patch(
            "app.mcp.server.neon_db.get_document_by_id",
            new_callable=AsyncMock,
        ) as mock_doc,
    ):
        mock_chunk.return_value = fake_chunk
        mock_doc.return_value = fake_doc
        async with connected_client() as client:
            result = await client.call_tool(
                "fetch",
                {"id": "00000000-0000-0000-0000-000000000001:00000000-0000-0000-0000-000000000002"},
            )
            assert not result.is_error
            data = json.loads(result.content[0].text)
            assert (
                data["id"]
                == "00000000-0000-0000-0000-000000000001:00000000-0000-0000-0000-000000000002"
            )
            assert data["title"] == "benchmarks.md"
            assert data["text"] == "Passage full text content"
            assert data["metadata"] == {"page": 3}

    assert len(audit_calls) == 1
    assert audit_calls[0]["tool_name"] == "mcp.fetch"
    assert audit_calls[0]["mcp_server"] == "mcp-public"
