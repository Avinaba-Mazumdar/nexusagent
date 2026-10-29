import asyncio
import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.neon import NeonDatabase, neon_db
from app.rag.embeddings import EmbeddingService, default_embedding_service

logger = logging.getLogger("nexusagent.rag.hybrid_search")


class HybridSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    chunk_index: int
    content: str
    filename: str
    similarity_score: float = Field(
        description="Reciprocal Rank Fusion (RRF) combined relevance score"
    )
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    start_line: int | None = None
    end_line: int | None = None
    header_path: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def compute_rrf(
    dense_results: list[dict],
    sparse_results: list[dict],
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
    rrf_k: int = 60,
    limit: int = 5,
) -> list[HybridSearchResult]:
    """
    Reciprocal Rank Fusion (RRF) algorithm combining dense vector and BM25 full-text rankings.

    Formula:
        RRF_Score(d) = (w_dense / (k + rank_dense(d))) + (w_sparse / (k + rank_sparse(d)))

    Args:
        dense_results: Ordered list of dense cosine similarity candidate dicts.
        sparse_results: Ordered list of full-text ts_rank candidate dicts.
        dense_weight: Multiplier weight for dense vector rankings (default 0.5).
        sparse_weight: Multiplier weight for sparse lexical rankings (default 0.5).
        rrf_k: Smoothing parameter constant (default 60).
        limit: Top-K items to return after fusion.
    """
    scores: dict[str, dict[str, Any]] = {}

    # 1. Process dense rankings
    for rank_idx, item in enumerate(dense_results, start=1):
        cid = str(item["id"])
        score_contrib = dense_weight / (rrf_k + rank_idx)
        if cid not in scores:
            scores[cid] = {
                "item": item,
                "rrf_score": score_contrib,
                "dense_rank": rank_idx,
                "sparse_rank": None,
                "dense_score": float(item.get("similarity", 0.0) or 0.0),
                "sparse_score": None,
            }
        else:
            scores[cid]["rrf_score"] += score_contrib
            scores[cid]["dense_rank"] = rank_idx
            scores[cid]["dense_score"] = float(item.get("similarity", 0.0) or 0.0)

    # 2. Process sparse rankings
    for rank_idx, item in enumerate(sparse_results, start=1):
        cid = str(item["id"])
        score_contrib = sparse_weight / (rrf_k + rank_idx)
        if cid not in scores:
            scores[cid] = {
                "item": item,
                "rrf_score": score_contrib,
                "dense_rank": None,
                "sparse_rank": rank_idx,
                "dense_score": None,
                "sparse_score": float(item.get("rank_score", 0.0) or 0.0),
            }
        else:
            scores[cid]["rrf_score"] += score_contrib
            scores[cid]["sparse_rank"] = rank_idx
            scores[cid]["sparse_score"] = float(item.get("rank_score", 0.0) or 0.0)

    # 3. Sort by combined RRF score descending
    sorted_items = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)

    results: list[HybridSearchResult] = []
    for entry in sorted_items[:limit]:
        raw_item = entry["item"]
        meta = raw_item.get("metadata") or {}
        if isinstance(meta, str):
            import json

            try:
                meta = json.loads(meta)
            except json.JSONDecodeError, TypeError, ValueError:
                meta = {}

        header_path = meta.get("header_path") or meta.get("headerPath") or []
        if isinstance(header_path, str):
            header_path = [header_path]
        start_line = meta.get("start_line", meta.get("startLine"))
        end_line = meta.get("end_line", meta.get("endLine"))

        results.append(
            HybridSearchResult(
                id=str(raw_item["id"]),
                document_id=str(raw_item["document_id"]),
                chunk_index=int(raw_item.get("chunk_index", 0)),
                content=str(raw_item.get("content", "")),
                filename=str(raw_item.get("filename", "")),
                similarity_score=round(entry["rrf_score"], 6),
                dense_rank=entry["dense_rank"],
                sparse_rank=entry["sparse_rank"],
                dense_score=round(entry["dense_score"], 4)
                if entry["dense_score"] is not None
                else None,
                sparse_score=round(entry["sparse_score"], 4)
                if entry["sparse_score"] is not None
                else None,
                start_line=start_line,
                end_line=end_line,
                header_path=header_path,
                metadata=meta,
            )
        )

    return results


class HybridSearchEngine:
    """
    Hybrid Search Engine coordinating dense vector embedding search and
    Postgres BM25 full-text tsvector search with Reciprocal Rank Fusion.
    """

    def __init__(
        self,
        db: NeonDatabase | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.db = db or neon_db
        self.embedding_service = embedding_service or default_embedding_service

    async def search(
        self,
        query: str,
        user_id: UUID | None = None,
        document_id: UUID | None = None,
        limit: int = 5,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
        rrf_k: int = 60,
        candidate_pool_multiplier: int = 3,
    ) -> list[HybridSearchResult]:
        """
        Execute parallel hybrid search across dense embeddings and lexical tsvector indexes.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        if not self.db or not self.db.pool:
            raise RuntimeError("Knowledge base unavailable: database not connected")

        candidate_limit = max(limit * candidate_pool_multiplier, 15)

        async def dense() -> list[dict]:
            try:
                embedding = await self.embedding_service.get_embedding(clean_query)
            except RuntimeError as exc:
                # Degrade to lexical-only retrieval rather than failing the whole request.
                logger.warning("Dense retrieval skipped, embedding failed: %s", exc)
                return []
            return await self.db.search_chunks_dense(
                query_embedding=embedding,
                user_id=user_id,
                document_id=document_id,
                limit=candidate_limit,
            )

        dense_candidates, sparse_candidates = await asyncio.gather(
            dense(),
            self.db.search_chunks_lexical(
                query=clean_query,
                user_id=user_id,
                document_id=document_id,
                limit=candidate_limit,
            ),
        )

        # Fuse rankings using Reciprocal Rank Fusion
        fused = compute_rrf(
            dense_results=dense_candidates,
            sparse_results=sparse_candidates,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            rrf_k=rrf_k,
            limit=limit,
        )

        return fused


default_hybrid_search_engine = HybridSearchEngine()
