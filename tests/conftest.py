"""Pytest configuration and fixtures."""

import asyncio
from pathlib import Path
from typing import AsyncIterator

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
    """Create a test database."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    await db.connect()
    await db.init_schema()

    yield db

    await db.disconnect()
