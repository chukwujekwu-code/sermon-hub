"""Async MongoDB connection manager using Motor."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class MongoDB:
    """Async MongoDB connection manager."""

    def __init__(self):
        """Initialize MongoDB manager."""
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        """Initialize MongoDB connection."""
        if not settings.mongodb_uri:
            logger.warning("mongodb_not_configured")
            return

        self._client = AsyncIOMotorClient(
            settings.mongodb_uri,
            maxPoolSize=10,
            minPoolSize=1,
        )
        self._db = self._client[settings.mongodb_database]

        # Verify connection
        await self._client.admin.command("ping")
        logger.info(
            "mongodb_connected",
            database=settings.mongodb_database,
        )

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("mongodb_disconnected")

    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance."""
        if self._db is None:
            raise RuntimeError("MongoDB not connected")
        return self._db

    @property
    def is_connected(self) -> bool:
        """Check if MongoDB is connected."""
        return self._db is not None

    async def ensure_indexes(self) -> None:
        """Create required indexes."""
        if self._db is None:
            return

        transcripts = self._db["transcripts"]
        await transcripts.create_index("video_id", unique=True)
        await transcripts.create_index("channel_id")
        await transcripts.create_index([("created_at", -1)])
        logger.info("mongodb_indexes_created")


# Global instance
mongodb = MongoDB()
