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


class StrategySearchRequest(_CleanTextRequest):
    """One parent/carer question for the approved strategy library."""

    question: str = Field(
        min_length=1,
        max_length=10_000,
        description="Natural-language strategy question.",
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of source-backed strategies to return.",
    )

    @field_validator("question")
    @classmethod
    def validate_question(
        cls,
        value: str,
    ) -> str:
        clean = cls._clean(
            value
        )

        if not clean:
            raise ValueError(
                "The strategy question cannot be empty."
            )

        return clean


class StrategyFeedbackRequest(_CleanTextRequest):
    """Explicit feedback for one strategy displayed by an accepted search."""

    search_id: int = Field(
        ge=1,
        description="Accepted strategy-search identifier.",
    )
    strategy_rank: int = Field(
        ge=1,
        description="Display rank returned by the search endpoint.",
    )
    rating: Literal[
        "worked_well",
        "helped_somewhat",
        "not_relevant",
        "did_not_work_well",
    ]
    comment: str | None = Field(
        default=None,
        max_length=2_000,
        description="Optional local note about the strategy outcome.",
    )

    @field_validator("comment")
    @classmethod
    def validate_comment(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        clean = cls._clean(
            value
        )
        return clean or None


class StrategyConfidenceResponse(BaseModel):
    """Explainable retrieval-confidence decision."""

    level: Literal[
        "strong",
        "moderate",
        "weak",
    ]
    should_abstain: bool
    reason: str | None = None
    query_token_count: int | None = Field(
        default=None,
        ge=0,
    )
    evidence_count: int | None = Field(
        default=None,
        ge=0,
    )
    top_original_score: float | None = Field(
        default=None,
        ge=0.0,
    )
    top_overlap_count: int | None = Field(
        default=None,
        ge=0,
    )
    top_overlap_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    overlapping_evidence_count: int | None = Field(
        default=None,
        ge=0,
    )


class StrategyContextResponse(BaseModel):
    """Minimal confirmed context selected for a strategy question."""

    detected_topics: list[str] = Field(
        default_factory=list
    )
    profile_items: list[str] = Field(
        default_factory=list
    )
    journal_items: list[str] = Field(
        default_factory=list
    )
    quick_track_items: list[str] = Field(
        default_factory=list
    )
    active_strategy_items: list[str] = Field(
        default_factory=list
    )
    omitted_sensitive_fields: list[str] = Field(
        default_factory=list
    )


class StrategyEvidenceResponse(BaseModel):
    """One source-backed strategy with transparent history adjustment."""

    rank: int = Field(ge=1)
    original_rank: int = Field(ge=1)
    original_score: float = Field(ge=0.0)
    history_adjustment: float
    personalised_score: float
    strategy_code: str | None = None
    strategy_title: str | None = None
    collection_title: str
    source_file: str
    theme: str | None = None
    chunk_id: str
    passage: str
    lifecycle_status: str
    latest_outcome: str
    times_used: int = Field(ge=0)
    history_note: str


class StrategyFeedbackResponse(BaseModel):
    """One persisted feedback record for a displayed strategy."""

    feedback_id: int = Field(ge=1)
    search_id: int = Field(ge=1)
    strategy_rank: int = Field(ge=1)
    strategy_code: str | None = None
    strategy_title: str | None = None
    collection_title: str
    source_file: str
    rating: Literal[
        "worked_well",
        "helped_somewhat",
        "not_relevant",
        "did_not_work_well",
    ]
    rating_label: str
    comment: str | None = None
    created_at: str


class StrategySearchResponse(BaseModel):
    """Complete result of a strategy search or safety abstention."""

    outcome: Literal[
        "results",
        "abstained",
        "safety_limited",
    ]
    search_id: int | None = Field(
        default=None,
        ge=1,
    )
    question: str
    retrieval_query: str | None = None
    message: str
    safety_notice: str | None = None
    confidence: StrategyConfidenceResponse | None = None
    context: StrategyContextResponse | None = None
    strategies: list[StrategyEvidenceResponse] = Field(
        default_factory=list
    )
    feedback: list[StrategyFeedbackResponse] = Field(
        default_factory=list
    )
    strategy_count: int = Field(ge=0)
    can_submit_feedback: bool
    created_at: str | None = None


class StrategyFeedbackSubmissionResponse(BaseModel):
    """Acknowledgement of an inserted or updated feedback record."""

    message: str
    feedback: StrategyFeedbackResponse
