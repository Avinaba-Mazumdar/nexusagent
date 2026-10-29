from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.db.models import User
from app.db.neon import neon_db
from app.main import app
from app.rag.parser import (
    MAX_CHUNK_CHARS,
    compute_line_positions,
    default_markdown_parser,
    split_large_section,
)

NL = chr(10)

SAMPLE_RFC_MARKDOWN = """# RFC-104: Raft Consensus vs Multi-Paxos for High-Throughput Write Pipelines

Category: Distributed Systems Consensus
Status: Draft
Author: Systems Architecture Working Group

---

## 1. Abstract and Core Tradeoffs

Distributed consensus protocols under write-heavy workloads face severe bottlenecks when leader election is contested.
In this specification, we contrast Raft linearizable log replication against Multi-Paxos pipelining.
Key design criteria include:
- Commit latency under partition
- Heartbeat traffic overhead
- Out-of-order log application

## 2. Invariants & Guarantees

Every leader must uphold monotonic sequence numbering.
If a partition occurs across three availability zones, quorums require `floor(N/2) + 1` nodes to acknowledge state transitions before client ACK is returned.
Under high concurrency, batched write windows achieve 14,000 IOPS with a 99th percentile commit latency bounded by 4.2ms.

### 2.1 State Machine Safety

If server S1 has applied an entry at a given index, no other server can ever apply a different log entry for the same index.

```rust
pub struct ConsensusNode {
    pub current_term: u64,
    pub voted_for: Option<NodeId>,
    pub commit_index: u64,
}
```

## 3. Performance & Throughput Limits

Benchmark results across AWS us-east-1 and eu-central-1 demonstrate significant divergence in tail latency during network flapping events.
"""


def test_compute_line_positions():
    text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    sub = "Line 2\nLine 3"
    start, end = compute_line_positions(text, sub)
    assert start == 2
    assert end == 3


def test_line_positions_use_cursor_for_repeated_lines():
    """LOG-07: a repeated line maps to the occurrence at/after the cursor, not the first."""
    lines = ["intro", "---", "body"] + [f"filler {i}" for i in range(10)] + ["---", "tail"]
    text = NL.join(lines)
    first_hr = text.index("---")
    start, _ = compute_line_positions(text, NL.join(["---", "tail"]), search_from=first_hr + 1)
    assert start == len(lines) - 1


def test_parser_line_numbers_survive_private_key_redaction():
    """LOG-07: redacting a multi-line key must not shift later line numbers."""
    key = NL.join(
        ["-----BEGIN PRIVATE KEY-----", "AAAA", "BBBB", "CCCC", "-----END PRIVATE KEY-----"]
    )
    lines = ["# Title", "", key, "", "## After", "", "marker paragraph here", ""]
    md = NL.join(lines)
    chunks = default_markdown_parser.parse_markdown(md, document_id=uuid4())
    target = next(c for c in chunks if "marker paragraph" in c.content)
    expected = md.split(NL).index("marker paragraph here") + 1
    assert target.metadata["startLine"] <= expected <= target.metadata["endLine"]
    assert "BEGIN PRIVATE KEY" not in "".join(c.content for c in chunks)


def test_split_large_section_hard_caps_long_line():
    # Long line of 2,500 characters
    long_line = "A" * 2500
    chunks = split_large_section(long_line, max_chars=MAX_CHUNK_CHARS)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= MAX_CHUNK_CHARS


def test_markdown_hierarchical_parser_chunks_and_metadata():
    doc_id = uuid4()
    chunks = default_markdown_parser.parse_markdown(
        markdown_text=SAMPLE_RFC_MARKDOWN,
        document_id=doc_id,
        extra_metadata={"filename": "rfc-104.md"},
    )

    assert len(chunks) >= 3
    for chunk in chunks:
        assert chunk.document_id == doc_id
        assert chunk.content
        assert len(chunk.content) <= MAX_CHUNK_CHARS
        assert "startLine" in chunk.metadata
        assert "endLine" in chunk.metadata
        assert chunk.metadata["startLine"] >= 1
        assert chunk.metadata["endLine"] >= chunk.metadata["startLine"]
        assert "sha256" in chunk.metadata
        assert chunk.metadata["filename"] == "rfc-104.md"

    # Check header hierarchy extraction
    header_paths = [c.metadata.get("headerPath") for c in chunks]
    has_sub_header = any("2.1 State Machine Safety" in " ".join(h) for h in header_paths if h)
    assert has_sub_header, (
        f"Expected at least one chunk to capture sub-header '2.1 State Machine Safety', got {header_paths}"
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_upload_and_list_documents():
    transport = ASGITransport(app=app)
    user_id = uuid4()
    token, _ = create_access_token({"sub": str(user_id), "role": "user", "is_guest": False})

    # Pre-seed user in database if neon is connected
    test_user = User(
        id=user_id,
        name="RFC Architect",
        email=f"architect-{user_id.hex[:6]}@nexusagent.test",
        is_guest=False,
    )
    if neon_db.pool:
        await neon_db.create_user(test_user)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload sample RFC
        files = {
            "file": (
                "rfc-104-raft.md",
                SAMPLE_RFC_MARKDOWN.encode("utf-8"),
                "text/markdown",
            )
        }
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post("/api/documents/upload", files=files, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "document" in data
        assert data["document"]["filename"] == "rfc-104-raft.md"
        assert data["chunksCount"] >= 3
        assert len(data["previewChunks"]) > 0

        doc_id = data["document"]["id"]

        # 2. Fetch document chunks
        chunk_response = await client.get(f"/api/documents/{doc_id}/chunks", headers=headers)
        assert chunk_response.status_code == 200
        chunk_data = chunk_response.json()
        assert "chunks" in chunk_data
        assert len(chunk_data["chunks"]) == data["chunksCount"]
        first_chunk = chunk_data["chunks"][0]
        assert "startLine" in first_chunk["metadata"]
        assert "endLine" in first_chunk["metadata"]

        # 3. List documents for user
        list_response = await client.get("/api/documents", headers=headers)
        assert list_response.status_code == 200
        docs_list = list_response.json()["documents"]
        filenames = [d["filename"] for d in docs_list]
        assert "rfc-104-raft.md" in filenames

        # 4. Upload duplicate file (test deduplication response)
        files_dup = {
            "file": (
                "rfc-104-raft.md",
                SAMPLE_RFC_MARKDOWN.encode("utf-8"),
                "text/markdown",
            )
        }
        dup_response = await client.post("/api/documents/upload", files=files_dup, headers=headers)
        assert dup_response.status_code == 200


@pytest.mark.asyncio
async def test_document_upload_size_limit_413():
    from unittest.mock import AsyncMock

    from app.core.auth import get_current_user
    from app.db.neon import get_db

    user = User(
        id=uuid4(),
        email="test@user.com",
        name="Test",
        is_guest=False,
    )
    mock_db = AsyncMock()
    mock_db.count_user_documents.return_value = 0

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1.5 MB generated file exceeds 1 MB limit
            large_content = b"A" * int(1.5 * 1024 * 1024)
            files = {"file": ("large.md", large_content, "text/markdown")}
            headers = {"Authorization": "Bearer test-token"}
            resp = await client.post("/api/documents/upload", files=files, headers=headers)
            assert resp.status_code == 413
            assert "exceeds maximum allowed size" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_document_upload_chunks_cap_413(monkeypatch):
    """Test that a file producing > 400 chunks returns 413 (SEC-03)."""
    from unittest.mock import AsyncMock

    from app.core.auth import get_current_user
    from app.db.neon import get_db

    user = User(
        id=uuid4(),
        email="chunk-cap@user.com",
        name="Chunk Cap",
        is_guest=False,
    )
    mock_db = AsyncMock()
    mock_db.count_user_documents.return_value = 0
    mock_db.get_document_by_hash.return_value = None

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    monkeypatch.setattr("app.routes.documents.default_embedding_service.api_key", "test-key")

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            content = "\n\n".join(f"## Header {i}\nContent {i}" for i in range(401))
            files = {"file": ("many_chunks.md", content.encode("utf-8"), "text/markdown")}
            headers = {"Authorization": "Bearer test-token"}
            resp = await client.post("/api/documents/upload", files=files, headers=headers)
            assert resp.status_code == 413
            assert "exceeding the maximum allowed limit of 400" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_document_upload_concurrent_lock_409(monkeypatch, fake_rate_db):
    """Test that concurrent uploads by the same user return 409 for the second request (SEC-03)."""
    import asyncio
    from unittest.mock import AsyncMock

    from app.core.auth import get_current_user
    from app.db.neon import get_db

    user = User(
        id=uuid4(),
        email="lock-test@user.com",
        name="Lock Test",
        is_guest=False,
    )
    mock_db = AsyncMock()
    mock_db.count_user_documents.return_value = 0
    mock_db.get_document_by_hash.return_value = None
    mock_db.create_document_with_chunks.side_effect = lambda doc, chunks: doc

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    monkeypatch.setattr("app.routes.documents.default_embedding_service.api_key", "test-key")

    async def slow_get_embeddings(*args, **kwargs):
        await asyncio.sleep(0.5)
        return [[0.1] * 768]

    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.get_embeddings",
        slow_get_embeddings,
    )

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files1 = {"file": ("test1.md", b"# Test 1\nLine 1", "text/markdown")}
            files2 = {"file": ("test2.md", b"# Test 2\nLine 2", "text/markdown")}
            headers = {"Authorization": "Bearer test-token"}

            res1, res2 = await asyncio.gather(
                client.post("/api/documents/upload", files=files1, headers=headers),
                client.post("/api/documents/upload", files=files2, headers=headers),
            )
            statuses = [res1.status_code, res2.status_code]
            assert 409 in statuses
            detail_409 = res1.json()["detail"] if res1.status_code == 409 else res2.json()["detail"]
            assert "Upload already in progress" in detail_409
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_duplicate_upload_does_not_consume_quota_log_09(fake_rate_db, monkeypatch):
    """Regression (LOG-09): duplicate file upload returns 200 with quota unchanged."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.core.auth import get_current_user
    from app.core.rate_limiter import default_rate_limiter
    from app.db.models import Document, User
    from app.db.neon import get_db

    default_rate_limiter.reset_for_test()
    now = datetime.now(UTC)
    user_id = uuid4()
    test_user = User(
        id=user_id,
        email="dup-quota@example.com",
        name="Dup Quota",
        is_guest=True,
        client_ip="127.0.0.1",
        created_at=now,
        last_seen_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: test_user

    mock_db = AsyncMock()
    mock_db.count_user_documents.return_value = 1
    existing_doc = Document(
        id=uuid4(),
        user_id=user_id,
        filename="dup.md",
        mime_type="text/markdown",
        sha256_hash="test-hash",
        total_chunks=2,
    )
    mock_db.get_document_by_hash.return_value = existing_doc
    mock_db.get_document_chunks.return_value = []
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("dup.md", b"# Dup Content", "text/markdown")}
            headers = {"Authorization": "Bearer test-token"}
            resp = await client.post("/api/documents/upload", files=files, headers=headers)
            assert resp.status_code == 200
            quota_after = await default_rate_limiter.get_quota(user_id=user_id, is_guest=True)
            assert quota_after == 5
    finally:
        app.dependency_overrides.clear()
        default_rate_limiter.reset_for_test()


@pytest.mark.asyncio
async def test_document_upload_user_cap_409():
    from unittest.mock import AsyncMock

    from app.core.auth import get_current_user
    from app.db.neon import get_db

    user = User(
        id=uuid4(),
        email="test@user.com",
        name="Test",
        is_guest=False,
    )
    mock_db = AsyncMock()
    mock_db.count_user_documents.return_value = 20

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("test.md", b"# Test", "text/markdown")}
            headers = {"Authorization": "Bearer test-token"}
            resp = await client.post("/api/documents/upload", files=files, headers=headers)
            assert resp.status_code == 409
            assert "Document limit reached" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def upload_client(monkeypatch, fake_rate_db):
    """Authenticated client with a mocked DB that has no documents yet."""
    from unittest.mock import AsyncMock

    from app.core.auth import get_current_user
    from app.db.neon import get_db

    user = User(id=uuid4(), name="Uploader", is_guest=False, email="up@example.com")
    mock_db = AsyncMock()
    mock_db.count_user_documents.return_value = 0
    mock_db.get_document_by_hash.return_value = None
    mock_db.create_document_with_chunks.side_effect = lambda doc, chunks: doc
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    monkeypatch.setattr("app.routes.documents.default_embedding_service.api_key", "k")

    async def fake_embed(texts, **kwargs):
        return [[0.1] * 768 for _ in texts]

    monkeypatch.setattr("app.routes.documents.default_embedding_service.get_embeddings", fake_embed)
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), mock_db
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "content", "ctype"),
    [
        ("evil.png", b"# looks like text", "text/plain"),  # forged MIME, wrong extension
        ("bin.md", b"abc" + bytes([0]) + b"def", "text/markdown"),  # NUL byte
        ("latin.md", "caf\u00e9".encode("latin-1"), "text/markdown"),  # not UTF-8
    ],
)
async def test_upload_rejects_non_text_payloads_sec_05(upload_client, name, content, ctype):
    client, _db = upload_client
    async with client:
        res = await client.post("/api/documents/upload", files={"file": (name, content, ctype)})
    assert res.status_code == 415


@pytest.mark.asyncio
async def test_upload_truncates_overlong_filename_and_ignores_client_mime_sec_05(upload_client):
    client, db = upload_client
    long_name = "a" * 300 + ".md"
    async with client:
        res = await client.post(
            "/api/documents/upload",
            files={"file": (long_name, b"# Title\nbody text", "application/octet-stream")},
        )
    assert res.status_code == 200
    saved = db.create_document_with_chunks.call_args.args[0]
    assert len(saved.filename) <= 200 and saved.filename.endswith(".md")
    assert saved.mime_type == "text/markdown"


def test_safe_filename_strips_paths_and_control_characters():
    from app.routes.documents import safe_filename

    BS = chr(92)

    assert safe_filename("../../etc/passwd.md") == "passwd.md"
    assert safe_filename(BS.join(["C:", "dir", "notes.txt"])) == "notes.txt"
    assert safe_filename(None) == "uploaded_document.md"
    assert safe_filename("a" + chr(7) + "b.md") == "ab.md"


@pytest.mark.asyncio
async def test_delete_document_owner_ok_and_others_404_log_13(upload_client):
    client, db = upload_client
    doc_id = uuid4()
    db.delete_user_document.return_value = True
    async with client:
        ok = await client.delete(f"/api/documents/{doc_id}")
        db.delete_user_document.return_value = False
        missing = await client.delete(f"/api/documents/{doc_id}")
        bad = await client.delete("/api/documents/not-a-uuid")
    assert ok.status_code == 200 and ok.json() == {"success": True, "id": str(doc_id)}
    assert missing.status_code == 404
    assert bad.status_code == 422
