#!/usr/bin/env python3
"""CLI script for channel ingestion."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.connection import db
from app.services.ingestion.orchestrator import IngestionOrchestrator

setup_logging()
logger = get_logger(__name__)


async def main(
    channel_url: str,
    max_videos: int,
    download: bool,
    transcribe: bool,
) -> None:
    """Run the ingestion pipeline."""
    logger.info(
        "starting_ingestion",
        channel_url=channel_url,
        max_videos=max_videos,
        download=download,
        transcribe=transcribe,
    )

    try:
        # Connect to database
        await db.connect()

        # Initialize schema if needed
        try:
            await db.init_schema()
        except Exception:
            pass  # Schema already exists

        # Run ingestion
        orchestrator = IngestionOrchestrator()
        result = await orchestrator.sync_channel(
            channel_url=channel_url,
            max_videos=max_videos,
            download=download,
            transcribe=transcribe,
        )

        # Print summary
        print("\n" + "=" * 50)
        print("INGESTION COMPLETE")
        print("=" * 50)
        print(f"Channel: {result['channel_name']}")
        print(f"Videos found: {result['videos_found']}")
        print(f"Videos skipped (< {settings.min_video_duration_minutes} min): {result.get('videos_skipped', 0)}")
        print(f"Videos created: {result['videos_created']}")
        print(f"Videos downloaded: {result['videos_downloaded']}")
        print(f"Videos transcribed: {result['videos_transcribed']}")
        print(f"Videos failed: {result['videos_failed']}")
        print("=" * 50)

    except KeyboardInterrupt:
        logger.info("ingestion_interrupted")
        print("\nIngestion interrupted by user")
    except Exception as e:
        logger.error("ingestion_failed", error=str(e))
        print(f"\nError: {e}")
        raise
    finally:
        await db.disconnect()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest videos from a YouTube channel",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "channel_url",
        help="YouTube channel URL (e.g., https://www.youtube.com/@PastorPoju)",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=settings.default_max_videos,
        help="Maximum number of videos to ingest",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip audio download (metadata only)",
    )
    parser.add_argument(
        "--no-transcribe",
        action="store_true",
        help="Skip transcription (download only)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        main(
            channel_url=args.channel_url,
            max_videos=args.max_videos,
            download=not args.no_download,
            transcribe=not args.no_transcribe,
        )
    )
