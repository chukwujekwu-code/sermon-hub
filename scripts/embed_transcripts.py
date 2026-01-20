#!/usr/bin/env python3
"""CLI script for embedding sermon transcripts into Qdrant."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import setup_logging, get_logger
from app.db.mongodb import mongodb
from app.db.qdrant import qdrant
from app.services.embeddings.pipeline import embedding_pipeline

setup_logging()
logger = get_logger(__name__)

# Rate limit delay (seconds) - Cohere trial has 100k tokens/min limit
RATE_LIMIT_DELAY = 1.0


async def main(video_id: str | None = None, recreate: bool = False, delay: float = RATE_LIMIT_DELAY) -> None:
    """Run the embedding pipeline.

    Args:
        video_id: Optional specific video to process
        recreate: Whether to recreate the collection (delete all existing data)
        delay: Delay between transcripts (for rate limiting)
    """
    logger.info("embedding_pipeline_started", video_id=video_id or "all", recreate=recreate)

    try:
        # Connect to MongoDB
        await mongodb.connect()
        if not mongodb.is_connected:
            print("ERROR: Could not connect to MongoDB")
            return

        if recreate:
            print("Recreating Qdrant collection (deleting all existing embeddings)...")
            qdrant.recreate_collection()

        if video_id:
            # Process single video
            result = await embedding_pipeline.process_transcript(video_id)
            print(f"\nProcessed video: {video_id}")
            print(f"Status: {result['status']}")
            print(f"Chunks created: {result['chunks']}")
        else:
            # Process all transcripts with rate limiting
            from app.db.repositories.transcript import TranscriptRepository

            qdrant.ensure_collection()
            repo = TranscriptRepository(mongodb.db)
            video_ids = await repo.list_all_video_ids()

            print(f"Found {len(video_ids)} transcripts to process")
            print(f"Rate limit delay: {delay}s between transcripts\n")

            completed = 0
            failed = 0
            total_chunks = 0

            for i, vid in enumerate(video_ids, 1):
                try:
                    result = await embedding_pipeline.process_transcript(vid)
                    if result["status"] == "completed":
                        completed += 1
                        total_chunks += result["chunks"]
                        print(f"[{i}/{len(video_ids)}] {vid}: {result['chunks']} chunks")
                    else:
                        failed += 1
                        print(f"[{i}/{len(video_ids)}] {vid}: {result['status']}")

                    # Rate limit delay
                    if delay > 0 and i < len(video_ids):
                        await asyncio.sleep(delay)

                except Exception as e:
                    failed += 1
                    print(f"[{i}/{len(video_ids)}] {vid}: ERROR - {e}")
                    # On rate limit, wait longer
                    if "rate limit" in str(e).lower():
                        print("Rate limit hit, waiting 60s...")
                        await asyncio.sleep(60)

            print("\n" + "=" * 50)
            print("EMBEDDING PIPELINE COMPLETE")
            print("=" * 50)
            print(f"Total transcripts: {len(video_ids)}")
            print(f"Completed: {completed}")
            print(f"Failed: {failed}")
            print(f"Total chunks created: {total_chunks}")
            print("=" * 50)

            # Show collection info
            info = qdrant.get_collection_info()
            print(f"\nQdrant Collection: {info['name']}")
            if "error" not in info:
                print(f"Total points: {info['points_count']}")
                print(f"Status: {info['status']}")

    except Exception as e:
        logger.error("embedding_pipeline_failed", error=str(e))
        print(f"\nError: {e}")
        raise
    finally:
        await mongodb.disconnect()
        qdrant.close()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Embed sermon transcripts into Qdrant vector database",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--video-id",
        help="Process only this specific video ID",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate the collection (delete all existing embeddings first)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=RATE_LIMIT_DELAY,
        help="Delay in seconds between transcripts (for rate limiting)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(video_id=args.video_id, recreate=args.recreate, delay=args.delay))
