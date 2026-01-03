#!/usr/bin/env python3
"""Initialize the database schema."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import setup_logging, get_logger
from app.db.connection import db

setup_logging()
logger = get_logger(__name__)


async def main() -> None:
    """Initialize the database."""
    logger.info("initializing_database")

    try:
        await db.connect()
        await db.init_schema()
        logger.info("database_initialized_successfully")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
