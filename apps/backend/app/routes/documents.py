import asyncio
import hashlib
import logging
import time
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.config import settings
from app.core.access import require_document_access
from app.core.audit_log import default_audit_logger
from app.core.auth import get_current_user, get_current_user_optional, require_admin
from app.db.models import (
    Document,
    DocumentChunkWire,
    DocumentListResponseWire,
    DocumentMetadataWire,
    DocumentUploadResponseWire,
    SuccessResponse,
    User,
)
from app.db.neon import NeonDatabase, get_db
from app.rag.embeddings import EmbeddingUnavailable, default_embedding_service
from app.rag.ingest import build_chunks

logger = logging.getLogger("nexusagent.documents")

router = APIRouter(prefix="/documents", tags=["Document Ingestion & Vault"])

# The extension decides the type; the client-supplied Content-Type is never trusted.
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}
MAX_FILENAME_CHARS = 200
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB per document


def safe_filename(raw: str | None) -> str:
    """Basename only, control characters stripped, capped to the DB column; never empty."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    if len(name) > MAX_FILENAME_CHARS:
        stem, dot, ext = name.rpartition(".")
        keep = MAX_FILENAME_CHARS - len(ext) - 1
        name = f"{stem[:keep]}.{ext}" if dot and keep > 0 else name[:MAX_FILENAME_CHARS]
    return name or "uploaded_document.md"


@router.get("", response_model=DocumentListResponseWire)
async def list_documents(
    _current_user: User | None = Depends(get_current_user_optional),
    db: NeonDatabase = Depends(get_db),
):
    """
    List all documents in the knowledge base.
    """
    docs = await db.list_all_documents()
    return DocumentListResponseWire(
        documents=[DocumentMetadataWire.model_validate(d) for d in docs]
    )


@router.get("/{document_id}/chunks/{chunk_id}", response_model=DocumentChunkWire)
async def get_document_chunk(
    document_id: UUID,
    chunk_id: UUID,
    _current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Fetch one chunk (the passage a citation points at) with its section metadata."""
    await require_document_access(db, document_id)
    chunk = await db.get_document_chunk(document_id, chunk_id)
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")
    return DocumentChunkWire.model_validate(chunk)


@router.delete("/{document_id}", response_model=SuccessResponse)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(require_admin),
    db: NeonDatabase = Depends(get_db),
):
    """Delete a document and its chunks (admin only)."""
    if not await db.delete_document(document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await default_audit_logger.log_tool_audit(
        tool_name="document_delete",
        input_args={"document_id": str(document_id)},
        output_summary={"deleted": True},
        duration_ms=1,
        user_id=current_user.id,
        mcp_server="http-api",
    )
    return {"success": True, "id": str(document_id)}


@router.post("/upload", response_model=DocumentUploadResponseWire)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: NeonDatabase = Depends(get_db),
):
    """
    Upload and parse PDF or markdown benchmark documents (admin only).
    Enforces file size ceiling (5MB), computes SHA-256 hash, runs LlamaIndex chunking,
    and batch persists document record and chunk rows into Neon PostgreSQL.
    """
    upload_started = time.perf_counter()
    filename = safe_filename(file.filename)
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and Markdown files (.pdf, .md, .markdown) are supported",
        )

    raw_bytes = await file.read(MAX_FILE_BYTES + 1)
    if len(raw_bytes) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_BYTES // (1024 * 1024)}MB",
        )

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if ext == ".pdf":
        if not raw_bytes.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File is not a valid PDF.",
            )
    else:
        try:
            content_text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            content_text = None
        if content_text is None or "\x00" in content_text:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File is not valid UTF-8 text.",
            )

    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    # Deduplication check: If same content was already uploaded
    existing_doc = await db.get_document_by_hash(sha256_hash)
    if existing_doc:
        existing_chunks = await db.get_document_chunks(existing_doc.id, limit=5)
        return DocumentUploadResponseWire(
            document=DocumentMetadataWire.model_validate(existing_doc),
            chunks_count=existing_doc.total_chunks,
            preview_chunks=[DocumentChunkWire.model_validate(c) for c in existing_chunks],
            quota_remaining=None,
        )

    if not default_embedding_service.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document ingestion is unavailable: embeddings are not configured.",
        )

    # 1. Parse document into hierarchical chunks off the event loop
    new_doc_id = uuid4()
    chunks = await asyncio.to_thread(build_chunks, raw_bytes, filename, new_doc_id)

    if len(chunks) > settings.MAX_CHUNKS_PER_DOCUMENT:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Document produced {len(chunks)} chunks, exceeding the maximum allowed limit of {settings.MAX_CHUNKS_PER_DOCUMENT}.",
        )

    try:
        # 2. Generate dense vector embeddings for all chunks
        if chunks:
            texts = [c.content for c in chunks]
            embeddings = await default_embedding_service.get_embeddings(texts)
            for chunk, emb in zip(chunks, embeddings):
                chunk.embedding = emb

        # 3. Persist Document record and chunks transactionally
        doc_record = Document(
            id=new_doc_id,
            uploaded_by=current_user.id,
            filename=filename,
            mime_type=ALLOWED_EXTENSIONS[ext],
            sha256_hash=sha256_hash,
            total_chunks=len(chunks),
            is_seeded=False,
        )
        saved_doc = await db.create_document_with_chunks(doc_record, chunks)
    except EmbeddingUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service is busy. Try again in a minute.",
            headers={"Retry-After": "30"},
        )

    await default_audit_logger.log_tool_audit(
        tool_name="document_upload",
        input_args={"filename": filename, "bytes": len(raw_bytes)},
        output_summary={"document_id": str(new_doc_id), "chunks": len(chunks)},
        duration_ms=max(int((time.perf_counter() - upload_started) * 1000), 1),
        user_id=current_user.id,
        mcp_server="http-api",
    )

    return DocumentUploadResponseWire(
        document=DocumentMetadataWire.model_validate(saved_doc),
        chunks_count=len(chunks),
        preview_chunks=[DocumentChunkWire.model_validate(c) for c in chunks[:5]],
        quota_remaining=None,
    )
