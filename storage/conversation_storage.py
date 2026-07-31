"""SQLite persistence for Hey Joey conversation sessions and messages."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Mapping

from storage.database import (
    DEFAULT_DATABASE_PATH,
    create_database,
)


class ConversationWorkflow(str, Enum):
    """Supported Joey conversation workflows."""

    record_observation = "record_observation"
    ask_strategy = "ask_strategy"


class StoredConversationStatus(str, Enum):
    """Persistence-level conversation states."""

    active = "active"
    ready_for_review = "ready_for_review"
    confirmed = "confirmed"
    rejected = "rejected"
    completed = "completed"
    archived = "archived"


class ConversationRole(str, Enum):
    """Roles displayed in the chat history."""

    user = "user"
    assistant = "assistant"


@dataclass(frozen=True)
class StoredConversationMessage:
    """One ordered message belonging to a persisted session."""

    id: int
    session_id: int
    sequence_number: int
    role: ConversationRole
    content: str
    message_type: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        return data


@dataclass(frozen=True)
class StoredConversation:
    """One persisted conversation and its ordered messages."""

    id: int
    workflow: ConversationWorkflow
    status: StoredConversationStatus
    created_at: str
    updated_at: str
    draft_state: dict[str, Any] | None
    metadata: dict[str, Any]
    messages: list[StoredConversationMessage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow": self.workflow.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "draft_state": self.draft_state,
            "metadata": self.metadata,
            "messages": [
                message.to_dict()
                for message in self.messages
            ],
        }


def _database_path(
    database_path: str | Path | None,
) -> Path:
    """Resolve the configured SQLite path."""

    if database_path is None:
        return DEFAULT_DATABASE_PATH

    return Path(database_path)


@contextmanager
def _connection(
    database_path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """Open, commit or roll back, and always close a connection."""

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


def _timestamp(
    value: str | None = None,
) -> str:
    """Return a stable ISO timestamp."""

    return (
        value
        or datetime.now().isoformat(
            timespec="seconds"
        )
    )


def _required_text(
    value: Any,
    field_name: str,
) -> str:
    """Validate required text."""

    text = str(value or "").strip()

    if not text:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return text


def _json_ready(value: Any) -> Any:
    """Convert enums, models and containers to JSON-compatible data."""

    if isinstance(value, Enum):
        return value.value

    if hasattr(value, "model_dump"):
        return value.model_dump(
            mode="json"
        )

    if hasattr(value, "to_dict"):
        return value.to_dict()

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


def _json_text(
    value: Any,
    *,
    default: Any,
) -> str:
    """Serialise application data consistently."""

    prepared = (
        default
        if value is None
        else _json_ready(value)
    )

    return json.dumps(
        prepared,
        ensure_ascii=False,
    )


def _json_object(
    raw_value: str | None,
    *,
    allow_none: bool,
) -> dict[str, Any] | None:
    """Decode one stored JSON object safely."""

    if raw_value is None:
        return None if allow_none else {}

    try:
        decoded = json.loads(
            raw_value
        )
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return None if allow_none else {}

    if decoded is None and allow_none:
        return None

    if isinstance(decoded, dict):
        return decoded

    return None if allow_none else {}


def normalise_workflow(
    workflow: ConversationWorkflow | str,
) -> ConversationWorkflow:
    """Convert UI or storage wording to a workflow enum."""

    if isinstance(
        workflow,
        ConversationWorkflow,
    ):
        return workflow

    clean = " ".join(
        str(workflow or "")
        .strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )

    aliases = {
        "record observation": (
            ConversationWorkflow.record_observation
        ),
        "record what happened": (
            ConversationWorkflow.record_observation
        ),
        "ask strategy": (
            ConversationWorkflow.ask_strategy
        ),
        "ask for a strategy": (
            ConversationWorkflow.ask_strategy
        ),
    }

    result = aliases.get(clean)

    if result is None:
        raise ValueError(
            "Unsupported conversation workflow."
        )

    return result


def normalise_status(
    status: StoredConversationStatus | str,
) -> StoredConversationStatus:
    """Convert a conversation state to its storage enum."""

    if isinstance(
        status,
        StoredConversationStatus,
    ):
        return status

    clean = str(status or "").strip().lower()

    try:
        return StoredConversationStatus(
            clean
        )
    except ValueError as error:
        raise ValueError(
            "Unsupported conversation status."
        ) from error


def normalise_role(
    role: ConversationRole | str,
) -> ConversationRole:
    """Convert a message role to its enum."""

    if isinstance(
        role,
        ConversationRole,
    ):
        return role

    clean = str(role or "").strip().lower()

    try:
        return ConversationRole(
            clean
        )
    except ValueError as error:
        raise ValueError(
            "Message role must be user or assistant."
        ) from error


def create_conversation_tables(
    database_path: str | Path | None = None,
) -> Path:
    """Create persistent session and message tables."""

    path = create_database(
        database_path
    )

    with _connection(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow TEXT NOT NULL
                    CHECK (
                        workflow IN (
                            'record_observation',
                            'ask_strategy'
                        )
                    ),
                status TEXT NOT NULL
                    CHECK (
                        status IN (
                            'active',
                            'ready_for_review',
                            'confirmed',
                            'rejected',
                            'completed',
                            'archived'
                        )
                    ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                draft_state_json TEXT,
                metadata_json TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                sequence_number INTEGER NOT NULL
                    CHECK (sequence_number >= 1),
                role TEXT NOT NULL
                    CHECK (
                        role IN (
                            'user',
                            'assistant'
                        )
                    ),
                content TEXT NOT NULL,
                message_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id)
                    REFERENCES conversation_sessions(id)
                    ON DELETE CASCADE,
                UNIQUE (
                    session_id,
                    sequence_number
                )
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_conversation_sessions_workflow_updated
            ON conversation_sessions(
                workflow,
                updated_at
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_conversation_messages_session_sequence
            ON conversation_messages(
                session_id,
                sequence_number
            )
            """
        )

    return path


def create_conversation_session(
    workflow: ConversationWorkflow | str,
    *,
    status: StoredConversationStatus | str = (
        StoredConversationStatus.active
    ),
    draft_state: Any = None,
    metadata: Mapping[str, Any] | None = None,
    created_at: str | None = None,
    database_path: str | Path | None = None,
) -> int:
    """Create one persistent conversation session."""

    path = create_conversation_tables(
        database_path
    )
    workflow_value = normalise_workflow(
        workflow
    )
    status_value = normalise_status(
        status
    )
    timestamp = _timestamp(
        created_at
    )

    with _connection(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO conversation_sessions (
                workflow,
                status,
                created_at,
                updated_at,
                draft_state_json,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_value.value,
                status_value.value,
                timestamp,
                timestamp,
                (
                    None
                    if draft_state is None
                    else _json_text(
                        draft_state,
                        default={},
                    )
                ),
                _json_text(
                    metadata,
                    default={},
                ),
            ),
        )

        if cursor.lastrowid is None:
            raise RuntimeError(
                "SQLite did not return a conversation-session ID."
            )

        return int(
            cursor.lastrowid
        )


def _require_session(
    connection: sqlite3.Connection,
    session_id: int,
) -> sqlite3.Row:
    """Return one session row or raise a controlled error."""

    if session_id < 1:
        raise ValueError(
            "session_id must be at least 1."
        )

    row = connection.execute(
        """
        SELECT *
        FROM conversation_sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()

    if row is None:
        raise ValueError(
            "Conversation session was not found."
        )

    return row


def add_conversation_message(
    session_id: int,
    role: ConversationRole | str,
    content: str,
    *,
    message_type: str = "chat_message",
    created_at: str | None = None,
    database_path: str | Path | None = None,
) -> int:
    """Append one ordered message to a stored session."""

    path = create_conversation_tables(
        database_path
    )
    role_value = normalise_role(
        role
    )
    message_content = _required_text(
        content,
        "content",
    )
    message_type_text = _required_text(
        message_type,
        "message_type",
    )
    timestamp = _timestamp(
        created_at
    )

    with _connection(path) as connection:
        _require_session(
            connection,
            session_id,
        )

        sequence_row = connection.execute(
            """
            SELECT COALESCE(
                MAX(sequence_number),
                0
            ) + 1 AS next_sequence
            FROM conversation_messages
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        if sequence_row is None:
            raise RuntimeError(
                "SQLite did not return the next message sequence."
            )

        sequence_number = int(
            sequence_row["next_sequence"]
        )

        cursor = connection.execute(
            """
            INSERT INTO conversation_messages (
                session_id,
                sequence_number,
                role,
                content,
                message_type,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                sequence_number,
                role_value.value,
                message_content,
                message_type_text,
                timestamp,
            ),
        )

        connection.execute(
            """
            UPDATE conversation_sessions
            SET updated_at = ?
            WHERE id = ?
            """,
            (
                timestamp,
                session_id,
            ),
        )

        if cursor.lastrowid is None:
            raise RuntimeError(
                "SQLite did not return a conversation-message ID."
            )

        return int(
            cursor.lastrowid
        )


def update_conversation_session(
    session_id: int,
    *,
    status: StoredConversationStatus | str | None = None,
    draft_state: Any = None,
    update_draft_state: bool = False,
    metadata: Mapping[str, Any] | None = None,
    update_metadata: bool = False,
    updated_at: str | None = None,
    database_path: str | Path | None = None,
) -> None:
    """
    Update session status, draft state or metadata.

    `update_draft_state` and `update_metadata` distinguish an intentional
    clear operation from leaving the existing value unchanged.
    """

    path = create_conversation_tables(
        database_path
    )
    timestamp = _timestamp(
        updated_at
    )

    with _connection(path) as connection:
        current = _require_session(
            connection,
            session_id,
        )

        next_status = (
            normalise_status(status).value
            if status is not None
            else str(current["status"])
        )

        next_draft = current[
            "draft_state_json"
        ]

        if update_draft_state:
            next_draft = (
                None
                if draft_state is None
                else _json_text(
                    draft_state,
                    default={},
                )
            )

        next_metadata = current[
            "metadata_json"
        ]

        if update_metadata:
            next_metadata = _json_text(
                metadata,
                default={},
            )

        connection.execute(
            """
            UPDATE conversation_sessions
            SET
                status = ?,
                updated_at = ?,
                draft_state_json = ?,
                metadata_json = ?
            WHERE id = ?
            """,
            (
                next_status,
                timestamp,
                next_draft,
                next_metadata,
                session_id,
            ),
        )


def _message_from_row(
    row: sqlite3.Row,
) -> StoredConversationMessage:
    """Convert a message row to a typed record."""

    return StoredConversationMessage(
        id=int(row["id"]),
        session_id=int(
            row["session_id"]
        ),
        sequence_number=int(
            row["sequence_number"]
        ),
        role=ConversationRole(
            row["role"]
        ),
        content=str(
            row["content"]
        ),
        message_type=str(
            row["message_type"]
        ),
        created_at=str(
            row["created_at"]
        ),
    )


def get_conversation_session(
    session_id: int,
    database_path: str | Path | None = None,
) -> StoredConversation | None:
    """Return one session and all messages in display order."""

    path = create_conversation_tables(
        database_path
    )

    with _connection(path) as connection:
        session_row = connection.execute(
            """
            SELECT *
            FROM conversation_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        if session_row is None:
            return None

        message_rows = connection.execute(
            """
            SELECT *
            FROM conversation_messages
            WHERE session_id = ?
            ORDER BY sequence_number
            """,
            (session_id,),
        ).fetchall()

    return StoredConversation(
        id=int(session_row["id"]),
        workflow=ConversationWorkflow(
            session_row["workflow"]
        ),
        status=StoredConversationStatus(
            session_row["status"]
        ),
        created_at=str(
            session_row["created_at"]
        ),
        updated_at=str(
            session_row["updated_at"]
        ),
        draft_state=_json_object(
            session_row[
                "draft_state_json"
            ],
            allow_none=True,
        ),
        metadata=(
            _json_object(
                session_row[
                    "metadata_json"
                ],
                allow_none=False,
            )
            or {}
        ),
        messages=[
            _message_from_row(row)
            for row in message_rows
        ],
    )


def list_conversation_sessions(
    *,
    workflow: ConversationWorkflow | str | None = None,
    limit: int = 50,
    database_path: str | Path | None = None,
) -> list[StoredConversation]:
    """Return recent sessions, optionally filtered by workflow."""

    if limit < 1:
        raise ValueError(
            "limit must be at least 1."
        )

    path = create_conversation_tables(
        database_path
    )

    with _connection(path) as connection:
        if workflow is None:
            rows = connection.execute(
                """
                SELECT id
                FROM conversation_sessions
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            workflow_value = normalise_workflow(
                workflow
            )
            rows = connection.execute(
                """
                SELECT id
                FROM conversation_sessions
                WHERE workflow = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (
                    workflow_value.value,
                    limit,
                ),
            ).fetchall()

    sessions: list[StoredConversation] = []

    for row in rows:
        session = get_conversation_session(
            int(row["id"]),
            database_path=path,
        )

        if session is not None:
            sessions.append(
                session
            )

    return sessions


def delete_conversation_session(
    session_id: int,
    database_path: str | Path | None = None,
) -> None:
    """Delete one session and cascade-delete all of its messages."""

    path = create_conversation_tables(
        database_path
    )

    with _connection(path) as connection:
        _require_session(
            connection,
            session_id,
        )

        connection.execute(
            """
            DELETE FROM conversation_sessions
            WHERE id = ?
            """,
            (session_id,),
        )


def count_conversation_sessions(
    database_path: str | Path | None = None,
) -> int:
    """Return the number of stored sessions."""

    path = create_conversation_tables(
        database_path
    )

    with _connection(path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS item_count
            FROM conversation_sessions
            """
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "SQLite did not return the conversation-session count."
        )

    return int(
        row["item_count"]
    )


def count_conversation_messages(
    database_path: str | Path | None = None,
) -> int:
    """Return the number of stored conversation messages."""

    path = create_conversation_tables(
        database_path
    )

    with _connection(path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS item_count
            FROM conversation_messages
            """
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "SQLite did not return the conversation-message count."
        )

    return int(
        row["item_count"]
    )


def main() -> None:
    """Create the tables and print local conversation counts."""

    path = create_conversation_tables()

    print("HEY JOEY CONVERSATION STORAGE")
    print("=" * 60)
    print(f"Database: {path}")
    print(
        "Stored conversation sessions: "
        f"{count_conversation_sessions(path)}"
    )
    print(
        "Stored conversation messages: "
        f"{count_conversation_messages(path)}"
    )


if __name__ == "__main__":
    main()
