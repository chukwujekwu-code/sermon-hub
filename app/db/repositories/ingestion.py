"""Ingestion status repository for database operations."""

from datetime import datetime, UTC
from typing import Any

import libsql_experimental as libsql
import structlog

logger = structlog.get_logger(__name__)


class IngestionRepository:
    """Repository for ingestion status CRUD operations."""

    def __init__(self, connection: libsql.Connection):
        """Initialize with database connection."""
        self.conn = connection

    async def create(self, video_id: str, status: str = "pending") -> int:
        """Create a new ingestion status record."""
        cursor = self.conn.execute(
            """
            INSERT INTO ingestion_status (video_id, status)
            VALUES (?, ?)
            ON CONFLICT(video_id) DO NOTHING
            """,
            (video_id, status),
        )
        self.conn.commit()
        return cursor.lastrowid or 0

    async def get_by_video_id(self, video_id: str) -> dict[str, Any] | None:
        """Get ingestion status for a video."""
        cursor = self.conn.execute(
            "SELECT * FROM ingestion_status WHERE video_id = ?",
            (video_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    async def update_status(
        self,
        video_id: str,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Update ingestion status and optional fields."""
        now = datetime.now(UTC).isoformat()

        # Build dynamic update query
        fields = ["status = ?", "updated_at = ?"]
        values: list[Any] = [status, now]

        for key, value in kwargs.items():
            if key == "increment_error_count":
                fields.append("error_count = error_count + 1")
            else:
                fields.append(f"{key} = ?")
                values.append(value)

        values.append(video_id)

        query = f"""
            UPDATE ingestion_status
            SET {", ".join(fields)}
            WHERE video_id = ?
        """
        self.conn.execute(query, values)
        self.conn.commit()

        logger.info("ingestion_status_updated", video_id=video_id, status=status)

    async def set_downloading(self, video_id: str) -> None:
        """Mark video as downloading."""
        now = datetime.now(UTC).isoformat()
        await self.update_status(video_id, "downloading", download_started_at=now)

    async def set_downloaded(
        self,
        video_id: str,
        audio_path: str,
        audio_format: str,
        audio_size_bytes: int,
    ) -> None:
        """Mark video as downloaded with audio info."""
        now = datetime.now(UTC).isoformat()
        await self.update_status(
            video_id,
            "downloaded",
            audio_path=audio_path,
            audio_format=audio_format,
            audio_size_bytes=audio_size_bytes,
            download_completed_at=now,
        )

    async def set_transcribing(self, video_id: str) -> None:
        """Mark video as transcribing."""
        now = datetime.now(UTC).isoformat()
        await self.update_status(video_id, "transcribing", transcription_started_at=now)

    async def set_completed(
        self,
        video_id: str,
        transcript_text: str,
        transcript_path: str | None = None,
    ) -> None:
        """Mark video as completed with transcript info."""
        now = datetime.now(UTC).isoformat()
        kwargs: dict[str, Any] = {
            "transcript_text": transcript_text,
            "transcription_completed_at": now,
        }
        if transcript_path:
            kwargs["transcript_path"] = transcript_path
        await self.update_status(video_id, "completed", **kwargs)

    async def set_failed(self, video_id: str, error_message: str) -> None:
        """Mark video as failed with error message."""
        await self.update_status(
            video_id,
            "failed",
            error_message=error_message,
            increment_error_count=True,
        )

    async def list_by_status(
        self,
        status: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List ingestion records by status."""
        cursor = self.conn.execute(
            """
            SELECT * FROM ingestion_status
            WHERE status = ?
            ORDER BY created_at
            LIMIT ?
            """,
            (status, limit),
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def list_failed(
        self,
        max_error_count: int = 3,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List failed ingestions that can be retried."""
        cursor = self.conn.execute(
            """
            SELECT * FROM ingestion_status
            WHERE status = 'failed' AND error_count < ?
            ORDER BY updated_at
            LIMIT ?
            """,
            (max_error_count, limit),
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def count_by_status(self, status: str) -> int:
        """Count ingestion records by status."""
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM ingestion_status WHERE status = ?",
            (status,),
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    async def get_stats(self) -> dict[str, int]:
        """Get ingestion statistics by status."""
        cursor = self.conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM ingestion_status
            GROUP BY status
            """
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return {dict(zip(columns, row))["status"]: dict(zip(columns, row))["count"] for row in rows}
