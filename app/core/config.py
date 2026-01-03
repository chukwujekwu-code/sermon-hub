"""Application configuration using pydantic-settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Sermon Recommender"
    debug: bool = False

    # Database
    database_url: str = Field(default="data/sermon.db")

    # Audio settings
    audio_output_dir: str = Field(default="data/audio")
    audio_format: Literal["mp3", "wav", "m4a"] = Field(default="mp3")
    audio_quality: str = Field(default="192")

    # Transcription settings
    transcripts_output_dir: str = Field(default="data/transcripts")
    whisper_model: str = Field(default="large-v3")

    # Download settings
    max_concurrent_downloads: int = Field(default=2, ge=1, le=10)
    download_delay_seconds: float = Field(default=3.0)
    download_timeout_seconds: int = Field(default=600)

    # Ingestion settings
    default_max_videos: int = Field(default=10)
    min_video_duration_minutes: int = Field(default=15, description="Minimum video duration in minutes")

    # Retry settings
    max_retry_attempts: int = Field(default=3)

    # Qdrant settings
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = Field(default=None)
    qdrant_collection_name: str = Field(default="sermon_chunks")

    # Embedding settings
    embedding_model: str = Field(default="all-mpnet-base-v2")
    embedding_dimensions: int = Field(default=768)
    chunk_size: int = Field(default=500, description="Target words per chunk")
    chunk_overlap: int = Field(default=50, description="Overlap words between chunks")

    # LLM settings
    groq_api_key: str | None = Field(default=None)
    groq_model: str = Field(default="llama-3.1-8b-instant")

    # Search settings
    min_relevance_score: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score to include in results"
    )

    @property
    def database_path(self) -> Path:
        """Get the database path as a Path object."""
        return Path(self.database_url)

    @property
    def audio_path(self) -> Path:
        """Get the audio output directory as a Path object."""
        return Path(self.audio_output_dir)

    @property
    def transcripts_path(self) -> Path:
        """Get the transcripts output directory as a Path object."""
        return Path(self.transcripts_output_dir)


settings = Settings()
