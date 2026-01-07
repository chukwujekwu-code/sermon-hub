#!/usr/bin/env python3
"""
Sync all active channels from channels.json.

This script:
1. Reads channels.json for list of pastors
2. Syncs each active channel (fetches videos, extracts captions)
3. Saves transcripts to MongoDB

Usage:
    python scripts/sync_all_channels.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import setup_logging, get_logger
from app.db.connection import db
from app.db.mongodb import mongodb
from app.services.ingestion.orchestrator import IngestionOrchestrator

setup_logging()
logger = get_logger(__name__)


async def main() -> int:
    """Sync all active channels and return exit code."""

    # Load channels config
    config_path = Path(__file__).parent.parent / "channels.json"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found")
        return 1

    with open(config_path) as f:
        config = json.load(f)

    channels = config.get("channels", [])
    if not channels:
        print("No channels configured in channels.json")
        return 0

    # Connect to databases
    await db.connect()
    await mongodb.connect()
    await mongodb.ensure_indexes()

    orchestrator = IngestionOrchestrator()

    results = []
    total_transcribed = 0
    total_failed = 0

    for channel in channels:
        # Skip inactive channels
        if not channel.get("active", True):
            print(f"\nSkipping (inactive): {channel['name']}")
            continue

        print(f"\n{'='*50}")
        print(f"Syncing: {channel['name']}")
        print(f"URL: {channel['url']}")
        print(f"{'='*50}")

        try:
            result = await orchestrator.sync_channel(
                channel_url=channel["url"],
                max_videos=channel.get("max_videos", 50),
                download=False,  # Captions only, no audio download
                transcribe=True,
            )

            results.append({
                "channel": channel["name"],
                "status": "success",
                **result
            })

            total_transcribed += result.get("videos_transcribed", 0)
            print(f"OK: {result.get('videos_transcribed', 0)} transcribed, {result.get('videos_failed', 0)} failed")

        except Exception as e:
            logger.error("channel_sync_failed", channel=channel["name"], error=str(e))
            print(f"FAILED: {e}")
            results.append({
                "channel": channel["name"],
                "status": "error",
                "error": str(e)
            })
            total_failed += 1

    # Cleanup
    await mongodb.disconnect()
    await db.disconnect()

    # Print summary
    print(f"\n{'='*50}")
    print("SYNC COMPLETE")
    print(f"{'='*50}")

    for r in results:
        if r["status"] == "error":
            print(f"  FAIL: {r['channel']} - {r.get('error', 'unknown')}")
        else:
            print(f"  OK: {r['channel']} - {r.get('videos_transcribed', 0)} new transcripts")

    print(f"\nTotal new transcripts: {total_transcribed}")
    print(f"Channels failed: {total_failed}")

    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
