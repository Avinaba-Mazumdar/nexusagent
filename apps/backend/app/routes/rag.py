import logging
import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.access import require_document_access
from app.core.audit_log import default_audit_logger
from app.core.auth import get_client_ip, get_current_user
from app.core.rate_limiter import default_rate_limiter
from app.db.models import User, WireModel
from app.db.neon import NeonDatabase, get_db
from app.rag.hybrid_search import (
    DEFAULT_DENSE_WEIGHT,
    DEFAULT_RRF_K,
    DEFAULT_SPARSE_WEIGHT,
    HybridSearchEngine,
)

logger = logging.getLogger("nexusagent.routes.rag")

router = APIRouter(prefix="/rag", tags=["RAG Hybrid Search & Embeddings"])


class HybridSearchRequestWire(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query string for hybrid vector and lexical retrieval",
    )
    documentId: UUID | None = Field(
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
        DEFAULT_DENSE_WEIGHT,
        ge=0.0,
        le=1.0,
        description="Weight for dense vector cosine similarity rankings (0.0 to 1.0)",
    )
    sparseWeight: float = Field(
        DEFAULT_SPARSE_WEIGHT,
        ge=0.0,
        le=1.0,
        description="Weight for BM25 tsvector lexical rankings (0.0 to 1.0)",
    )
    rrfK: int = Field(
        DEFAULT_RRF_K,
        ge=1,
        le=200,
        description="Reciprocal Rank Fusion smoothing constant k (standard default: 60)",
    )


class HybridSearchResultWire(WireModel):
    id: str
    document_id: str
    chunk_index: int
    content: str
    filename: str
    similarity_score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    start_line: int | None = None
    end_line: int | None = None
    header_path: list[str] = Field(default_factory=list)
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

    # Validate input and tenancy before charging the quota.
    doc_uuid = payload.documentId
    if doc_uuid:
        await require_document_access(db, doc_uuid, current_user)

    await default_rate_limiter.check_and_consume(
        user_id=current_user.id,
        client_ip=client_ip,
        is_guest=current_user.is_guest,
    )

    engine = HybridSearchEngine(db=db)
    start_time = time.perf_counter()
    results = await engine.search(
        query=payload.query,
        user_id=current_user.id,
        document_id=doc_uuid,
        limit=payload.limit,
        dense_weight=payload.denseWeight,
        sparse_weight=payload.sparseWeight,
        rrf_k=payload.rrfK,
    )
    duration_ms = max(int((time.perf_counter() - start_time) * 1000), 0)
    await default_audit_logger.log_tool_audit(
        tool_name="hybrid_rag_search",
        input_args={"query": payload.query, "limit": payload.limit},
        output_summary={"results": len(results)},
        duration_ms=duration_ms,
        user_id=current_user.id,
        mcp_server="http-api",
    )

    wire_results = [HybridSearchResultWire.model_validate(r) for r in results]

    return HybridSearchResponseWire(
        query=payload.query,
        totalResults=len(wire_results),
        results=wire_results,
    )
