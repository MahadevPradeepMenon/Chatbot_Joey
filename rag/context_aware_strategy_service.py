from __future__ import annotations

from dataclasses import dataclass

from app.context_builder import ContextSelection, SyntheticContextBuilder
from rag.hybrid_retriever import HybridSearchResult, HybridStrategyRetriever
from rag.joey_strategy_service import JoeyStrategyEvidence

@dataclass(frozen=True)
class ContextAwareRetrieval:
    question: str
    context: ContextSelection
    retrieval_query: str
    evidence: list[JoeyStrategyEvidence]


def build_context_aware_query(question: str, context: ContextSelection) -> str:
    return (
        'Current parent/carer strategy question:\n'
        f'{question}\n\n'
        'Relevant confirmed Hey Joey context:\n'
        f'{context.context_text}'
    )


class ContextAwareStrategyService:
    def __init__(self, context_builder: SyntheticContextBuilder | None = None, retriever: HybridStrategyRetriever | None = None) -> None:
        self.context_builder = context_builder or SyntheticContextBuilder()
        self.retriever = retriever or HybridStrategyRetriever()

    def retrieve(self, question: str, top_k: int = 3) -> ContextAwareRetrieval:
        context = self.context_builder.build(question)
        retrieval_query = build_context_aware_query(question, context)
        results = self.retriever.search(query=retrieval_query, top_k=top_k, strategy_only=True)
        evidence = self._convert_results(results)
        return ContextAwareRetrieval(question, context, retrieval_query, evidence)

    @staticmethod
    def _convert_results(results: list[HybridSearchResult]) -> list[JoeyStrategyEvidence]:
        return [
            JoeyStrategyEvidence(
                rank=result.rank,
                score=result.score,
                strategy_code=result.strategy_code,
                strategy_title=result.strategy_title,
                collection_title=result.collection_title,
                source_file=result.source_file,
                theme=result.theme,
                chunk_id=result.chunk_id,
                passage=result.text,
            )
            for result in results
        ]
