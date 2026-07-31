"""FastAPI application factory for the Hey Joey backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from api.dependencies import (
    initialise_local_storage,
    resolve_database_path,
)
from api.routers.system import router as system_router


SERVICE_NAME = "Hey Joey API"
APPLICATION_VERSION = "1.0.0"
API_VERSION = "v1"


def create_app(
    database_path: str | Path | None = None,
) -> FastAPI:
    """Create an independently configurable Hey Joey API instance."""

    resolved_database_path = (
        resolve_database_path(
            database_path
        )
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

        yield

        application.state.storage_initialised = False

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
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.state.database_path = (
        resolved_database_path
    )
    application.state.storage_initialised = False
    application.state.application_version = (
        APPLICATION_VERSION
    )

    application.include_router(
        system_router
    )

    return application


app = create_app()
