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


SERVICE_NAME = "Hey Joey API"
APPLICATION_VERSION = "1.0.0"
API_VERSION = "v1"
LOGGER = logging.getLogger("hey_joey.api")


def create_app(
    database_path: str | Path | None = None,
    strategy_service_factory: object | None = None,
    settings: JoeySettings | None = None,
) -> FastAPI:
    """Create an independently configurable Hey Joey API instance."""

    resolved_settings = (
        settings
        if settings is not None
        else get_settings()
    )
    configure_logging(
        resolved_settings
    )

    resolved_database_path = (
        Path(database_path)
        if database_path is not None
        else resolved_settings.database_path
    )

    @asynccontextmanager
    async def lifespan(
        application: FastAPI,
    ) -> AsyncIterator[None]:
        """Initialise local persistence before accepting requests."""

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

        yield

        application.state.storage_initialised = False
        LOGGER.info(
            "Hey Joey API stopped",
            extra={
                "event": "api_stopped",
            },
        )

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


app = create_app()
