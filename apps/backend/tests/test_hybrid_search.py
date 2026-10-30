import hashlib
from uuid import uuid4

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.db.models import Document, DocumentChunk, User
from app.db.neon import neon_db
from app.main import app
from app.rag.embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingService,
)
from app.rag.hybrid_search import compute_rrf


def generate_deterministic_embedding(text: str, dim: int = EMBEDDING_DIMENSION) -> list[float]:
    if not text.strip():
        vec = np.zeros(dim, dtype=np.float32)
        vec[0] = 1.0
        return vec.tolist()
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], byteorder="big") % (2**32)
    rng = np.random.RandomState(seed)
    vector = rng.standard_normal(dim).astype(np.float32)
    words = [w.lower().strip(".,;:!?\"'()[]{}") for w in text.split() if len(w) > 2]
    for i, word in enumerate(words):
        word_digest = hashlib.sha256(word.encode("utf-8")).digest()
        idx1 = int.from_bytes(word_digest[:4], "big") % dim
        idx2 = int.from_bytes(word_digest[4:8], "big") % dim
        vector[idx1] += 1.5 / (1.0 + 0.1 * i)
        vector[idx2] -= 1.0 / (1.0 + 0.1 * i)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()


@pytest.mark.asyncio
async def test_embedding_service_batch():
    """Verify EmbeddingService processes batch inputs."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "embeddings": [{"values": [0.1] * EMBEDDING_DIMENSION} for _ in range(3)]
    }

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_post:
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


def test_rrf_camelcase_metadata():
    """Verify compute_rrf correctly extracts camelCase metadata keys (L-03)."""
    dense_candidates = [
        {
            "id": "c1",
            "document_id": "d1",
            "content": "Test content",
            "similarity": 0.9,
            "metadata": {"headerPath": ["A", "B"], "startLine": 3, "endLine": 9},
        }
    ]
    fused = compute_rrf(dense_results=dense_candidates, sparse_results=[])
    assert len(fused) == 1
    assert fused[0].header_path == ["A", "B"]
    assert fused[0].start_line == 3
    assert fused[0].end_line == 9


@pytest.mark.asyncio
async def test_search_raises_runtime_error_when_db_disconnected():
    """Verify hybrid search raises RuntimeError instead of fabricating offline results (L-11, D-6)."""
    from app.rag.hybrid_search import HybridSearchEngine

    engine = HybridSearchEngine(db=None)
    with pytest.raises(RuntimeError, match="Knowledge base unavailable: database not connected"):
        await engine.search("Raft consensus")


@pytest.mark.asyncio
async def test_mcp_registry_catches_runtime_error():
    """Verify default_mcp_registry._exec_hybrid_search returns isError=True on RuntimeError (L-11)."""
    from app.mcp.registry import HybridRagSearchArgs, default_mcp_registry

    res = await default_mcp_registry._exec_hybrid_search(
        HybridRagSearchArgs(query="Raft consensus")
    )
    assert res.isError is True
    assert "Knowledge base unavailable" in res.content[0].text


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
        metadata={"startLine": 1, "endLine": 20, "headerPath": ["Raft Consensus", "Heartbeats"]},
    )
    chunk2 = DocumentChunk(
        id=uuid4(),
        document_id=doc_id,
        chunk_index=1,
        content="PostgreSQL B-Tree and GIN indexes for architectural queries.",
        embedding=emb_chunk2,
        metadata={"startLine": 21, "endLine": 40, "headerPath": ["Database", "Indexes"]},
    )
    await neon_db.create_document_with_chunks(doc, [chunk1, chunk2])

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


@pytest.mark.asyncio
async def test_embedding_payload_has_task_type_and_pinned_model():
    """LOG-04: one pinned model, taskType sent for documents vs queries."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [{"values": [0.1] * EMBEDDING_DIMENSION}]}
    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_post:
        service = EmbeddingService(api_key="k")
        await service.get_embeddings(["doc text"])
        await service.get_embedding("query text")
    docs_req = mock_post.call_args_list[0].kwargs["json"]["requests"][0]
    query_req = mock_post.call_args_list[1].kwargs["json"]["requests"][0]
    assert docs_req["taskType"] == "RETRIEVAL_DOCUMENT"
    assert query_req["taskType"] == "RETRIEVAL_QUERY"
    assert docs_req["model"] == f"models/{service.model}"


@pytest.mark.asyncio
async def test_embedding_404_does_not_fall_back_to_another_model():
    """LOG-04: a failing model raises instead of mixing vector spaces."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with (
        patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_post,
        pytest.raises(RuntimeError),
    ):
        await EmbeddingService(api_key="k").get_embeddings(["x"])
    assert mock_post.call_count == 1


def test_build_or_tsquery_is_safe_and_or_joined():
    """LOG-08: free text becomes alnum-only OR terms."""
    from app.db.neon import build_or_tsquery

    assert (
        build_or_tsquery("Which models: lowest cost? (1M) 'x'")
        == "which | models | lowest | cost | 1m"
    )
    assert build_or_tsquery("!!! ???") == ""


@pytest.mark.asyncio
async def test_search_degrades_to_sparse_only_when_embedding_fails():
    """LOG-08: embedding outage still returns lexical results."""
    from unittest.mock import AsyncMock, MagicMock

    from app.rag.hybrid_search import HybridSearchEngine

    db = MagicMock()
    db.pool = object()
    db.search_chunks_dense = AsyncMock()
    db.search_chunks_lexical = AsyncMock(
        return_value=[
            {
                "id": "c1",
                "document_id": "d1",
                "chunk_index": 0,
                "content": "raft quorum",
                "metadata": {},
                "filename": "a.md",
                "rank_score": 0.4,
            }
        ]
    )
    embedder = MagicMock()
    embedder.get_embedding = AsyncMock(side_effect=RuntimeError("down"))
    results = await HybridSearchEngine(db=db, embedding_service=embedder).search("raft quorum")
    assert len(results) == 1
    assert results[0].dense_rank is None and results[0].sparse_rank == 1
    db.search_chunks_dense.assert_not_called()


def test_mcp_tool_schema_is_generated_from_the_validation_model():
    """SEC-06: advertised schema and validation cannot drift."""
    from app.mcp.registry import TOOLS

    props = TOOLS[0].inputSchema.properties
    assert props["limit"]["maximum"] == 20 and props["query"]["maxLength"] == 1000
    assert TOOLS[0].inputSchema.required == ["query"]


@pytest.mark.parametrize(
    "arguments",
    [{"query": "x", "limit": "abc"}, [], {"query": "q" * 1001}, {"query": "x", "extra": 1}, {}],
)
@pytest.mark.asyncio
async def test_mcp_invalid_arguments_return_invalid_params(arguments):
    """SEC-06: bad arguments are rejected as -32602 before any quota is consumed."""
    from app.mcp.dispatch import dispatch_mcp_method
    from app.mcp.protocol import INVALID_PARAMS, JsonRpcRequest

    req = JsonRpcRequest(
        id=1,
        method="tools/call",
        params={"name": "hybrid_rag_search", "arguments": arguments},
    )
    res = await dispatch_mcp_method(req)
    assert res.error is not None and res.error.code == INVALID_PARAMS


@pytest.mark.asyncio
async def test_mcp_search_output_is_wrapped_as_untrusted(monkeypatch):
    """SEC-10: chunks returned to external agents sit inside untrusted-context delimiters."""
    from unittest.mock import AsyncMock

    from app.mcp import registry
    from app.rag.hybrid_search import HybridSearchResult

    chunk = HybridSearchResult(
        id="c1",
        document_id="d1",
        chunk_index=0,
        content="Raft needs a quorum.",
        filename="a.md",
        similarity_score=0.1,
    )
    monkeypatch.setattr(
        registry.default_hybrid_search_engine, "search", AsyncMock(return_value=[chunk])
    )
    res = await registry.McpRegistry._exec_hybrid_search(registry.HybridRagSearchArgs(query="raft"))
    assert "<untrusted_document_context" in res.content[0].text


@pytest.mark.asyncio
async def test_embedding_retries_rate_limits_then_succeeds(monkeypatch):
    """R2-LOG-01: two 429s are retried; the third response is used."""
    import httpx

    from app.rag import embeddings

    monkeypatch.setattr(embeddings, "RETRY_DELAYS", (0, 0))
    statuses = iter([429, 503, 200])
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        calls.append(status)
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"embeddings": [{"values": [0.1] * EMBEDDING_DIMENSION}]})

    service = EmbeddingService(api_key="k")
    service._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await service.get_embeddings(["x"])
    finally:
        await service.aclose()
    assert len(result) == 1
    assert calls == [429, 503, 200]


@pytest.mark.asyncio
async def test_embedding_gives_up_after_retries_with_unavailable(monkeypatch):
    import httpx

    from app.rag import embeddings
    from app.rag.embeddings import EmbeddingUnavailable

    monkeypatch.setattr(embeddings, "RETRY_DELAYS", (0, 0))
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429)

    service = EmbeddingService(api_key="k")
    service._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(EmbeddingUnavailable):
            await service.get_embeddings(["x"])
    finally:
        await service.aclose()
    assert len(calls) == 3


@pytest.mark.db
@pytest.mark.asyncio
async def test_dense_search_finds_user_chunks_behind_many_seeded_chunks_r2_log_03():
    """The HNSW scan must keep going until the user's own chunks pass the WHERE filter."""
    import random
    from uuid import uuid4

    from app.db.models import Document, DocumentChunk, User
    from app.db.neon import neon_db

    rng = random.Random(7)
    query_vec = [rng.random() for _ in range(EMBEDDING_DIMENSION)]

    def near(scale: float) -> list[float]:
        return [v + rng.random() * scale for v in query_vec]

    user = await neon_db.create_user(
        User(id=uuid4(), name="Dense", is_guest=True, device_id=uuid4().hex)
    )
    seeded_doc = Document(
        id=uuid4(),
        user_id=None,
        filename="seed.md",
        mime_type="text/markdown",
        sha256_hash=uuid4().hex,
        total_chunks=300,
        is_seeded=True,
    )
    user_doc = Document(
        id=uuid4(),
        user_id=user.id,
        filename="mine.md",
        mime_type="text/markdown",
        sha256_hash=uuid4().hex,
        total_chunks=3,
        is_seeded=False,
    )
    # 300 seeded chunks closer to the query than the user's 3 chunks.
    seeded_chunks = [
        DocumentChunk(
            document_id=seeded_doc.id, chunk_index=i, content=f"seed {i}", embedding=near(0.01)
        )
        for i in range(300)
    ]
    user_chunks = [
        DocumentChunk(
            document_id=user_doc.id, chunk_index=i, content=f"mine {i}", embedding=near(0.5)
        )
        for i in range(3)
    ]
    try:
        await neon_db.create_document_with_chunks(seeded_doc, seeded_chunks)
        await neon_db.create_document_with_chunks(user_doc, user_chunks)
        rows = await neon_db.search_chunks_dense(query_vec, user_id=user.id, limit=400)
        assert {r["content"] for r in rows if r["content"].startswith("mine")} == {
            "mine 0",
            "mine 1",
            "mine 2",
        }
    finally:
        pool = neon_db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM documents WHERE id = ANY($1::uuid[]);", [seeded_doc.id])
            await conn.execute("DELETE FROM users WHERE id = $1;", user.id)
