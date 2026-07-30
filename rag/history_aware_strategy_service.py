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


StoredHistoryLoader = Callable[
    [],
    list[StrategyHistoryRecord],
]


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

        self.base_history_records = list(
            self.history_ranker.history_records
        )

        if stored_history_loader is not None:
            self.stored_history_loader = (
                stored_history_loader
            )
        elif (
            use_stored_feedback
            and history_ranker is None
        ):
            self.stored_history_loader = (
                load_stored_feedback_history
            )
        else:
            # Injected rankers remain deterministic unless a loader is
            # explicitly supplied by the caller.
            self.stored_history_loader = (
                lambda: []
            )

    def _current_ranker(
        self,
    ) -> StrategyHistoryRanker:
        """Build a ranker from base history plus current SQLite feedback."""

        stored_history = (
            self.stored_history_loader()
        )

        combined_history = (
            merge_strategy_history(
                self.base_history_records,
                stored_history,
            )
        )

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

        pool_size = max(
            candidate_pool,
            top_k,
        )

        base_result: ContextAwareRetrieval = (
            self.base_service.retrieve(
                question=question,
                top_k=pool_size,
            )
        )

        reranked = (
            self._current_ranker().rerank(
                base_result.evidence
            )
        )

        return HistoryAwareRetrieval(
            question=base_result.question,
            context=base_result.context,
            retrieval_query=(
                base_result.retrieval_query
            ),
            evidence=reranked[:top_k],
        )
