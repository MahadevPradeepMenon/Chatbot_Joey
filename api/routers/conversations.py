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


router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversation UI"],
)

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


def _require_conversation(
    session_id: int,
    database_path: Path,
) -> StoredConversation:
    conversation = get_conversation_session(
        session_id,
        database_path=database_path,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "The requested frontend conversation was not found."
            ),
        )

    return conversation


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

    session_id = create_conversation_session(
        workflow=payload.workflow,
        metadata=payload.metadata,
        database_path=database_path,
    )

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

    workflow_value: ConversationWorkflow = (
        normalise_workflow(
            workflow
        )
    )
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
    return _response(
        _require_conversation(
            session_id,
            database_path,
        )
    )


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
