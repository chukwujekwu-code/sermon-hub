"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import ingestion, search
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.connection import db
from app.db.mongodb import mongodb

# Set up logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager for startup/shutdown."""
    # Startup
    logger.info("application_starting", app_name=settings.app_name)

    # Connect to database
    await db.connect()

    # Initialize schema if database is new
    try:
        await db.init_schema()
    except Exception as e:
        logger.warning("schema_init_skipped", reason=str(e))

    # Connect to MongoDB (transcripts) - optional, app works without it
    if settings.use_mongodb:
        try:
            await mongodb.connect()
            await mongodb.ensure_indexes()
        except Exception as e:
            logger.warning("mongodb_connection_failed", error=str(e))

    logger.info("application_started")

    yield

    # Shutdown
    logger.info("application_stopping")
    if mongodb.is_connected:
        await mongodb.disconnect()
    await db.disconnect()
    logger.info("application_stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="API for sermon recommendation based on emotional needs",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(ingestion.router)
app.include_router(search.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Sermon Recommender API",
        "docs": "/docs",
    }
