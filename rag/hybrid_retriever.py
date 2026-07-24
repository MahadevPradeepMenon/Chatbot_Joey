from dataclasses import asdict, dataclass
from typing import Any

from rag.bm25_retriever import (
    BM25SearchResult,
    BM25StrategyRetriever,
)
from rag.semantic_retriever import (
    SemanticSearchResult,
    SemanticStrategyRetriever,
)


DEFAULT_TOP_K = 5
DEFAULT_CANDIDATE_POOL = 30
DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class HybridSearchResult:
    """One strategy produced by semantic + BM25 rank fusion."""

    rank: int
    score: float
    semantic_rank: int | None
    lexical_rank: int | None
    semantic_score: float | None
    lexical_score: float | None
    chunk_id: str
    source_file: str
    collection_title: str
    theme: str | None
    strategy_code: str | None
    strategy_title: str | None
    section_type: str
    section_title: str
    chunk_part: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def result_identity(
    source_file: str,
    strategy_code: str | None,
    strategy_title: str | None,
    chunk_id: str,
) -> tuple[str, str, str]:
    """Return a stable strategy identity for fusion."""

    code = str(strategy_code or "")
    title = str(strategy_title or "")

    if code or title:
        return source_file, code, title

    return source_file, "", chunk_id


class HybridStrategyRetriever:
    """
    Combine semantic and BM25 rankings with Reciprocal Rank Fusion.
    """

    def __init__(
        self,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1.")

        self.semantic = SemanticStrategyRetriever()
        self.lexical = BM25StrategyRetriever()
        self.rrf_k = rrf_k

    @staticmethod
    def _semantic_identity(
        result: SemanticSearchResult,
    ) -> tuple[str, str, str]:
        return result_identity(
            source_file=result.source_file,
            strategy_code=result.strategy_code,
            strategy_title=result.strategy_title,
            chunk_id=result.chunk_id,
        )

    @staticmethod
    def _lexical_identity(
        result: BM25SearchResult,
    ) -> tuple[str, str, str]:
        return result_identity(
            source_file=result.source_file,
            strategy_code=result.strategy_code,
            strategy_title=result.strategy_title,
            chunk_id=result.chunk_id,
        )

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        strategy_only: bool = True,
        candidate_pool: int = DEFAULT_CANDIDATE_POOL,
    ) -> list[HybridSearchResult]:
        """Return final hybrid strategy results."""

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        pool_size = max(candidate_pool, top_k * 5)

        semantic_results = self.semantic.search(
            query=query,
            top_k=pool_size,
            strategy_only=strategy_only,
            deduplicate_strategies=True,
        )

        lexical_results = self.lexical.search(
            query=query,
            top_k=pool_size,
            strategy_only=strategy_only,
            deduplicate_strategies=True,
        )

        fused: dict[
            tuple[str, str, str],
            dict[str, Any],
        ] = {}

        for result in semantic_results:
            identity = self._semantic_identity(result)

            fused.setdefault(
                identity,
                {"semantic": None, "lexical": None},
            )["semantic"] = result

        for result in lexical_results:
            identity = self._lexical_identity(result)

            fused.setdefault(
                identity,
                {"semantic": None, "lexical": None},
            )["lexical"] = result

        ranked_items: list[tuple[float, dict[str, Any]]] = []

        for item in fused.values():
            semantic_result = item["semantic"]
            lexical_result = item["lexical"]
            hybrid_score = 0.0

            if semantic_result is not None:
                hybrid_score += (
                    1.0
                    / (self.rrf_k + semantic_result.rank)
                )

            if lexical_result is not None:
                hybrid_score += (
                    1.0
                    / (self.rrf_k + lexical_result.rank)
                )

            ranked_items.append((hybrid_score, item))

        ranked_items.sort(
            key=lambda item: (
                item[0],
                (
                    item[1]["semantic"].score
                    if item[1]["semantic"] is not None
                    else float("-inf")
                ),
                (
                    item[1]["lexical"].score
                    if item[1]["lexical"] is not None
                    else float("-inf")
                ),
            ),
            reverse=True,
        )

        results: list[HybridSearchResult] = []

        for hybrid_score, item in ranked_items[:top_k]:
            semantic_result = item["semantic"]
            lexical_result = item["lexical"]

            representative = (
                semantic_result
                if semantic_result is not None
                else lexical_result
            )

            if representative is None:
                continue

            results.append(
                HybridSearchResult(
                    rank=len(results) + 1,
                    score=float(hybrid_score),
                    semantic_rank=(
                        semantic_result.rank
                        if semantic_result is not None
                        else None
                    ),
                    lexical_rank=(
                        lexical_result.rank
                        if lexical_result is not None
                        else None
                    ),
                    semantic_score=(
                        semantic_result.score
                        if semantic_result is not None
                        else None
                    ),
                    lexical_score=(
                        lexical_result.score
                        if lexical_result is not None
                        else None
                    ),
                    chunk_id=representative.chunk_id,
                    source_file=representative.source_file,
                    collection_title=(
                        representative.collection_title
                    ),
                    theme=representative.theme,
                    strategy_code=(
                        representative.strategy_code
                    ),
                    strategy_title=(
                        representative.strategy_title
                    ),
                    section_type=(
                        representative.section_type
                    ),
                    section_title=(
                        representative.section_title
                    ),
                    chunk_part=representative.chunk_part,
                    text=representative.text,
                )
            )

        return results


def main() -> None:
    """Run a hybrid retrieval smoke test."""

    query = (
        "What can help a child who becomes overwhelmed "
        "by loud classroom noise and covers their ears?"
    )

    retriever = HybridStrategyRetriever()
    results = retriever.search(query=query, top_k=5)

    print("\nHEY JOEY HYBRID RETRIEVAL")
    print("=" * 70)
    print(f"Query: {query}")

    for result in results:
        print("\n" + "-" * 70)
        print(
            f"Rank {result.rank} "
            f"| Hybrid score: {result.score:.6f}"
        )
        print(
            f"Semantic rank: {result.semantic_rank} "
            f"| BM25 rank: {result.lexical_rank}"
        )
        print(
            f"Strategy: {result.strategy_code} - "
            f"{result.strategy_title}"
        )
        print(f"Collection: {result.collection_title}")
        print(f"Source: {result.source_file}")


if __name__ == "__main__":
    main()
