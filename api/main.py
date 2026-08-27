"""FastAPI application factory for the Hey Joey backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from app.logging_config import configure_logging
from app.settings import JoeySettings, get_settings
from api.dependencies import initialise_local_storage
from api.routers.conversations import router as conversations_router
from api.routers.record import router as record_router
from api.routers.strategies import router as strategies_router
from api.routers.system import router as system_router


# Keep service/version identifiers in one place for application metadata
# and system-level responses.
SERVICE_NAME = "Hey Joey API"
APPLICATION_VERSION = "1.0.0"
API_VERSION = "v1"
# Use the application-owned logger namespace configured by logging_config.
LOGGER = logging.getLogger("hey_joey.api")


def create_app(
    database_path: str | Path | None = None,
    strategy_service_factory: object | None = None,
    settings: JoeySettings | None = None,
) -> FastAPI:
    """Create an independently configurable Hey Joey API instance."""

    # Allow tests or alternate launch contexts to inject settings; normal
    # execution falls back to the cached process-wide configuration.
    resolved_settings = (
        settings
        if settings is not None
        else get_settings()
    )
    # Configure Joey logging before the API starts serving requests.
    configure_logging(
        resolved_settings
    )

    # A caller-provided database path overrides the configured default, which
    # keeps tests and isolated API instances independent.
    resolved_database_path = (
        Path(database_path)
        if database_path is not None
        else resolved_settings.database_path
    )

    # FastAPI lifespan logic provides one startup/shutdown boundary for local
    # persistence and service-level logging.
    @asynccontextmanager
    async def lifespan(
        application: FastAPI,
    ) -> AsyncIterator[None]:
        """Initialise local persistence before accepting requests."""

        # Initialise local storage before request handling and keep the resolved
        # database path on application.state for dependency helpers.
        application.state.database_path = (
            initialise_local_storage(
                resolved_database_path
            )
        )
        application.state.storage_initialised = True
        LOGGER.info(
            "Hey Joey API started",
            extra={
                "event": "api_started",
            },
        )

        # Control is returned to FastAPI while the application serves requests.
        yield

        # Mark storage unavailable again during application shutdown.
        application.state.storage_initialised = False
        LOGGER.info(
            "Hey Joey API stopped",
            extra={
                "event": "api_stopped",
            },
        )

    # Build the API with validated settings and the lifespan hook defined above;
    # interactive documentation can be disabled by configuration.
    application = FastAPI(
        title=SERVICE_NAME,
        summary=(
            "Local backend for Hey Joey journalling and "
            "source-backed strategy support."
        ),
        description=(
            "A local-first API that exposes Hey Joey's deterministic "
            "conversation, safety, retrieval and persistence services."
        ),
        version=API_VERSION,
        lifespan=lifespan,
        docs_url=(
            "/docs"
            if resolved_settings.docs_enabled
            else None
        ),
        redoc_url=(
            "/redoc"
            if resolved_settings.docs_enabled
            else None
        ),
        openapi_url=(
            "/openapi.json"
            if resolved_settings.docs_enabled
            else None
        ),
    )

    # Store shared runtime objects on application.state so routers and dependency
    # helpers can access one consistent configuration.
    application.state.database_path = (
        resolved_database_path
    )
    application.state.storage_initialised = False
    application.state.application_version = (
        APPLICATION_VERSION
    )
    application.state.strategy_service_factory = (
        strategy_service_factory
    )
    application.state.settings = (
        resolved_settings
    )

    # Register each route group explicitly to assemble the complete API.
    application.include_router(
        system_router
    )
    application.include_router(
        conversations_router
    )
    application.include_router(
        record_router
    )
    application.include_router(
        strategies_router
    )

    return application


# Expose the default application object expected by Uvicorn while keeping
# create_app() available for isolated tests and alternate configuration.
app = create_app()
