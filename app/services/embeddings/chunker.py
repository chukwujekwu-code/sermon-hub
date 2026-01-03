"""Text chunking utilities for sermon transcripts."""

from dataclasses import dataclass

from app.core.config import settings


@dataclass
class Chunk:
    """A chunk of text from a sermon transcript."""

    video_id: str
    chunk_index: int
    text: str
    start_word: int
    end_word: int


def chunk_text(
    text: str,
    video_id: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Split text into overlapping chunks.

    Args:
        text: Full transcript text
        video_id: ID of the source video
        chunk_size: Target words per chunk (defaults to settings)
        chunk_overlap: Overlap words between chunks (defaults to settings)

    Returns:
        List of Chunk objects
    """
    if chunk_size is None:
        chunk_size = settings.chunk_size
    if chunk_overlap is None:
        chunk_overlap = settings.chunk_overlap

    # Split into words
    words = text.split()

    if not words:
        return []

    chunks = []
    chunk_index = 0
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))

        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        chunks.append(
            Chunk(
                video_id=video_id,
                chunk_index=chunk_index,
                text=chunk_text,
                start_word=start,
                end_word=end,
            )
        )

        chunk_index += 1

        # Move start position, accounting for overlap
        start = end - chunk_overlap

        # Avoid infinite loop on small texts
        if start >= len(words) - chunk_overlap:
            break

    return chunks


def estimate_chunk_count(text: str, chunk_size: int | None = None) -> int:
    """Estimate how many chunks a text will produce.

    Args:
        text: Full transcript text
        chunk_size: Target words per chunk

    Returns:
        Estimated number of chunks
    """
    if chunk_size is None:
        chunk_size = settings.chunk_size

    words = len(text.split())
    if words == 0:
        return 0

    # Account for overlap
    overlap = settings.chunk_overlap
    effective_step = chunk_size - overlap

    return max(1, (words - overlap) // effective_step + 1)
