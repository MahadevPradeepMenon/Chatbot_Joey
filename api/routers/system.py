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


router = APIRouter(
    tags=["system"],
)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API liveness",
)
def health(
    request: Request,
) -> HealthResponse:
    """Return a cheap response that does not run retrieval or storage work."""

    return HealthResponse(
        service=request.app.title,
        api_version=request.app.version,
    )


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

    readiness = inspect_database_readiness(
        database_path
    )

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

    return ReadinessResponse(
        required_table_count=len(
            REQUIRED_DATABASE_TABLES
        ),
        missing_tables=[],
    )


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Return API version information",
)
def version(
    request: Request,
) -> VersionResponse:
    """Return application and HTTP API discovery information."""

    return VersionResponse(
        service=request.app.title,
        application_version=(
            request.app.state.application_version
        ),
        api_version=request.app.version,
        docs_path=request.app.docs_url or "",
        openapi_path=request.app.openapi_url or "",
    )
