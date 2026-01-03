#!/usr/bin/env python3
"""CLI script for embedding sermon transcripts into Qdrant."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import setup_logging, get_logger
from app.db.qdrant import qdrant
from app.services.embeddings.pipeline import embedding_pipeline

setup_logging()
logger = get_logger(__name__)


async def main(video_id: str | None = None, recreate: bool = False) -> None:
    """Run the embedding pipeline.

    Args:
        video_id: Optional specific video to process
        recreate: Whether to recreate the collection (delete all existing data)
    """
    logger.info("embedding_pipeline_started", video_id=video_id or "all", recreate=recreate)

    try:
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
            # Process all transcripts
            result = await embedding_pipeline.process_all_transcripts()

            print("\n" + "=" * 50)
            print("EMBEDDING PIPELINE COMPLETE")
            print("=" * 50)
            print(f"Total transcripts: {result['total']}")
            print(f"Completed: {result['completed']}")
            print(f"Failed: {result['failed']}")
            print(f"Total chunks created: {result['total_chunks']}")
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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(video_id=args.video_id, recreate=args.recreate))
