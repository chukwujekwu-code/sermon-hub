"""Transcript cleaning utilities to remove noise and repetition."""

import re

import structlog

logger = structlog.get_logger(__name__)


def clean_transcript(text: str) -> str:
    """Clean transcript text by removing repetition and noise.

    YouTube auto-captions often have overlapping segments that cause
    phrases to repeat 2-3 times. This function removes that noise.

    Args:
        text: Raw transcript text

    Returns:
        Cleaned transcript text
    """
    if not text:
        return text

    original_length = len(text)

    # Step 1: Remove consecutive duplicate sentences/phrases
    text = _remove_consecutive_duplicates(text)

    # Step 2: Remove stuttering patterns (word word word)
    text = _remove_word_stuttering(text)

    # Step 3: Clean up filler words and noise
    text = _clean_fillers(text)

    # Step 4: Normalize whitespace
    text = _normalize_whitespace(text)

    cleaned_length = len(text)
    reduction = (1 - cleaned_length / original_length) * 100 if original_length > 0 else 0

    logger.info(
        "transcript_cleaned",
        original_chars=original_length,
        cleaned_chars=cleaned_length,
        reduction_percent=round(reduction, 1),
    )

    return text


def _remove_consecutive_duplicates(text: str) -> str:
    """Remove consecutive duplicate phrases.

    Handles patterns like:
    "I want to share I want to share I want to share something"
    -> "I want to share something"
    """
    words = text.split()
    if len(words) < 4:
        return text

    result = []
    i = 0

    while i < len(words):
        # Try to find repeating patterns of length 3-15 words
        found_repeat = False

        for pattern_len in range(3, min(16, (len(words) - i) // 2 + 1)):
            pattern = words[i : i + pattern_len]
            next_chunk = words[i + pattern_len : i + pattern_len * 2]

            if pattern == next_chunk:
                # Found a repeat - skip ahead past all repetitions
                repeat_count = 1
                pos = i + pattern_len

                while pos + pattern_len <= len(words):
                    if words[pos : pos + pattern_len] == pattern:
                        repeat_count += 1
                        pos += pattern_len
                    else:
                        break

                # Add pattern once and skip all repetitions
                result.extend(pattern)
                i = pos
                found_repeat = True
                break

        if not found_repeat:
            result.append(words[i])
            i += 1

    return " ".join(result)


def _remove_word_stuttering(text: str) -> str:
    """Remove word-level stuttering like 'the the the' or 'um um'.

    Handles patterns like:
    "he he he said" -> "he said"
    "um um um" -> "um"
    """
    # Match 2+ consecutive identical words
    pattern = r'\b(\w+)(\s+\1){1,}\b'

    def replace_stutter(match):
        return match.group(1)

    return re.sub(pattern, replace_stutter, text, flags=re.IGNORECASE)


def _clean_fillers(text: str) -> str:
    """Remove or reduce filler words and verbal tics."""
    # Remove excessive "uh", "um", "ah" (keep one if multiple)
    text = re.sub(r'\b(uh|um|ah|er)\b(\s+\b(uh|um|ah|er)\b)+', r'\1', text, flags=re.IGNORECASE)

    # Remove standalone fillers at sentence boundaries
    text = re.sub(r'\.\s*(Uh|Um|Ah)\s*,?\s*', '. ', text)
    text = re.sub(r'^(Uh|Um|Ah)\s*,?\s*', '', text)

    return text


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace and punctuation."""
    # Multiple spaces to single
    text = re.sub(r'\s+', ' ', text)

    # Fix spacing around punctuation
    text = re.sub(r'\s+([.,!?])', r'\1', text)
    text = re.sub(r'([.,!?])(?=[A-Za-z])', r'\1 ', text)

    # Remove space at start/end
    text = text.strip()

    return text


def estimate_cleaning_reduction(text: str) -> float:
    """Estimate what percentage of text will be removed by cleaning.

    Args:
        text: Raw transcript text

    Returns:
        Estimated reduction as a decimal (0.0 to 1.0)
    """
    if not text:
        return 0.0

    original_len = len(text)
    cleaned = clean_transcript(text)
    cleaned_len = len(cleaned)

    return 1 - (cleaned_len / original_len) if original_len > 0 else 0.0
