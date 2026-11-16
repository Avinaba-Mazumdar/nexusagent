import io
from datetime import UTC, datetime
from typing import override
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.core.auth import get_current_user
from app.db.models import Document, DocumentChunk, DocumentUploadResponseWire, User
from app.db.neon import NeonDatabase, get_db
from app.main import app

type Users = tuple[User, User, User]
"""(guest, Google user, admin)"""


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
    _ = writer.write(buf)
    return buf.getvalue()


class _FakeDocumentsDb(NeonDatabase):
    """The document methods of NeonDatabase, in memory. ``existing`` is a stored duplicate."""

    def __init__(
        self, existing: Document | None = None, existing_chunks: list[DocumentChunk] | None = None
    ) -> None:
        super().__init__(dsn="")
        self.existing: Document | None = existing
        self.existing_chunks: list[DocumentChunk] = existing_chunks or []
        self.created: list[Document] = []
        self.deleted: list[UUID] = []

    @override
    async def get_document_by_hash(self, sha256_hash: str) -> Document | None:
        return self.existing

    @override
    async def get_document_chunks(
        self, document_id: UUID, limit: int | None = None
    ) -> list[DocumentChunk]:
        return self.existing_chunks[:limit]

    @override
    async def create_document_with_chunks(
        self, document: Document, chunks: list[DocumentChunk]
    ) -> Document:
        self.created.append(document)
        return document

    @override
    async def delete_document(self, document_id: UUID) -> bool:
        self.deleted.append(document_id)
        return True


@pytest.fixture
def users() -> Users:
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


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_guest_upload_is_forbidden_403(users: Users):
    guest, _, _ = users
    app.dependency_overrides[get_current_user] = lambda: guest
    try:
        async with _client() as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("bench.md", b"# Benchmark\nContent", "text/markdown")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_regular_google_user_upload_is_forbidden_403(users: Users):
    _, google_user, _ = users
    app.dependency_overrides[get_current_user] = lambda: google_user
    try:
        async with _client() as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("bench.md", b"# Benchmark\nContent", "text/markdown")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_can_upload_pdf_and_gets_chunks(users: Users, monkeypatch: pytest.MonkeyPatch):
    _, _, admin = users
    pdf_bytes = _create_sample_pdf("MMLU evaluation scores for Gemini Flash.")

    db = _FakeDocumentsDb()
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: db

    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.api_key",
        "mock-key",
    )
    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.get_embeddings",
        AsyncMock(return_value=[[0.1] * 768]),
    )

    try:
        async with _client() as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("mmlu.pdf", pdf_bytes, "application/pdf")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 200
            data = DocumentUploadResponseWire.model_validate_json(res.content)
            assert data.chunks_count >= 1
            assert data.document.filename == "mmlu.pdf"
            assert data.preview_chunks[0].metadata["page"] == 1
            assert len(db.created) == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_can_upload_markdown(users: Users, monkeypatch: pytest.MonkeyPatch):
    _, _, admin = users
    md_bytes = (
        b"# GSM8K Benchmark\n\n"
        + b"Introduction to math benchmarks.\n\n"
        + b"## Math Reasoning\n\n"
        + b"GSM8K evaluates multi-step mathematical reasoning."
    )

    db = _FakeDocumentsDb()
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: db

    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.api_key",
        "mock-key",
    )
    monkeypatch.setattr(
        "app.routes.documents.default_embedding_service.get_embeddings",
        AsyncMock(return_value=[[0.1] * 768, [0.1] * 768]),
    )

    try:
        async with _client() as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("gsm8k.md", md_bytes, "text/markdown")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 200
            data = DocumentUploadResponseWire.model_validate_json(res.content)
            assert data.chunks_count >= 1
            assert data.document.filename == "gsm8k.md"
            paths = [c.metadata["headerPath"] for c in data.preview_chunks]
            assert any(isinstance(p, list) and "GSM8K Benchmark" in p for p in paths)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_without_magic_header_rejected_415(users: Users):
    _, _, admin = users
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        async with _client() as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("fake.pdf", b"NOT-A-PDF-HEADER", "application/pdf")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_document_admin_ok_others_403(users: Users):
    guest, google_user, admin = users
    doc_id = uuid4()

    db = _FakeDocumentsDb()
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with _client() as client:
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
            assert db.deleted == [doc_id]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_document_deduplication_by_hash(users: Users, monkeypatch: pytest.MonkeyPatch):
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

    db = _FakeDocumentsDb(existing=existing_doc, existing_chunks=[existing_chunk])
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: db

    monkeypatch.setattr("app.routes.documents.default_embedding_service.api_key", "mock-key")

    try:
        async with _client() as client:
            res = await client.post(
                "/api/documents/upload",
                files={"file": ("dup.md", md_bytes, "text/markdown")},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 200
            data = DocumentUploadResponseWire.model_validate_json(res.content)
            assert data.document.id == str(doc_id)
            assert db.created == []
    finally:
        app.dependency_overrides.clear()
