#!/usr/bin/env python3
"""
Incremental channel sync script for production use.

This script:
1. Fetches new videos from the channel (skips existing)
2. Downloads audio and extracts captions
3. Logs results for monitoring
4. Exits with appropriate status codes for cron

Usage:
    # Incremental sync (default 50 videos check)
    python scripts/sync_channel.py

    # Initial bulk load (all videos)
    python scripts/sync_channel.py --max-videos 1000

    # Specific channel
    python scripts/sync_channel.py --channel "https://www.youtube.com/@PastorPoju"
"""

import argparse
import asyncio
import sys
from datetime import datetime, UTC
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.connection import db
from app.services.ingestion.orchestrator import IngestionOrchestrator

setup_logging()
logger = get_logger(__name__)

# Default channel to sync
DEFAULT_CHANNEL = "https://www.youtube.com/@PastorPoju"


async def main(
    channel_url: str,
    max_videos: int,
    download: bool,
    transcribe: bool,
) -> int:
    """Run the sync and return exit code.

    Returns:
        0 = success
        1 = partial failure (some videos failed)
        2 = complete failure
    """
    start_time = datetime.now(UTC)

    logger.info(
        "sync_started",
        channel_url=channel_url,
        max_videos=max_videos,
        timestamp=start_time.isoformat(),
    )

    try:
        await db.connect()
        await db.init_schema()

        orchestrator = IngestionOrchestrator()
        result = await orchestrator.sync_channel(
            channel_url=channel_url,
            max_videos=max_videos,
            download=download,
            transcribe=transcribe,
        )

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        # Log summary for monitoring
        logger.info(
            "sync_completed",
            channel_name=result["channel_name"],
            videos_found=result["videos_found"],
            videos_created=result["videos_created"],
            videos_transcribed=result["videos_transcribed"],
            videos_failed=result["videos_failed"],
            duration_seconds=round(duration, 1),
        )

        # Print summary
        print(f"\n{'='*50}")
        print(f"SYNC COMPLETE - {result['channel_name']}")
        print(f"{'='*50}")
        print(f"Videos checked:     {result['videos_found']}")
        print(f"Videos skipped:     {result.get('videos_skipped', 0)} (< {settings.min_video_duration_minutes} min)")
        print(f"New videos added:   {result['videos_created']}")
        print(f"Transcribed:        {result['videos_transcribed']}")
        print(f"Failed:             {result['videos_failed']}")
        print(f"Duration:           {duration:.1f}s")
        print(f"{'='*50}\n")

        # Return appropriate exit code
        if result["videos_failed"] > 0:
            if result["videos_transcribed"] == 0:
                return 2  # Complete failure
            return 1  # Partial failure
        return 0  # Success

    except Exception as e:
        logger.error("sync_failed", error=str(e))
        print(f"\nERROR: {e}")
        return 2
    finally:
        await db.disconnect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync videos from a YouTube channel",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--channel",
        default=DEFAULT_CHANNEL,
        help="YouTube channel URL",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=50,
        help="Maximum videos to check (use high number for bulk load)",
    )
    parser.add_argument(
        "--download-audio",
        action="store_true",
        help="Download audio for Whisper fallback (usually not needed - captions preferred)",
    )
    parser.add_argument(
        "--no-transcribe",
        action="store_true",
        help="Skip transcription",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(
        main(
            channel_url=args.channel,
            max_videos=args.max_videos,
            download=args.download_audio,  # Default: False (captions preferred)
            transcribe=not args.no_transcribe,
        )
    )
    sys.exit(exit_code)
