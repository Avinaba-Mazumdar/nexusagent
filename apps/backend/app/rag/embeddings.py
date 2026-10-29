import logging
from collections.abc import Sequence

import httpx

from app.config import settings

logger = logging.getLogger("nexusagent.rag.embeddings")

EMBEDDING_DIMENSION = 768
GEMINI_EMBED_MODELS = ["gemini-embedding-001", "gemini-embedding-2", "text-embedding-004"]
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class EmbeddingService:
    """
    Embedding generation service supporting Google Gemini embeddings (768-d)
    with graceful fallback between gemini-embedding-001 and gemini-embedding-2.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.dimension = EMBEDDING_DIMENSION
        self.active_model = GEMINI_EMBED_MODELS[0]

    async def get_embedding(self, text: str) -> list[float]:
        """Generate a 768-d dense embedding for a single text chunk."""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]

    async def get_embeddings(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Generate 768-d dense embeddings for a batch of text strings via Google Gemini API.
        Processes in slices of 100.
        """
        if not texts:
            return []

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured for EmbeddingService.")

        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for start in range(0, len(texts), 100):
                slice_texts = texts[start : start + 100]
                slice_embeddings = None
                last_error = None

                models_to_try = [self.active_model] + [m for m in GEMINI_EMBED_MODELS if m != self.active_model]

                for model_name in models_to_try:
                    try:
                        url = f"{GEMINI_API_URL}/{model_name}:batchEmbedContents"
                        headers = {"x-goog-api-key": self.api_key}
                        requests_payload = [
                            {
                                "model": f"models/{model_name}",
                                "content": {"parts": [{"text": t[:2048]}]},
                                "outputDimensionality": self.dimension,
                            }
                            for t in slice_texts
                        ]
                        response = await client.post(url, headers=headers, json={"requests": requests_payload})
                        if response.status_code == 200:
                            data = response.json()
                            embeddings = [item["values"] for item in data.get("embeddings", [])]
                            if len(embeddings) == len(slice_texts):
                                self.active_model = model_name
                                slice_embeddings = embeddings
                                break
                        last_error = f"Gemini embedding API ({model_name}) status {response.status_code}"
                        if response.status_code != 404:
                            break
                    except Exception:  # noqa: BLE001
                        last_error = f"Connection error ({model_name})"

                if slice_embeddings is None:
                    logger.error(f"Error calling Gemini Embedding API: {last_error}")
                    raise RuntimeError("Gemini embedding provider unavailable")

                all_embeddings.extend(slice_embeddings)

        return all_embeddings


default_embedding_service = EmbeddingService()
