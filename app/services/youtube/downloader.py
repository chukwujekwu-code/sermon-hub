"""YouTube audio downloader using yt-dlp."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import structlog
import yt_dlp

from app.core.config import settings
from app.services.youtube.exceptions import (
    DownloadError,
    DownloadTimeoutError,
    VideoUnavailableError,
)

logger = structlog.get_logger(__name__)

# Thread pool for running yt-dlp (which is synchronous)
_executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_downloads)

# Semaphore to limit concurrent downloads
_semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)


def _get_output_dir() -> Path:
    """Get and ensure output directory exists."""
    output_dir = settings.audio_path
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _download_audio_sync(video_id: str) -> dict[str, Any]:
    """Synchronous audio download implementation."""
    output_dir = _get_output_dir()
    output_template = str(output_dir / f"{video_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": settings.audio_format,
                "preferredquality": settings.audio_quality,
            }
        ],
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "continuedl": True,  # Resume partial downloads
        "noprogress": True,
    }

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            if info is None:
                raise DownloadError(f"Failed to download: {video_id}")

            # Find the output file
            output_path = output_dir / f"{video_id}.{settings.audio_format}"

            if not output_path.exists():
                # yt-dlp might use a different extension, try to find it
                possible_files = list(output_dir.glob(f"{video_id}.*"))
                audio_files = [
                    f for f in possible_files
                    if f.suffix.lower() in [".mp3", ".m4a", ".wav", ".opus", ".webm"]
                ]
                if audio_files:
                    output_path = audio_files[0]
                else:
                    raise DownloadError(f"Output file not found for {video_id}")

            return {
                "video_id": video_id,
                "audio_path": str(output_path),
                "audio_format": output_path.suffix.lstrip("."),
                "audio_size_bytes": output_path.stat().st_size,
                "title": info.get("title"),
                "duration": info.get("duration"),
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if "private video" in error_msg or "unavailable" in error_msg:
            raise VideoUnavailableError(f"Video {video_id} is unavailable: {e}") from e
        raise DownloadError(f"Download failed for {video_id}: {e}") from e


async def download_audio(
    video_id: str,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Download audio for a video asynchronously.

    Args:
        video_id: YouTube video ID
        timeout: Download timeout in seconds

    Returns:
        Dictionary with video_id, audio_path, audio_format, audio_size_bytes
    """
    if timeout is None:
        timeout = settings.download_timeout_seconds

    async with _semaphore:
        logger.info("download_started", video_id=video_id)

        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(_executor, _download_audio_sync, video_id),
                timeout=timeout,
            )

            logger.info(
                "download_completed",
                video_id=video_id,
                size_bytes=result["audio_size_bytes"],
            )

            return result

        except asyncio.TimeoutError:
            raise DownloadTimeoutError(
                f"Download timeout ({timeout}s) for {video_id}"
            )
        except Exception as e:
            logger.error("download_failed", video_id=video_id, error=str(e))
            raise


def get_audio_path(video_id: str) -> Path | None:
    """Get the path to a downloaded audio file, if it exists.

    Args:
        video_id: YouTube video ID

    Returns:
        Path to audio file or None if not found
    """
    output_dir = settings.audio_path
    for ext in [settings.audio_format, "m4a", "wav", "opus", "webm"]:
        path = output_dir / f"{video_id}.{ext}"
        if path.exists():
            return path
    return None


def cleanup_audio(video_id: str) -> bool:
    """Remove downloaded audio file.

    Args:
        video_id: YouTube video ID

    Returns:
        True if file was removed, False otherwise
    """
    path = get_audio_path(video_id)
    if path and path.exists():
        path.unlink()
        logger.info("audio_cleaned_up", video_id=video_id)
        return True
    return False
