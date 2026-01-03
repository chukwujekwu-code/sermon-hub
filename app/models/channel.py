"""Pydantic models for channels."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChannelBase(BaseModel):
    """Base channel schema."""

    channel_id: str = Field(..., description="YouTube channel ID")
    channel_name: str = Field(..., description="Channel display name")
    channel_url: str = Field(..., description="Channel URL")


class ChannelCreate(ChannelBase):
    """Schema for creating a channel."""

    pass


class Channel(ChannelBase):
    """Full channel schema with database fields."""

    id: int
    last_sync_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelSyncRequest(BaseModel):
    """Request to sync a channel's videos."""

    channel_url: str = Field(..., description="YouTube channel URL")
    max_videos: Optional[int] = Field(
        default=None,
        description="Maximum number of videos to fetch (default from config)",
    )
    download: bool = Field(
        default=True,
        description="Whether to download audio after fetching metadata",
    )
    transcribe: bool = Field(
        default=True,
        description="Whether to transcribe audio after downloading",
    )
