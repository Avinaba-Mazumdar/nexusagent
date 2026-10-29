import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.auth import get_client_ip, get_current_user
from app.core.rate_limiter import default_rate_limiter
from app.db.models import User
from app.db.neon import NeonDatabase, get_db
from app.rag.hybrid_search import HybridSearchEngine

logger = logging.getLogger("nexusagent.routes.rag")

router = APIRouter(prefix="/rag", tags=["RAG Hybrid Search & Embeddings"])


class HybridSearchRequestWire(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query string for hybrid vector and lexical retrieval",
    )
    documentId: str | None = Field(
        None,
        description="Optional document UUID filter to restrict search to a single file",
    )
    limit: int = Field(
        5,
        ge=1,
        le=50,
        description="Maximum number of top-K results to return after RRF fusion",
    )
    denseWeight: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Weight for dense vector cosine similarity rankings (0.0 to 1.0)",
    )
    sparseWeight: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Weight for BM25 tsvector lexical rankings (0.0 to 1.0)",
    )
    rrfK: int = Field(
        60,
        ge=1,
        le=200,
        description="Reciprocal Rank Fusion smoothing constant k (standard default: 60)",
    )


class HybridSearchResultWire(BaseModel):
    id: str
    documentId: str
    chunkIndex: int
    content: str
    filename: str
    similarityScore: float
    denseRank: int | None = None
    sparseRank: int | None = None
    denseScore: float | None = None
    sparseScore: float | None = None
    startLine: int | None = None
    endLine: int | None = None
    headerPath: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridSearchResponseWire(BaseModel):
    query: str
    totalResults: int
    results: list[HybridSearchResultWire]


@router.post("/search", response_model=HybridSearchResponseWire)
async def hybrid_search_documents(
    payload: HybridSearchRequestWire,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """
    Execute hybrid dense (pgvector HNSW) and sparse (BM25 tsvector GIN) search
    with Reciprocal Rank Fusion (RRF) re-ranking. Metered by token bucket rate limiter.
    """
    client_ip = get_client_ip(request)

    await default_rate_limiter.check_and_consume(
        user_id=current_user.id,
        client_ip=client_ip,
        is_guest=current_user.is_guest,
    )
    doc_uuid: UUID | None = None
    if payload.documentId:
        try:
            doc_uuid = UUID(payload.documentId)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid documentId format",
            )

        # Validate tenancy if documentId is provided
        doc = await db.get_document_by_id(doc_uuid)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target document not found",
            )
        if not doc.is_seeded and doc.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to target document",
            )

    engine = HybridSearchEngine(db=db)
    results = await engine.search(
        query=payload.query,
        user_id=current_user.id,
        document_id=doc_uuid,
        limit=payload.limit,
        dense_weight=payload.denseWeight,
        sparse_weight=payload.sparseWeight,
        rrf_k=payload.rrfK,
    )

    wire_results = [
        HybridSearchResultWire(
            id=r.id,
            documentId=r.document_id,
            chunkIndex=r.chunk_index,
            content=r.content,
            filename=r.filename,
            similarityScore=r.similarity_score,
            denseRank=r.dense_rank,
            sparseRank=r.sparse_rank,
            denseScore=r.dense_score,
            sparseScore=r.sparse_score,
            startLine=r.start_line,
            endLine=r.end_line,
            headerPath=r.header_path,
            metadata=r.metadata,
        )
        for r in results
    ]

    return HybridSearchResponseWire(
        query=payload.query,
        totalResults=len(wire_results),
        results=wire_results,
    )
