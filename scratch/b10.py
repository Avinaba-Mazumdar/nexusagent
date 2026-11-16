import os

from ed import ROOT, rep

H = "app/rag/hybrid_search.py"
p = os.path.join(ROOT, H)
raw = open(p, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
start = s.index("def _accumulate(")
end = s.index("class HybridSearchEngine:")
new_block = '''Candidate = Mapping[str, object]
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
                    "dense_score": None if entry.dense_score is None else round(entry.dense_score, 4),
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


'''
s = s[:start] + new_block + s[end:]
open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)

rep(H, "from typing import Any, ClassVar\n", "from collections.abc import Mapping, Sequence\nfrom dataclasses import dataclass\nfrom decimal import Decimal\nfrom typing import ClassVar, Literal, cast\n")
rep(H, "    metadata: dict[str, Any] = Field(default_factory=dict)", "    metadata: dict[str, object] = Field(default_factory=dict)")
rep(
    H,
    """        self.db = db or neon_db
        self.embedding_service = embedding_service or default_embedding_service""",
    """        self.db: NeonDatabase = db or neon_db
        self.embedding_service: EmbeddingService = embedding_service or default_embedding_service""",
)
rep(H, "        async def dense() -> list[dict]:", "        async def dense() -> list[dict[str, object]]:")
print("ok")
