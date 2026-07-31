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

    if database_path is None:
        return get_settings().database_path

    return Path(database_path)


def initialise_local_storage(
    database_path: str | Path | None = None,
) -> Path:
    """Create all SQLite tables required by the current Joey system."""

    path = resolve_database_path(
        database_path
    )

    create_database(path)
    create_conversation_tables(path)
    create_strategy_feedback_tables(path)

    return path


def inspect_database_readiness(
    database_path: str | Path,
) -> DatabaseReadiness:
    """Check that the SQLite file contains every required table."""

    path = Path(database_path)

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

    connection = sqlite3.connect(
        path,
        timeout=10.0,
    )

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
    missing = (
        REQUIRED_DATABASE_TABLES
        - available
    )

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

    database_path = getattr(
        request.app.state,
        "database_path",
        None,
    )

    if database_path is None:
        raise RuntimeError(
            "The FastAPI application has no configured database path."
        )

    return Path(database_path)
