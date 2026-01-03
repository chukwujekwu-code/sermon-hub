"""Embedding service using sentence-transformers."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = structlog.get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


class EmbeddingService:
    """Service for generating text embeddings."""

    def __init__(self):
        """Initialize the embedding service."""
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        """Get the embedding model, loading if needed."""
        if self._model is None:
            logger.info("loading_embedding_model", model=settings.embedding_model)
            self._model = SentenceTransformer(settings.embedding_model)
            logger.info("embedding_model_loaded", model=settings.embedding_model)
        return self._model

    def embed_sync(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings synchronously.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 10,
        )
        return embeddings.tolist()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings asynchronously.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, self.embed_sync, texts)
        return result

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embeddings = await self.embed([text])
        return embeddings[0]

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the embedding model."""
        return {
            "model_name": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "loaded": self._model is not None,
        }


# Global instance
embedding_service = EmbeddingService()
