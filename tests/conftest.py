"""Pytest configuration and fixtures."""

import asyncio
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.db.connection import Database


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db(tmp_path: Path) -> AsyncIterator[Database]:
    """Create a test database with temporary path."""
    db_path = tmp_path / "test.db"

    # Mock settings to use the temp database
    with patch("app.db.connection.settings") as mock_settings:
        mock_settings.use_turso = False
        mock_settings.database_path = db_path

        db = Database()
        await db.connect()
        await db.init_schema()

        yield db

        await db.disconnect()
