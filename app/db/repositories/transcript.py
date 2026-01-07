"""Transcript repository for MongoDB operations."""

from datetime import datetime, UTC
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
import structlog

from app.models.transcript import TranscriptCreate

logger = structlog.get_logger(__name__)


class TranscriptRepository:
    """Repository for transcript CRUD operations in MongoDB."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with MongoDB database."""
        self.collection = db["transcripts"]

    async def create(self, data: TranscriptCreate) -> str:
        """Create a new transcript."""
        doc = data.model_dump()
        doc["word_count"] = len(data.text.split())
        doc["created_at"] = datetime.now(UTC)
        doc["updated_at"] = datetime.now(UTC)

        result = await self.collection.insert_one(doc)
        logger.info("transcript_created", video_id=data.video_id)
        return str(result.inserted_id)

    async def upsert(self, data: TranscriptCreate) -> str:
        """Insert or update a transcript."""
        doc = data.model_dump()
        doc["word_count"] = len(data.text.split())
        doc["updated_at"] = datetime.now(UTC)

        result = await self.collection.update_one(
            {"video_id": data.video_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )

        if result.upserted_id:
            logger.info("transcript_created", video_id=data.video_id)
        else:
            logger.info("transcript_updated", video_id=data.video_id)

        return data.video_id

    async def get_by_video_id(self, video_id: str) -> dict[str, Any] | None:
        """Get a transcript by video ID."""
        doc = await self.collection.find_one({"video_id": video_id})
        return doc

    async def get_text_by_video_id(self, video_id: str) -> str | None:
        """Get only transcript text (efficient for embedding)."""
        doc = await self.collection.find_one(
            {"video_id": video_id}, {"text": 1, "_id": 0}
        )
        return doc["text"] if doc else None

    async def exists(self, video_id: str) -> bool:
        """Check if transcript exists."""
        count = await self.collection.count_documents({"video_id": video_id}, limit=1)
        return count > 0

    async def list_by_channel(
        self,
        channel_id: str,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """List transcripts for a channel."""
        cursor = (
            self.collection.find(
                {"channel_id": channel_id},
                {"segments": 0},  # Exclude segments for list view
            )
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        return await cursor.to_list(length=limit)

    async def list_all_video_ids(self) -> list[str]:
        """Get all video IDs with transcripts."""
        cursor = self.collection.find({}, {"video_id": 1, "_id": 0})
        docs = await cursor.to_list(length=None)
        return [doc["video_id"] for doc in docs]

    async def list_video_ids_by_channel(self, channel_id: str) -> list[str]:
        """Get video IDs for a specific channel."""
        cursor = self.collection.find(
            {"channel_id": channel_id}, {"video_id": 1, "_id": 0}
        )
        docs = await cursor.to_list(length=None)
        return [doc["video_id"] for doc in docs]

    async def count(self) -> int:
        """Count total transcripts."""
        return await self.collection.count_documents({})

    async def count_by_channel(self, channel_id: str) -> int:
        """Count transcripts for a channel."""
        return await self.collection.count_documents({"channel_id": channel_id})

    async def get_stats(self) -> dict[str, Any]:
        """Get transcript statistics by channel."""
        pipeline = [
            {
                "$group": {
                    "_id": "$channel_name",
                    "count": {"$sum": 1},
                    "total_words": {"$sum": "$word_count"},
                }
            },
            {"$sort": {"count": -1}},
        ]
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        return {
            "by_channel": results,
            "total": sum(r["count"] for r in results),
        }

    async def delete(self, video_id: str) -> bool:
        """Delete a transcript."""
        result = await self.collection.delete_one({"video_id": video_id})
        if result.deleted_count > 0:
            logger.info("transcript_deleted", video_id=video_id)
            return True
        return False
