"""Shared FastAPI dependencies and startup checks."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from app.settings import get_settings
from storage.conversation_storage import (
    create_conversation_tables,
)
from storage.database import create_database
from storage.strategy_feedback import (
    create_strategy_feedback_tables,
)


# List the tables the current API expects so health/readiness checks can
# detect an incomplete or uninitialised local SQLite schema.
REQUIRED_DATABASE_TABLES = frozenset(
    {
        "journal_entries",
        "conversation_sessions",
        "conversation_messages",
        "strategy_searches",
        "strategy_search_results",
        "strategy_feedback",
    }
)


# Immutable readiness result returned to system/health endpoints.
@dataclass(frozen=True)
class DatabaseReadiness:
    """Result of checking the local SQLite schema."""

    ready: bool
    available_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]


def resolve_database_path(
    database_path: str | Path | None = None,
) -> Path:
    """Return the configured SQLite path without creating it."""

    # Use the centrally validated database path unless a caller supplies an
    # explicit path, which is useful for tests and isolated API instances.
    if database_path is None:
        return get_settings().database_path

    return Path(database_path)


def initialise_local_storage(
    database_path: str | Path | None = None,
) -> Path:
    """Create all SQLite tables required by the current Joey system."""

    # Resolve the target path once, then pass the same location to every
    # storage module so all required tables live in one SQLite database.
    path = resolve_database_path(
        database_path
    )

    # Initialise the journal, conversation and strategy-feedback schemas
    # before the API begins serving requests.
    create_database(path)
    create_conversation_tables(path)
    create_strategy_feedback_tables(path)

    return path


def inspect_database_readiness(
    database_path: str | Path,
) -> DatabaseReadiness:
    """Check that the SQLite file contains every required table."""

    # Readiness inspection is non-destructive: it checks the existing file
    # rather than creating a missing database.
    path = Path(database_path)

    # A missing database file is immediately reported as not ready with all
    # required tables listed as missing.
    if not path.exists():
        return DatabaseReadiness(
            ready=False,
            available_tables=(),
            missing_tables=tuple(
                sorted(
                    REQUIRED_DATABASE_TABLES
                )
            ),
        )

    # Open a short-lived direct SQLite connection for schema inspection only.
    connection = sqlite3.connect(
        path,
        timeout=10.0,
    )

    # Query SQLite metadata for table names and always close the connection,
    # even if schema inspection raises an error.
    try:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
    finally:
        connection.close()

    available = {
        str(row[0])
        for row in rows
    }
    # Set subtraction identifies exactly which required tables are absent.
    missing = (
        REQUIRED_DATABASE_TABLES
        - available
    )

    # The database is considered ready only when no required tables are missing.
    return DatabaseReadiness(
        ready=not missing,
        available_tables=tuple(
            sorted(available)
        ),
        missing_tables=tuple(
            sorted(missing)
        ),
    )


def get_database_path(
    request: Request,
) -> Path:
    """Return the database path configured on the current app."""

    # Read the path placed on FastAPI application.state by the application
    # factory/lifespan rather than re-reading environment configuration.
    database_path = getattr(
        request.app.state,
        "database_path",
        None,
    )

    # Fail clearly if this dependency is used before the app has been given
    # a database path.
    if database_path is None:
        raise RuntimeError(
            "The FastAPI application has no configured database path."
        )

    return Path(database_path)
