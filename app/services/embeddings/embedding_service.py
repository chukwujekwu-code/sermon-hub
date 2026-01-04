"""Embedding service using FastEmbed (ONNX-based)."""

from typing import Any

import structlog
from fastembed import TextEmbedding

from app.core.config import settings

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using FastEmbed."""

    def __init__(self):
        """Initialize the embedding service."""
        self._model: TextEmbedding | None = None

    @property
    def model(self) -> TextEmbedding:
        """Get the embedding model, loading if needed."""
        if self._model is None:
            logger.info("loading_embedding_model", model=settings.embedding_model)
            self._model = TextEmbedding(model_name=settings.embedding_model)
            logger.info("embedding_model_loaded", model=settings.embedding_model)
        return self._model

    def embed_sync(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings synchronously.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = list(self.model.embed(texts))
        return [emb.tolist() for emb in embeddings]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings asynchronously.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        # FastEmbed is already lightweight, run directly
        return self.embed_sync(texts)

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
