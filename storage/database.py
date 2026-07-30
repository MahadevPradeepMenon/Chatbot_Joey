"""SQLite persistence for confirmed Hey Joey journal entries."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "local"
    / "joey.db"
)

JSON_COLUMNS = {
    "mood_labels_json": "mood_labels",
    "behaviours_json": "behaviours",
    "possible_triggers_json": "possible_triggers",
    "quick_track_suggestions_json": "quick_track_suggestions",
    "strategy_categories_json": "strategy_categories",
    "risk_flags_json": "risk_flags",
    "missing_information_json": "missing_information",
    "conversation_history_json": "conversation_history",
    "structured_record_json": "structured_record",
}


def _database_path(
    database_path: str | Path | None,
) -> Path:
    """Resolve the configured database path."""

    if database_path is None:
        return DEFAULT_DATABASE_PATH

    return Path(database_path)


@contextmanager
def _connection(
    database_path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """
    Open, commit or roll back, and always close a SQLite connection.

    Explicit closing is important on Windows because an open SQLite
    handle prevents temporary database files from being deleted.
    """

    path = _database_path(database_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        path,
        timeout=10.0,
    )
    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_database(
    database_path: str | Path | None = None,
) -> Path:
    """Create the local database and journal-entry table."""

    path = _database_path(database_path)

    with _connection(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                saved_at TEXT NOT NULL,
                source TEXT NOT NULL,
                original_note TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                event_date TEXT,
                time_of_day TEXT,
                anxiety_level TEXT NOT NULL,
                mood_zone TEXT NOT NULL,
                mood_labels_json TEXT NOT NULL,
                behaviours_json TEXT NOT NULL,
                activity TEXT,
                environment TEXT,
                possible_triggers_json TEXT NOT NULL,
                quick_track_suggestions_json TEXT NOT NULL,
                strategy_categories_json TEXT NOT NULL,
                risk_flags_json TEXT NOT NULL,
                missing_information_json TEXT NOT NULL,
                follow_up_question TEXT,
                confidence TEXT NOT NULL,
                requires_parent_confirmation INTEGER NOT NULL
                    CHECK (
                        requires_parent_confirmation IN (0, 1)
                    ),
                conversation_history_json TEXT NOT NULL,
                structured_record_json TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_journal_entries_saved_at
            ON journal_entries(saved_at)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_journal_entries_mood_zone
            ON journal_entries(mood_zone)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_journal_entries_anxiety_level
            ON journal_entries(anxiety_level)
            """
        )

    return path


def _json_ready(value: Any) -> Any:
    """Convert Pydantic and enum values into JSON-compatible data."""

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Mapping):
        return {
            str(key): _json_ready(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _json_ready(item)
            for item in value
        ]

    return value


def _record_dict(record: Any) -> dict[str, Any]:
    """Convert a Joey record into a plain JSON-ready dictionary."""

    if hasattr(record, "model_dump"):
        data = record.model_dump(
            mode="json"
        )
    elif hasattr(record, "dict"):
        data = record.dict()
    elif isinstance(record, Mapping):
        data = dict(record)
    else:
        raise TypeError(
            "record must be a Pydantic model or mapping."
        )

    return _json_ready(data)


def _history_item(item: Any) -> dict[str, Any]:
    """Normalise one conversation turn."""

    if isinstance(item, Mapping):
        return _json_ready(dict(item))

    fields = (
        "question",
        "answer",
        "field_name",
    )

    return {
        field: _json_ready(
            getattr(item, field, None)
        )
        for field in fields
    }


def _history_list(
    conversation_history: Iterable[Any] | None,
) -> list[dict[str, Any]]:
    """Normalise a conversation history for storage."""

    if conversation_history is None:
        return []

    return [
        _history_item(item)
        for item in conversation_history
    ]


def _required_text(
    value: Any,
    field_name: str,
) -> str:
    """Validate a required text value."""

    text = str(value or "").strip()

    if not text:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return text


def _enum_text(
    value: Any,
    default: str = "Unknown",
) -> str:
    """Return a stable text value from an enum or scalar."""

    if isinstance(value, Enum):
        value = value.value

    text = str(value or "").strip()

    return text or default


def save_confirmed_record(
    record: Any,
    original_note: str,
    conversation_history: Iterable[Any] | None = None,
    source: str = "streamlit_chat_interface",
    saved_at: str | None = None,
    database_path: str | Path | None = None,
) -> int:
    """
    Save one already-confirmed structured record.

    The caller remains responsible for confirming the draft before
    invoking this lower-level persistence function.
    """

    path = create_database(
        database_path
    )
    data = _record_dict(record)
    history = _history_list(
        conversation_history
    )

    saved_timestamp = (
        saved_at
        or datetime.now().isoformat(
            timespec="seconds"
        )
    )

    original_note_text = _required_text(
        original_note,
        "original_note",
    )
    summary = _required_text(
        data.get("summary"),
        "record.summary",
    )

    values = {
        "saved_at": saved_timestamp,
        "source": _required_text(
            source,
            "source",
        ),
        "original_note": original_note_text,
        "entry_type": _enum_text(
            data.get("entry_type"),
            "journal_entry",
        ),
        "summary": summary,
        "event_date": data.get("date"),
        "time_of_day": _enum_text(
            data.get("time_of_day"),
        ),
        "anxiety_level": _enum_text(
            data.get("anxiety_level"),
        ),
        "mood_zone": _enum_text(
            data.get("mood_zone"),
        ),
        "mood_labels_json": json.dumps(
            data.get("mood_labels") or [],
            ensure_ascii=False,
        ),
        "behaviours_json": json.dumps(
            data.get("behaviours") or [],
            ensure_ascii=False,
        ),
        "activity": data.get("activity"),
        "environment": data.get("environment"),
        "possible_triggers_json": json.dumps(
            data.get("possible_triggers") or [],
            ensure_ascii=False,
        ),
        "quick_track_suggestions_json": json.dumps(
            data.get("quick_track_suggestions") or [],
            ensure_ascii=False,
        ),
        "strategy_categories_json": json.dumps(
            data.get("strategy_categories") or [],
            ensure_ascii=False,
        ),
        "risk_flags_json": json.dumps(
            data.get("risk_flags") or [],
            ensure_ascii=False,
        ),
        "missing_information_json": json.dumps(
            data.get("missing_information") or [],
            ensure_ascii=False,
        ),
        "follow_up_question": data.get(
            "follow_up_question"
        ),
        "confidence": _enum_text(
            data.get("confidence"),
            "Medium",
        ),
        "requires_parent_confirmation": int(
            bool(
                data.get(
                    "requires_parent_confirmation",
                    True,
                )
            )
        ),
        "conversation_history_json": json.dumps(
            history,
            ensure_ascii=False,
        ),
        "structured_record_json": json.dumps(
            data,
            ensure_ascii=False,
        ),
    }

    with _connection(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO journal_entries (
                saved_at,
                source,
                original_note,
                entry_type,
                summary,
                event_date,
                time_of_day,
                anxiety_level,
                mood_zone,
                mood_labels_json,
                behaviours_json,
                activity,
                environment,
                possible_triggers_json,
                quick_track_suggestions_json,
                strategy_categories_json,
                risk_flags_json,
                missing_information_json,
                follow_up_question,
                confidence,
                requires_parent_confirmation,
                conversation_history_json,
                structured_record_json
            )
            VALUES (
                :saved_at,
                :source,
                :original_note,
                :entry_type,
                :summary,
                :event_date,
                :time_of_day,
                :anxiety_level,
                :mood_zone,
                :mood_labels_json,
                :behaviours_json,
                :activity,
                :environment,
                :possible_triggers_json,
                :quick_track_suggestions_json,
                :strategy_categories_json,
                :risk_flags_json,
                :missing_information_json,
                :follow_up_question,
                :confidence,
                :requires_parent_confirmation,
                :conversation_history_json,
                :structured_record_json
            )
            """,
            values,
        )

        if cursor.lastrowid is None:
            raise RuntimeError(
                "SQLite did not return a journal-entry ID."
            )

        entry_id = int(
            cursor.lastrowid
        )

    return entry_id


def _status_text(status: Any) -> str:
    """Return a comparable conversation-status value."""

    if isinstance(status, Enum):
        status = status.value

    return str(status or "").strip().lower()


def save_confirmed_session(
    session: Any,
    source: str = "streamlit_chat_interface",
    database_path: str | Path | None = None,
) -> int:
    """Validate and save one confirmed Joey conversation session."""

    if _status_text(
        getattr(session, "status", None)
    ) != "confirmed":
        raise ValueError(
            "The draft has not been confirmed."
        )

    record = getattr(
        session,
        "current_record",
        None,
    )

    if record is None:
        raise ValueError(
            "The confirmed session has no structured record."
        )

    return save_confirmed_record(
        record=record,
        original_note=getattr(
            session,
            "original_note",
            "",
        ),
        conversation_history=getattr(
            session,
            "history",
            [],
        ),
        source=source,
        database_path=database_path,
    )


def _decode_row(
    row: sqlite3.Row,
) -> dict[str, Any]:
    """Convert one SQLite row into an application dictionary."""

    item = dict(row)

    for database_name, output_name in JSON_COLUMNS.items():
        raw_value = item.pop(
            database_name,
            "[]",
        )

        try:
            item[output_name] = json.loads(
                raw_value
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            item[output_name] = (
                {}
                if output_name == "structured_record"
                else []
            )

    item["requires_parent_confirmation"] = bool(
        item["requires_parent_confirmation"]
    )

    return item


def get_journal_entry(
    entry_id: int,
    database_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return one saved journal entry by ID."""

    path = create_database(
        database_path
    )

    with _connection(path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM journal_entries
            WHERE id = ?
            """,
            (entry_id,),
        ).fetchone()

    if row is None:
        return None

    return _decode_row(row)


def list_journal_entries(
    limit: int = 50,
    database_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return recent journal entries, newest first."""

    if limit < 1:
        raise ValueError(
            "limit must be at least 1."
        )

    path = create_database(
        database_path
    )

    with _connection(path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM journal_entries
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        _decode_row(row)
        for row in rows
    ]


def count_journal_entries(
    database_path: str | Path | None = None,
) -> int:
    """Return the number of stored journal entries."""

    path = create_database(
        database_path
    )

    with _connection(path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS entry_count
            FROM journal_entries
            """
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "SQLite did not return the journal-entry count."
        )

    return int(
        row["entry_count"]
    )


def main() -> None:
    """Create the default database as a small smoke test."""

    path = create_database()

    print("HEY JOEY SQLITE STORAGE")
    print("=" * 60)
    print(f"Database: {path}")
    print(
        "Stored journal entries: "
        f"{count_journal_entries(path)}"
    )


if __name__ == "__main__":
    main()