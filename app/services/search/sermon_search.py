"""Sermon search service combining query expansion and vector search."""

from typing import Any

import structlog

from app.core.config import settings
from app.db.connection import db
from app.db.qdrant import qdrant
from app.db.repositories.video import VideoRepository
from app.services.embeddings import embedding_service
from app.services.search.query_expander import query_expander

logger = structlog.get_logger(__name__)


class SermonSearchService:
    """Search service for finding sermons based on user feelings."""

    async def search(
        self,
        user_feeling: str,
        limit: int = 5,
        expand_query: bool = True,
    ) -> dict[str, Any]:
        """Search for sermons that can help with how the user is feeling.

        Args:
            user_feeling: How the user is feeling (natural language)
            limit: Maximum number of results to return
            expand_query: Whether to use LLM to expand the query

        Returns:
            Search results with sermons and metadata
        """
        logger.info("sermon_search_started", feeling=user_feeling[:100], limit=limit)

        # Step 1: Expand query using LLM (if enabled)
        if expand_query:
            search_query = await query_expander.expand(user_feeling)
        else:
            search_query = user_feeling

        # Step 2: Embed the search query
        query_embedding = await embedding_service.embed_single(search_query)
        logger.info("query_embedded", dimensions=len(query_embedding))

        # Step 3: Search Qdrant for matching chunks
        search_results = qdrant.client.query_points(
            collection_name=settings.qdrant_collection_name,
            query=query_embedding,
            limit=limit * 3,  # Get more chunks, then dedupe by video
        )

        # Step 4: Deduplicate by video and get top results (filter by relevance)
        logger.info(
            "qdrant_raw_results",
            count=len(search_results.points),
            top_scores=[p.score for p in search_results.points[:5]] if search_results.points else [],
        )
        seen_videos = set()
        unique_results = []

        for point in search_results.points:
            # Skip results below minimum relevance threshold
            if point.score < settings.min_relevance_score:
                continue

            video_id = point.payload["video_id"]
            if video_id not in seen_videos:
                seen_videos.add(video_id)
                unique_results.append({
                    "video_id": video_id,
                    "score": point.score,
                    "matching_text": point.payload["text"],
                    "chunk_index": point.payload["chunk_index"],
                })

                if len(unique_results) >= limit:
                    break

        # Step 5: Enrich with video metadata from SQLite
        video_repo = VideoRepository(db.connection)
        enriched_results = []

        for result in unique_results:
            video = await video_repo.get_by_video_id(result["video_id"])
            if video:
                description = video.get("description") or ""
                enriched_results.append({
                    "video_id": result["video_id"],
                    "title": video.get("title") or "Untitled",
                    "description": description[:200] if description else "",
                    "duration_seconds": video.get("duration_seconds"),
                    "published_at": video.get("published_at"),
                    "thumbnail_url": video.get("thumbnail_url"),
                    "youtube_url": f"https://www.youtube.com/watch?v={result['video_id']}",
                    "relevance_score": round(result["score"], 3),
                    "matching_excerpt": result["matching_text"][:300] + "...",
                })

        logger.info(
            "sermon_search_completed",
            feeling=user_feeling[:50],
            results_count=len(enriched_results),
        )

        return {
            "query": user_feeling,
            "expanded_query": search_query if expand_query else None,
            "results": enriched_results,
            "total_results": len(enriched_results),
        }

    async def search_by_mood(
        self,
        mood: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search for sermons by predefined mood category.

        Args:
            mood: One of the predefined mood categories
            limit: Maximum number of results

        Returns:
            Search results
        """
        # Predefined mood mappings for common categories
        mood_prompts = {
            "anxious": "I'm feeling anxious and worried about the future",
            "sad": "I'm feeling sad and going through a difficult time",
            "grieving": "I'm grieving and dealing with loss",
            "lost": "I feel lost and confused about my purpose",
            "angry": "I'm feeling angry and frustrated",
            "grateful": "I'm feeling grateful and want to praise God",
            "hopeless": "I'm feeling hopeless and need encouragement",
            "fearful": "I'm feeling fearful and need courage",
            "lonely": "I'm feeling lonely and isolated",
            "overwhelmed": "I'm feeling overwhelmed and stressed",
        }

        feeling = mood_prompts.get(mood.lower(), f"I'm feeling {mood}")
        return await self.search(feeling, limit=limit)


# Global instance
sermon_search = SermonSearchService()
