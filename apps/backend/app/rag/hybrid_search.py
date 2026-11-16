import asyncio
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.neon import NeonDatabase, neon_db
from app.rag.embeddings import EmbeddingService, default_embedding_service

logger = logging.getLogger("nexusagent.rag.hybrid_search")


class HybridSearchResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

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
    page: int | None = None
    header_path: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


DEFAULT_DENSE_WEIGHT = 0.5
DEFAULT_SPARSE_WEIGHT = 0.5
DEFAULT_RRF_K = 60


Candidate = Mapping[str, object]
"""One row from ``search_chunks_dense`` or ``search_chunks_lexical``."""


@dataclass
class _Fused:
    """A candidate's combined Reciprocal Rank Fusion score and its rank in each list."""

    item: Candidate
    rrf_score: float = 0.0
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None
    sparse_score: float | None = None


def _number(value: object) -> float:
    return float(value) if isinstance(value, int | float | Decimal) else 0.0


def _accumulate(
    scores: dict[str, _Fused],
    items: Sequence[Candidate],
    weight: float,
    rrf_k: int,
    kind: Literal["dense", "sparse"],
    score_field: str,
) -> None:
    """Add one ranking's RRF contribution to ``scores``."""
    for rank, item in enumerate(items, start=1):
        entry = scores.setdefault(str(item["id"]), _Fused(item=item))
        entry.rrf_score += weight / (rrf_k + rank)
        score = _number(item.get(score_field))
        if kind == "dense":
            entry.dense_rank, entry.dense_score = rank, score
        else:
            entry.sparse_rank, entry.sparse_score = rank, score


def _metadata(item: Candidate) -> dict[str, object]:
    """The chunk's metadata, stored as JSON text or already decoded."""
    meta = item.get("metadata")
    if isinstance(meta, str):
        try:
            meta = cast(object, json.loads(meta))
        except json.JSONDecodeError, TypeError, ValueError:
            meta = None
    return dict(cast(dict[str, object], meta)) if isinstance(meta, dict) else {}


def _header_path(meta: Mapping[str, object]) -> list[str]:
    # The parser writes camelCase metadata keys only.
    header_path = meta.get("headerPath")
    if isinstance(header_path, str):
        return [header_path]
    if isinstance(header_path, list):
        return [str(h) for h in cast(list[object], header_path)]
    return []


def compute_rrf(
    dense_results: Sequence[Candidate],
    sparse_results: Sequence[Candidate],
    dense_weight: float = DEFAULT_DENSE_WEIGHT,
    sparse_weight: float = DEFAULT_SPARSE_WEIGHT,
    rrf_k: int = DEFAULT_RRF_K,
    limit: int = 5,
) -> list[HybridSearchResult]:
    """
    Reciprocal Rank Fusion (RRF) algorithm combining dense vector and full-text keyword rankings.

    Formula:
        RRF_Score(d) = (w_dense / (k + rank_dense(d))) + (w_sparse / (k + rank_sparse(d)))

    Args:
        dense_results: Ordered list of dense cosine similarity candidate dicts.
        sparse_results: Ordered list of full-text ts_rank candidate dicts.
        dense_weight: Multiplier weight for dense vector rankings.
        sparse_weight: Multiplier weight for sparse lexical rankings.
        rrf_k: Smoothing parameter constant.
        limit: Top-K items to return after fusion.
    """
    scores: dict[str, _Fused] = {}
    _accumulate(scores, dense_results, dense_weight, rrf_k, "dense", "similarity")
    _accumulate(scores, sparse_results, sparse_weight, rrf_k, "sparse", "rank_score")

    ranked = sorted(scores.values(), key=lambda entry: entry.rrf_score, reverse=True)

    results: list[HybridSearchResult] = []
    for entry in ranked[:limit]:
        item = entry.item
        meta = _metadata(item)
        results.append(
            HybridSearchResult.model_validate(
                {
                    "id": str(item["id"]),
                    "document_id": str(item["document_id"]),
                    "chunk_index": item.get("chunk_index", 0),
                    "content": str(item.get("content", "")),
                    "filename": str(item.get("filename", "")),
                    "similarity_score": round(entry.rrf_score, 6),
                    "dense_rank": entry.dense_rank,
                    "sparse_rank": entry.sparse_rank,
                    "dense_score": None
                    if entry.dense_score is None
                    else round(entry.dense_score, 4),
                    "sparse_score": None
                    if entry.sparse_score is None
                    else round(entry.sparse_score, 4),
                    "page": meta.get("page"),
                    "header_path": _header_path(meta),
                    "metadata": meta,
                }
            )
        )

    return results


class HybridSearchEngine:
    """
    Hybrid Search Engine coordinating dense vector embedding search and
    Postgres full-text tsvector search (ts_rank_cd) with Reciprocal Rank Fusion.
    """

    def __init__(
        self,
        db: NeonDatabase | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.db: NeonDatabase = db or neon_db
        self.embedding_service: EmbeddingService = embedding_service or default_embedding_service

    async def search(
        self,
        query: str,
        document_id: UUID | None = None,
        limit: int = 5,
        dense_weight: float = DEFAULT_DENSE_WEIGHT,
        sparse_weight: float = DEFAULT_SPARSE_WEIGHT,
        rrf_k: int = DEFAULT_RRF_K,
        candidate_pool_multiplier: int = 3,
        use_embeddings: bool = True,
    ) -> list[HybridSearchResult]:
        """
        Execute parallel hybrid search across dense embeddings and lexical tsvector indexes.

        ``use_embeddings`` is false when the caller has spent its embedding budget. Retrieval
        then uses the lexical index only.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        if not self.db or not self.db.pool:
            raise RuntimeError("Knowledge base unavailable: database not connected")

        candidate_limit = max(limit * candidate_pool_multiplier, 15)

        async def dense() -> list[dict[str, object]]:
            if not use_embeddings:
                return []
            try:
                embedding = await self.embedding_service.get_embedding(clean_query)
            except RuntimeError as exc:
                # Degrade to lexical-only retrieval rather than failing the whole request.
                logger.warning("Dense retrieval skipped, embedding failed: %s", exc)
                return []
            return await self.db.search_chunks_dense(
                query_embedding=embedding,
                document_id=document_id,
                limit=candidate_limit,
            )

        dense_candidates, sparse_candidates = await asyncio.gather(
            dense(),
            self.db.search_chunks_lexical(
                query=clean_query,
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
