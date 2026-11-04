import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.core.auth import get_current_user
from app.db.models import Document, DocumentChunk, User
from app.db.neon import get_db
from app.main import app


def _create_sample_pdf(text: str = "Sample benchmark evaluation results.") -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    page[NameObject("/Resources")] = resources
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 100 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = stream
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def users():
    now = datetime.now(UTC)
    guest = User(
        id=uuid4(),
        email="guest@example.com",
        name="Guest",
        is_guest=True,
        is_admin=False,
        created_at=now,
        last_seen_at=now,
    )
    google_user = User(
        id=uuid4(),
        email="user@example.com",
        name="Regular User",
        is_guest=False,
        is_admin=False,
        created_at=now,
        last_seen_at=now,
    )
    admin_user = User(
        id=uuid4(),
        email="admin@example.com",
        name="Admin User",
        is_guest=False,
        is_admin=True,
        created_at=now,
        last_seen_at=now,
    )
    return guest, google_user, admin_user


@pytest.mark.asyncio
async def test_guest_upload_is_forbidden_403(users):
    guest, _, _ = users
    app.dependency_overrides[get_current_user] = lambda: guest
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("bench.md", b"# Benchmark\nContent", "text/markdown")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_regular_google_user_upload_is_forbidden_403(users):
    _, google_user, _ = users
    app.dependency_overrides[get_current_user] = lambda: google_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("bench.md", b"# Benchmark\nContent", "text/markdown")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_can_upload_pdf_and_gets_chunks(users, monkeypatch):
    _, _, admin = users
    pdf_bytes = _create_sample_pdf("MMLU evaluation scores for Gemini Flash.")

    mock_db = AsyncMock()
    mock_db.get_document_by_hash.return_value = None

    async def fake_create_document(doc, chunks):
        return doc

    mock_db.create_document_with_chunks = AsyncMock(side_effect=fake_create_document)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: mock_db

    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.api_key",
        "mock-key",
    )
    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.get_embeddings",
        AsyncMock(return_value=[[0.1] * 768]),
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("mmlu.pdf", pdf_bytes, "application/pdf")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["chunksCount"] >= 1
            assert data["document"]["filename"] == "mmlu.pdf"
            assert data["previewChunks"][0]["metadata"]["page"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_can_upload_markdown(users, monkeypatch):
    _, _, admin = users
    md_bytes = (
        b"# GSM8K Benchmark\n\n"
        b"Introduction to math benchmarks.\n\n"
        b"## Math Reasoning\n\n"
        b"GSM8K evaluates multi-step mathematical reasoning."
    )

    mock_db = AsyncMock()
    mock_db.get_document_by_hash.return_value = None

    async def fake_create_document(doc, chunks):
        return doc

    mock_db.create_document_with_chunks = AsyncMock(side_effect=fake_create_document)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: mock_db

    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.api_key",
        "mock-key",
    )
    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.get_embeddings",
        AsyncMock(return_value=[[0.1] * 768, [0.1] * 768]),
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("gsm8k.md", md_bytes, "text/markdown")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["chunksCount"] >= 1
            assert data["document"]["filename"] == "gsm8k.md"
            paths = [c["metadata"]["headerPath"] for c in data["previewChunks"]]
            assert any("GSM8K Benchmark" in p for p in paths)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_without_magic_header_rejected_415(users):
    _, _, admin = users
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("fake.pdf", b"NOT-A-PDF-HEADER", "application/pdf")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_document_admin_ok_others_403(users):
    guest, google_user, admin = users
    doc_id = uuid4()

    mock_db = AsyncMock()
    mock_db.delete_document.return_value = True
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Guest 403
            app.dependency_overrides[get_current_user] = lambda: guest
            res_guest = await client.delete(
                f"/api/documents/{doc_id}",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res_guest.status_code == 403

            # Regular user 403
            app.dependency_overrides[get_current_user] = lambda: google_user
            res_user = await client.delete(
                f"/api/documents/{doc_id}",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res_user.status_code == 403

            # Admin 200
            app.dependency_overrides[get_current_user] = lambda: admin
            res_admin = await client.delete(
                f"/api/documents/{doc_id}",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res_admin.status_code == 200
            assert res_admin.json() == {"success": True, "id": str(doc_id)}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_document_deduplication_by_hash(users, monkeypatch):
    _, _, admin = users
    md_bytes = b"# Duplicate Benchmark\n\nContent identical to existing document."

    doc_id = uuid4()
    existing_doc = Document(
        id=doc_id,
        uploaded_by=admin.id,
        filename="existing.md",
        mime_type="text/markdown",
        sha256_hash="hash123",
        total_chunks=1,
    )
    existing_chunk = DocumentChunk(
        document_id=doc_id,
        chunk_index=0,
        content="Content identical to existing document.",
        metadata={"filename": "existing.md", "headerPath": ["Duplicate Benchmark"], "page": None},
    )

    mock_db = AsyncMock()
    mock_db.get_document_by_hash.return_value = existing_doc
    mock_db.get_document_chunks.return_value = [existing_chunk]
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: mock_db

    monkeypatch.setattr("app.routes.documents.default_embedding_service.api_key", "mock-key")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("dup.md", md_bytes, "text/markdown")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["document"]["id"] == str(doc_id)
            mock_db.create_document_with_chunks.assert_not_called()
    finally:
        app.dependency_overrides.clear()
