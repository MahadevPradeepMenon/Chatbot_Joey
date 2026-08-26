"""Framework-neutral strategy search and feedback workflow services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.context_builder import ContextSelection
from app.extractor import extract_structured_record
from rag.retrieval_confidence import (
    RetrievalConfidenceDecision,
    assess_retrieval_confidence,
    build_abstention_message,
)
from safety.safety_guard import (
    build_safety_notice,
    should_limit_strategy_suggestions,
)
from storage.strategy_feedback import (
    StoredStrategyFeedback,
    feedback_label,
    get_strategy_search,
    list_strategy_feedback,
    normalise_feedback_rating,
    save_strategy_feedback,
    save_strategy_search,
)


# This user-facing message is returned when safety screening prevents
# ordinary strategy retrieval from continuing.
SAFETY_LIMIT_MESSAGE = (
    "What you described may involve an immediate safety or injury "
    "concern. Joey will not provide ordinary strategy suggestions for "
    "that situation. Please make sure the child is safe and seek "
    "appropriate urgent or professional support."
)


# Workflow-specific exceptions let API adapters distinguish missing
# searches from invalid feedback operations.
class StrategySearchNotFoundError(LookupError):
    """Raised when an accepted strategy-search ID does not exist."""


class StrategyFeedbackStateError(RuntimeError):
    """Raised when feedback conflicts with the stored search state."""


# The protocol keeps this workflow independent of one concrete retriever,
# which also makes deterministic testing with mock services easier.
class StrategyRetrievalService(Protocol):
    """Small protocol used by the API and deterministic tests."""

    def retrieve(
        self,
        question: str,
        top_k: int = 3,
        candidate_pool: int = 6,
    ) -> Any:
        """Return history-aware, source-backed strategy evidence."""
        ...


# Immutable snapshots expose retrieval evidence without leaking the
# implementation-specific result objects returned by the RAG layer.
@dataclass(frozen=True)
class StrategyEvidenceSnapshot:
    """Framework-neutral copy of one history-aware evidence result."""

    rank: int
    original_rank: int
    original_score: float
    history_adjustment: float
    personalised_score: float
    strategy_code: str | None
    strategy_title: str | None
    collection_title: str
    source_file: str
    theme: str | None
    chunk_id: str
    passage: str
    lifecycle_status: str
    latest_outcome: str
    times_used: int
    history_note: str


@dataclass(frozen=True)
class StrategySearchWorkflowResult:
    """Complete result of one strategy-search request."""

    outcome: str
    search_id: int | None
    question: str
    retrieval_query: str | None
    message: str
    safety_notice: str | None
    confidence: RetrievalConfidenceDecision | None
    context: ContextSelection | None
    evidence: tuple[StrategyEvidenceSnapshot, ...]
    created_at: str | None = None
    feedback: tuple[StoredStrategyFeedback, ...] = ()

    @property
    def can_submit_feedback(self) -> bool:
        """Return whether the result has persisted strategies to rate."""

        # Feedback is allowed only for persisted searches that actually returned
        # accepted evidence to the user.
        return (
            self.outcome == "results"
            and self.search_id is not None
            and bool(self.evidence)
        )


@dataclass(frozen=True)
class StrategyFeedbackWorkflowResult:
    """One stored strategy-feedback result."""

    feedback: StoredStrategyFeedback
    message: str


def build_strategy_retrieval_service(
    database_path: str | Path | None = None,
) -> StrategyRetrievalService:
    """Build a real retrieval service bound to the configured database."""

    # Import the embedding/history stack only when a real search is requested;
# this avoids unnecessary model initialisation during API setup and tests.
    # These imports are deliberately lazy so API foundation and mocked
    # tests do not initialise the embedding stack until a real search is
    # requested.
    from rag.history_aware_strategy_service import (
        HistoryAwareStrategyService,
    )
    from storage.feedback_history_provider import (
        load_stored_feedback_history,
    )

    # Preserve the caller-provided database location so retrieval history
    # and feedback are loaded from the same local store as the workflow.
    path = (
        Path(database_path)
        if database_path is not None
        else None
    )

    return HistoryAwareStrategyService(
        stored_history_loader=lambda: load_stored_feedback_history(
            database_path=path
        )
    )


def _clean_text(value: str) -> str:
    """Normalise user text without changing its meaning."""

    return " ".join(
        str(value or "").split()
    ).strip()


def _copy_evidence(item: Any) -> StrategyEvidenceSnapshot:
    """Copy one retrieval result into the framework-neutral contract."""

    # getattr() provides safe defaults so mocked or alternate retrieval
    # result objects can still be converted into the workflow contract.
    return StrategyEvidenceSnapshot(
        rank=max(
            int(getattr(item, "rank", 1)),
            1,
        ),
        original_rank=max(
            int(getattr(item, "original_rank", 1)),
            1,
        ),
        original_score=max(
            float(getattr(item, "original_score", 0.0)),
            0.0,
        ),
        history_adjustment=float(
            getattr(item, "history_adjustment", 0.0)
        ),
        personalised_score=float(
            getattr(
                item,
                "personalised_score",
                getattr(item, "original_score", 0.0),
            )
        ),
        strategy_code=(
            str(getattr(item, "strategy_code", "")).strip()
            or None
        ),
        strategy_title=(
            str(getattr(item, "strategy_title", "")).strip()
            or None
        ),
        collection_title=str(
            getattr(item, "collection_title", "")
        ).strip(),
        source_file=str(
            getattr(item, "source_file", "")
        ).strip(),
        theme=(
            str(getattr(item, "theme", "")).strip()
            or None
        ),
        chunk_id=str(
            getattr(item, "chunk_id", "")
        ).strip(),
        passage=str(
            getattr(item, "passage", "")
        ).strip(),
        lifecycle_status=str(
            getattr(item, "lifecycle_status", "not_active")
        ).strip(),
        latest_outcome=str(
            getattr(item, "latest_outcome", "not_recorded")
        ).strip(),
        times_used=max(
            int(getattr(item, "times_used", 0)),
            0,
        ),
        history_note=str(
            getattr(
                item,
                "history_note",
                "Stored accepted strategy evidence.",
            )
        ).strip(),
    )


def _results_message(
    evidence: tuple[StrategyEvidenceSnapshot, ...],
) -> str:
    """Return cautious summary wording for accepted evidence."""

    # The response wording deliberately describes retrieved items as support
    # options rather than diagnoses or medical recommendations.
    count = len(evidence)
    strategy_word = "strategy" if count == 1 else "strategies"

    return (
        f"Joey found {count} source-backed {strategy_word} for parent "
        "or carer review. These are support options, not a diagnosis "
        "or medical recommendation."
    )


def search_strategy_workflow(
    question: str,
    *,
    top_k: int = 3,
    database_path: str | Path | None = None,
    retrieval_service: StrategyRetrievalService | None = None,
) -> StrategySearchWorkflowResult:
    """Run safety, retrieval, confidence and accepted-search storage."""

    # Normalise the parent/carer query before safety screening, retrieval,
    # confidence assessment, and persistence.
    clean_question = _clean_text(
        question
    )

    if not clean_question:
        raise ValueError(
            "The strategy question cannot be empty."
        )

    if top_k < 1 or top_k > 5:
        raise ValueError(
            "top_k must be between 1 and 5."
        )

    # Reuse the deterministic extractor as a lightweight safety screen before
    # any ordinary strategy suggestions are retrieved.
    screening_record = extract_structured_record(
        clean_question
    )
    safety_notice = build_safety_notice(
        screening_record
    )

    # Safety-limited queries stop here: no retrieval is run and no search
    # result is persisted for strategy feedback.
    if should_limit_strategy_suggestions(
        screening_record
    ):
        return StrategySearchWorkflowResult(
            outcome="safety_limited",
            search_id=None,
            question=clean_question,
            retrieval_query=None,
            message=SAFETY_LIMIT_MESSAGE,
            safety_notice=safety_notice,
            confidence=None,
            context=None,
            evidence=(),
        )

    # A caller-supplied retrieval service is used in tests; otherwise build
    # the real history-aware local retrieval service.
    service = (
        retrieval_service
        if retrieval_service is not None
        else build_strategy_retrieval_service(
            database_path
        )
    )

    # Search a larger candidate pool than top_k so history-aware ranking has
    # enough alternatives before the final displayed results are selected.
    retrieval = service.retrieve(
        question=clean_question,
        top_k=top_k,
        candidate_pool=max(
            6,
            top_k * 2,
        ),
    )
    # Convert implementation-specific evidence items into immutable,
    # framework-neutral snapshots before confidence evaluation or storage.
    evidence = tuple(
        _copy_evidence(item)
        for item in list(
            getattr(retrieval, "evidence", [])
        )
    )

    # Confidence is assessed after retrieval and can force abstention even
    # when the retriever has produced ranked evidence.
    confidence = assess_retrieval_confidence(
        question=clean_question,
        evidence=evidence,
    )

    retrieval_query = str(
        getattr(retrieval, "retrieval_query", clean_question)
    ).strip()
    context = getattr(
        retrieval,
        "context",
        None,
    )

    # Abstained searches return no strategy evidence to the user and are not
    # stored as accepted searches for later feedback.
    if confidence.should_abstain:
        return StrategySearchWorkflowResult(
            outcome="abstained",
            search_id=None,
            question=clean_question,
            retrieval_query=retrieval_query,
            message=build_abstention_message(),
            safety_notice=safety_notice,
            confidence=confidence,
            context=context,
            evidence=(),
        )

    # Only accepted, non-abstained searches are persisted so later feedback
    # is tied to evidence that was actually shown to the user.
    search_id = save_strategy_search(
        question=clean_question,
        retrieval_query=retrieval_query,
        evidence=evidence,
        confidence_level=confidence.level.value,
        source="fastapi_strategy_workflow",
        database_path=database_path,
    )

    return StrategySearchWorkflowResult(
        outcome="results",
        search_id=search_id,
        question=clean_question,
        retrieval_query=retrieval_query,
        message=_results_message(
            evidence
        ),
        safety_notice=safety_notice,
        confidence=confidence,
        context=context,
        evidence=evidence,
    )


def _stored_evidence(
    stored: dict[str, Any],
) -> tuple[StrategyEvidenceSnapshot, ...]:
    """Reconstruct API-safe evidence from the accepted-search snapshot."""

    rows = stored.get(
        "evidence",
        [],
    )
    snapshot_rows = stored.get(
        "evidence_snapshot",
        [],
    )
    # Snapshot rows contain history/lifecycle fields that are joined back to
    # the stored evidence by display rank when a search is reloaded.
    snapshot_by_rank = {
        int(item.get("display_rank", 0)): item
        for item in snapshot_rows
        if isinstance(item, dict)
    }

    evidence: list[StrategyEvidenceSnapshot] = []

    for row in rows:
        rank = int(
            row["display_rank"]
        )
        snapshot = snapshot_by_rank.get(
            rank,
            {},
        )

        evidence.append(
            StrategyEvidenceSnapshot(
                rank=rank,
                original_rank=int(
                    row["original_rank"]
                ),
                original_score=float(
                    row["original_score"]
                ),
                history_adjustment=float(
                    row["history_adjustment"]
                ),
                personalised_score=float(
                    row["personalised_score"]
                ),
                strategy_code=row.get(
                    "strategy_code"
                ),
                strategy_title=row.get(
                    "strategy_title"
                ),
                collection_title=str(
                    row["collection_title"]
                ),
                source_file=str(
                    row["source_file"]
                ),
                theme=row.get(
                    "theme"
                ),
                chunk_id=str(
                    row["chunk_id"]
                ),
                passage=str(
                    row["passage"]
                ),
                lifecycle_status=str(
                    snapshot.get(
                        "lifecycle_status",
                        "not_active",
                    )
                ),
                latest_outcome=str(
                    snapshot.get(
                        "latest_outcome",
                        "not_recorded",
                    )
                ),
                times_used=max(
                    int(
                        snapshot.get(
                            "times_used",
                            0,
                        )
                    ),
                    0,
                ),
                history_note=str(
                    snapshot.get(
                        "history_note",
                        "Stored accepted strategy evidence.",
                    )
                ),
            )
        )

    return tuple(
        evidence
    )


def _feedback_for_search(
    search_id: int,
    database_path: str | Path | None,
) -> tuple[StoredStrategyFeedback, ...]:
    """Return feedback belonging only to the requested accepted search."""

    # Feedback is filtered by search ID so callers receive only ratings for
    # the requested accepted search.
    return tuple(
        item
        for item in list_strategy_feedback(
            limit=10_000,
            database_path=database_path,
        )
        if item.search_id == search_id
    )


def get_strategy_search_workflow(
    search_id: int,
    *,
    database_path: str | Path | None = None,
) -> StrategySearchWorkflowResult:
    """Return one persisted accepted search and any submitted feedback."""

    if search_id < 1:
        raise ValueError(
            "search_id must be at least 1."
        )

    # Accepted searches are reloaded from local storage before being exposed
    # through the workflow result.
    stored = get_strategy_search(
        search_id,
        database_path=database_path,
    )

    if stored is None:
        raise StrategySearchNotFoundError(
            "The requested strategy search was not found."
        )

    evidence = _stored_evidence(
        stored
    )

    return StrategySearchWorkflowResult(
        outcome="results",
        search_id=search_id,
        question=str(
            stored["question"]
        ),
        retrieval_query=str(
            stored["retrieval_query"]
        ),
        message=_results_message(
            evidence
        ),
        safety_notice=None,
        confidence=None,
        context=None,
        evidence=evidence,
        created_at=str(
            stored["created_at"]
        ),
        feedback=_feedback_for_search(
            search_id,
            database_path,
        ),
    )


def submit_strategy_feedback_workflow(
    search_id: int,
    strategy_rank: int,
    rating: str,
    *,
    comment: str | None = None,
    database_path: str | Path | None = None,
) -> StrategyFeedbackWorkflowResult:
    """Validate and upsert feedback for one displayed strategy."""

    stored = get_strategy_search(
        search_id,
        database_path=database_path,
    )

    if stored is None:
        raise StrategySearchNotFoundError(
            "The requested strategy search was not found."
        )

    # Validate/normalise the rating first, then upsert feedback against the
    # displayed strategy rank from the stored search.
    try:
        normalised_rating = normalise_feedback_rating(
            rating
        )
        feedback_id = save_strategy_feedback(
            search_id=search_id,
            strategy_rank=strategy_rank,
            rating=normalised_rating,
            comment=comment,
            database_path=database_path,
        )
    except ValueError as error:
        raise StrategyFeedbackStateError(
            str(error)
        ) from error

    # Reload the stored feedback after saving so the workflow returns the
    # canonical persisted record, including its generated ID and metadata.
    matching = next(
        (
            item
            for item in _feedback_for_search(
                search_id,
                database_path,
            )
            if item.id == feedback_id
        ),
        None,
    )

    if matching is None:
        raise RuntimeError(
            "The stored strategy feedback could not be retrieved."
        )

    return StrategyFeedbackWorkflowResult(
        feedback=matching,
        message=(
            "Feedback recorded for strategy "
            f"{strategy_rank} as {feedback_label(normalised_rating)}."
        ),
    )

