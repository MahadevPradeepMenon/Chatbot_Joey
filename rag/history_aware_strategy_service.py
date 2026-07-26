from __future__ import annotations

from dataclasses import dataclass

from app.context_builder import ContextSelection
from rag.context_aware_strategy_service import (
    ContextAwareRetrieval,
    ContextAwareStrategyService,
)
from rag.strategy_history_ranker import (
    HistoryAwareStrategyEvidence,
    StrategyHistoryRanker,
)


@dataclass(frozen=True)
class HistoryAwareRetrieval:
    """Context-aware retrieval with transparent history adjustments."""

    question: str
    context: ContextSelection
    retrieval_query: str
    evidence: list[HistoryAwareStrategyEvidence]


class HistoryAwareStrategyService:
    """
    Add active-strategy and feedback history to context-aware Hybrid RAG.
    """

    def __init__(
        self,
        base_service: ContextAwareStrategyService | None = None,
        history_ranker: StrategyHistoryRanker | None = None,
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

    def retrieve(
        self,
        question: str,
        top_k: int = 3,
        candidate_pool: int = 6,
    ) -> HistoryAwareRetrieval:
        """
        Retrieve a slightly larger relevant pool, then apply history signals.
        """

        pool_size = max(candidate_pool, top_k)

        base_result: ContextAwareRetrieval = (
            self.base_service.retrieve(
                question=question,
                top_k=pool_size,
            )
        )

        reranked = self.history_ranker.rerank(
            base_result.evidence
        )

        return HistoryAwareRetrieval(
            question=base_result.question,
            context=base_result.context,
            retrieval_query=base_result.retrieval_query,
            evidence=reranked[:top_k],
        )
