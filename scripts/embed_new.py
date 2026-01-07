#!/usr/bin/env python3
"""
Embed only new transcripts that aren't already in Qdrant.

This script:
1. Finds all transcripts in MongoDB
2. Checks which video_ids are already in Qdrant
3. Only embeds new ones
4. Logs results for monitoring

Usage:
    python scripts/embed_new.py
"""

import asyncio
import sys
from datetime import datetime, UTC
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.mongodb import mongodb
from app.db.qdrant import qdrant
from app.db.repositories.transcript import TranscriptRepository
from app.services.embeddings.pipeline import embedding_pipeline

setup_logging()
logger = get_logger(__name__)


def get_embedded_video_ids() -> set[str]:
    """Get all video_ids currently in Qdrant."""
    collection_name = settings.qdrant_collection_name

    try:
        # Scroll through all points to get video_ids
        video_ids = set()
        offset = None

        while True:
            results, offset = qdrant.client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=offset,
                with_payload=["video_id"],
                with_vectors=False,
            )

            for point in results:
                video_ids.add(point.payload["video_id"])

            if offset is None:
                break

        return video_ids

    except Exception as e:
        logger.warning("failed_to_get_embedded_ids", error=str(e))
        return set()


async def get_transcript_video_ids() -> set[str]:
    """Get all video_ids that have transcripts in MongoDB."""
    if not mongodb.is_connected:
        logger.warning("mongodb_not_connected")
        return set()

    repo = TranscriptRepository(mongodb.db)
    video_ids = await repo.list_all_video_ids()
    return set(video_ids)


async def main() -> int:
    """Embed new transcripts and return exit code."""
    start_time = datetime.now(UTC)

    logger.info("embed_new_started", timestamp=start_time.isoformat())

    try:
        # Connect to MongoDB
        await mongodb.connect()

        # Ensure collection exists
        qdrant.ensure_collection()

        # Find what needs embedding
        transcript_ids = await get_transcript_video_ids()
        embedded_ids = get_embedded_video_ids()
        new_ids = transcript_ids - embedded_ids

        logger.info(
            "embedding_analysis",
            total_transcripts=len(transcript_ids),
            already_embedded=len(embedded_ids),
            to_embed=len(new_ids),
        )

        if not new_ids:
            print("No new transcripts to embed.")
            logger.info("embed_new_completed", embedded=0, failed=0)
            return 0

        total = len(new_ids)
        print(f"Found {total} new transcripts to embed...\n")

        # Embed each new transcript
        embedded = 0
        failed = 0
        new_ids_list = list(new_ids)

        for i, video_id in enumerate(new_ids_list, 1):
            remaining = total - i
            try:
                result = await embedding_pipeline.process_transcript(video_id)
                if result["status"] == "completed":
                    embedded += 1
                    print(f"[{i}/{total}] ✓ {video_id} ({result['chunks']} chunks) | {remaining} left")
                else:
                    failed += 1
                    print(f"[{i}/{total}] ✗ {video_id} ({result['status']}) | {remaining} left")
            except Exception as e:
                failed += 1
                logger.error("embed_failed", video_id=video_id, error=str(e))
                print(f"[{i}/{total}] ✗ {video_id} (error: {e}) | {remaining} left")

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        # Log summary
        logger.info(
            "embed_new_completed",
            embedded=embedded,
            failed=failed,
            duration_seconds=round(duration, 1),
        )

        # Print summary
        print(f"\n{'='*50}")
        print("EMBEDDING COMPLETE")
        print(f"{'='*50}")
        print(f"New transcripts embedded: {embedded}")
        print(f"Failed: {failed}")
        print(f"Duration: {duration:.1f}s")
        print(f"{'='*50}\n")

        # Get collection stats
        info = qdrant.get_collection_info()
        print(f"Total vectors in Qdrant: {info.get('points_count', 'unknown')}")

        return 1 if failed > 0 else 0

    except Exception as e:
        logger.error("embed_new_failed", error=str(e))
        print(f"\nERROR: {e}")
        return 2
    finally:
        qdrant.close()
        await mongodb.disconnect()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
