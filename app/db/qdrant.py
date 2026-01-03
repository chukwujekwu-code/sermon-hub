"""Qdrant vector database connection manager."""

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, HnswConfigDiff
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class QdrantConnection:
    """Manages Qdrant client connection and collection setup."""

    def __init__(self):
        """Initialize the Qdrant connection manager."""
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        """Get the Qdrant client, creating if needed."""
        if self._client is None:
            self._client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                timeout=120,
            )
            logger.info(
                "qdrant_connected",
                url=settings.qdrant_url[:50] + "..." if len(settings.qdrant_url) > 50 else settings.qdrant_url,
            )
        return self._client

    def ensure_collection(self) -> None:
        """Ensure the sermon chunks collection exists."""
        collection_name = settings.qdrant_collection_name

        # Check if collection exists
        collections = self.client.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)

        if not exists:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimensions,
                    distance=Distance.COSINE,
                    hnsw_config=HnswConfigDiff(
                        m=16,
                        ef_construct=100,
                    ),
                ),
            )
            logger.info("qdrant_collection_created", collection_name=collection_name)
        else:
            logger.info("qdrant_collection_exists", collection_name=collection_name)

    def get_collection_info(self) -> dict:
        """Get information about the collection."""
        collection_name = settings.qdrant_collection_name
        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "points_count": info.points_count,
                "status": info.status.value,
            }
        except Exception as e:
            logger.warning("qdrant_collection_info_failed", error=str(e))
            return {"name": collection_name, "error": str(e)}

    def recreate_collection(self) -> None:
        """Delete and recreate the collection (for re-indexing)."""
        collection_name = settings.qdrant_collection_name

        # Delete if exists
        try:
            self.client.delete_collection(collection_name)
            logger.info("qdrant_collection_deleted", collection_name=collection_name)
        except Exception:
            pass  # Collection didn't exist

        # Create fresh
        self.ensure_collection()

    def close(self) -> None:
        """Close the Qdrant client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("qdrant_disconnected")


# Global instance
qdrant = QdrantConnection()
