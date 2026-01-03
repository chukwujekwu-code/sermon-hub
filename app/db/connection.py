"""Async SQLite database connection manager."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class Database:
    """Async SQLite database connection manager."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize database with path."""
        self.db_path = Path(db_path) if db_path else settings.database_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize the database connection."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(
            self.db_path,
            check_same_thread=False,
        )
        self._connection.row_factory = aiosqlite.Row

        # Enable foreign keys
        await self._connection.execute("PRAGMA foreign_keys = ON")

        logger.info("database_connected", path=str(self.db_path))

    async def disconnect(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("database_disconnected")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Context manager for database transactions."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        try:
            yield self._connection
            await self._connection.commit()
        except Exception:
            await self._connection.rollback()
            raise

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the current database connection."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    async def init_schema(self, schema_path: str | Path | None = None) -> None:
        """Initialize database schema from SQL file."""
        if schema_path is None:
            # Default to schema.sql in the same directory
            schema_path = Path(__file__).parent / "schema.sql"

        with open(schema_path) as f:
            schema = f.read()

        async with self.transaction() as conn:
            await conn.executescript(schema)

        logger.info("database_schema_initialized")


# Global database instance
db = Database()
