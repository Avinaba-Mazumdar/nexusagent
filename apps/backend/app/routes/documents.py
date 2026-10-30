import asyncio
import hashlib
import logging
import math
import time
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.config import settings
from app.core.access import require_document_access
from app.core.audit_log import default_audit_logger
from app.core.auth import get_client_ip, get_current_user, get_current_user_optional
from app.core.rate_limiter import default_rate_limiter
from app.db.models import (
    Document,
    DocumentChunk,
    DocumentChunkWire,
    DocumentListResponseWire,
    DocumentMetadataWire,
    DocumentUploadResponseWire,
    SuccessResponse,
    User,
)
from app.db.neon import DocumentLimitReached, NeonDatabase, get_db
from app.rag.embeddings import EmbeddingUnavailable, default_embedding_service
from app.rag.parser import default_markdown_parser

logger = logging.getLogger("nexusagent.documents")

router = APIRouter(prefix="/documents", tags=["Document Ingestion & Vault"])

# The extension decides the type; the client-supplied Content-Type is never trusted.
ALLOWED_EXTENSIONS = {".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain"}
MAX_FILENAME_CHARS = 200
MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB per document


def safe_filename(raw: str | None) -> str:
    """Basename only, control characters stripped, capped to the DB column; never empty."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    if len(name) > MAX_FILENAME_CHARS:
        stem, dot, ext = name.rpartition(".")
        keep = MAX_FILENAME_CHARS - len(ext) - 1
        name = f"{stem[:keep]}.{ext}" if dot and keep > 0 else name[:MAX_FILENAME_CHARS]
    return name or "uploaded_document.md"


def document_to_wire(d: Document) -> DocumentMetadataWire:
    return DocumentMetadataWire(
        id=str(d.id),
        userId=str(d.user_id) if d.user_id else None,
        filename=d.filename,
        mimeType=d.mime_type,
        sha256Hash=d.sha256_hash,
        totalChunks=d.total_chunks,
        isSeeded=d.is_seeded,
        uploadedAt=d.uploaded_at.isoformat(),
    )


def chunk_to_wire(c: DocumentChunk) -> DocumentChunkWire:
    return DocumentChunkWire(
        id=str(c.id),
        documentId=str(c.document_id),
        chunkIndex=c.chunk_index,
        content=c.content,
        metadata=c.metadata,
        createdAt=c.created_at.isoformat(),
    )


@router.get("", response_model=DocumentListResponseWire)
async def list_documents(
    current_user: User | None = Depends(get_current_user_optional),
    db: NeonDatabase = Depends(get_db),
):
    """
    List documents visible to the caller: seeded documents, plus the user's uploads if signed in.
    """
    docs = await db.list_all_documents(user_id=current_user.id if current_user else None)
    return {"documents": [document_to_wire(d) for d in docs]}


@router.get("/{document_id}/chunks/{chunk_id}", response_model=DocumentChunkWire)
async def get_document_chunk(
    document_id: UUID,
    chunk_id: UUID,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Fetch one chunk (the passage a citation points at) with its line-level section metadata."""
    await require_document_access(db, document_id, current_user)
    chunk = await db.get_document_chunk(document_id, chunk_id)
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")
    return chunk_to_wire(chunk)


@router.delete("/{document_id}", response_model=SuccessResponse)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Delete one of the caller's uploaded documents and its chunks."""
    if not await db.delete_user_document(current_user.id, document_id):
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
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """
    Upload and parse markdown or RFC documents.
    Enforces file size ceiling (1MB), computes SHA-256 hash, runs the markdown header parser,
    and batch persists document record and chunk rows into Neon PostgreSQL.
    """
    upload_started = time.perf_counter()
    client_ip = get_client_ip(request)
    filename = safe_filename(file.filename)
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only Markdown and RFC text files (.md, .markdown, .txt) are supported",
        )

    user_doc_count = await db.count_user_documents(current_user.id)
    if user_doc_count >= settings.MAX_DOCUMENTS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document limit reached ({settings.MAX_DOCUMENTS_PER_USER}). Delete a document first.",
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

    # Deduplication check: If same content was already uploaded by user
    existing_doc = await db.get_document_by_hash(sha256_hash, user_id=current_user.id)
    if existing_doc:
        existing_chunks = await db.get_document_chunks(existing_doc.id, limit=5)
        current_quota = await default_rate_limiter.get_quota(
            user_id=current_user.id, is_guest=current_user.is_guest
        )
        return DocumentUploadResponseWire(
            document=document_to_wire(existing_doc),
            chunksCount=existing_doc.total_chunks,
            previewChunks=[chunk_to_wire(c) for c in existing_chunks],
            quotaRemaining=current_quota,
        )

    if not default_embedding_service.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document ingestion is unavailable: embeddings are not configured.",
        )

    # 1. Parse document into hierarchical chunks off the event loop
    new_doc_id = uuid4()
    chunks = await asyncio.to_thread(
        default_markdown_parser.parse_markdown,
        markdown_text=content_text,
        document_id=new_doc_id,
        extra_metadata={"filename": filename},
    )

    if len(chunks) > settings.MAX_CHUNKS_PER_DOCUMENT:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Document produced {len(chunks)} chunks, exceeding the maximum allowed limit of {settings.MAX_CHUNKS_PER_DOCUMENT}.",
        )

    # Charge quota proportional to chunk count
    cost = max(1, math.ceil(len(chunks) / 100))
    remaining_quota = await default_rate_limiter.check_and_consume(
        user_id=current_user.id,
        client_ip=client_ip,
        is_guest=current_user.is_guest,
        cost=cost,
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
            user_id=current_user.id,
            filename=filename,
            mime_type=ALLOWED_EXTENSIONS[ext],
            sha256_hash=sha256_hash,
            total_chunks=len(chunks),
            is_seeded=False,
        )
        saved_doc = await db.create_document_with_chunks(doc_record, chunks)
    except EmbeddingUnavailable:
        await default_rate_limiter.refund(current_user.id, cost)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service is busy. Nothing was charged; try again in a minute.",
            headers={"Retry-After": "30"},
        )
    except DocumentLimitReached:
        await default_rate_limiter.refund(current_user.id, cost)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document limit reached ({settings.MAX_DOCUMENTS_PER_USER}). Delete a document first.",
        )
    except Exception:
        await default_rate_limiter.refund(current_user.id, cost)
        raise

    await default_audit_logger.log_tool_audit(
        tool_name="document_upload",
        input_args={"filename": filename, "bytes": len(raw_bytes)},
        output_summary={"document_id": str(new_doc_id), "chunks": len(chunks)},
        duration_ms=max(int((time.perf_counter() - upload_started) * 1000), 1),
        user_id=current_user.id,
        mcp_server="http-api",
    )

    return DocumentUploadResponseWire(
        document=document_to_wire(saved_doc),
        chunksCount=len(chunks),
        previewChunks=[chunk_to_wire(c) for c in chunks[:5]],
        quotaRemaining=remaining_quota,
    )
