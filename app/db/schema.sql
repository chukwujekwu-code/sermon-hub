-- Sermon Recommender Database Schema

-- Channels being monitored
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT UNIQUE NOT NULL,
    channel_name TEXT NOT NULL,
    channel_url TEXT NOT NULL,
    last_sync_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_channels_channel_id ON channels(channel_id);
CREATE INDEX IF NOT EXISTS idx_channels_is_active ON channels(is_active);

-- Video metadata
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT UNIQUE NOT NULL,
    channel_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    duration_seconds INTEGER,
    published_at TIMESTAMP,
    thumbnail_url TEXT,
    view_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
);

CREATE INDEX IF NOT EXISTS idx_videos_video_id ON videos(video_id);
CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at DESC);

-- Ingestion tracking (includes transcription status)
CREATE TABLE IF NOT EXISTS ingestion_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    audio_path TEXT,
    audio_format TEXT,
    audio_size_bytes INTEGER,
    transcript_path TEXT,
    transcript_text TEXT,
    error_message TEXT,
    error_count INTEGER DEFAULT 0,
    download_started_at TIMESTAMP,
    download_completed_at TIMESTAMP,
    transcription_started_at TIMESTAMP,
    transcription_completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_status ON ingestion_status(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_video_id ON ingestion_status(video_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_error_count ON ingestion_status(error_count);
