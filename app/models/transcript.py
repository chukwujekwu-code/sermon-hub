"""Transcript models for MongoDB storage."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """Individual timed segment from transcript."""

    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Segment text content")


class TranscriptCreate(BaseModel):
    """Schema for creating a transcript."""

    video_id: str = Field(..., description="YouTube video ID")
    channel_id: str = Field(..., description="YouTube channel ID for filtering")
    channel_name: str = Field(..., description="Pastor/channel name for display")
    source: Literal["youtube_captions", "whisper"] = Field(
        ..., description="Transcription source"
    )
    text: str = Field(..., description="Full transcript text")
    segments: list[TranscriptSegment] = Field(default_factory=list)
    language: str = Field(default="en")


class Transcript(TranscriptCreate):
    """Full transcript with MongoDB fields."""

    id: str = Field(..., alias="_id")
    word_count: int = Field(..., description="Cached word count for stats")
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}
