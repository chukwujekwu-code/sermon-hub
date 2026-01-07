"""YouTube caption extraction using yt-dlp."""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import structlog
import yt_dlp

from app.core.config import settings

logger = structlog.get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


def _get_transcripts_dir() -> Path:
    """Get and ensure transcripts directory exists."""
    transcripts_dir = settings.transcripts_path
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    return transcripts_dir


def _parse_vtt_to_text(vtt_content: str) -> tuple[str, list[dict[str, Any]]]:
    """Parse VTT content to extract plain text and segments.

    Returns:
        Tuple of (full_text, segments)
    """
    lines = vtt_content.split('\n')
    segments = []
    current_segment = None

    # Regex for timestamp line: 00:00:00.000 --> 00:00:05.000
    timestamp_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})')

    for line in lines:
        line = line.strip()

        # Skip header and empty lines
        if not line or line == 'WEBVTT' or line.startswith('Kind:') or line.startswith('Language:'):
            continue

        # Check for timestamp
        match = timestamp_pattern.match(line)
        if match:
            if current_segment and current_segment.get('text'):
                segments.append(current_segment)

            start_time = match.group(1)
            end_time = match.group(2)

            # Convert to seconds
            def time_to_seconds(t: str) -> float:
                parts = t.split(':')
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

            current_segment = {
                'start': time_to_seconds(start_time),
                'end': time_to_seconds(end_time),
                'text': ''
            }
        elif current_segment is not None:
            # This is caption text - clean it
            # Remove tags like <c> </c> and position info
            clean_text = re.sub(r'<[^>]+>', '', line)
            clean_text = re.sub(r'\[.*?\]', '', clean_text)  # Remove [Music] etc
            clean_text = clean_text.strip()

            if clean_text:
                if current_segment['text']:
                    current_segment['text'] += ' ' + clean_text
                else:
                    current_segment['text'] = clean_text

    # Don't forget the last segment
    if current_segment and current_segment.get('text'):
        segments.append(current_segment)

    # Deduplicate overlapping segments (YouTube often repeats text)
    deduped_segments = []
    seen_texts = set()
    for seg in segments:
        text = seg['text'].strip()
        if text and text not in seen_texts:
            seen_texts.add(text)
            deduped_segments.append(seg)

    # Build full text
    full_text = ' '.join(seg['text'] for seg in deduped_segments)
    # Clean up multiple spaces
    full_text = re.sub(r'\s+', ' ', full_text).strip()

    return full_text, deduped_segments


def _extract_captions_sync(video_id: str) -> dict[str, Any] | None:
    """Synchronous caption extraction."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    transcripts_dir = _get_transcripts_dir()

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["en", "en-orig"],
        "subtitlesformat": "vtt",
        "outtmpl": str(transcripts_dir / f"{video_id}"),
        # Help avoid bot detection
        "extractor_args": {"youtube": {"player_client": ["web", "android"]}},
        "sleep_interval": 1,
        "max_sleep_interval": 3,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            if info is None:
                return None

            # Check what subtitle files were created
            vtt_files = list(transcripts_dir.glob(f"{video_id}*.vtt"))

            if not vtt_files:
                logger.info("no_captions_found", video_id=video_id)
                return None

            # Prefer manual subs over auto-generated
            vtt_file = vtt_files[0]
            for f in vtt_files:
                if 'en.' in f.name and 'en-orig' not in f.name:
                    vtt_file = f
                    break

            # Read and parse VTT
            vtt_content = vtt_file.read_text(encoding='utf-8')
            full_text, segments = _parse_vtt_to_text(vtt_content)

            if not full_text:
                logger.info("empty_captions", video_id=video_id)
                return None

            # Clean up VTT files
            for f in vtt_files:
                f.unlink()

            logger.info(
                "captions_extracted",
                video_id=video_id,
                text_length=len(full_text),
                segments_count=len(segments),
            )

            # Return data for orchestrator to persist to MongoDB
            return {
                "video_id": video_id,
                "source": "youtube_captions",
                "text": full_text,
                "segments": segments,
                "language": "en",
            }

    except Exception as e:
        logger.warning("caption_extraction_failed", video_id=video_id, error=str(e))
        return None


async def extract_captions(video_id: str) -> dict[str, Any] | None:
    """Extract captions for a video asynchronously.

    Args:
        video_id: YouTube video ID

    Returns:
        Dict with transcript data, or None if no captions available
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _extract_captions_sync, video_id)
    return result


def has_captions(video_id: str) -> bool:
    """Check if a video has captions available (sync check)."""
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {"quiet": True, "no_warnings": True}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                return False

            # Check for manual subtitles first
            subs = info.get("subtitles", {})
            if "en" in subs:
                return True

            # Check for auto-captions
            auto_caps = info.get("automatic_captions", {})
            return "en" in auto_caps or "en-orig" in auto_caps

    except Exception:
        return False
