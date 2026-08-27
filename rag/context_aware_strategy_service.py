from __future__ import annotations

from dataclasses import dataclass

from app.context_builder import ContextSelection, SyntheticContextBuilder
from rag.hybrid_retriever import HybridSearchResult, HybridStrategyRetriever
from rag.joey_strategy_service import JoeyStrategyEvidence

# Bundle the original question, selected context, final retrieval query and
# returned evidence into one immutable result for downstream inspection.
@dataclass(frozen=True)
class ContextAwareRetrieval:
    question: str
    context: ContextSelection
    retrieval_query: str
    evidence: list[JoeyStrategyEvidence]


# Keep query construction explicit so the current question and selected confirmed
# context remain clearly separated in the text sent to hybrid retrieval.
def build_context_aware_query(question: str, context: ContextSelection) -> str:
    # Label both sections in plain text so the retrieval query is human-readable
    # and preserves the distinction between current need and prior context.
    return (
        'Current parent/carer strategy question:\n'
        f'{question}\n\n'
        'Relevant confirmed Hey Joey context:\n'
        f'{context.context_text}'
    )


# This service composes context selection with the existing local hybrid retriever
# without changing either component's internal logic.
class ContextAwareStrategyService:
    # Optional dependency injection supports testing while defaulting to the project
    # context builder and hybrid retriever in normal use.
    def __init__(self, context_builder: SyntheticContextBuilder | None = None, retriever: HybridStrategyRetriever | None = None) -> None:
        # Reuse supplied components when present; otherwise construct local defaults.
        self.context_builder = context_builder or SyntheticContextBuilder()
        self.retriever = retriever or HybridStrategyRetriever()

    # Execute the full context-aware retrieval flow: select context, build a combined
    # query, run strategy-only hybrid search, then convert results to Joey evidence.
    def retrieve(self, question: str, top_k: int = 3) -> ContextAwareRetrieval:
        # Select only the context considered relevant to the current question.
        context = self.context_builder.build(question)
        retrieval_query = build_context_aware_query(question, context)
        # Restrict hybrid retrieval to strategy chunks so contextual source sections
        # are not returned as user-facing strategy evidence.
        results = self.retriever.search(query=retrieval_query, top_k=top_k, strategy_only=True)
        evidence = self._convert_results(results)
        # Return both the retrieval evidence and the intermediate context/query so the
        # decision path remains transparent to callers and tests.
        return ContextAwareRetrieval(question, context, retrieval_query, evidence)

    @staticmethod
    # Convert hybrid-specific results into the smaller evidence contract shared by
    # Joey application services while preserving source and passage provenance.
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
