"""YouTube service exceptions."""


class YouTubeError(Exception):
    """Base exception for YouTube service errors."""

    pass


class ChannelNotFoundError(YouTubeError):
    """Raised when a channel cannot be found."""

    pass


class VideoNotFoundError(YouTubeError):
    """Raised when a video cannot be found."""

    pass


class VideoUnavailableError(YouTubeError):
    """Raised when a video is unavailable (private, deleted, etc.)."""

    pass


class DownloadError(YouTubeError):
    """Raised when a download fails."""

    pass


class DownloadTimeoutError(DownloadError):
    """Raised when a download times out."""

    pass


class MetadataExtractionError(YouTubeError):
    """Raised when metadata extraction fails."""

    pass
