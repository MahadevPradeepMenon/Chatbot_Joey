"""HTTP endpoints for Joey's 'Record what happened' workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from api.dependencies import get_database_path
from api.models import (
    ConversationMessageResponse,
    RecordDraftResponse,
    RecordMessageRequest,
    RecordSessionCreateRequest,
    RecordSessionResponse,
)
from app.record_workflow_service import (
    RecordSessionNotFoundError,
    RecordWorkflowResult,
    RecordWorkflowStateError,
    confirm_record_workflow,
    create_record_workflow,
    get_record_workflow,
    reject_record_workflow,
    submit_record_message,
)
from app.schemas import StructuredJoeyRecord
from safety.safety_guard import should_limit_strategy_suggestions


router = APIRouter(
    prefix="/api/v1/record",
    tags=["record workflow"],
)


def _not_found(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )


def _conflict(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(error),
    )


def _draft_response(
    draft_state: dict[str, Any] | None,
) -> RecordDraftResponse | None:
    """Validate a stored JSON snapshot for the HTTP response."""

    if draft_state is None:
        return None

    record = StructuredJoeyRecord.model_validate(
        draft_state.get(
            "structured_record",
            {},
        )
    )
    response_data = dict(
        draft_state
    )
    response_data["structured_record"] = record
    response_data["safety_limited"] = (
        should_limit_strategy_suggestions(
            record
        )
    )

    return RecordDraftResponse.model_validate(
        response_data
    )


RecordWorkflowValue = Literal[
    "record_observation"
]
RecordStatusValue = Literal[
    "active",
    "ready_for_review",
    "confirmed",
    "rejected",
]
RecordNextActionValue = Literal[
    "answer_follow_up",
    "confirm_or_reject",
    "completed",
]


def _record_workflow_value(
    value: str,
) -> RecordWorkflowValue:
    """Validate the stored workflow before returning the API literal."""

    if value != "record_observation":
        raise RuntimeError(
            "The stored session is not a record-observation workflow."
        )

    return "record_observation"


def _record_status_value(
    value: str,
) -> RecordStatusValue:
    """Validate the stored status before returning the API literal."""

    if value == "active":
        return "active"

    if value == "ready_for_review":
        return "ready_for_review"

    if value == "confirmed":
        return "confirmed"

    if value == "rejected":
        return "rejected"

    raise RuntimeError(
        f"Unsupported record-workflow status: {value}"
    )


def _next_action(
    status_value: RecordStatusValue,
) -> RecordNextActionValue:
    """Map persistent status to the next explicit client action."""

    if status_value == "active":
        return "answer_follow_up"

    if status_value == "ready_for_review":
        return "confirm_or_reject"

    return "completed"


def _response(
    result: RecordWorkflowResult,
) -> RecordSessionResponse:
    """Convert the framework-neutral service result to an API model."""

    conversation = result.conversation
    workflow_value = _record_workflow_value(
        conversation.workflow.value
    )
    status_value = _record_status_value(
        conversation.status.value
    )

    return RecordSessionResponse(
        session_id=conversation.id,
        workflow=workflow_value,
        status=status_value,
        next_action=_next_action(
            status_value
        ),
        assistant_messages=list(
            result.assistant_messages
        ),
        messages=[
            ConversationMessageResponse(
                id=message.id,
                sequence_number=(
                    message.sequence_number
                ),
                role=message.role.value,
                content=message.content,
                message_type=message.message_type,
                created_at=message.created_at,
            )
            for message in conversation.messages
        ],
        draft=_draft_response(
            conversation.draft_state
        ),
        journal_entry_id=(
            result.journal_entry_id
        ),
        metadata=dict(
            conversation.metadata
        ),
    )


@router.post(
    "/sessions",
    response_model=RecordSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a journal conversation",
)
def create_session(
    request: RecordSessionCreateRequest,
    database_path: Path = Depends(
        get_database_path
    ),
) -> RecordSessionResponse:
    """Create a persistent draft from the first parent observation."""

    try:
        result = create_record_workflow(
            request.note,
            database_path=database_path,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    return _response(
        result
    )


@router.get(
    "/sessions/{session_id}",
    response_model=RecordSessionResponse,
    summary="Get a journal conversation",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The conversation does not exist."
        },
        status.HTTP_409_CONFLICT: {
            "description": "The ID belongs to another workflow."
        },
    },
)
def get_session(
    session_id: int,
    database_path: Path = Depends(
        get_database_path
    ),
) -> RecordSessionResponse:
    """Return the persistent draft and ordered message history."""

    try:
        result = get_record_workflow(
            session_id,
            database_path=database_path,
        )
    except RecordSessionNotFoundError as error:
        raise _not_found(
            error
        ) from error
    except RecordWorkflowStateError as error:
        raise _conflict(
            error
        ) from error

    return _response(
        result
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=RecordSessionResponse,
    summary="Answer the current follow-up question",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The conversation does not exist."
        },
        status.HTTP_409_CONFLICT: {
            "description": "The conversation is not collecting answers."
        },
    },
)
def submit_message(
    session_id: int,
    request: RecordMessageRequest,
    database_path: Path = Depends(
        get_database_path
    ),
) -> RecordSessionResponse:
    """Merge one parent answer into the same structured draft."""

    try:
        result = submit_record_message(
            session_id=session_id,
            message=request.message,
            database_path=database_path,
        )
    except RecordSessionNotFoundError as error:
        raise _not_found(
            error
        ) from error
    except RecordWorkflowStateError as error:
        raise _conflict(
            error
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    return _response(
        result
    )


@router.post(
    "/sessions/{session_id}/confirm",
    response_model=RecordSessionResponse,
    summary="Confirm and save a reviewed journal draft",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The conversation does not exist."
        },
        status.HTTP_409_CONFLICT: {
            "description": "The draft is not ready or was already completed."
        },
    },
)
def confirm_session(
    session_id: int,
    database_path: Path = Depends(
        get_database_path
    ),
) -> RecordSessionResponse:
    """Save only a draft that has reached explicit review confirmation."""

    try:
        result = confirm_record_workflow(
            session_id,
            database_path=database_path,
        )
    except RecordSessionNotFoundError as error:
        raise _not_found(
            error
        ) from error
    except RecordWorkflowStateError as error:
        raise _conflict(
            error
        ) from error

    return _response(
        result
    )


@router.post(
    "/sessions/{session_id}/reject",
    response_model=RecordSessionResponse,
    summary="Reject a reviewed journal draft",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The conversation does not exist."
        },
        status.HTTP_409_CONFLICT: {
            "description": "The draft is not ready or was already completed."
        },
    },
)
def reject_session(
    session_id: int,
    database_path: Path = Depends(
        get_database_path
    ),
) -> RecordSessionResponse:
    """Discard a reviewed draft without creating a journal entry."""

    try:
        result = reject_record_workflow(
            session_id,
            database_path=database_path,
        )
    except RecordSessionNotFoundError as error:
        raise _not_found(
            error
        ) from error
    except RecordWorkflowStateError as error:
        raise _conflict(
            error
        ) from error

    return _response(
        result
    )
