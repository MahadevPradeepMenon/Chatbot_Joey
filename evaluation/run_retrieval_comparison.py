import csv
import json
import re
import time
from pathlib import Path
from statistics import mean
from typing import Any

from app.extractor import extract_structured_record
from rag.joey_strategy_service import (
    JoeyStrategyEvidence,
    JoeyStrategyService,
)
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
    """Load the retrieval comparison cases."""

    if not CASES_FILE.exists():
        raise FileNotFoundError(
            f"Comparison cases not found: {CASES_FILE}"
        )

    cases = json.loads(
        CASES_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(cases, list) or not cases:
        raise ValueError(
            "The comparison file must contain a non-empty list."
        )

    return cases


def baseline_descriptor(
    result: Any,
) -> str:
    """
    Create comparison text from one rule-based result.

    Metadata-style fields are preferred so the comparison does not
    depend only on words appearing inside a long suggestion.
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


def semantic_descriptor(
    result: JoeyStrategyEvidence,
) -> str:
    """Create comparison text from semantic-result metadata."""

    return normalise_text(
        [
            result.strategy_code,
            result.strategy_title,
            result.collection_title,
            result.theme,
            result.source_file,
        ]
    )


def semantic_label(
    result: JoeyStrategyEvidence,
) -> str:
    """Create a readable semantic-result label."""

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
    """Return the rank of the first expected result."""

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
    semantic_service: JoeyStrategyService,
) -> dict[str, Any]:
    """Compare both retrieval methods for one query."""

    case_id = str(case["case_id"])
    query = str(case["query"])

    expected_keywords = [
        str(keyword)
        for keyword in case[
            "expected_keywords"
        ]
    ]

    record = extract_structured_record(
        query
    )

    baseline_error: str | None = None
    semantic_error: str | None = None

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
        semantic_results = (
            semantic_service.retrieve_for_record(
                record,
                original_note=query,
                top_k=TOP_K,
            )
        )
    except Exception as error:
        semantic_results = []
        semantic_error = str(error)

    semantic_seconds = (
        time.perf_counter()
        - semantic_started
    )

    baseline_descriptors = [
        baseline_descriptor(result)
        for result in baseline_results
    ]

    semantic_descriptors = [
        semantic_descriptor(result)
        for result in semantic_results
    ]

    baseline_rank = first_relevant_rank(
        baseline_descriptors,
        expected_keywords,
    )

    semantic_rank = first_relevant_rank(
        semantic_descriptors,
        expected_keywords,
    )

    return {
        "case_id": case_id,
        "query": query,
        "expected_keywords": expected_keywords,
        "baseline_first_relevant_rank": baseline_rank,
        "semantic_first_relevant_rank": semantic_rank,
        "baseline_hit_at_1": baseline_rank == 1,
        "semantic_hit_at_1": semantic_rank == 1,
        "baseline_hit_at_3": (
            baseline_rank is not None
            and baseline_rank <= TOP_K
        ),
        "semantic_hit_at_3": (
            semantic_rank is not None
            and semantic_rank <= TOP_K
        ),
        "baseline_latency_seconds": round(
            baseline_seconds,
            6,
        ),
        "semantic_latency_seconds": round(
            semantic_seconds,
            6,
        ),
        "baseline_result_count": len(
            baseline_results
        ),
        "semantic_result_count": len(
            semantic_results
        ),
        "baseline_titles": [
            baseline_label(result)
            for result in baseline_results
        ],
        "semantic_titles": [
            semantic_label(result)
            for result in semantic_results
        ],
        "semantic_sources": [
            result.source_file
            for result in semantic_results
        ],
        "baseline_error": baseline_error,
        "semantic_error": semantic_error,
    }


def summarise_method(
    results: list[dict[str, Any]],
    prefix: str,
) -> dict[str, Any]:
    """Calculate retrieval metrics for one method."""

    ranks = [
        result[
            f"{prefix}_first_relevant_rank"
        ]
        for result in results
    ]

    latencies = [
        float(
            result[
                f"{prefix}_latency_seconds"
            ]
        )
        for result in results
    ]

    result_counts = [
        int(
            result[
                f"{prefix}_result_count"
            ]
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
    baseline_summary: dict[str, Any],
    semantic_summary: dict[str, Any],
) -> None:
    """Save detailed and summary comparison results."""

    payload = {
        "evaluation_name": (
            "Hey Joey rule-based versus "
            "semantic retrieval comparison"
        ),
        "top_k": TOP_K,
        "baseline_summary": baseline_summary,
        "semantic_summary": semantic_summary,
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
                "expected_keywords": " | ".join(
                    result["expected_keywords"]
                ),
                "baseline_first_relevant_rank": (
                    result[
                        "baseline_first_relevant_rank"
                    ]
                ),
                "semantic_first_relevant_rank": (
                    result[
                        "semantic_first_relevant_rank"
                    ]
                ),
                "baseline_hit_at_1": result[
                    "baseline_hit_at_1"
                ],
                "semantic_hit_at_1": result[
                    "semantic_hit_at_1"
                ],
                "baseline_hit_at_3": result[
                    "baseline_hit_at_3"
                ],
                "semantic_hit_at_3": result[
                    "semantic_hit_at_3"
                ],
                "baseline_latency_seconds": result[
                    "baseline_latency_seconds"
                ],
                "semantic_latency_seconds": result[
                    "semantic_latency_seconds"
                ],
                "baseline_titles": " | ".join(
                    result["baseline_titles"]
                ),
                "semantic_titles": " | ".join(
                    result["semantic_titles"]
                ),
                "semantic_sources": " | ".join(
                    result["semantic_sources"]
                ),
                "baseline_error": (
                    result["baseline_error"]
                    or ""
                ),
                "semantic_error": (
                    result["semantic_error"]
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
        writer.writerows(csv_rows)


def print_summary(
    results: list[dict[str, Any]],
    baseline_summary: dict[str, Any],
    semantic_summary: dict[str, Any],
) -> None:
    """Print the comparison results."""

    print("\nRETRIEVAL COMPARISON RESULTS")
    print("=" * 70)

    for result in results:
        baseline_rank = (
            result[
                "baseline_first_relevant_rank"
            ]
            or "Not found"
        )

        semantic_rank = (
            result[
                "semantic_first_relevant_rank"
            ]
            or "Not found"
        )

        print(
            f"\n{result['case_id']}"
        )

        print(
            f"  Rule-based first relevant rank: "
            f"{baseline_rank}"
        )

        print(
            f"  Semantic first relevant rank: "
            f"{semantic_rank}"
        )

    print("\n" + "-" * 70)
    print("RULE-BASED BASELINE")
    print(
        f"Hit@1: "
        f"{baseline_summary['hit_at_1']}/"
        f"{baseline_summary['query_count']}"
    )
    print(
        f"Hit@3: "
        f"{baseline_summary['hit_at_3']}/"
        f"{baseline_summary['query_count']}"
    )
    print(
        "MRR: "
        f"{baseline_summary['mean_reciprocal_rank']}"
    )
    print(
        "Average latency: "
        f"{baseline_summary['average_latency_seconds']}s"
    )

    print("\nSEMANTIC RETRIEVER")
    print(
        f"Hit@1: "
        f"{semantic_summary['hit_at_1']}/"
        f"{semantic_summary['query_count']}"
    )
    print(
        f"Hit@3: "
        f"{semantic_summary['hit_at_3']}/"
        f"{semantic_summary['query_count']}"
    )
    print(
        "MRR: "
        f"{semantic_summary['mean_reciprocal_rank']}"
    )
    print(
        "Average latency: "
        f"{semantic_summary['average_latency_seconds']}s"
    )

    print(f"\nJSON results: {RESULTS_JSON}")
    print(f"CSV results: {RESULTS_CSV}")


def main() -> None:
    """Run the retrieval comparison."""

    cases = load_cases()

    print(
        "Loading the local semantic strategy service..."
    )

    semantic_service = JoeyStrategyService()

    print(
        "Warming up the local semantic model..."
    )

    semantic_service.retrieve_for_text(
        "general child support needs",
        top_k=1,
    )

    results = [
        evaluate_case(
            case,
            semantic_service,
        )
        for case in cases
    ]

    baseline_summary = summarise_method(
        results,
        "baseline",
    )

    semantic_summary = summarise_method(
        results,
        "semantic",
    )

    save_results(
        results,
        baseline_summary,
        semantic_summary,
    )

    print_summary(
        results,
        baseline_summary,
        semantic_summary,
    )


if __name__ == "__main__":
    main()