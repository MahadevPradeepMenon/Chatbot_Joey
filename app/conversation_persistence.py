"""Application adapter for restoring and saving Joey conversations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.conversation_manager import (
    ConversationStatus,
    JoeyConversationSession,
)
from storage.conversation_storage import (
    ConversationWorkflow,
    StoredConversation,
    StoredConversationStatus,
    add_conversation_message,
    create_conversation_session,
    get_conversation_session,
    list_conversation_sessions,
    normalise_workflow,
    update_conversation_session,
)


# Immutable container returned to the Streamlit layer after restoring a
# conversation, including chat history, workflow state and metadata.
@dataclass(frozen=True)
class PersistentWorkflowState:
    """One restored Streamlit workflow state."""

    session_id: int
    workflow: ConversationWorkflow
    history: list[dict[str, str]]
    record_session: JoeyConversationSession | None
    metadata: dict[str, Any]


def _record_storage_status(
    session: JoeyConversationSession | None,
) -> StoredConversationStatus:
    """Map the journal workflow state to its SQLite status."""

    # If no in-memory journal draft exists, keep the stored conversation active.
    if session is None:
        return StoredConversationStatus.active

    # Translate application conversation states into the statuses stored in SQLite.
    status_map = {
        ConversationStatus.collecting_information: (
            StoredConversationStatus.active
        ),
        ConversationStatus.ready_for_review: (
            StoredConversationStatus.ready_for_review
        ),
        ConversationStatus.confirmed: (
            StoredConversationStatus.confirmed
        ),
        ConversationStatus.rejected: (
            StoredConversationStatus.rejected
        ),
    }

    return status_map[session.status]


def _history_from_stored(
    stored: StoredConversation,
) -> list[dict[str, str]]:
    """Convert stored typed messages into Streamlit chat dictionaries."""

    # Streamlit only needs role/content pairs, so storage-specific message
    # metadata is omitted from the displayed chat history.
    return [
        {
            "role": message.role.value,
            "content": message.content,
        }
        for message in stored.messages
    ]


def _restore_record_session(
    stored: StoredConversation,
) -> JoeyConversationSession | None:
    """Restore only an unfinished journal draft."""

    # Only the journal-record workflow owns a JoeyConversationSession draft.
    if stored.workflow != ConversationWorkflow.record_observation:
        return None

    # Restore only unfinished drafts; confirmed/rejected conversations remain closed.
    if stored.status not in {
        StoredConversationStatus.active,
        StoredConversationStatus.ready_for_review,
    }:
        return None

    # Without a persisted draft snapshot there is nothing to reconstruct.
    if stored.draft_state is None:
        return None

    return JoeyConversationSession.from_dict(
        stored.draft_state
    )


def load_or_create_workflow_state(
    workflow: ConversationWorkflow | str,
    greeting: str,
    *,
    database_path: str | Path | None = None,
) -> PersistentWorkflowState:
    """Restore the latest workflow session or create its first session."""

    # Normalise enum/string input once before querying persistent storage.
    workflow_value = normalise_workflow(
        workflow
    )
    # Restore only the latest session for the requested workflow.
    sessions = list_conversation_sessions(
        workflow=workflow_value,
        limit=1,
        database_path=database_path,
    )

    # Reuse the most recent persisted conversation; otherwise create a new one.
    if sessions:
        stored = sessions[0]
    else:
        session_id = create_conversation_session(
            workflow=workflow_value,
            metadata={},
            database_path=database_path,
        )

        add_conversation_message(
            session_id=session_id,
            role="assistant",
            content=greeting,
            message_type="greeting",
            database_path=database_path,
        )

        stored = get_conversation_session(
            session_id,
            database_path=database_path,
        )

        if stored is None:
            raise RuntimeError(
                "The newly created conversation could not be restored."
            )

    # Defensive fallback: ensure a restored session always has a greeting.
    if not stored.messages:
        add_conversation_message(
            session_id=stored.id,
            role="assistant",
            content=greeting,
            message_type="greeting",
            database_path=database_path,
        )

        refreshed = get_conversation_session(
            stored.id,
            database_path=database_path,
        )

        if refreshed is None:
            raise RuntimeError(
                "The conversation greeting could not be restored."
            )

        stored = refreshed

    # Convert the stored conversation into the state object expected by the app.
    return PersistentWorkflowState(
        session_id=stored.id,
        workflow=stored.workflow,
        history=_history_from_stored(
            stored
        ),
        record_session=_restore_record_session(
            stored
        ),
        metadata=dict(
            stored.metadata
        ),
    )


def persist_chat_exchange(
    session_id: int,
    user_content: str,
    assistant_messages: Iterable[str],
    *,
    user_message_type: str,
    assistant_message_type: str,
    database_path: str | Path | None = None,
) -> None:
    """Append one user message and all resulting Joey messages."""

    # Save the user message first so stored order matches the visible conversation.
    add_conversation_message(
        session_id=session_id,
        role="user",
        content=user_content,
        message_type=user_message_type,
        database_path=database_path,
    )

    # Persist each assistant response separately so the full exchange can be restored.
    for message in assistant_messages:
        add_conversation_message(
            session_id=session_id,
            role="assistant",
            content=message,
            message_type=assistant_message_type,
            database_path=database_path,
        )


def persist_record_workflow_state(
    session_id: int,
    record_session: JoeyConversationSession | None,
    *,
    clear_draft: bool = False,
    database_path: str | Path | None = None,
) -> None:
    """Persist or intentionally clear the current journal draft."""

    # Clearing a draft removes only the saved draft snapshot, not the session itself.
    if clear_draft:
        update_conversation_session(
            session_id=session_id,
            status=StoredConversationStatus.active,
            draft_state=None,
            update_draft_state=True,
            database_path=database_path,
        )
        return

    # Persist both the mapped workflow status and the serialised journal draft.
    update_conversation_session(
        session_id=session_id,
        status=_record_storage_status(
            record_session
        ),
        draft_state=(
            record_session.to_dict()
            if record_session is not None
            else None
        ),
        update_draft_state=True,
        database_path=database_path,
    )


def persist_strategy_workflow_state(
    session_id: int,
    pending_feedback: Mapping[str, Any] | None,
    *,
    database_path: str | Path | None = None,
) -> None:
    """Persist the current feedback target needed after an app restart."""

    # Pending strategy feedback is lightweight workflow state stored in metadata.
    metadata: dict[str, Any] = {}

    # Store only the currently pending feedback target needed after a restart.
    if pending_feedback is not None:
        metadata[
            "pending_strategy_feedback"
        ] = dict(
            pending_feedback
        )

    # Keep the strategy conversation active while updating only its metadata.
    update_conversation_session(
        session_id=session_id,
        status=StoredConversationStatus.active,
        metadata=metadata,
        update_metadata=True,
        database_path=database_path,
    )
