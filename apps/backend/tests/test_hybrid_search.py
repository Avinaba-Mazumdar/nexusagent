import math
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.db.models import Document, DocumentChunk, User
from app.db.neon import neon_db
from app.main import app
from app.rag.embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingService,
    generate_deterministic_embedding,
)
from app.rag.hybrid_search import compute_rrf


def test_embedding_generation_dimension_and_norm():
    """Verify that deterministic embeddings produce normalized 768-d vectors."""
    text = "Raft linearizable consensus protocol with monotonic log sequencing"
    emb = generate_deterministic_embedding(text)

    assert len(emb) == EMBEDDING_DIMENSION
    assert isinstance(emb, list)
    assert all(isinstance(x, float) for x in emb)

    # Assert L2 unit norm
    norm = math.sqrt(sum(x * x for x in emb))
    assert abs(norm - 1.0) < 1e-4


def test_embedding_determinism():
    """Verify identical text produces identical embeddings."""
    text = "Multi-Paxos leader election under network partition"
    emb1 = generate_deterministic_embedding(text)
    emb2 = generate_deterministic_embedding(text)
    assert emb1 == emb2

    # Different text should produce different vectors
    emb3 = generate_deterministic_embedding("Completely unrelated string about databases")
    assert emb1 != emb3


@pytest.mark.asyncio
async def test_embedding_service_batch():
    """Verify EmbeddingService processes batch inputs."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "embeddings": [{"values": [0.1] * EMBEDDING_DIMENSION} for _ in range(3)]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        service = EmbeddingService(api_key="test-key")
        texts = [
            "Distributed consensus protocol",
            "AST execution sandbox",
            "Vector search with pgvector",
        ]
        results = await service.get_embeddings(texts)
        assert len(results) == 3
        for r in results:
            assert len(r) == EMBEDDING_DIMENSION
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["x-goog-api-key"] == "test-key"
        assert "?key=" not in mock_post.call_args[0][0]


def test_rrf_scoring_algorithm():
    """Verify Reciprocal Rank Fusion calculation and ordering."""
    dense_candidates = [
        {"id": "c1", "document_id": "d1", "content": "Raft leader election", "similarity": 0.95},
        {"id": "c2", "document_id": "d1", "content": "Paxos commit latency", "similarity": 0.85},
        {
            "id": "c3",
            "document_id": "d1",
            "content": "Byzantine fault tolerance",
            "similarity": 0.75,
        },
    ]

    sparse_candidates = [
        {"id": "c2", "document_id": "d1", "content": "Paxos commit latency", "rank_score": 0.8},
        {"id": "c1", "document_id": "d1", "content": "Raft leader election", "rank_score": 0.6},
        {"id": "c4", "document_id": "d1", "content": "Gossip protocol", "rank_score": 0.5},
    ]

    # c1: dense rank 1, sparse rank 2 -> 0.5 / (60+1) + 0.5 / (60+2) = 0.5/61 + 0.5/62
    # c2: dense rank 2, sparse rank 1 -> 0.5 / (60+2) + 0.5 / (60+1) = 0.5/62 + 0.5/61 (identical score)
    # c3: dense rank 3, sparse None   -> 0.5 / (60+3) = 0.5/63
    # c4: dense None,   sparse rank 3 -> 0.5 / (60+3) = 0.5/63
    fused = compute_rrf(
        dense_results=dense_candidates,
        sparse_results=sparse_candidates,
        dense_weight=0.5,
        sparse_weight=0.5,
        rrf_k=60,
        limit=5,
    )

    assert len(fused) == 4
    # Top two should be c1 and c2
    top_ids = {fused[0].id, fused[1].id}
    assert top_ids == {"c1", "c2"}
    assert fused[0].similarity_score > fused[2].similarity_score
    assert fused[0].similarity_score > 0


@pytest.mark.db
@pytest.mark.asyncio
async def test_hybrid_search_end_to_end_endpoint():
    """End-to-end verification of POST /api/rag/search with Neon database."""
    # 1. Create a test user
    user_id = uuid4()
    test_user = User(
        id=user_id,
        email=f"rag_tester_{uuid4().hex[:6]}@example.com",
        name="RAG Verification Agent",
        is_guest=False,
    )
    user_query = """
        INSERT INTO users (id, email, name, is_guest)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (id) DO NOTHING;
    """
    async with neon_db.get_pool().acquire() as conn:
        await conn.execute(
            user_query, test_user.id, test_user.email, test_user.name, test_user.is_guest
        )

    # 2. Insert test document & chunks
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        user_id=test_user.id,
        filename="rfc-104-raft-consensus.md",
        mime_type="text/markdown",
        sha256_hash=uuid4().hex,
        total_chunks=2,
        is_seeded=False,
    )
    await neon_db.create_document(doc)

    emb_chunk1 = generate_deterministic_embedding(
        "Raft consensus leader heartbeat quorum and election timeout."
    )
    emb_chunk2 = generate_deterministic_embedding(
        "PostgreSQL B-Tree and GIN indexes for architectural queries."
    )

    chunk1 = DocumentChunk(
        id=uuid4(),
        document_id=doc_id,
        chunk_index=0,
        content="Raft consensus leader heartbeat quorum and election timeout.",
        embedding=emb_chunk1,
        metadata={"start_line": 1, "end_line": 20, "header_path": ["Raft Consensus", "Heartbeats"]},
    )
    chunk2 = DocumentChunk(
        id=uuid4(),
        document_id=doc_id,
        chunk_index=1,
        content="PostgreSQL B-Tree and GIN indexes for architectural queries.",
        embedding=emb_chunk2,
        metadata={"start_line": 21, "end_line": 40, "header_path": ["Database", "Indexes"]},
    )
    await neon_db.insert_document_chunks([chunk1, chunk2])

    # 3. Authenticate and query /api/rag/search
    token, _ = create_access_token({"sub": str(test_user.id), "role": "user"})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/rag/search",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "Raft consensus quorum",
                "documentId": str(doc_id),
                "limit": 3,
                "denseWeight": 0.6,
                "sparseWeight": 0.4,
                "rrfK": 60,
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["query"] == "Raft consensus quorum"
        assert data["totalResults"] >= 1
        top_result = data["results"][0]
        assert top_result["documentId"] == str(doc_id)
        assert "Raft" in top_result["content"]
        assert top_result["similarityScore"] > 0
        assert top_result["startLine"] == 1
        assert top_result["endLine"] == 20
        assert top_result["headerPath"] == ["Raft Consensus", "Heartbeats"]
        assert top_result["filename"] == "rfc-104-raft-consensus.md"
