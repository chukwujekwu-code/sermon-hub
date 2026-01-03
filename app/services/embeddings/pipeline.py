"""Embedding pipeline for processing sermon transcripts."""

import json
from typing import Any
from uuid import uuid4

import structlog
from qdrant_client.http.models import PointStruct

from app.core.config import settings
from app.db.qdrant import qdrant
from app.services.embeddings.chunker import Chunk, chunk_text
from app.services.embeddings.cleaner import clean_transcript
from app.services.embeddings.embedding_service import embedding_service

logger = structlog.get_logger(__name__)

# Batch size for Qdrant upserts
UPSERT_BATCH_SIZE = 100


class EmbeddingPipeline:
    """Pipeline for embedding sermon transcripts and storing in Qdrant."""

    def __init__(self):
        """Initialize the embedding pipeline."""
        self.transcripts_dir = settings.transcripts_path

    async def process_transcript(self, video_id: str) -> dict[str, Any]:
        """Process a single transcript: chunk, embed, and store.

        Args:
            video_id: ID of the video to process

        Returns:
            Summary of processing
        """
        transcript_path = self.transcripts_dir / f"{video_id}.json"

        if not transcript_path.exists():
            logger.warning("transcript_not_found", video_id=video_id)
            return {"video_id": video_id, "status": "not_found", "chunks": 0}

        # Load transcript
        with open(transcript_path, encoding="utf-8") as f:
            transcript_data = json.load(f)

        text = transcript_data.get("text", "")
        if not text:
            logger.warning("transcript_empty", video_id=video_id)
            return {"video_id": video_id, "status": "empty", "chunks": 0}

        # Clean the transcript (removes repetition from YouTube captions)
        text = clean_transcript(text)

        # Chunk the text
        chunks = chunk_text(text, video_id)
        logger.info("transcript_chunked", video_id=video_id, chunks=len(chunks))

        if not chunks:
            return {"video_id": video_id, "status": "no_chunks", "chunks": 0}

        # Embed chunks
        chunk_texts = [c.text for c in chunks]
        embeddings = await embedding_service.embed(chunk_texts)
        logger.info("chunks_embedded", video_id=video_id, embeddings=len(embeddings))

        # Store in Qdrant
        points = self._create_points(chunks, embeddings, transcript_data)
        await self._upsert_points(points)

        return {
            "video_id": video_id,
            "status": "completed",
            "chunks": len(chunks),
        }

    def _create_points(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        transcript_data: dict,
    ) -> list[PointStruct]:
        """Create Qdrant points from chunks and embeddings.

        Args:
            chunks: List of text chunks
            embeddings: List of embedding vectors
            transcript_data: Original transcript data for metadata

        Returns:
            List of PointStruct for Qdrant
        """
        points = []

        for chunk, embedding in zip(chunks, embeddings):
            point_id = str(uuid4())

            payload = {
                "video_id": chunk.video_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "start_word": chunk.start_word,
                "end_word": chunk.end_word,
                "source": transcript_data.get("source", "unknown"),
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        return points

    async def _upsert_points(self, points: list[PointStruct]) -> None:
        """Upsert points to Qdrant in batches.

        Args:
            points: List of points to upsert
        """
        collection_name = settings.qdrant_collection_name

        # Batch upserts
        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[i : i + UPSERT_BATCH_SIZE]
            qdrant.client.upsert(
                collection_name=collection_name,
                points=batch,
            )
            logger.debug(
                "points_upserted",
                batch_start=i,
                batch_size=len(batch),
            )

    async def process_all_transcripts(self) -> dict[str, Any]:
        """Process all available transcripts.

        Returns:
            Summary of all processing
        """
        # Ensure collection exists
        qdrant.ensure_collection()

        # Find all transcript files
        transcript_files = list(self.transcripts_dir.glob("*.json"))
        logger.info("transcripts_found", count=len(transcript_files))

        if not transcript_files:
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "total_chunks": 0,
            }

        completed = 0
        failed = 0
        total_chunks = 0
        results = []

        for transcript_file in transcript_files:
            video_id = transcript_file.stem

            try:
                result = await self.process_transcript(video_id)
                results.append(result)

                if result["status"] == "completed":
                    completed += 1
                    total_chunks += result["chunks"]
                else:
                    failed += 1

            except Exception as e:
                logger.error(
                    "transcript_processing_failed",
                    video_id=video_id,
                    error=str(e),
                )
                failed += 1
                results.append({
                    "video_id": video_id,
                    "status": "error",
                    "error": str(e),
                })

        summary = {
            "total": len(transcript_files),
            "completed": completed,
            "failed": failed,
            "total_chunks": total_chunks,
            "results": results,
        }

        logger.info("embedding_pipeline_completed", **{k: v for k, v in summary.items() if k != "results"})
        return summary

    def delete_video_chunks(self, video_id: str) -> int:
        """Delete all chunks for a specific video.

        Args:
            video_id: ID of the video

        Returns:
            Number of points deleted
        """
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        collection_name = settings.qdrant_collection_name

        # Delete by filter
        result = qdrant.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="video_id",
                        match=MatchValue(value=video_id),
                    )
                ]
            ),
        )

        logger.info("video_chunks_deleted", video_id=video_id)
        return result


# Global instance
embedding_pipeline = EmbeddingPipeline()
