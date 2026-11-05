"""Public, read-only MCP server (Streamable HTTP at /mcp, or stdio with `python -m app.mcp.server`).

Tools follow the search/fetch shape ChatGPT connectors expect; Claude and other clients use them too.
"""

from uuid import UUID

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.config import settings
from app.core.security_guardrails import sanitize_retrieved_chunks
from app.db.neon import neon_db
from app.rag.hybrid_search import default_hybrid_search_engine

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
    await _db()
    results, _ = sanitize_retrieved_chunks(
        await default_hybrid_search_engine.search(query=query[:1000], limit=8)
    )
    return {
        "results": [
            {
                "id": f"{r.document_id}:{r.id}",
                "title": f"{r.filename} - {' > '.join(r.header_path) or 'passage'}",
                "url": _url(r.document_id, r.id),
            }
            for r in results
        ]
    }


@mcp.tool()
async def fetch(id: str) -> dict:
    """Fetch the full text of a passage returned by `search` (id is `document_id:chunk_id`)."""
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

    return {
        "id": id,
        "title": filename,
        "text": chunk.content,
        "url": _url(str(doc_id), str(chunk_id)),
        "metadata": chunk.metadata,
    }


def create_streamable_http_app():
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


mcp_http_app = create_streamable_http_app()


if __name__ == "__main__":
    mcp.run()  # stdio
