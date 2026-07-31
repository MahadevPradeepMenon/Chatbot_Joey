"""Pydantic response models for the Hey Joey API foundation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Lightweight liveness response."""

    status: Literal["ok"] = "ok"
    service: str = Field(
        description="Human-readable API service name."
    )
    api_version: str = Field(
        description="Current HTTP API version."
    )


class ReadinessResponse(BaseModel):
    """Readiness result for Joey's local persistence layer."""

    status: Literal["ready"] = "ready"
    database_ready: bool = True
    required_table_count: int = Field(
        ge=1,
        description="Number of required SQLite tables checked.",
    )
    missing_tables: list[str] = Field(
        default_factory=list,
        description="Required tables that were not found.",
    )


class VersionResponse(BaseModel):
    """Version and API-discovery information."""

    service: str
    application_version: str
    api_version: str
    docs_path: str
    openapi_path: str
