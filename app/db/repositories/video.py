"""Video repository for database operations."""

from typing import Any

import libsql_experimental as libsql
import structlog

logger = structlog.get_logger(__name__)


class VideoRepository:
    """Repository for video CRUD operations."""

    def __init__(self, connection: libsql.Connection):
        """Initialize with database connection."""
        self.conn = connection

    async def create(self, data: dict[str, Any]) -> int:
        """Create a new video."""
        cursor = self.conn.execute(
            """
            INSERT INTO videos (
                video_id, channel_id, title, description,
                duration_seconds, published_at, thumbnail_url, view_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["video_id"],
                data["channel_id"],
                data["title"],
                data.get("description"),
                data.get("duration_seconds"),
                data.get("published_at"),
                data.get("thumbnail_url"),
                data.get("view_count"),
            ),
        )
        self.conn.commit()
        logger.info("video_created", video_id=data["video_id"])
        return cursor.lastrowid or 0

    async def upsert(self, data: dict[str, Any]) -> int:
        """Insert or update a video."""
        cursor = self.conn.execute(
            """
            INSERT INTO videos (
                video_id, channel_id, title, description,
                duration_seconds, published_at, thumbnail_url, view_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                duration_seconds = excluded.duration_seconds,
                thumbnail_url = excluded.thumbnail_url,
                view_count = excluded.view_count
            """,
            (
                data["video_id"],
                data["channel_id"],
                data["title"],
                data.get("description"),
                data.get("duration_seconds"),
                data.get("published_at"),
                data.get("thumbnail_url"),
                data.get("view_count"),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid or 0

    async def get_by_video_id(self, video_id: str) -> dict[str, Any] | None:
        """Get a video by its YouTube video ID."""
        cursor = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = ?",
            (video_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    async def get_by_id(self, id: int) -> dict[str, Any] | None:
        """Get a video by its database ID."""
        cursor = self.conn.execute(
            "SELECT * FROM videos WHERE id = ?",
            (id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    async def list_by_channel(
        self,
        channel_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List videos for a channel, ordered by publish date."""
        cursor = self.conn.execute(
            """
            SELECT * FROM videos
            WHERE channel_id = ?
            ORDER BY published_at DESC
            LIMIT ? OFFSET ?
            """,
            (channel_id, limit, offset),
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def count_by_channel(self, channel_id: str) -> int:
        """Count videos for a channel."""
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM videos WHERE channel_id = ?",
            (channel_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    async def exists(self, video_id: str) -> bool:
        """Check if a video exists."""
        cursor = self.conn.execute(
            "SELECT 1 FROM videos WHERE video_id = ? LIMIT 1",
            (video_id,),
        )
        row = cursor.fetchone()
        return row is not None
