"""Whisper transcription service."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import structlog

from app.core.config import settings
from app.services.transcription.exceptions import (
    AudioFileNotFoundError,
    ModelLoadError,
    TranscriptionFailedError,
)

logger = structlog.get_logger(__name__)

# Thread pool for running Whisper (which is synchronous/GPU-bound)
_executor = ThreadPoolExecutor(max_workers=1)  # Whisper is memory-intensive

# Lazy-loaded Whisper model
_model = None


def _get_model():
    """Load the Whisper model lazily."""
    global _model
    if _model is None:
        try:
            import whisper

            logger.info("loading_whisper_model", model=settings.whisper_model)
            _model = whisper.load_model(settings.whisper_model)
            logger.info("whisper_model_loaded", model=settings.whisper_model)
        except Exception as e:
            raise ModelLoadError(f"Failed to load Whisper model: {e}") from e
    return _model


def _get_transcripts_dir() -> Path:
    """Get and ensure transcripts directory exists."""
    transcripts_dir = settings.transcripts_path
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    return transcripts_dir


def _transcribe_sync(audio_path: str, video_id: str) -> dict[str, Any]:
    """Synchronous transcription implementation."""
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise AudioFileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        model = _get_model()

        logger.info("transcription_started", video_id=video_id, audio_path=audio_path)

        # Transcribe the audio
        result = model.transcribe(
            str(audio_file),
            language="en",  # Assume English for sermons
            verbose=False,
        )

        # Extract text and segments
        full_text = result.get("text", "").strip()
        segments = result.get("segments", [])

        # Format segments with timestamps
        formatted_segments = [
            {
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": seg.get("text", "").strip(),
            }
            for seg in segments
        ]

        # Save transcript to JSON file
        transcripts_dir = _get_transcripts_dir()
        transcript_path = transcripts_dir / f"{video_id}.json"

        transcript_data = {
            "video_id": video_id,
            "text": full_text,
            "segments": formatted_segments,
            "language": result.get("language", "en"),
        }

        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)

        logger.info(
            "transcription_completed",
            video_id=video_id,
            text_length=len(full_text),
            segments_count=len(formatted_segments),
        )

        return {
            "video_id": video_id,
            "transcript_path": str(transcript_path),
            "transcript_text": full_text,
            "segments": formatted_segments,
            "language": result.get("language", "en"),
        }

    except Exception as e:
        if isinstance(e, (AudioFileNotFoundError, ModelLoadError)):
            raise
        raise TranscriptionFailedError(f"Transcription failed: {e}") from e


async def transcribe(audio_path: str, video_id: str) -> dict[str, Any]:
    """Transcribe an audio file asynchronously.

    Args:
        audio_path: Path to the audio file
        video_id: YouTube video ID for naming the output

    Returns:
        Dictionary with transcript_path, transcript_text, segments, language
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        _transcribe_sync,
        audio_path,
        video_id,
    )
    return result


def get_transcript(video_id: str) -> dict[str, Any] | None:
    """Get a saved transcript for a video.

    Args:
        video_id: YouTube video ID

    Returns:
        Transcript data or None if not found
    """
    transcripts_dir = settings.transcripts_path
    transcript_path = transcripts_dir / f"{video_id}.json"

    if not transcript_path.exists():
        return None

    with open(transcript_path, encoding="utf-8") as f:
        return json.load(f)


def cleanup_transcript(video_id: str) -> bool:
    """Remove a transcript file.

    Args:
        video_id: YouTube video ID

    Returns:
        True if file was removed, False otherwise
    """
    transcripts_dir = settings.transcripts_path
    transcript_path = transcripts_dir / f"{video_id}.json"

    if transcript_path.exists():
        transcript_path.unlink()
        logger.info("transcript_cleaned_up", video_id=video_id)
        return True
    return False
