import csv
import json
from pathlib import Path
from typing import Any

from app.extractor import extract_structured_record
from app.response_builder import build_parent_response
from rag.strategy_retriever import retrieve_strategies


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

    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(
            f"Test case file was not found: {TEST_CASES_FILE}"
        )

    with open(TEST_CASES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def check_required_items(
    actual_items: list[str],
    required_items: list[str],
    field_name: str,
) -> list[dict[str, Any]]:
    """Check that all required values appear in the actual list."""

    checks = []

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

    record = extract_structured_record(note)

    strategies = retrieve_strategies(
        record=record,
        original_note=note,
        top_k=4,
    )

    parent_response = build_parent_response(
        original_note=note,
        record=record,
        retrieved_strategies=strategies,
    )

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

    failed_checks = [
        check["name"] for check in checks if not check["passed"]
    ]

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

    csv_rows = []

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

    with open(RESULTS_JSON, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)


def main() -> None:
    test_cases = load_test_cases()
    results = [evaluate_case(case) for case in test_cases]

    save_results(results)

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


if __name__ == "__main__":
    main()