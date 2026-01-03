"""Pydantic models for ingestion status."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IngestionStatusEnum(str, Enum):
    """Possible ingestion statuses."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionStatus(BaseModel):
    """Full ingestion status schema."""

    id: int
    video_id: str
    status: IngestionStatusEnum
    audio_path: Optional[str] = None
    audio_format: Optional[str] = None
    audio_size_bytes: Optional[int] = None
    transcript_path: Optional[str] = None
    transcript_text: Optional[str] = None
    error_message: Optional[str] = None
    error_count: int = 0
    download_started_at: Optional[datetime] = None
    download_completed_at: Optional[datetime] = None
    transcription_started_at: Optional[datetime] = None
    transcription_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IngestionStats(BaseModel):
    """Overall ingestion statistics."""

    pending: int = 0
    downloading: int = 0
    downloaded: int = 0
    transcribing: int = 0
    completed: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        """Total number of ingestion records."""
        return (
            self.pending
            + self.downloading
            + self.downloaded
            + self.transcribing
            + self.completed
            + self.failed
        )


class IngestionProgress(BaseModel):
    """Progress update for an ingestion run."""

    channel_id: str
    channel_name: str
    current_video: Optional[str] = None
    current_status: Optional[str] = None
    videos_total: int
    videos_completed: int
    videos_failed: int


class RetryRequest(BaseModel):
    """Request to retry failed ingestions."""

    max_error_count: int = Field(
        default=3,
        description="Only retry videos with error_count less than this",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of videos to retry",
    )
