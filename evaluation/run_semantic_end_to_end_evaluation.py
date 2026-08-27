import csv
import json
import re
import time
from pathlib import Path
from typing import Any

from app.extractor import extract_structured_record
from app.response_builder import build_parent_response
from rag.joey_strategy_service import (
    JoeyStrategyEvidence,
    JoeyStrategyService,
)
from safety.safety_guard import (
    should_limit_strategy_suggestions,
)


# Resolve evaluation fixtures and outputs relative to the repository so the
# integrated evaluation can be rerun consistently from different directories.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

TEST_CASES_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "semantic_end_to_end_test_cases.json"
)

RESULTS_JSON = (
    PROJECT_ROOT
    / "evaluation"
    / "semantic_end_to_end_results.json"
)

RESULTS_CSV = (
    PROJECT_ROOT
    / "evaluation"
    / "semantic_end_to_end_results.csv"
)

# Use a fixed top-k so retrieval-count checks and saved results are comparable
# across repeated evaluation runs.
TOP_K = 3


def normalise_text(value: str) -> str:
    """Normalise text for resilient filename comparisons."""

    # Normalise filenames and expected source keywords to lowercase underscore
    # tokens so punctuation differences do not affect source matching.
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        value.lower(),
    ).strip("_")


def load_test_cases() -> list[dict[str, Any]]:
    """Load the synthetic evaluation cases."""

    # Fail early when the synthetic semantic evaluation fixture is unavailable.
    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(
            f"Test-case file not found: {TEST_CASES_FILE}"
        )

    cases = json.loads(
        TEST_CASES_FILE.read_text(
            encoding="utf-8"
        )
    )

    # Require a non-empty case list so aggregate pass counts remain meaningful.
    if not isinstance(cases, list) or not cases:
        raise ValueError(
            "The evaluation file must contain a non-empty list."
        )

    return cases


def expected_source_found(
    strategies: list[JoeyStrategyEvidence],
    expected_keywords: list[str],
    safety_limited: bool,
) -> bool:
    """
    Check whether at least one expected strategy collection
    appeared in the retrieved source filenames.
    """

    # Safety-limited cases intentionally skip strategy retrieval, so source matching
    # is treated as satisfied rather than requiring evidence that should not exist.
    if safety_limited:
        return True

    if not expected_keywords:
        return True

    # Compare expected collection keywords against normalised source filenames from
    # the retrieved evidence rather than relying on exact filename spelling.
    normalised_sources = [
        normalise_text(strategy.source_file)
        for strategy in strategies
    ]

    return any(
        normalise_text(keyword) in source
        for keyword in expected_keywords
        for source in normalised_sources
    )


def evaluate_case(
    test_case: dict[str, Any],
    strategy_service: JoeyStrategyService,
) -> dict[str, Any]:
    """Run one case through the complete integrated workflow."""

    case_id = str(test_case["case_id"])
    note = str(test_case["note"])

    expected_keywords = [
        str(keyword)
        for keyword in test_case.get(
            "expected_source_keywords",
            [],
        )
    ]

    minimum_results = int(
        test_case.get(
            "minimum_results",
            1,
        )
    )

    expected_safety_limit = bool(
        test_case.get(
            "expect_safety_limit",
            False,
        )
    )

    started_at = time.perf_counter()

    # Run the production deterministic extractor first so the evaluation follows
    # the same structured-record path as the application.
    record = extract_structured_record(note)

    # Apply the production safety guard before retrieval so risk-sensitive cases
    # are evaluated with the same strategy-limiting behaviour as normal use.
    safety_limited = (
        should_limit_strategy_suggestions(
            record
        )
    )

    strategies: list[
        JoeyStrategyEvidence
    ] = []

    # Only retrieve local strategy evidence when the safety layer permits ordinary
    # strategy suggestions for the current record.
    if not safety_limited:
        strategies = (
            strategy_service.retrieve_for_record(
                record,
                original_note=note,
                top_k=TOP_K,
            )
        )

    # Build the actual parent-facing response from the extracted record and any
    # retrieved evidence so response safeguards are included in the evaluation.
    response = build_parent_response(
        original_note=note,
        record=record,
        retrieved_strategies=strategies,
    )

    # Measure the complete integrated workflow from extraction through response
    # construction rather than retrieval latency alone.
    elapsed_seconds = (
        time.perf_counter() - started_at
    )

    # Preserve source filenames, readable strategy titles and rounded scores so
    # saved artifacts can be inspected without rerunning the system.
    source_files = [
        strategy.source_file
        for strategy in strategies
    ]

    strategy_titles = [
        (
            f"{strategy.strategy_code}: "
            f"{strategy.strategy_title}"
            if strategy.strategy_code
            else str(strategy.strategy_title)
        )
        for strategy in strategies
    ]

    scores = [
        round(strategy.score, 4)
        for strategy in strategies
    ]

    # Evaluate whether at least one expected source collection appears unless the
    # case was intentionally safety-limited.
    source_match = expected_source_found(
        strategies,
        expected_keywords,
        safety_limited,
    )

    # Combine extraction, confirmation, safety, retrieval, provenance and response
    # expectations into one transparent set of per-case boolean checks.
    checks = {
        "record_created": bool(
            record.summary
        ),
        "confirmation_required": (
            record.requires_parent_confirmation
            is True
        ),
        "safety_behaviour_matches": (
            safety_limited
            == expected_safety_limit
        ),
        "retrieval_count_matches": (
            len(strategies)
            >= minimum_results
            if not safety_limited
            else len(strategies) == 0
        ),
        "expected_source_retrieved": (
            source_match
        ),
        "retrieval_sources_present": (
            all(source_files)
            if strategies
            else safety_limited
        ),
        "response_requests_review": (
            "Before saving:" in response
        ),
        "response_contains_disclaimer": (
            "does not diagnose" in response
        ),
        "response_handles_safety": (
            (
                "not treating it as an ordinary strategy request"
                in response
            )
            if expected_safety_limit
            else (
                "Relevant source-backed support strategies:"
                in response
            )
        ),
    }

    # A case passes only when every defined integration check succeeds.
    passed_checks = sum(
        checks.values()
    )

    total_checks = len(checks)
    case_passed = passed_checks == total_checks

    # Save the original note, timing, retrieval evidence summary and full check map
    # so each case result remains traceable.
    return {
        "case_id": case_id,
        "note": note,
        "case_passed": case_passed,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "elapsed_seconds": round(
            elapsed_seconds,
            4,
        ),
        "safety_limited": safety_limited,
        "retrieval_count": len(strategies),
        "source_files": source_files,
        "strategy_titles": strategy_titles,
        "similarity_scores": scores,
        "checks": checks,
    }


def save_results(
    results: list[dict[str, Any]],
) -> None:
    """Save detailed JSON and summary CSV results."""

    # JSON output keeps aggregate totals together with every detailed case result.
    summary = {
        "evaluation_name": (
            "Hey Joey integrated semantic "
            "end-to-end evaluation"
        ),
        "case_count": len(results),
        "cases_passed": sum(
            result["case_passed"]
            for result in results
        ),
        "checks_passed": sum(
            result["passed_checks"]
            for result in results
        ),
        "total_checks": sum(
            result["total_checks"]
            for result in results
        ),
        "results": results,
    }

    RESULTS_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Flatten list-valued fields and failed-check names for a spreadsheet-friendly
    # CSV companion to the detailed JSON artifact.
    csv_rows: list[dict[str, Any]] = []

    # Print one compact status block per case before the overall summary totals.
    for result in results:
        csv_rows.append(
            {
                "case_id": result["case_id"],
                "case_passed": result[
                    "case_passed"
                ],
                "passed_checks": result[
                    "passed_checks"
                ],
                "total_checks": result[
                    "total_checks"
                ],
                "elapsed_seconds": result[
                    "elapsed_seconds"
                ],
                "safety_limited": result[
                    "safety_limited"
                ],
                "retrieval_count": result[
                    "retrieval_count"
                ],
                "source_files": " | ".join(
                    result["source_files"]
                ),
                "strategy_titles": " | ".join(
                    result["strategy_titles"]
                ),
                "similarity_scores": " | ".join(
                    str(score)
                    for score in result[
                        "similarity_scores"
                    ]
                ),
                "failed_checks": " | ".join(
                    check_name
                    for check_name, passed
                    in result["checks"].items()
                    if not passed
                ),
            }
        )

    # Use UTF-8 with BOM for compatibility with common spreadsheet applications.
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


def print_results(
    results: list[dict[str, Any]],
) -> None:
    """Display a readable terminal summary."""

    print("\nINTEGRATED SEMANTIC EVALUATION RESULTS")
    print("=" * 70)

    for result in results:
        status = (
            "PASS"
            if result["case_passed"]
            else "FAIL"
        )

        print(
            f"\n[{status}] "
            f"{result['case_id']}"
        )

        print(
            f"Checks: "
            f"{result['passed_checks']}/"
            f"{result['total_checks']}"
        )

        print(
            f"Retrieval results: "
            f"{result['retrieval_count']}"
        )

        print(
            f"Safety limited: "
            f"{result['safety_limited']}"
        )

        print(
            f"Time: "
            f"{result['elapsed_seconds']:.4f}s"
        )

        # Reconstruct failed check names directly from the stored boolean check map.
        failed_checks = [
            check_name
            for check_name, passed
            in result["checks"].items()
            if not passed
        ]

        if failed_checks:
            print(
                "Failed checks: "
                + ", ".join(failed_checks)
            )

    cases_passed = sum(
        result["case_passed"]
        for result in results
    )

    checks_passed = sum(
        result["passed_checks"]
        for result in results
    )

    total_checks = sum(
        result["total_checks"]
        for result in results
    )

    print("\n" + "-" * 70)
    print(
        f"Cases passed: "
        f"{cases_passed}/{len(results)}"
    )
    print(
        f"Checks passed: "
        f"{checks_passed}/{total_checks}"
    )
    print(f"JSON results: {RESULTS_JSON}")
    print(f"CSV results: {RESULTS_CSV}")


def main() -> None:
    """Run the integrated semantic system evaluation."""

    # Load fixtures before initialising the heavier local strategy service.
    test_cases = load_test_cases()

    print(
        "Loading the local semantic strategy service..."
    )

    # Reuse one local strategy service instance across all cases so the semantic
    # model/index are not repeatedly reloaded during the evaluation.
    strategy_service = JoeyStrategyService()

    results: list[dict[str, Any]] = []

    # Run every case through the same integrated extraction-safety-retrieval-response path.
    for test_case in test_cases:
        result = evaluate_case(
            test_case,
            strategy_service,
        )

        results.append(result)

    save_results(results)
    print_results(results)


# Run the integrated semantic end-to-end evaluation only when executed directly.
if __name__ == "__main__":
    main()