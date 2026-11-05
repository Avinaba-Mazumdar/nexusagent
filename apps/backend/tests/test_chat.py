import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.db
@pytest.mark.asyncio
async def test_list_seeded_documents_without_auth():
    from uuid import NAMESPACE_URL, uuid5

    from app.db.models import Document
    from app.db.neon import neon_db

    names = [
        "benchlm_evals.md",
        "cursor_bench.md",
        "openrouter_metrics.md",
        "artificial_analysis.md",
    ]
    # A fresh database has no seeded corpus; add whichever of the four documents is missing.
    created = []
    for name in names:
        doc_id = uuid5(NAMESPACE_URL, f"nexusagent:kb:{name}")
        if await neon_db.get_document_by_id(doc_id) is None:
            doc = Document(
                id=doc_id,
                user_id=None,
                filename=name,
                mime_type="text/markdown",
                sha256_hash=doc_id.hex,
                total_chunks=0,
                is_seeded=True,
            )
            await neon_db.create_document_with_chunks(doc, [])
            created.append(doc_id)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/documents")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert len(data["documents"]) >= 4
        filenames = [d["filename"] for d in data["documents"]]
        for name in names:
            assert name in filenames
    finally:
        async with neon_db.get_pool().acquire() as conn:
            for doc_id in created:
                await conn.execute("DELETE FROM documents WHERE id = $1;", doc_id)
