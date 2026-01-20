"""Embedding service using Cohere API."""

from typing import Any, Literal

import cohere
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Cohere batch limit
MAX_BATCH_SIZE = 96


class EmbeddingService:
    """Service for generating text embeddings using Cohere API."""

    def __init__(self):
        """Initialize the embedding service."""
        self._client: cohere.AsyncClient | None = None

    @property
    def client(self) -> cohere.AsyncClient:
        """Get the Cohere client, creating if needed."""
        if self._client is None:
            if not settings.cohere_api_key:
                raise ValueError("COHERE_API_KEY is not configured")
            logger.info("initializing_cohere_client")
            self._client = cohere.AsyncClient(api_key=settings.cohere_api_key)
        return self._client

    async def embed(
        self,
        texts: list[str],
        input_type: Literal["search_document", "search_query"] = "search_document",
    ) -> list[list[float]]:
        """Generate embeddings asynchronously.

        Args:
            texts: List of texts to embed
            input_type: Type of input - "search_document" for indexing,
                       "search_query" for queries

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Process in batches
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]
            logger.debug(
                "embedding_batch",
                batch_num=i // MAX_BATCH_SIZE + 1,
                batch_size=len(batch),
            )

            response = await self.client.embed(
                texts=batch,
                model=settings.embedding_model,
                input_type=input_type,
                embedding_types=["float"],
            )

            # Extract float embeddings
            embeddings = response.embeddings
            if embeddings is not None and hasattr(embeddings, "float_"):
                float_embeddings = embeddings.float_
                if float_embeddings:
                    all_embeddings.extend(float_embeddings)

        return all_embeddings

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents for indexing.

        Args:
            texts: List of document texts to embed

        Returns:
            List of embedding vectors
        """
        return await self.embed(texts, input_type="search_document")

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query for search.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector
        """
        embeddings = await self.embed([text], input_type="search_query")
        return embeddings[0] if embeddings else []

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text (alias for embed_query).

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        return await self.embed_query(text)

    def embed_sync(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings synchronously (for backwards compatibility).

        Note: This creates a new sync client for each call. Prefer async methods.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        if not settings.cohere_api_key:
            raise ValueError("COHERE_API_KEY is not configured")

        sync_client = cohere.Client(api_key=settings.cohere_api_key)
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]

            response = sync_client.embed(
                texts=batch,
                model=settings.embedding_model,
                input_type="search_document",
                embedding_types=["float"],
            )

            embeddings = response.embeddings
            if embeddings is not None and hasattr(embeddings, "float_"):
                float_embeddings = embeddings.float_
                if float_embeddings:
                    all_embeddings.extend(float_embeddings)

        return all_embeddings

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the embedding model."""
        return {
            "provider": "cohere",
            "model_name": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "initialized": self._client is not None,
        }


# Global instance
embedding_service = EmbeddingService()
