"""Pydantic models for videos."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VideoBase(BaseModel):
    """Base video schema."""

    video_id: str = Field(..., description="YouTube video ID")
    channel_id: str = Field(..., description="YouTube channel ID")
    title: str = Field(..., description="Video title")


class VideoCreate(VideoBase):
    """Schema for creating a video."""

    description: Optional[str] = None
    duration_seconds: Optional[int] = None
    published_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None


class Video(VideoBase):
    """Full video schema with database fields."""

    id: int
    description: Optional[str] = None
    duration_seconds: Optional[int] = None
    published_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoWithStatus(Video):
    """Video with ingestion status."""

    status: str
    audio_path: Optional[str] = None
    transcript_text: Optional[str] = None
