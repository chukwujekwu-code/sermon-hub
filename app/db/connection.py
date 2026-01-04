"""Async database connection manager supporting Turso (libSQL) and local SQLite."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Any

import libsql_experimental as libsql
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class Database:
    """Async database connection manager supporting Turso and local SQLite."""

    def __init__(self):
        """Initialize database manager."""
        self._connection: libsql.Connection | None = None

    async def connect(self) -> None:
        """Initialize the database connection."""
        if settings.use_turso:
            # Connect to Turso cloud database
            self._connection = libsql.connect(
                database=settings.turso_database_url,
                auth_token=settings.turso_auth_token,
            )
            logger.info(
                "database_connected",
                type="turso",
                url=settings.turso_database_url[:50] + "..." if len(settings.turso_database_url) > 50 else settings.turso_database_url,
            )
        else:
            # Connect to local SQLite file
            db_path = settings.database_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = libsql.connect(database=str(db_path))
            logger.info("database_connected", type="sqlite", path=str(db_path))

        # Enable foreign keys
        self._connection.execute("PRAGMA foreign_keys = ON")

    async def disconnect(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("database_disconnected")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[libsql.Connection]:
        """Context manager for database transactions."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        try:
            yield self._connection
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    @property
    def connection(self) -> libsql.Connection:
        """Get the current database connection."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    async def execute(self, sql: str, parameters: tuple = ()) -> Any:
        """Execute a SQL statement."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection.execute(sql, parameters)

    async def executemany(self, sql: str, parameters: list[tuple]) -> Any:
        """Execute a SQL statement with multiple parameter sets."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection.executemany(sql, parameters)

    async def fetchone(self, sql: str, parameters: tuple = ()) -> dict | None:
        """Execute query and fetch one row as dict."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        cursor = self._connection.execute(sql, parameters)
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    async def fetchall(self, sql: str, parameters: tuple = ()) -> list[dict]:
        """Execute query and fetch all rows as dicts."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        cursor = self._connection.execute(sql, parameters)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    async def init_schema(self, schema_path: str | Path | None = None) -> None:
        """Initialize database schema from SQL file."""
        if schema_path is None:
            schema_path = Path(__file__).parent / "schema.sql"

        with open(schema_path) as f:
            schema = f.read()

        if not self._connection:
            raise RuntimeError("Database not connected")

        # Execute each statement separately (libsql doesn't have executescript)
        for statement in schema.split(";"):
            statement = statement.strip()
            if statement:
                self._connection.execute(statement)
        self._connection.commit()

        logger.info("database_schema_initialized")


# Global database instance
db = Database()
