from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.context_builder import ContextSelection
from rag.context_aware_strategy_service import (
    ContextAwareRetrieval,
    ContextAwareStrategyService,
)
from rag.strategy_history_ranker import (
    HistoryAwareStrategyEvidence,
    StrategyHistoryRanker,
    StrategyHistoryRecord,
)
from storage.feedback_history_provider import (
    load_stored_feedback_history,
    merge_strategy_history,
)


# Define the injectable stored-history loader contract so tests can replace
# SQLite-backed feedback loading with a deterministic in-memory function.
StoredHistoryLoader = Callable[
    [],
    list[StrategyHistoryRecord],
]


# Keep the complete history-aware retrieval response immutable while preserving
# the original question, selected context, query and reranked evidence.
@dataclass(frozen=True)
class HistoryAwareRetrieval:
    """Context-aware retrieval with transparent history adjustments."""

    question: str
    context: ContextSelection
    retrieval_query: str
    evidence: list[
        HistoryAwareStrategyEvidence
    ]


class HistoryAwareStrategyService:
    """
    Add active-strategy and stored feedback history to Hybrid RAG.

    Stored feedback is reloaded before every retrieval so a newly saved
    rating can affect the next related strategy search without restarting
    Streamlit.
    """

    def __init__(
        self,
        base_service: ContextAwareStrategyService
        | None = None,
        history_ranker: StrategyHistoryRanker
        | None = None,
        stored_history_loader: StoredHistoryLoader
        | None = None,
        use_stored_feedback: bool = True,
    ) -> None:
        # Use injected components when supplied; otherwise construct the project
        # defaults for context-aware retrieval and history reranking.
        self.base_service = (
            base_service
            if base_service is not None
            else ContextAwareStrategyService()
        )

        self.history_ranker = (
            history_ranker
            if history_ranker is not None
            else StrategyHistoryRanker()
        )

        # Snapshot the ranker's initial history so fresh stored feedback can be
        # merged into the same stable base on every retrieval.
        self.base_history_records = list(
            self.history_ranker.history_records
        )

        # An explicitly supplied loader takes priority, which keeps dependency
        # injection predictable for tests and alternative storage backends.
        if stored_history_loader is not None:
            self.stored_history_loader = (
                stored_history_loader
            )
        # In normal application use, reload current SQLite feedback before each
        # search so newly saved ratings can affect the next related retrieval.
        elif (
            use_stored_feedback
            and history_ranker is None
        ):
            self.stored_history_loader = (
                load_stored_feedback_history
            )
        else:
            # When feedback loading is disabled—or a custom ranker is injected
            # without a loader—use an empty source to avoid hidden state changes.
            # Injected rankers remain deterministic unless a loader is
            # explicitly supplied by the caller.
            self.stored_history_loader = (
                lambda: []
            )

    def _current_ranker(
        self,
    ) -> StrategyHistoryRanker:
        """Build a ranker from base history plus current SQLite feedback."""

        # Load the latest persisted feedback at call time rather than caching it
        # for the lifetime of the service.
        stored_history = (
            self.stored_history_loader()
        )

        # Merge current stored feedback with the initial history snapshot before
        # constructing a fresh ranker for this request.
        combined_history = (
            merge_strategy_history(
                self.base_history_records,
                stored_history,
            )
        )

        # A new ranker ensures the current request uses the just-merged history
        # without mutating the service's original ranker object.
        return StrategyHistoryRanker(
            history_records=(
                combined_history
            )
        )

    def retrieve(
        self,
        question: str,
        top_k: int = 3,
        candidate_pool: int = 6,
    ) -> HistoryAwareRetrieval:
        """Retrieve a relevant pool, then apply current history signals."""

        # Retrieve at least top_k candidates, but normally use a wider pool so
        # history signals have room to reorder otherwise relevant strategies.
        pool_size = max(
            candidate_pool,
            top_k,
        )

        # Run context-aware Hybrid retrieval first; history is applied only after
        # the relevance-based candidate pool has been established.
        base_result: ContextAwareRetrieval = (
            self.base_service.retrieve(
                question=question,
                top_k=pool_size,
            )
        )

        # Apply the latest combined history signals to the relevance-ranked pool.
        reranked = (
            self._current_ranker().rerank(
                base_result.evidence
            )
        )

        # Preserve the base question/context/query and expose only the requested
        # number of history-aware results after reranking.
        return HistoryAwareRetrieval(
            question=base_result.question,
            context=base_result.context,
            retrieval_query=(
                base_result.retrieval_query
            ),
            evidence=reranked[:top_k],
        )
