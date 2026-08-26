"""Framework-neutral orchestration for Joey's journal workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.conversation_manager import (
    ConversationStatus,
    JoeyConversationSession,
)
from app.conversation_persistence import (
    persist_record_workflow_state,
)
from safety.safety_guard import build_safety_notice
from storage.conversation_storage import (
    ConversationWorkflow,
    StoredConversation,
    StoredConversationStatus,
    add_conversation_message,
    create_conversation_session,
    get_conversation_session,
    update_conversation_session,
)
from storage.database import save_confirmed_session


# Workflow-specific exceptions distinguish missing sessions from invalid
# operations on an existing record workflow.
class RecordSessionNotFoundError(LookupError):
    """Raised when an API record-session ID does not exist."""


class RecordWorkflowStateError(RuntimeError):
    """Raised when an operation conflicts with the current draft state."""


# Immutable result object returned to the API/UI layer after each workflow action.
@dataclass(frozen=True)
class RecordWorkflowResult:
    """One complete record-workflow result returned to an API adapter."""

    conversation: StoredConversation
    assistant_messages: tuple[str, ...] = ()

    @property
    def journal_entry_id(self) -> int | None:
        """Return the confirmed journal-entry ID stored in metadata."""

        # A journal entry exists only after confirmation, so its database ID
        # is read from conversation metadata when available.
        raw_value = self.conversation.metadata.get(
            "journal_entry_id"
        )

        if raw_value is None:
            return None

        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None


def _clean_text(value: str) -> str:
    """Normalise user-provided text without changing its meaning."""

    return " ".join(
        str(value or "").split()
    ).strip()


def _readable_list(values: list[str]) -> str:
    """Join a short list into parent-facing prose."""

    # Clean values before turning them into parent-facing prose and ignore blanks.
    clean_values = [
        _clean_text(value)
        for value in values
        if _clean_text(value)
    ]

    if not clean_values:
        return ""

    if len(clean_values) == 1:
        return clean_values[0]

    if len(clean_values) == 2:
        return (
            f"{clean_values[0]} and {clean_values[1]}"
        )

    return (
        ", ".join(clean_values[:-1])
        + f", and {clean_values[-1]}"
    )


def _build_initial_summary(
    session: JoeyConversationSession,
) -> str:
    """Summarise only information extracted from the first note."""

    record = session.current_record
    details: list[str] = []

    if record.anxiety_level.value != "Unknown":
        details.append(
            "anxiety was initially understood as "
            f"{record.anxiety_level.value.lower()}"
        )

    if record.mood_zone.value != "Unknown":
        details.append(
            "the mood zone was initially understood as "
            f"{record.mood_zone.value}"
        )

    if record.environment:
        details.append(
            f"the setting was {_clean_text(record.environment)}"
        )

    if record.possible_triggers:
        details.append(
            "possible triggers included "
            + _readable_list(
                record.possible_triggers
            )
        )

    if not details:
        return (
            "I have created a journal draft from what you described."
        )

    return (
        "I have created a journal draft: "
        + "; ".join(details)
        + "."
    )


def _build_answer_acknowledgement(
    field_name: str | None,
    answer: str,
    session: JoeyConversationSession,
) -> str:
    """Acknowledge only the latest follow-up answer."""

    clean_answer = _clean_text(answer)
    record = session.current_record

    skipped_answers = {
        "i don't know",
        "i do not know",
        "don't know",
        "do not know",
        "not sure",
        "unsure",
        "skip",
        "unknown",
    }

    if clean_answer.lower() in skipped_answers:
        return (
            "I have left that detail as unknown in the journal draft."
        )

    if field_name == "possible_triggers":
        return (
            "I have added this possible trigger to the draft: "
            f"{clean_answer}"
        )

    if field_name == "anxiety_level":
        return (
            "I have recorded the anxiety level as "
            f"{record.anxiety_level.value}."
        )

    if field_name == "mood":
        mood_text = record.mood_zone.value

        if record.mood_labels:
            mood_text += (
                ", with "
                + _readable_list(
                    record.mood_labels
                )
            )

        return (
            "I have updated the mood information to "
            f"{mood_text}."
        )

    if field_name == "environment":
        return (
            "I have recorded the setting as "
            f"{record.environment}."
        )

    if field_name == "safety_status":
        return (
            "I have added the safety information you provided "
            "to the draft."
        )

    if field_name == "medication_context":
        return (
            "I have added the medication context to the draft. "
            "Joey does not provide medication or dosage advice."
        )

    return (
        "I have added that detail to the same journal draft."
    )


def _build_final_summary(
    session: JoeyConversationSession,
) -> str:
    """Return the final draft summary before explicit confirmation."""

    if session.current_record.summary:
        return (
            "My summary is: "
            f"{session.current_record.summary}"
        )

    return (
        "The journal draft is now ready for your review."
    )


def _confirmation_prompt() -> str:
    """Explain the explicit confirmation boundary."""

    return (
        "Review the draft, then use the confirm endpoint to save it "
        "or the reject endpoint to discard it."
    )


def _start_messages(
    session: JoeyConversationSession,
) -> list[tuple[str, str]]:
    """Build typed Joey messages for a newly created draft."""

    messages: list[tuple[str, str]] = [
        (
            "record_summary",
            _build_initial_summary(
                session
            ),
        )
    ]

    # Safety messaging is kept separate from the ordinary draft summary so
    # risk-related information can be surfaced explicitly when needed.
    safety_notice = build_safety_notice(
        session.current_record
    )

    if safety_notice:
        messages.append(
            (
                "safety_notice",
                safety_notice,
            )
        )

    # While information is still being collected, return one follow-up question.
    # Otherwise move the user to review and explicit confirmation.
    if (
        session.status
        == ConversationStatus.collecting_information
    ):
        messages.append(
            (
                "follow_up_question",
                session.follow_up_question
                or "Would you like to add more detail?",
            )
        )
    else:
        messages.extend(
            [
                (
                    "review_summary",
                    _build_final_summary(
                        session
                    ),
                ),
                (
                    "confirmation_prompt",
                    _confirmation_prompt(),
                ),
            ]
        )

    return messages


def _answer_messages(
    session: JoeyConversationSession,
    answered_field: str | None,
    answer: str,
) -> list[tuple[str, str]]:
    """Build typed Joey messages after one follow-up answer."""

    messages: list[tuple[str, str]] = [
        (
            "answer_acknowledgement",
            _build_answer_acknowledgement(
                field_name=answered_field,
                answer=answer,
                session=session,
            ),
        )
    ]

    if (
        session.status
        == ConversationStatus.collecting_information
    ):
        messages.append(
            (
                "follow_up_question",
                session.follow_up_question
                or "Would you like to add more detail?",
            )
        )
    else:
        messages.extend(
            [
                (
                    "review_summary",
                    _build_final_summary(
                        session
                    ),
                ),
                (
                    "confirmation_prompt",
                    _confirmation_prompt(),
                ),
            ]
        )

    return messages


def _stored_record_conversation(
    session_id: int,
    database_path: str | Path | None,
) -> StoredConversation:
    """Load one record workflow or raise a controlled API error."""

    # Reload the conversation by ID before each operation so this service
    # always works from persisted state rather than stale in-memory data.
    stored = get_conversation_session(
        session_id,
        database_path=database_path,
    )

    if stored is None:
        raise RecordSessionNotFoundError(
            "The requested record conversation was not found."
        )

    # A valid session ID is not sufficient: this service must not operate on
    # conversations that belong to another Joey workflow.
    if (
        stored.workflow
        != ConversationWorkflow.record_observation
    ):
        raise RecordWorkflowStateError(
            "The requested conversation belongs to another workflow."
        )

    return stored


def _restore_session(
    stored: StoredConversation,
) -> JoeyConversationSession:
    """Restore the validated draft snapshot for one record conversation."""

    # A record workflow cannot continue without its persisted draft snapshot.
    if stored.draft_state is None:
        raise RecordWorkflowStateError(
            "The record conversation has no journal draft."
        )

    try:
        return JoeyConversationSession.from_dict(
            stored.draft_state
        )
    except ValueError as error:
        raise RecordWorkflowStateError(
            "The stored journal draft could not be restored."
        ) from error


def _persist_typed_exchange(
    session_id: int,
    user_content: str,
    user_message_type: str,
    assistant_messages: list[tuple[str, str]],
    database_path: str | Path | None,
) -> None:
    """Persist one user message and specifically typed Joey messages."""

    # Persist the user message first; assistant messages are then stored with
    # explicit message types so the complete exchange can be reconstructed.
    add_conversation_message(
        session_id=session_id,
        role="user",
        content=user_content,
        message_type=user_message_type,
        database_path=database_path,
    )

    for message_type, message in assistant_messages:
        add_conversation_message(
            session_id=session_id,
            role="assistant",
            content=message,
            message_type=message_type,
            database_path=database_path,
        )


def _refresh_result(
    session_id: int,
    database_path: str | Path | None,
    assistant_messages: list[str] | tuple[str, ...] = (),
) -> RecordWorkflowResult:
    """Reload the complete persisted conversation after a mutation."""

    stored = _stored_record_conversation(
        session_id,
        database_path,
    )

    return RecordWorkflowResult(
        conversation=stored,
        assistant_messages=tuple(
            assistant_messages
        ),
    )


def create_record_workflow(
    note: str,
    *,
    database_path: str | Path | None = None,
) -> RecordWorkflowResult:
    """Create and persist a record conversation from the first note."""

    # Normalise the first note before extraction and persistence.
    clean_note = _clean_text(note)

    if not clean_note:
        raise ValueError(
            "The parent/carer note cannot be empty."
        )

    # Starting a session runs the deterministic extractor and selects the
    # first follow-up question when more information is required.
    session = JoeyConversationSession.start(
        clean_note
    )
    # Create the durable workflow session before storing any conversation messages.
    session_id = create_conversation_session(
        workflow=ConversationWorkflow.record_observation,
        database_path=database_path,
    )
    typed_messages = _start_messages(
        session
    )

    _persist_typed_exchange(
        session_id=session_id,
        user_content=clean_note,
        user_message_type="observation",
        assistant_messages=typed_messages,
        database_path=database_path,
    )

    # The visible exchange is stored before the draft snapshot so the persisted
    # state change is accompanied by the messages that caused it.
    # Persist the validated draft after all visible messages are stored.
    persist_record_workflow_state(
        session_id=session_id,
        record_session=session,
        database_path=database_path,
    )

    return _refresh_result(
        session_id,
        database_path,
        [
            message
            for _, message in typed_messages
        ],
    )


def get_record_workflow(
    session_id: int,
    *,
    database_path: str | Path | None = None,
) -> RecordWorkflowResult:
    """Return one persisted record conversation."""

    return _refresh_result(
        session_id,
        database_path,
    )


def submit_record_message(
    session_id: int,
    message: str,
    *,
    database_path: str | Path | None = None,
) -> RecordWorkflowResult:
    """Submit one follow-up answer to an active record conversation."""

    # Follow-up answers are normalised using the same whitespace handling as notes.
    clean_message = _clean_text(
        message
    )

    if not clean_message:
        raise ValueError(
            "The follow-up answer cannot be empty."
        )

    stored = _stored_record_conversation(
        session_id,
        database_path,
    )

    if stored.status != StoredConversationStatus.active:
        if (
            stored.status
            == StoredConversationStatus.ready_for_review
        ):
            raise RecordWorkflowStateError(
                "The draft is ready for review. Use the confirm or "
                "reject endpoint instead of adding another message."
            )

        raise RecordWorkflowStateError(
            "This record conversation is no longer collecting answers."
        )

    session = _restore_session(
        stored
    )

    # The restored draft must still be in the information-collection state
    # before another follow-up answer can be merged into it.
    if (
        session.status
        != ConversationStatus.collecting_information
    ):
        raise RecordWorkflowStateError(
            "This record conversation is not collecting information."
        )

    # Capture the field before submit_answer() advances to the next question;
    # the acknowledgement needs to describe the field that was just updated.
    answered_field = session.pending_field
    session.submit_answer(
        clean_message
    )
    typed_messages = _answer_messages(
        session,
        answered_field,
        clean_message,
    )

    _persist_typed_exchange(
        session_id=session_id,
        user_content=clean_message,
        user_message_type="follow_up_answer",
        assistant_messages=typed_messages,
        database_path=database_path,
    )
    persist_record_workflow_state(
        session_id=session_id,
        record_session=session,
        database_path=database_path,
    )

    return _refresh_result(
        session_id,
        database_path,
        [
            item
            for _, item in typed_messages
        ],
    )


def confirm_record_workflow(
    session_id: int,
    *,
    database_path: str | Path | None = None,
) -> RecordWorkflowResult:
    """Confirm a review-ready draft and save one journal entry."""

    stored = _stored_record_conversation(
        session_id,
        database_path,
    )

    if stored.status == StoredConversationStatus.confirmed:
        raise RecordWorkflowStateError(
            "This journal draft has already been confirmed."
        )

    # Confirmation or rejection is allowed only after questioning has finished
    # and the draft has explicitly entered the review state.
    if (
        stored.status
        != StoredConversationStatus.ready_for_review
    ):
        raise RecordWorkflowStateError(
            "The draft must be ready for review before confirmation."
        )

    session = _restore_session(
        stored
    )
    session.confirm()

    # This is the explicit save boundary: no journal entry is written until
    # the parent/carer has reviewed and confirmed the draft.
    journal_entry_id = save_confirmed_session(
        session,
        source="fastapi_record_workflow",
        database_path=database_path,
    )
    assistant_messages = [
        (
            "The journal entry has been confirmed and stored locally."
        ),
        (
            "Its structured information is now available in the "
            "local Joey database."
        ),
    ]

    _persist_typed_exchange(
        session_id=session_id,
        user_content="confirm",
        user_message_type="confirmation_command",
        assistant_messages=[
            (
                "confirmation_response",
                message,
            )
            for message in assistant_messages
        ],
        database_path=database_path,
    )
    persist_record_workflow_state(
        session_id=session_id,
        record_session=session,
        database_path=database_path,
    )

    # Preserve existing metadata and attach the saved journal-entry ID so
    # callers can link the confirmed workflow to the stored record.
    metadata: dict[str, Any] = dict(
        stored.metadata
    )
    metadata["journal_entry_id"] = (
        journal_entry_id
    )

    update_conversation_session(
        session_id=session_id,
        metadata=metadata,
        update_metadata=True,
        database_path=database_path,
    )

    return _refresh_result(
        session_id,
        database_path,
        assistant_messages,
    )


def reject_record_workflow(
    session_id: int,
    *,
    database_path: str | Path | None = None,
) -> RecordWorkflowResult:
    """Reject a review-ready draft without creating a journal entry."""

    stored = _stored_record_conversation(
        session_id,
        database_path,
    )

    if stored.status == StoredConversationStatus.confirmed:
        raise RecordWorkflowStateError(
            "A confirmed journal draft cannot be rejected."
        )

    if stored.status == StoredConversationStatus.rejected:
        raise RecordWorkflowStateError(
            "This journal draft has already been rejected."
        )

    # Confirmation or rejection is allowed only after questioning has finished
    # and the draft has explicitly entered the review state.
    if (
        stored.status
        != StoredConversationStatus.ready_for_review
    ):
        raise RecordWorkflowStateError(
            "The draft must be ready for review before rejection."
        )

    session = _restore_session(
        stored
    )
    # Rejection changes only the workflow state; save_confirmed_session() is
    # deliberately not called, so no journal entry is created.
    session.reject()
    assistant_messages = [
        "The draft was discarded and no journal entry was saved."
    ]

    _persist_typed_exchange(
        session_id=session_id,
        user_content="reject",
        user_message_type="rejection_command",
        assistant_messages=[
            (
                "rejection_response",
                message,
            )
            for message in assistant_messages
        ],
        database_path=database_path,
    )
    persist_record_workflow_state(
        session_id=session_id,
        record_session=session,
        database_path=database_path,
    )

    return _refresh_result(
        session_id,
        database_path,
        assistant_messages,
    )
