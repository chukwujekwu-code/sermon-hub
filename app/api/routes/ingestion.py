"""Ingestion API routes."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

import structlog

from app.models.channel import ChannelSyncRequest
from app.models.ingestion import IngestionStats, RetryRequest
from app.services.ingestion.orchestrator import IngestionOrchestrator
from app.services.transcription import whisper_service

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["ingestion"])


def get_orchestrator() -> IngestionOrchestrator:
    """Get an orchestrator instance."""
    return IngestionOrchestrator()


@router.post("/channels/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_channel(
    request: ChannelSyncRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Start syncing a YouTube channel.

    Fetches video metadata, downloads audio, and transcribes.
    Runs in the background and returns immediately.
    """
    orchestrator = get_orchestrator()

    async def run_sync():
        try:
            await orchestrator.sync_channel(
                channel_url=request.channel_url,
                max_videos=request.max_videos,
                download=request.download,
                transcribe=request.transcribe,
            )
        except Exception as e:
            logger.error("background_sync_failed", error=str(e))

    background_tasks.add_task(run_sync)

    return {
        "message": "Sync started",
        "channel_url": request.channel_url,
        "max_videos": request.max_videos,
    }


@router.post("/channels/sync/blocking")
async def sync_channel_blocking(request: ChannelSyncRequest) -> dict[str, Any]:
    """Sync a YouTube channel and wait for completion.

    Use this for smaller syncs or when you need the result immediately.
    """
    orchestrator = get_orchestrator()

    result = await orchestrator.sync_channel(
        channel_url=request.channel_url,
        max_videos=request.max_videos,
        download=request.download,
        transcribe=request.transcribe,
    )

    return result


@router.get("/ingestion/status", response_model=IngestionStats)
async def get_ingestion_status() -> IngestionStats:
    """Get overall ingestion statistics."""
    orchestrator = get_orchestrator()
    return await orchestrator.get_stats()


@router.get("/videos/{video_id}/status")
async def get_video_status(video_id: str) -> dict[str, Any]:
    """Get status for a specific video."""
    orchestrator = get_orchestrator()
    result = await orchestrator.get_video_status(video_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )

    return result


@router.get("/videos/{video_id}/transcript")
async def get_video_transcript(video_id: str) -> dict[str, Any]:
    """Get the transcript for a video."""
    transcript = whisper_service.get_transcript(video_id)

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript not found: {video_id}",
        )

    return transcript


@router.post("/ingestion/retry")
async def retry_failed(
    request: RetryRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Retry failed ingestions.

    Runs in the background and returns immediately.
    """
    orchestrator = get_orchestrator()

    async def run_retry():
        try:
            await orchestrator.retry_failed(
                max_error_count=request.max_error_count,
                limit=request.limit,
            )
        except Exception as e:
            logger.error("background_retry_failed", error=str(e))

    background_tasks.add_task(run_retry)

    return {
        "message": "Retry started",
        "max_error_count": request.max_error_count,
        "limit": request.limit,
    }


@router.post("/ingestion/retry/blocking")
async def retry_failed_blocking(request: RetryRequest) -> dict[str, Any]:
    """Retry failed ingestions and wait for completion."""
    orchestrator = get_orchestrator()

    result = await orchestrator.retry_failed(
        max_error_count=request.max_error_count,
        limit=request.limit,
    )

    return result
