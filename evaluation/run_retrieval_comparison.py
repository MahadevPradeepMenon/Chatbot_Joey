import csv
import json
import re
import time
from pathlib import Path
from statistics import mean
from typing import Any

from app.extractor import extract_structured_record
from rag.hybrid_retriever import (
    HybridSearchResult,
    HybridStrategyRetriever,
)
from rag.joey_strategy_service import build_retrieval_query
from rag.semantic_retriever import SemanticSearchResult
from rag.strategy_retriever import retrieve_strategies


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASES_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "retrieval_comparison_cases.json"
)

RESULTS_JSON = (
    PROJECT_ROOT
    / "evaluation"
    / "retrieval_comparison_results.json"
)

RESULTS_CSV = (
    PROJECT_ROOT
    / "evaluation"
    / "retrieval_comparison_results.csv"
)

TOP_K = 3


def normalise_text(value: Any) -> str:
    """Convert values into comparable lowercase text."""

    if value is None:
        return ""

    if isinstance(value, dict):
        combined = " ".join(
            normalise_text(item)
            for item in value.values()
        )
        return normalise_text(combined)

    if isinstance(value, (list, tuple, set)):
        combined = " ".join(
            normalise_text(item)
            for item in value
        )
        return normalise_text(combined)

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value).lower(),
    ).strip()


def load_cases() -> list[dict[str, Any]]:
    """Load and validate the shared retrieval cases."""

    if not CASES_FILE.exists():
        raise FileNotFoundError(
            f"Comparison cases not found: {CASES_FILE}"
        )

    cases = json.loads(
        CASES_FILE.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(cases, list) or not cases:
        raise ValueError(
            "The comparison file must contain a non-empty list."
        )

    required_fields = {
        "case_id",
        "query",
        "expected_keywords",
    }

    for index, case in enumerate(
        cases,
        start=1,
    ):
        if not isinstance(case, dict):
            raise ValueError(
                f"Case {index} must be a JSON object."
            )

        missing = required_fields.difference(
            case
        )

        if missing:
            raise ValueError(
                f"Case {index} is missing: "
                f"{', '.join(sorted(missing))}"
            )

        if not isinstance(
            case["expected_keywords"],
            list,
        ) or not case["expected_keywords"]:
            raise ValueError(
                f"Case {index} needs at least one "
                "expected keyword."
            )

    return cases


def baseline_descriptor(
    result: Any,
) -> str:
    """
    Create comparison text from one rule-based result.

    Metadata fields are preferred so relevance does not depend only
    on words occurring inside a long strategy description.
    """

    if not isinstance(result, dict):
        return normalise_text(result)

    preferred_fields = [
        "title",
        "name",
        "category",
        "strategy_category",
        "collection_title",
        "source",
        "source_file",
    ]

    selected_values = [
        result.get(field)
        for field in preferred_fields
        if result.get(field)
    ]

    if selected_values:
        return normalise_text(
            selected_values
        )

    return normalise_text(result)


def baseline_label(
    result: Any,
) -> str:
    """Create a readable label for one rule-based result."""

    if isinstance(result, dict):
        preferred_fields = [
            "title",
            "name",
            "category",
            "strategy_category",
        ]

        for field in preferred_fields:
            value = result.get(field)

            if value:
                return str(value)

    return str(result)


def vector_descriptor(
    result: SemanticSearchResult | HybridSearchResult,
) -> str:
    """Create comparison text from retriever metadata."""

    return normalise_text(
        [
            result.strategy_code,
            result.strategy_title,
            result.collection_title,
            result.theme,
            result.source_file,
        ]
    )


def vector_label(
    result: SemanticSearchResult | HybridSearchResult,
) -> str:
    """Create a readable label for semantic or hybrid results."""

    if result.strategy_code and result.strategy_title:
        return (
            f"{result.strategy_code}: "
            f"{result.strategy_title}"
        )

    return (
        result.strategy_title
        or result.collection_title
        or "Unnamed strategy"
    )


def first_relevant_rank(
    descriptors: list[str],
    expected_keywords: list[str],
) -> int | None:
    """Return the first rank containing an expected keyword."""

    normalised_keywords = [
        normalise_text(keyword)
        for keyword in expected_keywords
        if normalise_text(keyword)
    ]

    for rank, descriptor in enumerate(
        descriptors,
        start=1,
    ):
        if any(
            keyword in descriptor
            for keyword in normalised_keywords
        ):
            return rank

    return None


def evaluate_case(
    case: dict[str, Any],
    hybrid_retriever: HybridStrategyRetriever,
) -> dict[str, Any]:
    """Evaluate all three retrieval methods for one shared query."""

    case_id = str(case["case_id"])
    query = str(case["query"])

    expected_keywords = [
        str(keyword)
        for keyword in case["expected_keywords"]
    ]

    record = extract_structured_record(
        query
    )

    retrieval_query = build_retrieval_query(
        record,
        original_note=query,
    )

    baseline_error: str | None = None
    semantic_error: str | None = None
    hybrid_error: str | None = None

    baseline_started = time.perf_counter()

    try:
        baseline_results = list(
            retrieve_strategies(
                record,
                original_note=query,
            )
        )[:TOP_K]
    except Exception as error:
        baseline_results = []
        baseline_error = str(error)

    baseline_seconds = (
        time.perf_counter()
        - baseline_started
    )

    semantic_started = time.perf_counter()

    try:
        # Use the semantic retriever directly. JoeyStrategyService is
        # intentionally not used here because it now uses Hybrid RAG.
        semantic_results = (
            hybrid_retriever.semantic.search(
                query=retrieval_query,
                top_k=TOP_K,
                strategy_only=True,
                deduplicate_strategies=True,
            )
        )
    except Exception as error:
        semantic_results = []
        semantic_error = str(error)

    semantic_seconds = (
        time.perf_counter()
        - semantic_started
    )

    hybrid_started = time.perf_counter()

    try:
        hybrid_results = hybrid_retriever.search(
            query=retrieval_query,
            top_k=TOP_K,
            strategy_only=True,
        )
    except Exception as error:
        hybrid_results = []
        hybrid_error = str(error)

    hybrid_seconds = (
        time.perf_counter()
        - hybrid_started
    )

    baseline_descriptors = [
        baseline_descriptor(result)
        for result in baseline_results
    ]

    semantic_descriptors = [
        vector_descriptor(result)
        for result in semantic_results
    ]

    hybrid_descriptors = [
        vector_descriptor(result)
        for result in hybrid_results
    ]

    baseline_rank = first_relevant_rank(
        baseline_descriptors,
        expected_keywords,
    )

    semantic_rank = first_relevant_rank(
        semantic_descriptors,
        expected_keywords,
    )

    hybrid_rank = first_relevant_rank(
        hybrid_descriptors,
        expected_keywords,
    )

    return {
        "case_id": case_id,
        "query": query,
        "retrieval_query": retrieval_query,
        "expected_keywords": expected_keywords,
        "baseline_first_relevant_rank": baseline_rank,
        "semantic_first_relevant_rank": semantic_rank,
        "hybrid_first_relevant_rank": hybrid_rank,
        "baseline_hit_at_1": baseline_rank == 1,
        "semantic_hit_at_1": semantic_rank == 1,
        "hybrid_hit_at_1": hybrid_rank == 1,
        "baseline_hit_at_3": (
            baseline_rank is not None
            and baseline_rank <= TOP_K
        ),
        "semantic_hit_at_3": (
            semantic_rank is not None
            and semantic_rank <= TOP_K
        ),
        "hybrid_hit_at_3": (
            hybrid_rank is not None
            and hybrid_rank <= TOP_K
        ),
        "baseline_latency_seconds": round(
            baseline_seconds,
            6,
        ),
        "semantic_latency_seconds": round(
            semantic_seconds,
            6,
        ),
        "hybrid_latency_seconds": round(
            hybrid_seconds,
            6,
        ),
        "baseline_result_count": len(
            baseline_results
        ),
        "semantic_result_count": len(
            semantic_results
        ),
        "hybrid_result_count": len(
            hybrid_results
        ),
        "baseline_titles": [
            baseline_label(result)
            for result in baseline_results
        ],
        "semantic_titles": [
            vector_label(result)
            for result in semantic_results
        ],
        "hybrid_titles": [
            vector_label(result)
            for result in hybrid_results
        ],
        "semantic_sources": [
            result.source_file
            for result in semantic_results
        ],
        "hybrid_sources": [
            result.source_file
            for result in hybrid_results
        ],
        "baseline_error": baseline_error,
        "semantic_error": semantic_error,
        "hybrid_error": hybrid_error,
    }


def summarise_method(
    results: list[dict[str, Any]],
    prefix: str,
) -> dict[str, Any]:
    """Calculate retrieval metrics for one method."""

    ranks = [
        result[f"{prefix}_first_relevant_rank"]
        for result in results
    ]

    latencies = [
        float(
            result[f"{prefix}_latency_seconds"]
        )
        for result in results
    ]

    result_counts = [
        int(
            result[f"{prefix}_result_count"]
        )
        for result in results
    ]

    hit_at_1 = sum(
        rank == 1
        for rank in ranks
    )

    hit_at_3 = sum(
        rank is not None and rank <= TOP_K
        for rank in ranks
    )

    reciprocal_ranks = [
        (1.0 / rank)
        if rank is not None
        else 0.0
        for rank in ranks
    ]

    return {
        "query_count": len(results),
        "hit_at_1": hit_at_1,
        "hit_at_1_rate": round(
            hit_at_1 / len(results),
            4,
        ),
        "hit_at_3": hit_at_3,
        "hit_at_3_rate": round(
            hit_at_3 / len(results),
            4,
        ),
        "mean_reciprocal_rank": round(
            mean(reciprocal_ranks),
            4,
        ),
        "average_latency_seconds": round(
            mean(latencies),
            6,
        ),
        "average_results_returned": round(
            mean(result_counts),
            2,
        ),
        "errors": sum(
            bool(result[f"{prefix}_error"])
            for result in results
        ),
    }


def save_results(
    results: list[dict[str, Any]],
    summaries: dict[str, dict[str, Any]],
) -> None:
    """Save detailed and summary results as JSON and CSV."""

    payload = {
        "evaluation_name": (
            "Hey Joey rule-based versus semantic versus "
            "hybrid retrieval comparison"
        ),
        "top_k": TOP_K,
        "case_count": len(results),
        "method_notes": {
            "baseline": (
                "Local deterministic rule-based strategy retrieval."
            ),
            "semantic": (
                "Local sentence-embedding retrieval only."
            ),
            "hybrid": (
                "Local semantic and BM25 retrieval combined "
                "with Reciprocal Rank Fusion."
            ),
        },
        "summaries": summaries,
        # Preserve convenient top-level names for report scripts.
        "baseline_summary": summaries["baseline"],
        "semantic_summary": summaries["semantic"],
        "hybrid_summary": summaries["hybrid"],
        "results": results,
    }

    RESULTS_JSON.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    csv_rows: list[dict[str, Any]] = []

    for result in results:
        csv_rows.append(
            {
                "case_id": result["case_id"],
                "query": result["query"],
                "retrieval_query": result[
                    "retrieval_query"
                ],
                "expected_keywords": " | ".join(
                    result["expected_keywords"]
                ),
                "baseline_first_relevant_rank": result[
                    "baseline_first_relevant_rank"
                ],
                "semantic_first_relevant_rank": result[
                    "semantic_first_relevant_rank"
                ],
                "hybrid_first_relevant_rank": result[
                    "hybrid_first_relevant_rank"
                ],
                "baseline_hit_at_1": result[
                    "baseline_hit_at_1"
                ],
                "semantic_hit_at_1": result[
                    "semantic_hit_at_1"
                ],
                "hybrid_hit_at_1": result[
                    "hybrid_hit_at_1"
                ],
                "baseline_hit_at_3": result[
                    "baseline_hit_at_3"
                ],
                "semantic_hit_at_3": result[
                    "semantic_hit_at_3"
                ],
                "hybrid_hit_at_3": result[
                    "hybrid_hit_at_3"
                ],
                "baseline_latency_seconds": result[
                    "baseline_latency_seconds"
                ],
                "semantic_latency_seconds": result[
                    "semantic_latency_seconds"
                ],
                "hybrid_latency_seconds": result[
                    "hybrid_latency_seconds"
                ],
                "baseline_titles": " | ".join(
                    result["baseline_titles"]
                ),
                "semantic_titles": " | ".join(
                    result["semantic_titles"]
                ),
                "hybrid_titles": " | ".join(
                    result["hybrid_titles"]
                ),
                "semantic_sources": " | ".join(
                    result["semantic_sources"]
                ),
                "hybrid_sources": " | ".join(
                    result["hybrid_sources"]
                ),
                "baseline_error": (
                    result["baseline_error"]
                    or ""
                ),
                "semantic_error": (
                    result["semantic_error"]
                    or ""
                ),
                "hybrid_error": (
                    result["hybrid_error"]
                    or ""
                ),
            }
        )

    with RESULTS_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(
                csv_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            csv_rows
        )


def format_rank(
    rank: int | None,
) -> str:
    """Return a readable rank value."""

    return (
        str(rank)
        if rank is not None
        else "Not found"
    )


def print_summary(
    results: list[dict[str, Any]],
    summaries: dict[str, dict[str, Any]],
) -> None:
    """Print per-case ranks and a compact comparison table."""

    print("\nRETRIEVAL COMPARISON RESULTS")
    print("=" * 78)

    for result in results:
        print(
            f"\n{result['case_id']}"
        )
        print(
            "  Rule-based first relevant rank: "
            f"{format_rank(result['baseline_first_relevant_rank'])}"
        )
        print(
            "  Semantic first relevant rank:   "
            f"{format_rank(result['semantic_first_relevant_rank'])}"
        )
        print(
            "  Hybrid first relevant rank:     "
            f"{format_rank(result['hybrid_first_relevant_rank'])}"
        )

    print("\n" + "-" * 78)
    print(
        f"{'Retriever':<16}"
        f"{'Hit@1':<12}"
        f"{'Hit@3':<12}"
        f"{'MRR':<12}"
        f"{'Avg latency':<16}"
        f"{'Errors':<8}"
    )
    print("-" * 78)

    labels = {
        "baseline": "Rule-based",
        "semantic": "Semantic",
        "hybrid": "Hybrid",
    }

    for key in (
        "baseline",
        "semantic",
        "hybrid",
    ):
        summary = summaries[key]
        hit_at_1 = (
            f"{summary['hit_at_1']}/"
            f"{summary['query_count']}"
        )
        hit_at_3 = (
            f"{summary['hit_at_3']}/"
            f"{summary['query_count']}"
        )
        latency = (
            f"{summary['average_latency_seconds']:.6f}s"
        )

        print(
            f"{labels[key]:<16}"
            f"{hit_at_1:<12}"
            f"{hit_at_3:<12}"
            f"{summary['mean_reciprocal_rank']:<12.4f}"
            f"{latency:<16}"
            f"{summary['errors']:<8}"
        )

    print(f"\nJSON results: {RESULTS_JSON}")
    print(f"CSV results:  {RESULTS_CSV}")


def main() -> None:
    """Run the three-way retrieval comparison."""

    cases = load_cases()

    print(
        "Loading the local semantic and BM25 retrievers..."
    )

    hybrid_retriever = HybridStrategyRetriever()

    print(
        "Warming up the local retrieval components..."
    )

    hybrid_retriever.semantic.search(
        query="general child support needs",
        top_k=1,
        strategy_only=True,
        deduplicate_strategies=True,
    )

    hybrid_retriever.lexical.search(
        query="general child support needs",
        top_k=1,
        strategy_only=True,
        deduplicate_strategies=True,
    )

    results = [
        evaluate_case(
            case,
            hybrid_retriever,
        )
        for case in cases
    ]

    summaries = {
        "baseline": summarise_method(
            results,
            "baseline",
        ),
        "semantic": summarise_method(
            results,
            "semantic",
        ),
        "hybrid": summarise_method(
            results,
            "hybrid",
        ),
    }

    save_results(
        results,
        summaries,
    )

    print_summary(
        results,
        summaries,
    )


if __name__ == "__main__":
    main()
