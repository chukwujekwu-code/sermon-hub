"""YouTube metadata extraction using yt-dlp."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import structlog
import yt_dlp

from app.core.config import settings
from app.services.youtube.exceptions import (
    ChannelNotFoundError,
    MetadataExtractionError,
)

logger = structlog.get_logger(__name__)

# Thread pool for running yt-dlp (which is synchronous)
_executor = ThreadPoolExecutor(max_workers=2)


def _extract_channel_info_sync(channel_url: str) -> dict[str, Any]:
    """Synchronous channel info extraction."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlist_items": "0",  # Don't fetch any videos, just channel info
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

            if info is None:
                raise ChannelNotFoundError(f"Channel not found: {channel_url}")

            return {
                "channel_id": info.get("channel_id") or info.get("id", ""),
                "channel_name": info.get("channel") or info.get("uploader", "Unknown"),
                "channel_url": info.get("channel_url") or channel_url,
            }
    except yt_dlp.utils.DownloadError as e:
        raise ChannelNotFoundError(f"Failed to fetch channel: {e}") from e


def _normalize_channel_url(channel_url: str) -> str:
    """Ensure channel URL points to the videos tab."""
    # Remove trailing slash
    url = channel_url.rstrip("/")
    # If URL doesn't end with /videos, append it
    if not url.endswith("/videos"):
        url = f"{url}/videos"
    return url


def _extract_channel_videos_sync(
    channel_url: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Synchronous video list extraction from channel."""
    # Ensure we're fetching from the videos tab
    videos_url = _normalize_channel_url(channel_url)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
    }

    if limit:
        ydl_opts["playlist_items"] = f"1:{limit}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(videos_url, download=False)

            if info is None:
                raise MetadataExtractionError(f"Failed to extract videos: {channel_url}")

            entries = info.get("entries", [])
            videos = []

            for entry in entries:
                if entry is None:
                    continue

                video_data = {
                    "video_id": entry.get("id", ""),
                    "title": entry.get("title", "Unknown"),
                    "description": entry.get("description"),
                    "duration_seconds": entry.get("duration"),
                    "view_count": entry.get("view_count"),
                    "thumbnail_url": entry.get("thumbnail"),
                }

                # Parse upload date if available
                upload_date = entry.get("upload_date")
                if upload_date:
                    try:
                        video_data["published_at"] = datetime.strptime(
                            upload_date, "%Y%m%d"
                        ).isoformat()
                    except ValueError:
                        video_data["published_at"] = None
                else:
                    video_data["published_at"] = None

                videos.append(video_data)

            return videos

    except yt_dlp.utils.DownloadError as e:
        raise MetadataExtractionError(f"Failed to extract videos: {e}") from e


def _extract_video_info_sync(video_id: str) -> dict[str, Any]:
    """Synchronous single video info extraction."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                raise MetadataExtractionError(f"Failed to extract video info: {video_id}")

            published_at = None
            upload_date = info.get("upload_date")
            if upload_date:
                try:
                    published_at = datetime.strptime(upload_date, "%Y%m%d").isoformat()
                except ValueError:
                    pass

            return {
                "video_id": info.get("id", video_id),
                "channel_id": info.get("channel_id", ""),
                "title": info.get("title", "Unknown"),
                "description": info.get("description"),
                "duration_seconds": info.get("duration"),
                "published_at": published_at,
                "thumbnail_url": info.get("thumbnail"),
                "view_count": info.get("view_count"),
            }

    except yt_dlp.utils.DownloadError as e:
        raise MetadataExtractionError(f"Failed to extract video info: {e}") from e


async def fetch_channel_info(channel_url: str) -> dict[str, Any]:
    """Fetch channel information asynchronously.

    Args:
        channel_url: YouTube channel URL (e.g., https://www.youtube.com/@PastorPoju)

    Returns:
        Dictionary with channel_id, channel_name, channel_url
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _extract_channel_info_sync, channel_url)
    logger.info("channel_info_fetched", channel_id=result.get("channel_id"))
    return result


async def fetch_channel_videos(
    channel_url: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch video list from a channel asynchronously.

    Args:
        channel_url: YouTube channel URL
        limit: Maximum number of videos to fetch

    Returns:
        List of video metadata dictionaries
    """
    if limit is None:
        limit = settings.default_max_videos

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        _extract_channel_videos_sync,
        channel_url,
        limit,
    )
    logger.info("channel_videos_fetched", count=len(result), limit=limit)
    return result


async def fetch_video_info(video_id: str) -> dict[str, Any]:
    """Fetch detailed info for a single video asynchronously.

    Args:
        video_id: YouTube video ID

    Returns:
        Dictionary with full video metadata
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _extract_video_info_sync, video_id)
    logger.info("video_info_fetched", video_id=video_id)
    return result
