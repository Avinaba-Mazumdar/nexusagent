import asyncio
import logging
from collections.abc import Sequence

import httpx

from app.config import settings

logger = logging.getLogger("nexusagent.rag.embeddings")

EMBEDDING_DIMENSION = 768
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
BATCH_SIZE = 100
# Backoff before retry 1 and 2 (the free tier rate-limits embeddings routinely).
RETRY_DELAYS = (0.5, 1.5)
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class EmbeddingUnavailable(RuntimeError):
    """The embedding provider failed (or is rate limiting) and the request can be retried later."""


class EmbeddingService:
    """Gemini embedding client pinned to one model so every stored vector shares a vector space."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.dimension = EMBEDDING_DIMENSION
        self.model = settings.EMBEDDING_MODEL
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post_with_retry(
        self, url: str, headers: dict[str, str], payload: dict
    ) -> httpx.Response:
        client = self._get_client()
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                logger.error("Gemini embedding connection error (%s): %s", self.model, exc)
                raise EmbeddingUnavailable("Gemini embedding provider unavailable") from exc
            if response.status_code not in RETRYABLE_STATUS or attempt == len(RETRY_DELAYS):
                return response
            logger.warning(
                "Gemini embedding API (%s) status %s, retrying", self.model, response.status_code
            )
            await asyncio.sleep(RETRY_DELAYS[attempt])
        raise AssertionError("unreachable")  # pragma: no cover

    async def get_embedding(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
        """Generate a 768-d dense embedding for a single query string."""
        embeddings = await self.get_embeddings([text], task_type=task_type)
        return embeddings[0]

    async def get_embeddings(
        self, texts: Sequence[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """Generate 768-d embeddings in slices of 100. Raises EmbeddingUnavailable on provider failure."""
        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured for EmbeddingService.")

        url = f"{GEMINI_API_URL}/{self.model}:batchEmbedContents"
        headers = {"x-goog-api-key": self.api_key}
        all_embeddings: list[list[float]] = []

        for start in range(0, len(texts), BATCH_SIZE):
            slice_texts = texts[start : start + BATCH_SIZE]
            requests_payload = [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": t[:2048]}]},
                    "taskType": task_type,
                    "outputDimensionality": self.dimension,
                }
                for t in slice_texts
            ]
            response = await self._post_with_retry(url, headers, {"requests": requests_payload})

            if response.status_code != 200:
                logger.error(
                    "Gemini embedding API (%s) status %s", self.model, response.status_code
                )
                raise EmbeddingUnavailable("Gemini embedding provider unavailable")

            embeddings = [item["values"] for item in response.json().get("embeddings", [])]
            if len(embeddings) != len(slice_texts):
                logger.error("Gemini embedding API (%s) returned a short batch", self.model)
                raise EmbeddingUnavailable("Gemini embedding provider unavailable")
            all_embeddings.extend(embeddings)

        return all_embeddings


default_embedding_service = EmbeddingService()
