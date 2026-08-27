import csv
import json
from pathlib import Path
from typing import Any

from app.extractor import extract_structured_record
from app.response_builder import build_parent_response
from rag.strategy_retriever import retrieve_strategies


# Resolve test-case and result paths relative to the repository so the end-to-end
# evaluation can be rerun consistently from different working directories.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

TEST_CASES_FILE = (
    PROJECT_ROOT / "evaluation" / "end_to_end_test_cases.json"
)

RESULTS_CSV = (
    PROJECT_ROOT / "evaluation" / "end_to_end_results.csv"
)

RESULTS_JSON = (
    PROJECT_ROOT / "evaluation" / "end_to_end_results.json"
)


def load_test_cases() -> list[dict[str, Any]]:
    """Load the synthetic end-to-end evaluation cases."""

    # Fail early when the synthetic evaluation fixture is missing rather than
    # producing an empty or misleading result set.
    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(
            f"Test case file was not found: {TEST_CASES_FILE}"
        )

    # Load the complete test-case definition as UTF-8 JSON for deterministic reuse.
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def check_required_items(
    actual_items: list[str],
    required_items: list[str],
    field_name: str,
) -> list[dict[str, Any]]:
    """Check that all required values appear in the actual list."""

    checks = []

    # Evaluate each expected list item independently so failures identify the exact
    # missing category, Quick Track suggestion or risk flag.
    for required_item in required_items:
        passed = required_item in actual_items

        checks.append(
            {
                "name": f"{field_name} contains '{required_item}'",
                "passed": passed,
                "actual": actual_items,
                "expected": required_item,
            }
        )

    return checks


def evaluate_case(test_case: dict[str, Any]) -> dict[str, Any]:
    """Run one note through Joey's complete local pipeline."""

    case_id = test_case["id"]
    note = test_case["note"]
    expected = test_case["expected"]

    # Use the production deterministic extractor so this test exercises the same
    # structured-record path used by the application.
    record = extract_structured_record(note)

    # Retrieve up to four local baseline strategies from the extracted record and
    # original note before building the parent-facing response.
    strategies = retrieve_strategies(
        record=record,
        original_note=note,
        top_k=4,
    )

    # Run the actual response builder so the evaluation covers extraction,
    # retrieval and response-generation integration in one local pipeline.
    parent_response = build_parent_response(
        original_note=note,
        record=record,
        retrieved_strategies=strategies,
    )

    # Core scalar checks compare the extracted mood/anxiety values and require the
    # confirmation safeguard to remain enabled.
    checks = [
        {
            "name": "mood zone",
            "passed": record.mood_zone.value == expected["mood_zone"],
            "actual": record.mood_zone.value,
            "expected": expected["mood_zone"],
        },
        {
            "name": "anxiety level",
            "passed": record.anxiety_level.value
            == expected["anxiety_level"],
            "actual": record.anxiety_level.value,
            "expected": expected["anxiety_level"],
        },
        {
            "name": "parent confirmation required",
            "passed": record.requires_parent_confirmation is True,
            "actual": record.requires_parent_confirmation,
            "expected": True,
        },
    ]

    # List-valued expectations are checked by required-item membership rather than
    # exact list equality so additional valid suggestions do not cause a failure.
    checks.extend(
        check_required_items(
            record.strategy_categories,
            expected["required_strategy_categories"],
            "strategy categories",
        )
    )

    checks.extend(
        check_required_items(
            record.quick_track_suggestions,
            expected["required_quick_tracks"],
            "Quick Track suggestions",
        )
    )

    checks.extend(
        check_required_items(
            record.risk_flags,
            expected["required_risk_flags"],
            "risk flags",
        )
    )

    # Response checks are case-insensitive substring tests against phrases defined
    # in each synthetic case.
    for expected_phrase in expected["response_contains"]:
        checks.append(
            {
                "name": f"response contains '{expected_phrase}'",
                "passed": expected_phrase.lower()
                in parent_response.lower(),
                "actual": parent_response,
                "expected": expected_phrase,
            }
        )

    # A case passes only when every individual check succeeds; failed check names
    # are retained for diagnosis in saved artifacts and terminal output.
    failed_checks = [
        check["name"] for check in checks if not check["passed"]
    ]

    # Preserve both summary fields and the full check list so each pass/fail result
    # can be traced back to the underlying expectations.
    return {
        "case_id": case_id,
        "note": note,
        "passed": len(failed_checks) == 0,
        "passed_checks": sum(check["passed"] for check in checks),
        "total_checks": len(checks),
        "failed_checks": failed_checks,
        "mood_zone": record.mood_zone.value,
        "anxiety_level": record.anxiety_level.value,
        "risk_flags": record.risk_flags,
        "strategy_categories": record.strategy_categories,
        "retrieved_strategy_titles": [
            strategy["title"] for strategy in strategies
        ],
        "follow_up_question": record.follow_up_question,
        "checks": checks,
    }


def save_results(results: list[dict[str, Any]]) -> None:
    """Save evaluation results in CSV and JSON formats."""

    # Flatten list-valued fields for a spreadsheet-friendly CSV while the JSON
    # output below retains the complete nested evaluation structure.
    csv_rows = []

    # Print each case status and only enumerate failed checks when present.
    for result in results:
        csv_rows.append(
            {
                "case_id": result["case_id"],
                "passed": result["passed"],
                "passed_checks": result["passed_checks"],
                "total_checks": result["total_checks"],
                "failed_checks": " | ".join(result["failed_checks"]),
                "mood_zone": result["mood_zone"],
                "anxiety_level": result["anxiety_level"],
                "risk_flags": " | ".join(result["risk_flags"]),
                "strategy_categories": " | ".join(
                    result["strategy_categories"]
                ),
                "retrieved_strategy_titles": " | ".join(
                    result["retrieved_strategy_titles"]
                ),
                "follow_up_question": result["follow_up_question"],
            }
        )

    # Write CSV with UTF-8 BOM for compatibility with common spreadsheet tools.
    with open(
        RESULTS_CSV,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=csv_rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    # JSON preserves all per-case checks and list fields for reproducible analysis.
    with open(RESULTS_JSON, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)


def main() -> None:
    # Evaluate every synthetic case through the complete local pipeline before
    # writing results and calculating aggregate pass counts.
    test_cases = load_test_cases()
    results = [evaluate_case(case) for case in test_cases]

    save_results(results)

    # Report both whole-case success and individual-check success because a single
    # failed expectation makes the overall case fail.
    passed_cases = sum(result["passed"] for result in results)
    total_cases = len(results)

    passed_checks = sum(
        result["passed_checks"] for result in results
    )
    total_checks = sum(
        result["total_checks"] for result in results
    )

    print("\nJOEY END-TO-END EVALUATION")
    print("=" * 60)
    print(f"Cases passed: {passed_cases}/{total_cases}")
    print(f"Checks passed: {passed_checks}/{total_checks}")

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"

        print(
            f"\n[{status}] {result['case_id']} "
            f"({result['passed_checks']}/{result['total_checks']})"
        )

        if result["failed_checks"]:
            for failure in result["failed_checks"]:
                print(f"- Failed: {failure}")

    print(f"\nCSV results: {RESULTS_CSV}")
    print(f"JSON results: {RESULTS_JSON}")


# Run the end-to-end evaluation only when this module is executed directly.
if __name__ == "__main__":
    main()
