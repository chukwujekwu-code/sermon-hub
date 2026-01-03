"""Channel repository for database operations."""

from datetime import datetime, UTC
from typing import Any

import aiosqlite
import structlog

logger = structlog.get_logger(__name__)


class ChannelRepository:
    """Repository for channel CRUD operations."""

    def __init__(self, connection: aiosqlite.Connection):
        """Initialize with database connection."""
        self.conn = connection

    async def create(self, data: dict[str, Any]) -> int:
        """Create a new channel."""
        cursor = await self.conn.execute(
            """
            INSERT INTO channels (channel_id, channel_name, channel_url)
            VALUES (:channel_id, :channel_name, :channel_url)
            """,
            data,
        )
        await self.conn.commit()
        logger.info("channel_created", channel_id=data["channel_id"])
        return cursor.lastrowid or 0

    async def get_by_channel_id(self, channel_id: str) -> dict[str, Any] | None:
        """Get a channel by its YouTube channel ID."""
        cursor = await self.conn.execute(
            "SELECT * FROM channels WHERE channel_id = ?",
            (channel_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_by_id(self, id: int) -> dict[str, Any] | None:
        """Get a channel by its database ID."""
        cursor = await self.conn.execute(
            "SELECT * FROM channels WHERE id = ?",
            (id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_active(self) -> list[dict[str, Any]]:
        """List all active channels."""
        cursor = await self.conn.execute(
            "SELECT * FROM channels WHERE is_active = TRUE ORDER BY channel_name"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_last_sync(self, channel_id: str) -> None:
        """Update the last sync timestamp for a channel."""
        now = datetime.now(UTC).isoformat()
        await self.conn.execute(
            """
            UPDATE channels
            SET last_sync_at = ?, updated_at = ?
            WHERE channel_id = ?
            """,
            (now, now, channel_id),
        )
        await self.conn.commit()
        logger.info("channel_sync_updated", channel_id=channel_id)

    async def set_active(self, channel_id: str, is_active: bool) -> None:
        """Set the active status of a channel."""
        now = datetime.now(UTC).isoformat()
        await self.conn.execute(
            """
            UPDATE channels
            SET is_active = ?, updated_at = ?
            WHERE channel_id = ?
            """,
            (is_active, now, channel_id),
        )
        await self.conn.commit()
