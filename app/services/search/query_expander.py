"""LLM-based query expansion for mood-to-sermon matching."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import structlog
from groq import Groq

from app.core.config import settings

logger = structlog.get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)

SYSTEM_PROMPT = """You are a helpful assistant that transforms how someone is feeling into search terms for finding relevant Christian sermons.

Given a user's emotional state or feeling, generate search terms that describe what KIND of sermon content would HELP them - not content about their problem, but content that provides the SOLUTION.

Examples:
- "I'm feeling anxious" → "peace, trusting God, letting go of worry, finding rest, calming your mind, faith over fear"
- "I'm grieving" → "comfort in pain, God's presence, healing from loss, hope after death, strength in sorrow"
- "I feel lost and confused" → "finding direction, God's purpose for your life, seeking wisdom, clarity, divine guidance"
- "I'm angry at someone" → "forgiveness, releasing bitterness, letting go, making peace, healing relationships"

Rules:
1. Focus on SOLUTIONS, not the problem
2. Use natural spoken language that would appear in a sermon (avoid specific Bible verse references)
3. Keep output concise - just the search terms, no explanations
4. Output should be a natural phrase suitable for semantic search
5. Do not use bullet points or formatting - just flowing text"""


class QueryExpander:
    """Expands user mood/feeling into sermon search terms using LLM."""

    def __init__(self):
        """Initialize the query expander."""
        self._client: Groq | None = None

    @property
    def client(self) -> Groq:
        """Get the Groq client, creating if needed."""
        if self._client is None:
            if not settings.groq_api_key:
                raise ValueError("GROQ_API_KEY not configured")
            self._client = Groq(api_key=settings.groq_api_key)
        return self._client

    def expand_sync(self, user_feeling: str) -> str:
        """Expand user feeling into search terms synchronously.

        Args:
            user_feeling: How the user is feeling

        Returns:
            Expanded search terms for finding helpful sermons
        """
        logger.info("expanding_query", input=user_feeling[:100])

        try:
            response = self.client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_feeling},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            expanded = response.choices[0].message.content.strip()
            logger.info("query_expanded", input=user_feeling[:50], output=expanded[:100])

            return expanded

        except Exception as e:
            # Fallback to original query if LLM fails
            logger.warning(
                "query_expansion_failed",
                input=user_feeling[:50],
                error=str(e),
                fallback="using_original_query",
            )
            return user_feeling

    async def expand(self, user_feeling: str) -> str:
        """Expand user feeling into search terms asynchronously.

        Args:
            user_feeling: How the user is feeling

        Returns:
            Expanded search terms for finding helpful sermons
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            self.expand_sync,
            user_feeling,
        )
        return result


# Global instance
query_expander = QueryExpander()
