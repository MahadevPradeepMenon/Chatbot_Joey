"""HTTP endpoints for Joey's source-backed strategy workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)

from api.dependencies import get_database_path
from api.models import (
    StrategyConfidenceResponse,
    StrategyContextResponse,
    StrategyEvidenceResponse,
    StrategyFeedbackRequest,
    StrategyFeedbackResponse,
    StrategyFeedbackSubmissionResponse,
    StrategySearchRequest,
    StrategySearchResponse,
)
from app.strategy_workflow_service import (
    StrategyFeedbackStateError,
    StrategyFeedbackWorkflowResult,
    StrategyRetrievalService,
    StrategySearchNotFoundError,
    StrategySearchWorkflowResult,
    build_strategy_retrieval_service,
    get_strategy_search_workflow,
    search_strategy_workflow,
    submit_strategy_feedback_workflow,
)
from storage.strategy_feedback import StoredStrategyFeedback


router = APIRouter(
    prefix="/api/v1/strategies",
    tags=["strategy workflow"],
)


StrategyOutcomeValue = Literal[
    "results",
    "abstained",
    "safety_limited",
]
ConfidenceLevelValue = Literal[
    "strong",
    "moderate",
    "weak",
]
FeedbackRatingValue = Literal[
    "worked_well",
    "helped_somewhat",
    "not_relevant",
    "did_not_work_well",
]


def _strategy_service(
    request: Request,
    database_path: Path = Depends(
        get_database_path
    ),
) -> StrategyRetrievalService:
    """Return a real service or a deterministic test factory product."""

    factory = getattr(
        request.app.state,
        "strategy_service_factory",
        None,
    )

    if factory is None:
        return build_strategy_retrieval_service(
            database_path
        )

    service = factory(
        database_path
    )
    return cast(
        StrategyRetrievalService,
        service,
    )


def _outcome_value(
    value: str,
) -> StrategyOutcomeValue:
    if value == "results":
        return "results"

    if value == "abstained":
        return "abstained"

    if value == "safety_limited":
        return "safety_limited"

    raise RuntimeError(
        f"Unsupported strategy-search outcome: {value}"
    )


def _confidence_level(
    value: str,
) -> ConfidenceLevelValue:
    if value == "strong":
        return "strong"

    if value == "moderate":
        return "moderate"

    if value == "weak":
        return "weak"

    raise RuntimeError(
        f"Unsupported confidence level: {value}"
    )


def _feedback_rating(
    value: str,
) -> FeedbackRatingValue:
    if value == "worked_well":
        return "worked_well"

    if value == "helped_somewhat":
        return "helped_somewhat"

    if value == "not_relevant":
        return "not_relevant"

    if value == "did_not_work_well":
        return "did_not_work_well"

    raise RuntimeError(
        f"Unsupported strategy feedback rating: {value}"
    )


def _feedback_response(
    item: StoredStrategyFeedback,
) -> StrategyFeedbackResponse:
    """Convert one typed SQLite result to a Pydantic response."""

    return StrategyFeedbackResponse(
        feedback_id=item.id,
        search_id=item.search_id,
        strategy_rank=item.strategy_rank,
        strategy_code=item.strategy_code,
        strategy_title=item.strategy_title,
        collection_title=item.collection_title,
        source_file=item.source_file,
        rating=_feedback_rating(
            item.rating.value
        ),
        rating_label=item.rating_label,
        comment=item.comment,
        created_at=item.created_at,
    )


def _search_response(
    result: StrategySearchWorkflowResult,
) -> StrategySearchResponse:
    """Convert the framework-neutral result into the HTTP contract."""

    confidence = None

    if result.confidence is not None:
        decision = result.confidence
        confidence = StrategyConfidenceResponse(
            level=_confidence_level(
                decision.level.value
            ),
            should_abstain=(
                decision.should_abstain
            ),
            reason=decision.reason,
            query_token_count=(
                decision.query_token_count
            ),
            evidence_count=(
                decision.evidence_count
            ),
            top_original_score=(
                decision.top_original_score
            ),
            top_overlap_count=(
                decision.top_overlap_count
            ),
            top_overlap_ratio=(
                decision.top_overlap_ratio
            ),
            overlapping_evidence_count=(
                decision.overlapping_evidence_count
            ),
        )

    context = None

    if result.context is not None:
        selected = result.context
        context = StrategyContextResponse(
            detected_topics=list(
                selected.detected_topics
            ),
            profile_items=list(
                selected.profile_items
            ),
            journal_items=list(
                selected.journal_items
            ),
            quick_track_items=list(
                selected.quick_track_items
            ),
            active_strategy_items=list(
                selected.active_strategy_items
            ),
            omitted_sensitive_fields=list(
                selected.omitted_sensitive_fields
            ),
        )

    strategies = [
        StrategyEvidenceResponse(
            rank=item.rank,
            original_rank=item.original_rank,
            original_score=item.original_score,
            history_adjustment=(
                item.history_adjustment
            ),
            personalised_score=(
                item.personalised_score
            ),
            strategy_code=item.strategy_code,
            strategy_title=item.strategy_title,
            collection_title=(
                item.collection_title
            ),
            source_file=item.source_file,
            theme=item.theme,
            chunk_id=item.chunk_id,
            passage=item.passage,
            lifecycle_status=(
                item.lifecycle_status
            ),
            latest_outcome=item.latest_outcome,
            times_used=item.times_used,
            history_note=item.history_note,
        )
        for item in result.evidence
    ]

    return StrategySearchResponse(
        outcome=_outcome_value(
            result.outcome
        ),
        search_id=result.search_id,
        question=result.question,
        retrieval_query=result.retrieval_query,
        message=result.message,
        safety_notice=result.safety_notice,
        confidence=confidence,
        context=context,
        strategies=strategies,
        feedback=[
            _feedback_response(item)
            for item in result.feedback
        ],
        strategy_count=len(
            strategies
        ),
        can_submit_feedback=(
            result.can_submit_feedback
        ),
        created_at=result.created_at,
    )


@router.post(
    "/search",
    response_model=StrategySearchResponse,
    summary="Search the approved strategy library",
)
def search_strategies(
    payload: StrategySearchRequest,
    database_path: Path = Depends(
        get_database_path
    ),
    retrieval_service: StrategyRetrievalService = Depends(
        _strategy_service
    ),
) -> StrategySearchResponse:
    """Run safety-first, confidence-gated Hybrid RAG."""

    try:
        result = search_strategy_workflow(
            question=payload.question,
            top_k=payload.top_k,
            database_path=database_path,
            retrieval_service=retrieval_service,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    return _search_response(
        result
    )


@router.get(
    "/searches/{search_id}",
    response_model=StrategySearchResponse,
    summary="Get an accepted strategy search",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The accepted strategy search does not exist."
        }
    },
)
def get_strategy_search(
    search_id: int,
    database_path: Path = Depends(
        get_database_path
    ),
) -> StrategySearchResponse:
    """Return stored evidence and any feedback for one accepted search."""

    try:
        result = get_strategy_search_workflow(
            search_id,
            database_path=database_path,
        )
    except StrategySearchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    return _search_response(
        result
    )


@router.post(
    "/feedback",
    response_model=StrategyFeedbackSubmissionResponse,
    summary="Store feedback for a displayed strategy",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The accepted strategy search does not exist."
        },
        status.HTTP_409_CONFLICT: {
            "description": "The strategy rank does not belong to the search."
        },
    },
)
def submit_feedback(
    payload: StrategyFeedbackRequest,
    database_path: Path = Depends(
        get_database_path
    ),
) -> StrategyFeedbackSubmissionResponse:
    """Insert or update explicit strategy feedback in local SQLite."""

    try:
        result: StrategyFeedbackWorkflowResult = (
            submit_strategy_feedback_workflow(
                search_id=payload.search_id,
                strategy_rank=payload.strategy_rank,
                rating=payload.rating,
                comment=payload.comment,
                database_path=database_path,
            )
        )
    except StrategySearchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except StrategyFeedbackStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return StrategyFeedbackSubmissionResponse(
        message=result.message,
        feedback=_feedback_response(
            result.feedback
        ),
    )
