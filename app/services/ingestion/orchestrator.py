"""Ingestion orchestrator - coordinates the full ingestion pipeline."""

import asyncio
from typing import Any

import structlog

from app.core.config import settings
from app.db.connection import db
from app.db.repositories.channel import ChannelRepository
from app.db.repositories.ingestion import IngestionRepository
from app.db.repositories.video import VideoRepository
from app.models.ingestion import IngestionStats
from app.services.transcription import whisper_service
from app.services.youtube import captions, downloader, metadata
from app.services.youtube.exceptions import DownloadError, VideoUnavailableError

logger = structlog.get_logger(__name__)


class IngestionOrchestrator:
    """Orchestrates the sermon ingestion pipeline."""

    def __init__(self):
        """Initialize the orchestrator with database repositories."""
        self.channel_repo = ChannelRepository(db.connection)
        self.video_repo = VideoRepository(db.connection)
        self.ingestion_repo = IngestionRepository(db.connection)

    async def sync_channel(
        self,
        channel_url: str,
        max_videos: int | None = None,
        download: bool = True,
        transcribe: bool = True,
    ) -> dict[str, Any]:
        """Sync videos from a YouTube channel.

        Args:
            channel_url: YouTube channel URL
            max_videos: Maximum number of videos to fetch
            download: Whether to download audio
            transcribe: Whether to transcribe audio

        Returns:
            Summary of the sync operation
        """
        if max_videos is None:
            max_videos = settings.default_max_videos

        logger.info(
            "channel_sync_started",
            channel_url=channel_url,
            max_videos=max_videos,
        )

        # Fetch channel info
        channel_info = await metadata.fetch_channel_info(channel_url)
        channel_id = channel_info["channel_id"]

        # Ensure channel exists in database
        existing_channel = await self.channel_repo.get_by_channel_id(channel_id)
        if not existing_channel:
            await self.channel_repo.create(channel_info)
            logger.info("channel_created", channel_id=channel_id)

        # Fetch video list
        videos = await metadata.fetch_channel_videos(channel_url, limit=max_videos)
        logger.info("videos_fetched", count=len(videos))

        # Process each video
        videos_created = 0
        videos_downloaded = 0
        videos_transcribed = 0
        videos_failed = 0

        min_duration_seconds = settings.min_video_duration_minutes * 60
        videos_skipped = 0

        for video_data in videos:
            video_id = video_data["video_id"]
            video_data["channel_id"] = channel_id

            try:
                # Check if video exists
                existing = await self.video_repo.get_by_video_id(video_id)
                if not existing:
                    # Get full video info if we only have flat data
                    if video_data.get("duration_seconds") is None:
                        try:
                            full_info = await metadata.fetch_video_info(video_id)
                            video_data.update(full_info)
                        except Exception as e:
                            logger.warning(
                                "video_info_fetch_failed",
                                video_id=video_id,
                                error=str(e),
                            )

                    # Skip videos shorter than minimum duration
                    duration = video_data.get("duration_seconds") or 0
                    if duration < min_duration_seconds:
                        logger.info(
                            "video_skipped_short_duration",
                            video_id=video_id,
                            duration_seconds=duration,
                            min_required=min_duration_seconds,
                        )
                        videos_skipped += 1
                        continue

                    await self.video_repo.create(video_data)
                    videos_created += 1

                # Create ingestion status
                await self.ingestion_repo.create(video_id)

                # Try to get transcript
                if transcribe:
                    status = await self.ingestion_repo.get_by_video_id(video_id)
                    if status and status["status"] in ("pending", "failed"):
                        try:
                            # First, try YouTube captions (fast, no download needed)
                            caption_result = await self._get_captions(video_id)
                            if caption_result:
                                videos_transcribed += 1
                            elif download:
                                # No captions available, fall back to download + Whisper
                                download_result = await self._download_video(video_id)
                                if download_result:
                                    videos_downloaded += 1
                                    transcript_result = await self._transcribe_video(
                                        video_id,
                                        download_result["audio_path"],
                                    )
                                    if transcript_result:
                                        videos_transcribed += 1

                        except Exception as e:
                            logger.error(
                                "video_processing_failed",
                                video_id=video_id,
                                error=str(e),
                            )
                            videos_failed += 1

                # Add delay between videos
                await asyncio.sleep(settings.download_delay_seconds)

            except Exception as e:
                logger.error(
                    "video_sync_failed",
                    video_id=video_id,
                    error=str(e),
                )
                videos_failed += 1

        # Update channel last sync
        await self.channel_repo.update_last_sync(channel_id)

        summary = {
            "channel_id": channel_id,
            "channel_name": channel_info["channel_name"],
            "videos_found": len(videos),
            "videos_skipped": videos_skipped,
            "videos_created": videos_created,
            "videos_downloaded": videos_downloaded,
            "videos_transcribed": videos_transcribed,
            "videos_failed": videos_failed,
        }

        logger.info("channel_sync_completed", **summary)
        return summary

    async def _download_video(self, video_id: str) -> dict[str, Any] | None:
        """Download audio for a video.

        Returns:
            Download result or None if failed
        """
        try:
            await self.ingestion_repo.set_downloading(video_id)

            result = await downloader.download_audio(video_id)

            await self.ingestion_repo.set_downloaded(
                video_id,
                audio_path=result["audio_path"],
                audio_format=result["audio_format"],
                audio_size_bytes=result["audio_size_bytes"],
            )

            return result

        except VideoUnavailableError as e:
            await self.ingestion_repo.set_failed(video_id, str(e))
            logger.warning("video_unavailable", video_id=video_id, error=str(e))
            return None

        except DownloadError as e:
            await self.ingestion_repo.set_failed(video_id, str(e))
            logger.error("download_failed", video_id=video_id, error=str(e))
            return None

    async def _get_captions(self, video_id: str) -> dict[str, Any] | None:
        """Try to get YouTube captions for a video.

        Returns:
            Caption result or None if no captions available
        """
        try:
            await self.ingestion_repo.set_transcribing(video_id)

            result = await captions.extract_captions(video_id)

            if result:
                await self.ingestion_repo.set_completed(
                    video_id,
                    transcript_path=result["transcript_path"],
                    transcript_text=result["transcript_text"],
                )
                logger.info(
                    "captions_obtained",
                    video_id=video_id,
                    source="youtube_captions",
                )
                return result

            # No captions available, reset status to pending for fallback
            await self.ingestion_repo.update_status(video_id, "pending")
            return None

        except Exception as e:
            logger.warning("caption_extraction_failed", video_id=video_id, error=str(e))
            # Reset to pending so fallback can try
            await self.ingestion_repo.update_status(video_id, "pending")
            return None

    async def _transcribe_video(
        self,
        video_id: str,
        audio_path: str,
    ) -> dict[str, Any] | None:
        """Transcribe audio for a video.

        Returns:
            Transcription result or None if failed
        """
        try:
            await self.ingestion_repo.set_transcribing(video_id)

            result = await whisper_service.transcribe(audio_path, video_id)

            await self.ingestion_repo.set_completed(
                video_id,
                transcript_path=result["transcript_path"],
                transcript_text=result["transcript_text"],
            )

            return result

        except Exception as e:
            await self.ingestion_repo.set_failed(video_id, str(e))
            logger.error("transcription_failed", video_id=video_id, error=str(e))
            return None

    async def retry_failed(
        self,
        max_error_count: int = 3,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Retry failed ingestions.

        Args:
            max_error_count: Only retry videos with fewer errors
            limit: Maximum number of videos to retry

        Returns:
            Summary of retry operation
        """
        failed_videos = await self.ingestion_repo.list_failed(
            max_error_count=max_error_count,
            limit=limit,
        )

        if not failed_videos:
            logger.info("no_failed_videos_to_retry")
            return {"retried": 0, "succeeded": 0, "failed": 0}

        logger.info("retry_started", count=len(failed_videos))

        retried = 0
        succeeded = 0
        failed = 0

        for status in failed_videos:
            video_id = status["video_id"]
            retried += 1

            try:
                # Check what needs to be done
                if status["audio_path"] and status["status"] == "failed":
                    # Audio exists, try transcription
                    result = await self._transcribe_video(
                        video_id,
                        status["audio_path"],
                    )
                    if result:
                        succeeded += 1
                    else:
                        failed += 1
                else:
                    # Need to download first
                    download_result = await self._download_video(video_id)
                    if download_result:
                        transcript_result = await self._transcribe_video(
                            video_id,
                            download_result["audio_path"],
                        )
                        if transcript_result:
                            succeeded += 1
                        else:
                            failed += 1
                    else:
                        failed += 1

                await asyncio.sleep(settings.download_delay_seconds)

            except Exception as e:
                logger.error("retry_failed", video_id=video_id, error=str(e))
                failed += 1

        summary = {"retried": retried, "succeeded": succeeded, "failed": failed}
        logger.info("retry_completed", **summary)
        return summary

    async def get_stats(self) -> IngestionStats:
        """Get ingestion statistics.

        Returns:
            IngestionStats with counts by status
        """
        stats_dict = await self.ingestion_repo.get_stats()
        return IngestionStats(
            pending=stats_dict.get("pending", 0),
            downloading=stats_dict.get("downloading", 0),
            downloaded=stats_dict.get("downloaded", 0),
            transcribing=stats_dict.get("transcribing", 0),
            completed=stats_dict.get("completed", 0),
            failed=stats_dict.get("failed", 0),
        )

    async def get_video_status(self, video_id: str) -> dict[str, Any] | None:
        """Get status for a specific video.

        Returns:
            Video data with ingestion status or None
        """
        video = await self.video_repo.get_by_video_id(video_id)
        if not video:
            return None

        status = await self.ingestion_repo.get_by_video_id(video_id)
        if status:
            video["ingestion_status"] = status

        return video
