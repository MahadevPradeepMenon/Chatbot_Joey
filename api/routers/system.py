"""System health, readiness and version endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)

from api.dependencies import (
    REQUIRED_DATABASE_TABLES,
    get_database_path,
    inspect_database_readiness,
)
from api.models import (
    HealthResponse,
    ReadinessResponse,
    VersionResponse,
)


# Group health, readiness and version endpoints under one system router.
router = APIRouter(
    tags=["system"],
)


# The liveness endpoint is intentionally lightweight: it confirms that the
# API process can respond without touching retrieval or persistent storage.
@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API liveness",
)
def health(
    request: Request,
) -> HealthResponse:
    """Return a cheap response that does not run retrieval or storage work."""

    # Read service/version metadata directly from the current FastAPI app.
    return HealthResponse(
        service=request.app.title,
        api_version=request.app.version,
    )


# Readiness is stricter than liveness because it verifies that the local
# SQLite schema required by the current API is actually available.
@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Check local storage readiness",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": (
                "One or more required SQLite tables are unavailable."
            )
        }
    },
)
def ready(
    database_path: Path = Depends(
        get_database_path
    ),
) -> ReadinessResponse:
    """Verify that every current Joey persistence table exists."""

    # Inspect the configured database path supplied through FastAPI dependency
    # injection rather than resolving configuration again inside the route.
    readiness = inspect_database_readiness(
        database_path
    )

    # Return HTTP 503 when required persistence tables are missing so callers
    # can distinguish an unavailable dependency from a live API process.
    if not readiness.ready:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail={
                "status": "not_ready",
                "database_ready": False,
                "missing_tables": list(
                    readiness.missing_tables
                ),
            },
        )

    # A ready response reports the number of tables checked and confirms that
    # no required tables are missing.
    return ReadinessResponse(
        required_table_count=len(
            REQUIRED_DATABASE_TABLES
        ),
        missing_tables=[],
    )


# Version discovery exposes application/API versions and documentation paths
# without running any business logic.
@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Return API version information",
)
def version(
    request: Request,
) -> VersionResponse:
    """Return application and HTTP API discovery information."""

    # Pull discovery information from FastAPI/application state so the route
    # reflects the configuration of the running API instance.
    return VersionResponse(
        service=request.app.title,
        application_version=(
            request.app.state.application_version
        ),
        api_version=request.app.version,
        docs_path=request.app.docs_url or "",
        openapi_path=request.app.openapi_url or "",
    )
