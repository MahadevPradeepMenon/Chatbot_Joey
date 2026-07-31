"""Pydantic request and response models for the Hey Joey API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.schemas import StructuredJoeyRecord


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


class _CleanTextRequest(BaseModel):
    """Base request that rejects empty or whitespace-only text."""

    @staticmethod
    def _clean(value: str) -> str:
        return " ".join(
            str(value or "").split()
        ).strip()


class RecordSessionCreateRequest(_CleanTextRequest):
    """Initial parent observation used to create a journal draft."""

    note: str = Field(
        min_length=1,
        max_length=10_000,
        description="Parent/carer observation in their own words.",
    )

    @field_validator("note")
    @classmethod
    def validate_note(
        cls,
        value: str,
    ) -> str:
        clean = cls._clean(
            value
        )

        if not clean:
            raise ValueError(
                "The parent/carer note cannot be empty."
            )

        return clean


class RecordMessageRequest(_CleanTextRequest):
    """One answer to Joey's current follow-up question."""

    message: str = Field(
        min_length=1,
        max_length=5_000,
        description="Answer to the active follow-up question.",
    )

    @field_validator("message")
    @classmethod
    def validate_message(
        cls,
        value: str,
    ) -> str:
        clean = cls._clean(
            value
        )

        if not clean:
            raise ValueError(
                "The follow-up answer cannot be empty."
            )

        return clean


class ConversationMessageResponse(BaseModel):
    """One ordered persistent conversation message."""

    id: int = Field(ge=1)
    sequence_number: int = Field(ge=1)
    role: Literal["user", "assistant"]
    content: str
    message_type: str
    created_at: str


class ConversationTurnResponse(BaseModel):
    """One follow-up question and parent answer in the draft."""

    question: str
    answer: str
    field_name: str


class RecordDraftResponse(BaseModel):
    """Validated snapshot of the current structured journal draft."""

    original_note: str
    status: Literal[
        "collecting_information",
        "ready_for_review",
        "confirmed",
        "rejected",
    ]
    pending_field: str | None = None
    follow_up_question: str | None = None
    history: list[ConversationTurnResponse] = Field(
        default_factory=list
    )
    completed_fields: list[str] = Field(
        default_factory=list
    )
    skipped_fields: list[str] = Field(
        default_factory=list
    )
    structured_record: StructuredJoeyRecord
    safety_limited: bool = False


class RecordSessionResponse(BaseModel):
    """Complete state of one persistent journal conversation."""

    session_id: int = Field(ge=1)
    workflow: Literal["record_observation"]
    status: Literal[
        "active",
        "ready_for_review",
        "confirmed",
        "rejected",
    ]
    next_action: Literal[
        "answer_follow_up",
        "confirm_or_reject",
        "completed",
    ]
    assistant_messages: list[str] = Field(
        default_factory=list,
        description="New Joey messages produced by this request.",
    )
    messages: list[ConversationMessageResponse]
    draft: RecordDraftResponse | None
    journal_entry_id: int | None = Field(
        default=None,
        ge=1,
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )
