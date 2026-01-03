"""Transcription service exceptions."""


class TranscriptionError(Exception):
    """Base exception for transcription service errors."""

    pass


class AudioFileNotFoundError(TranscriptionError):
    """Raised when the audio file to transcribe doesn't exist."""

    pass


class TranscriptionFailedError(TranscriptionError):
    """Raised when transcription fails."""

    pass


class ModelLoadError(TranscriptionError):
    """Raised when the Whisper model fails to load."""

    pass
