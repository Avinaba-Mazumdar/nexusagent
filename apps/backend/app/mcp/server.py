"""Public, read-only MCP server (Streamable HTTP at /mcp, or stdio with `python -m app.mcp.server`).

Tools follow the search/fetch shape ChatGPT connectors expect; Claude and other clients use them too.
"""

import time
from uuid import UUID

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.config import settings
from app.core.audit_log import default_audit_logger
from app.core.security_guardrails import (
    sanitize_retrieved_chunks,
    sanitize_untrusted_text,
    scrub_sensitive_information,
)
from app.db.neon import neon_db
from app.rag.hybrid_search import default_hybrid_search_engine

MCP_AUDIT_SOURCE = "mcp-public"

mcp = MCPServer(
    "nexusagent",
    instructions="Search LLM benchmark documents (Artificial Analysis, BenchLM, CursorBench, OpenRouter).",
)


async def _db():
    if not neon_db.pool:
        await neon_db.connect()


def _url(document_id: str, chunk_id: str) -> str:
    return f"https://{settings.PUBLIC_SITE_HOST}/?doc={document_id}&chunk={chunk_id}"


@mcp.tool()
async def search(query: str) -> dict:
    """Search the LLM benchmark knowledge base. Returns up to 8 matching passages (id, title, url)."""
    started = time.perf_counter()
    await _db()
    results, _ = sanitize_retrieved_chunks(
        await default_hybrid_search_engine.search(query=query[:1000], limit=8)
    )
    result_data = {
        "results": [
            {
                "id": f"{r.document_id}:{r.id}",
                "title": f"{r.filename} - {' > '.join(r.header_path) or 'passage'}",
                "url": _url(r.document_id, r.id),
            }
            for r in results
        ]
    }
    await default_audit_logger.log_tool_audit(
        tool_name="mcp.search",
        input_args={"query": query[:200]},
        output_summary={"results": len(results)},
        duration_ms=max(int((time.perf_counter() - started) * 1000), 1),
        mcp_server=MCP_AUDIT_SOURCE,
    )
    return result_data


@mcp.tool()
async def fetch(id: str) -> dict:
    """Fetch the full text of a passage returned by `search` (id is `document_id:chunk_id`)."""
    started = time.perf_counter()
    parts = id.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid id format: {id}. Expected 'document_id:chunk_id'")
    doc_str, chunk_str = parts
    try:
        doc_id = UUID(doc_str)
        chunk_id = UUID(chunk_str)
    except ValueError as exc:
        raise ValueError(f"Invalid UUID in id: {id}") from exc

    await _db()
    chunk = await neon_db.get_document_chunk(doc_id, chunk_id)
    if not chunk:
        raise ValueError(f"Passage not found: {id}")

    doc = await neon_db.get_document_by_id(doc_id)
    filename = doc.filename if doc else "document"

    result_data = {
        "id": id,
        "title": filename,
        "text": scrub_sensitive_information(sanitize_untrusted_text(chunk.content)),
        "url": _url(str(doc_id), str(chunk_id)),
        "metadata": chunk.metadata,
    }
    await default_audit_logger.log_tool_audit(
        tool_name="mcp.fetch",
        input_args={"id": id[:100]},
        output_summary={"chars": len(chunk.content)},
        duration_ms=max(int((time.perf_counter() - started) * 1000), 1),
        mcp_server=MCP_AUDIT_SOURCE,
    )
    return result_data


def mcp_transport_security() -> TransportSecuritySettings:
    """DNS rebinding allowlist for the public MCP endpoint.

    Host must be this site, the API host, or localhost. Origin may be absent: Claude, ChatGPT,
    and Cursor connectors call the server without a browser Origin. A present Origin must be one
    we already allow for the web app, or a localhost port.
    """
    site = settings.PUBLIC_SITE_HOST
    api = f"api.{site}"
    hosts = [
        site,
        f"{site}:*",
        api,
        f"{api}:*",
        "localhost",
        "localhost:*",
        "127.0.0.1",
        "127.0.0.1:*",
    ]
    if settings.is_dev:
        hosts.extend(["testserver", "testserver:*"])
    configured = settings.CORS_ORIGINS
    origins = list(configured) if isinstance(configured, list) else [str(configured)]
    for extra in ("http://localhost:*", "http://127.0.0.1:*"):
        if extra not in origins:
            origins.append(extra)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def create_streamable_http_app():
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=mcp_transport_security(),
    )


mcp_http_app = create_streamable_http_app()


if __name__ == "__main__":
    mcp.run()  # stdio
