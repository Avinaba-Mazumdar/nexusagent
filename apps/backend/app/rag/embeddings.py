import logging
from collections.abc import Sequence

import httpx

from app.config import settings

logger = logging.getLogger("nexusagent.rag.embeddings")

EMBEDDING_DIMENSION = 768
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
BATCH_SIZE = 100


class EmbeddingService:
    """Gemini embedding client pinned to one model so every stored vector shares a vector space."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.dimension = EMBEDDING_DIMENSION
        self.model = settings.EMBEDDING_MODEL

    async def get_embedding(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
        """Generate a 768-d dense embedding for a single query string."""
        embeddings = await self.get_embeddings([text], task_type=task_type)
        return embeddings[0]

    async def get_embeddings(
        self, texts: Sequence[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """Generate 768-d embeddings in slices of 100. Raises RuntimeError on any failure."""
        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured for EmbeddingService.")

        url = f"{GEMINI_API_URL}/{self.model}:batchEmbedContents"
        headers = {"x-goog-api-key": self.api_key}
        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
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
                try:
                    response = await client.post(
                        url, headers=headers, json={"requests": requests_payload}
                    )
                except httpx.HTTPError as exc:
                    logger.error("Gemini embedding connection error (%s): %s", self.model, exc)
                    raise RuntimeError("Gemini embedding provider unavailable") from exc

                if response.status_code != 200:
                    logger.error(
                        "Gemini embedding API (%s) status %s", self.model, response.status_code
                    )
                    raise RuntimeError("Gemini embedding provider unavailable")

                embeddings = [item["values"] for item in response.json().get("embeddings", [])]
                if len(embeddings) != len(slice_texts):
                    logger.error("Gemini embedding API (%s) returned a short batch", self.model)
                    raise RuntimeError("Gemini embedding provider unavailable")
                all_embeddings.extend(embeddings)

        return all_embeddings


default_embedding_service = EmbeddingService()
