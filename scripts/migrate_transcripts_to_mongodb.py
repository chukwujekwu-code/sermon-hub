#!/usr/bin/env python3
"""
Migrate existing JSON transcripts to MongoDB.

Usage:
    python scripts/migrate_transcripts_to_mongodb.py
    python scripts/migrate_transcripts_to_mongodb.py --dry-run
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.connection import db
from app.db.mongodb import mongodb
from app.db.repositories.transcript import TranscriptRepository
from app.db.repositories.video import VideoRepository
from app.db.repositories.channel import ChannelRepository
from app.models.transcript import TranscriptCreate, TranscriptSegment

setup_logging()
logger = get_logger(__name__)


async def migrate_transcripts(dry_run: bool = False) -> dict:
    """Migrate all JSON transcripts to MongoDB."""

    # Connect to databases
    await db.connect()
    await mongodb.connect()
    await mongodb.ensure_indexes()

    # Initialize repositories
    transcript_repo = TranscriptRepository(mongodb.db)
    video_repo = VideoRepository(db.connection)
    channel_repo = ChannelRepository(db.connection)

    # Build channel lookup cache
    channels: dict[str, str] = {}  # channel_id -> channel_name

    # Find all JSON files
    transcripts_dir = settings.transcripts_path
    if not transcripts_dir.exists():
        print(f"Transcripts directory not found: {transcripts_dir}")
        return {"error": "transcripts directory not found"}

    json_files = list(transcripts_dir.glob("*.json"))

    print(f"Found {len(json_files)} transcript files to migrate")
    print(f"Dry run: {dry_run}")
    print("-" * 50)

    migrated = 0
    skipped = 0
    failed = 0

    for i, json_file in enumerate(json_files, 1):
        video_id = json_file.stem

        try:
            # Load JSON
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            # Get video metadata for channel info
            video = await video_repo.get_by_video_id(video_id)
            if not video:
                print(f"[{i}/{len(json_files)}] SKIP {video_id} - no video metadata")
                skipped += 1
                continue

            channel_id = video["channel_id"]

            # Get channel name (cached)
            if channel_id not in channels:
                channel = await channel_repo.get_by_channel_id(channel_id)
                channels[channel_id] = channel["channel_name"] if channel else "Unknown"

            channel_name = channels[channel_id]

            # Prepare transcript document
            segments = [
                TranscriptSegment(start=s["start"], end=s["end"], text=s["text"])
                for s in data.get("segments", [])
            ]

            transcript = TranscriptCreate(
                video_id=video_id,
                channel_id=channel_id,
                channel_name=channel_name,
                source=data.get("source", "youtube_captions"),
                text=data.get("text", ""),
                segments=segments,
                language=data.get("language", "en"),
            )

            if dry_run:
                print(f"[{i}/{len(json_files)}] DRY-RUN {video_id} -> {channel_name}")
            else:
                await transcript_repo.upsert(transcript)
                print(f"[{i}/{len(json_files)}] OK {video_id} -> {channel_name}")

            migrated += 1

        except Exception as e:
            print(f"[{i}/{len(json_files)}] FAIL {video_id}: {e}")
            logger.error("migration_failed", video_id=video_id, error=str(e))
            failed += 1

    # Cleanup
    await mongodb.disconnect()
    await db.disconnect()

    summary = {
        "total": len(json_files),
        "migrated": migrated,
        "skipped": skipped,
        "failed": failed,
        "dry_run": dry_run,
    }

    print("\n" + "=" * 50)
    print("MIGRATION COMPLETE" if not dry_run else "DRY RUN COMPLETE")
    print("=" * 50)
    print(f"Total files: {summary['total']}")
    print(f"Migrated: {summary['migrated']}")
    print(f"Skipped: {summary['skipped']}")
    print(f"Failed: {summary['failed']}")

    return summary


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(migrate_transcripts(dry_run=dry_run))
