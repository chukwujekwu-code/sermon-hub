"""Search API routes for sermon recommendations."""

from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

import structlog

from app.services.search import sermon_search

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    """Request body for sermon search."""

    feeling: str = Field(
        ...,
        description="How the user is feeling (natural language)",
        min_length=3,
        max_length=500,
        examples=["I'm feeling anxious about the future"],
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of results to return",
    )


class MoodSearchRequest(BaseModel):
    """Request body for mood-based search."""

    mood: Literal[
        "anxious",
        "sad",
        "grieving",
        "lost",
        "angry",
        "grateful",
        "hopeless",
        "fearful",
        "lonely",
        "overwhelmed",
    ] = Field(..., description="Predefined mood category")
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/search")
async def search_sermons(request: SearchRequest) -> dict[str, Any]:
    """Search for sermons based on how you're feeling.

    Uses LLM to understand your emotional state and find sermons
    that can help, not just sermons about your problem.

    Example:
        Input: "I'm feeling anxious and worried about my job"
        Returns: Sermons about peace, trust in God, casting your cares
    """
    result = await sermon_search.search(
        user_feeling=request.feeling,
        limit=request.limit,
    )
    return result


@router.get("/search")
async def search_sermons_get(
    feeling: str = Query(
        ...,
        description="How you're feeling",
        min_length=3,
        examples=["I'm feeling anxious"],
    ),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """Search for sermons based on how you're feeling (GET version)."""
    result = await sermon_search.search(
        user_feeling=feeling,
        limit=limit,
    )
    return result


@router.post("/search/mood")
async def search_by_mood(request: MoodSearchRequest) -> dict[str, Any]:
    """Search for sermons by predefined mood category.

    Available moods:
    - anxious, sad, grieving, lost, angry
    - grateful, hopeless, fearful, lonely, overwhelmed
    """
    result = await sermon_search.search_by_mood(
        mood=request.mood,
        limit=request.limit,
    )
    return result


@router.get("/search/mood/{mood}")
async def search_by_mood_get(
    mood: Literal[
        "anxious",
        "sad",
        "grieving",
        "lost",
        "angry",
        "grateful",
        "hopeless",
        "fearful",
        "lonely",
        "overwhelmed",
    ],
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """Search for sermons by mood category (GET version)."""
    result = await sermon_search.search_by_mood(
        mood=mood,
        limit=limit,
    )
    return result
