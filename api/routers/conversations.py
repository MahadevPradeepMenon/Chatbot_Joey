"""HTTP persistence endpoints used by the Streamlit frontend."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from api.dependencies import get_database_path
from api.models import (
    ConversationMessageResponse,
    FrontendConversationCreateRequest,
    FrontendConversationExchangeRequest,
    FrontendConversationResponse,
)
from storage.conversation_storage import (
    ConversationWorkflow,
    StoredConversation,
    add_conversation_message,
    create_conversation_session,
    get_conversation_session,
    list_conversation_sessions,
    normalise_workflow,
    update_conversation_session,
)


# Group the Streamlit-facing persistence endpoints under one versioned
# conversation prefix, separate from the record and strategy APIs.
router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversation UI"],
)

# Literal aliases constrain workflow, status and role values exposed through
# the frontend conversation contract.
WorkflowValue = Literal[
    "record_observation",
    "ask_strategy",
]

StatusValue = Literal[
    "active",
    "ready_for_review",
    "confirmed",
    "rejected",
    "completed",
    "archived",
]

RoleValue = Literal[
    "user",
    "assistant",
]


# These conversion helpers reject unsupported stored values instead of
# silently coercing them into the narrower HTTP response types.
def _workflow_value(
    value: str,
) -> WorkflowValue:
    if value == "record_observation":
        return "record_observation"

    if value == "ask_strategy":
        return "ask_strategy"

    raise RuntimeError(
        f"Unsupported conversation workflow: {value}"
    )




def _status_value(
    value: str,
) -> StatusValue:
    if value == "active":
        return "active"
    if value == "ready_for_review":
        return "ready_for_review"
    if value == "confirmed":
        return "confirmed"
    if value == "rejected":
        return "rejected"
    if value == "completed":
        return "completed"
    if value == "archived":
        return "archived"

    raise RuntimeError(
        f"Unsupported conversation status: {value}"
    )


def _role_value(
    value: str,
) -> RoleValue:
    if value == "user":
        return "user"
    if value == "assistant":
        return "assistant"

    raise RuntimeError(
        f"Unsupported conversation role: {value}"
    )


# Convert the storage-layer conversation object into the Pydantic response
# model expected by the Streamlit client.
def _response(
    conversation: StoredConversation,
) -> FrontendConversationResponse:
    return FrontendConversationResponse(
        session_id=conversation.id,
        workflow=_workflow_value(
            conversation.workflow.value
        ),
        status=_status_value(
            conversation.status.value
        ),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        draft_state=conversation.draft_state,
        metadata=dict(
            conversation.metadata
        ),
        # Preserve the stored message order and message metadata when rebuilding
        # the frontend conversation history.
        messages=[
            ConversationMessageResponse(
                id=message.id,
                sequence_number=(
                    message.sequence_number
                ),
                role=_role_value(
                    message.role.value
                ),
                content=message.content,
                message_type=message.message_type,
                created_at=message.created_at,
            )
            for message in conversation.messages
        ],
    )


# Centralise conversation lookup and 404 handling so each endpoint behaves
# consistently for missing session IDs.
def _require_conversation(
    session_id: int,
    database_path: Path,
) -> StoredConversation:
    conversation = get_conversation_session(
        session_id,
        database_path=database_path,
    )

    # Missing frontend sessions are exposed as HTTP 404 rather than leaking a
    # storage-layer None result into the route logic.
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "The requested frontend conversation was not found."
            ),
        )

    return conversation


# Creating a frontend conversation persists both the workflow session and its
# initial Joey greeting so Streamlit can restore the same chat later.
@router.post(
    "/sessions",
    response_model=FrontendConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a persistent frontend conversation",
)
def create_frontend_conversation(
    payload: FrontendConversationCreateRequest,
    database_path: Path = Depends(
        get_database_path
    ),
) -> FrontendConversationResponse:
    """Create a workflow session with one Joey greeting."""

    # Persist the conversation first so the greeting can be attached to a
    # stable session identifier.
    session_id = create_conversation_session(
        workflow=payload.workflow,
        metadata=payload.metadata,
        database_path=database_path,
    )

    # Store the greeting as the first assistant message in the conversation.
    add_conversation_message(
        session_id=session_id,
        role="assistant",
        content=payload.greeting,
        message_type="greeting",
        database_path=database_path,
    )

    conversation = _require_conversation(
        session_id,
        database_path,
    )

    return _response(
        conversation
    )


# The latest-session endpoint is used by Streamlit to restore the most recent
# chat for one workflow after a rerun or application restart.
@router.get(
    "/sessions/latest",
    response_model=FrontendConversationResponse,
    summary="Get the latest conversation for one workflow",
)
def get_latest_frontend_conversation(
    workflow: WorkflowValue = Query(),
    database_path: Path = Depends(
        get_database_path
    ),
) -> FrontendConversationResponse:
    """Restore the latest stored workflow chat for Streamlit."""

    # Normalise the API workflow value into the storage-layer enum before
    # querying persistent conversation sessions.
    workflow_value: ConversationWorkflow = (
        normalise_workflow(
            workflow
        )
    )
    # Only the newest matching session is required for frontend restoration.
    conversations = list_conversation_sessions(
        workflow=workflow_value,
        limit=1,
        database_path=database_path,
    )

    if not conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No stored conversation exists for this workflow."
            ),
        )

    return _response(
        conversations[0]
    )


# Direct session lookup allows the frontend to reload a known conversation
# using its persistent identifier.
@router.get(
    "/sessions/{session_id}",
    response_model=FrontendConversationResponse,
    summary="Get one persistent frontend conversation",
)
def get_frontend_conversation(
    session_id: int,
    database_path: Path = Depends(
        get_database_path
    ),
) -> FrontendConversationResponse:
    # Reload the conversation after all writes so the response reflects the
    # canonical state stored in SQLite.
    return _response(
        _require_conversation(
            session_id,
            database_path,
        )
    )


# One exchange stores the user message followed by every assistant message
# produced for that frontend interaction.
@router.post(
    "/sessions/{session_id}/exchanges",
    response_model=FrontendConversationResponse,
    summary="Append one frontend chat exchange",
)
def append_frontend_exchange(
    session_id: int,
    payload: FrontendConversationExchangeRequest,
    database_path: Path = Depends(
        get_database_path
    ),
) -> FrontendConversationResponse:
    """Persist strategy chat or a UI-only validation exchange."""

    # Verify the session exists before writing any part of the exchange.
    _require_conversation(
        session_id,
        database_path,
    )

    add_conversation_message(
        session_id=session_id,
        role="user",
        content=payload.user_content,
        message_type=payload.user_message_type,
        database_path=database_path,
    )

    # Assistant responses are stored individually to preserve their original
    # ordering in the persistent chat history.
    for message in payload.assistant_messages:
        add_conversation_message(
            session_id=session_id,
            role="assistant",
            content=message,
            message_type=(
                payload.assistant_message_type
            ),
            database_path=database_path,
        )

    # Metadata updates are optional and are applied only when the caller
    # explicitly supplies a new metadata payload.
    if payload.metadata is not None:
        update_conversation_session(
            session_id=session_id,
            metadata=payload.metadata,
            update_metadata=True,
            database_path=database_path,
        )

    return _response(
        _require_conversation(
            session_id,
            database_path,
        )
    )
