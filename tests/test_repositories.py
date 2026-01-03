"""Tests for database repositories."""

import pytest

from app.db.connection import Database
from app.db.repositories.channel import ChannelRepository
from app.db.repositories.ingestion import IngestionRepository
from app.db.repositories.video import VideoRepository


@pytest.mark.asyncio
async def test_channel_create_and_get(test_db: Database) -> None:
    """Test creating and retrieving a channel."""
    repo = ChannelRepository(test_db.connection)

    # Create channel
    channel_data = {
        "channel_id": "UC123456789012345678901",
        "channel_name": "Test Channel",
        "channel_url": "https://www.youtube.com/@TestChannel",
    }
    await repo.create(channel_data)

    # Retrieve channel
    channel = await repo.get_by_channel_id("UC123456789012345678901")
    assert channel is not None
    assert channel["channel_name"] == "Test Channel"


@pytest.mark.asyncio
async def test_video_create_and_get(test_db: Database) -> None:
    """Test creating and retrieving a video."""
    # First create a channel
    channel_repo = ChannelRepository(test_db.connection)
    await channel_repo.create({
        "channel_id": "UC123456789012345678901",
        "channel_name": "Test Channel",
        "channel_url": "https://www.youtube.com/@TestChannel",
    })

    # Create video
    video_repo = VideoRepository(test_db.connection)
    video_data = {
        "video_id": "abcdefghijk",
        "channel_id": "UC123456789012345678901",
        "title": "Test Video",
        "description": "A test video",
        "duration_seconds": 3600,
        "published_at": "2024-01-01T00:00:00",
        "thumbnail_url": None,
        "view_count": 1000,
    }
    await video_repo.create(video_data)

    # Retrieve video
    video = await video_repo.get_by_video_id("abcdefghijk")
    assert video is not None
    assert video["title"] == "Test Video"


@pytest.mark.asyncio
async def test_ingestion_status_workflow(test_db: Database) -> None:
    """Test the ingestion status workflow."""
    # Create channel and video first
    channel_repo = ChannelRepository(test_db.connection)
    await channel_repo.create({
        "channel_id": "UC123456789012345678901",
        "channel_name": "Test Channel",
        "channel_url": "https://www.youtube.com/@TestChannel",
    })

    video_repo = VideoRepository(test_db.connection)
    await video_repo.create({
        "video_id": "abcdefghijk",
        "channel_id": "UC123456789012345678901",
        "title": "Test Video",
        "description": None,
        "duration_seconds": None,
        "published_at": None,
        "thumbnail_url": None,
        "view_count": None,
    })

    # Test ingestion workflow
    ingestion_repo = IngestionRepository(test_db.connection)

    # Create status
    await ingestion_repo.create("abcdefghijk")
    status = await ingestion_repo.get_by_video_id("abcdefghijk")
    assert status is not None
    assert status["status"] == "pending"

    # Update to downloading
    await ingestion_repo.set_downloading("abcdefghijk")
    status = await ingestion_repo.get_by_video_id("abcdefghijk")
    assert status["status"] == "downloading"

    # Update to downloaded
    await ingestion_repo.set_downloaded(
        "abcdefghijk",
        audio_path="/data/audio/abcdefghijk.mp3",
        audio_format="mp3",
        audio_size_bytes=1024000,
    )
    status = await ingestion_repo.get_by_video_id("abcdefghijk")
    assert status["status"] == "downloaded"
    assert status["audio_path"] == "/data/audio/abcdefghijk.mp3"

    # Update to completed
    await ingestion_repo.set_completed(
        "abcdefghijk",
        transcript_path="/data/transcripts/abcdefghijk.json",
        transcript_text="This is a test transcript.",
    )
    status = await ingestion_repo.get_by_video_id("abcdefghijk")
    assert status["status"] == "completed"
    assert "test transcript" in status["transcript_text"]


@pytest.mark.asyncio
async def test_ingestion_stats(test_db: Database) -> None:
    """Test getting ingestion statistics."""
    ingestion_repo = IngestionRepository(test_db.connection)

    # Initially empty
    stats = await ingestion_repo.get_stats()
    assert stats == {}

    # Create channel and video
    channel_repo = ChannelRepository(test_db.connection)
    await channel_repo.create({
        "channel_id": "UC123456789012345678901",
        "channel_name": "Test Channel",
        "channel_url": "https://www.youtube.com/@TestChannel",
    })

    video_repo = VideoRepository(test_db.connection)
    for i in range(3):
        await video_repo.create({
            "video_id": f"video{i}",
            "channel_id": "UC123456789012345678901",
            "title": f"Video {i}",
            "description": None,
            "duration_seconds": None,
            "published_at": None,
            "thumbnail_url": None,
            "view_count": None,
        })
        await ingestion_repo.create(f"video{i}")

    # Check stats
    stats = await ingestion_repo.get_stats()
    assert stats.get("pending", 0) == 3
