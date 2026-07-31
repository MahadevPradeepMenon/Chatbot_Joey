"""Regression tests for the Stage 5C strategy and feedback API."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app
from dataclasses import dataclass
from types import SimpleNamespace

from app.context_builder import ContextSelection
from app.strategy_workflow_service import StrategyEvidenceSnapshot
from storage.strategy_feedback import (
    count_strategy_feedback,
    count_strategy_searches,
    list_strategy_feedback,
)


class FakeStrategyService:
    """Deterministic retrieval service that can observe SQLite feedback."""

    def __init__(
        self,
        database_path: Path,
    ) -> None:
        self.database_path = database_path

    def retrieve(
        self,
        question: str,
        top_k: int = 3,
        candidate_pool: int = 6,
    ) -> SimpleNamespace:
        del candidate_pool

        feedback = list_strategy_feedback(
            limit=100,
            database_path=self.database_path,
        )
        positive_feedback = any(
            item.strategy_code == "SP-01"
            and item.rating.value == "worked_well"
            for item in feedback
        )

        irrelevant = "football score" in question.lower()
        first_score = 0.001 if irrelevant else 0.031
        second_score = 0.0005 if irrelevant else 0.028
        adjustment = 0.0021 if positive_feedback else 0.0
        outcome = "worked_great" if positive_feedback else "not_recorded"
        note = (
            "The latest confirmed feedback reported that it worked well."
            if positive_feedback
            else "This appears to be a new strategy option in the available history."
        )

        evidence = [
            StrategyEvidenceSnapshot(
                rank=1,
                original_rank=1,
                original_score=first_score,
                history_adjustment=adjustment,
                personalised_score=(
                    first_score + adjustment
                ),
                strategy_code="SP-01",
                strategy_title="Sensory Processing Support",
                collection_title="Sensory Processing",
                source_file="sensory_support.txt",
                theme="noise sensitivity",
                chunk_id="sensory-001",
                passage=(
                    "Reduce loud noise, offer a calmer space, and allow ear protection."
                    if not irrelevant
                    else "A visual routine may support transitions."
                ),
                lifecycle_status="not_active",
                latest_outcome=outcome,
                times_used=1 if positive_feedback else 0,
                history_note=note,
            ),
            StrategyEvidenceSnapshot(
                rank=2,
                original_rank=2,
                original_score=second_score,
                history_adjustment=0.0,
                personalised_score=second_score,
                strategy_code="ER-02",
                strategy_title="Emotional Regulation Support",
                collection_title="Emotional Regulation",
                source_file="emotional_regulation.txt",
                theme="distress",
                chunk_id="regulation-002",
                passage=(
                    "Use calm language and reduce demands during distress."
                    if not irrelevant
                    else "Use a first-then board for daily routines."
                ),
                lifecycle_status="not_active",
                latest_outcome="not_recorded",
                times_used=0,
                history_note=(
                    "This appears to be a new strategy option in the available history."
                ),
            ),
        ]

        context = ContextSelection(
            question=question,
            detected_topics=(
                []
                if irrelevant
                else ["sensory", "school"]
            ),
            profile_items=(
                []
                if irrelevant
                else ["Sensory preference: lower background noise"]
            ),
            journal_items=[],
            quick_track_items=[],
            active_strategy_items=[],
            omitted_sensitive_fields=["name"],
            context_text="Synthetic test context.",
        )

        return SimpleNamespace(
            question=question,
            context=context,
            retrieval_query=(
                "Current parent/carer strategy question:\n"
                f"{question}"
            ),
            evidence=evidence[:top_k],
        )


def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable API regression-test failure."""

    if not condition:
        raise AssertionError(message)


def search_question(
    client: TestClient,
    question: str = (
        "What may help when loud classroom noise makes my child cover their ears?"
    ),
) -> tuple[int, dict]:
    """Submit one strategy question and return status plus payload."""

    response = client.post(
        "/api/v1/strategies/search",
        json={
            "question": question,
            "top_k": 2,
        },
    )

    return response.status_code, response.json()


def test_accepted_search_persists(
    client: TestClient,
    database_path: Path,
) -> dict:
    """Relevant source-backed evidence should be returned and stored."""

    status_code, payload = search_question(
        client
    )

    assert_true(
        status_code == 200,
        "A relevant strategy search did not return HTTP 200.",
    )
    assert_true(
        payload["outcome"] == "results",
        "A relevant search did not return results.",
    )
    assert_true(
        isinstance(
            payload["search_id"],
            int,
        ),
        "The accepted search had no persistent ID.",
    )
    assert_true(
        payload["confidence"]["level"] == "strong",
        "The relevant test search was not assessed as strong.",
    )
    assert_true(
        payload["strategy_count"] == 2,
        "The requested strategy count was not respected.",
    )
    assert_true(
        payload["strategies"][0]["source_file"]
        == "sensory_support.txt",
        "The source-backed evidence was not returned.",
    )
    assert_true(
        count_strategy_searches(
            database_path
        ) == 1,
        "The accepted strategy search was not persisted.",
    )

    return payload


def test_request_validation(
    client: TestClient,
) -> None:
    """Whitespace questions and invalid result counts should be rejected."""

    whitespace = client.post(
        "/api/v1/strategies/search",
        json={
            "question": "   ",
        },
    )
    invalid_top_k = client.post(
        "/api/v1/strategies/search",
        json={
            "question": "What may help with noise?",
            "top_k": 9,
        },
    )

    assert_true(
        whitespace.status_code == 422,
        "A whitespace strategy question did not return HTTP 422.",
    )
    assert_true(
        invalid_top_k.status_code == 422,
        "An invalid top_k value did not return HTTP 422.",
    )


def test_safety_screening_priority(
    client: TestClient,
    database_path: Path,
) -> None:
    """Safety-sensitive questions must not produce ordinary strategies."""

    before_count = count_strategy_searches(
        database_path
    )
    status_code, payload = search_question(
        client,
        question=(
            "My child is hitting their own head and may be injured. What strategy should I use?"
        ),
    )

    assert_true(
        status_code == 200,
        "The safety-limited response did not return HTTP 200.",
    )
    assert_true(
        payload["outcome"] == "safety_limited",
        "The safety question was not limited before retrieval.",
    )
    assert_true(
        payload["strategies"] == [],
        "A safety-limited question returned ordinary strategies.",
    )
    assert_true(
        payload["can_submit_feedback"] is False,
        "A safety-limited result unexpectedly accepted feedback.",
    )
    assert_true(
        count_strategy_searches(
            database_path
        ) == before_count,
        "The safety-limited question was stored as an accepted search.",
    )


def test_weak_search_abstains(
    client: TestClient,
    database_path: Path,
) -> None:
    """Weak unrelated evidence should abstain and remain unstored."""

    before_count = count_strategy_searches(
        database_path
    )
    status_code, payload = search_question(
        client,
        question="What is tomorrow's football score?",
    )

    assert_true(
        status_code == 200,
        "The abstention response did not return HTTP 200.",
    )
    assert_true(
        payload["outcome"] == "abstained",
        "The unrelated question did not trigger abstention.",
    )
    assert_true(
        payload["confidence"]["level"] == "weak",
        "The abstention did not expose weak confidence.",
    )
    assert_true(
        payload["search_id"] is None,
        "An abstained search unexpectedly received a search ID.",
    )
    assert_true(
        count_strategy_searches(
            database_path
        ) == before_count,
        "The abstained search was stored as accepted evidence.",
    )


def test_get_accepted_search(
    client: TestClient,
    accepted: dict,
) -> None:
    """Stored accepted evidence should round-trip through the GET endpoint."""

    response = client.get(
        (
            "/api/v1/strategies/searches/"
            f"{accepted['search_id']}"
        )
    )
    payload = response.json()

    assert_true(
        response.status_code == 200,
        "The accepted-search GET endpoint did not return HTTP 200.",
    )
    assert_true(
        payload["search_id"] == accepted["search_id"],
        "The GET endpoint returned another strategy search.",
    )
    assert_true(
        payload["strategies"][0]["history_note"],
        "The stored evidence did not preserve transparent history wording.",
    )


def test_feedback_creation_and_get(
    client: TestClient,
    database_path: Path,
    accepted: dict,
) -> dict:
    """Explicit feedback should be stored and included in later GET output."""

    response = client.post(
        "/api/v1/strategies/feedback",
        json={
            "search_id": accepted["search_id"],
            "strategy_rank": 1,
            "rating": "worked_well",
            "comment": "Helpful during a noisy lesson.",
        },
    )
    payload = response.json()

    assert_true(
        response.status_code == 200,
        "Valid strategy feedback did not return HTTP 200.",
    )
    assert_true(
        payload["feedback"]["rating"] == "worked_well",
        "The feedback rating was not preserved.",
    )
    assert_true(
        count_strategy_feedback(
            database_path
        ) == 1,
        "The strategy feedback was not stored.",
    )

    restored = client.get(
        (
            "/api/v1/strategies/searches/"
            f"{accepted['search_id']}"
        )
    ).json()

    assert_true(
        len(restored["feedback"]) == 1,
        "The accepted-search GET response did not include feedback.",
    )

    return payload


def test_feedback_update_without_duplicate(
    client: TestClient,
    database_path: Path,
    accepted: dict,
    first_feedback: dict,
) -> None:
    """Repeating feedback for one result should update the same row."""

    response = client.post(
        "/api/v1/strategies/feedback",
        json={
            "search_id": accepted["search_id"],
            "strategy_rank": 1,
            "rating": "helped_somewhat",
        },
    )
    updated = response.json()

    assert_true(
        response.status_code == 200,
        "Updating strategy feedback did not return HTTP 200.",
    )
    assert_true(
        updated["feedback"]["feedback_id"]
        == first_feedback["feedback"]["feedback_id"],
        "The feedback update created another feedback identity.",
    )
    assert_true(
        count_strategy_feedback(
            database_path
        ) == 1,
        "Updating feedback created a duplicate row.",
    )

    # Restore positive feedback for the next ranking test.
    client.post(
        "/api/v1/strategies/feedback",
        json={
            "search_id": accepted["search_id"],
            "strategy_rank": 1,
            "rating": "worked_well",
        },
    )


def test_missing_and_invalid_feedback(
    client: TestClient,
    accepted: dict,
) -> None:
    """Missing searches and ranks not displayed by a search should fail."""

    missing_get = client.get(
        "/api/v1/strategies/searches/9999"
    )
    missing_feedback = client.post(
        "/api/v1/strategies/feedback",
        json={
            "search_id": 9999,
            "strategy_rank": 1,
            "rating": "not_relevant",
        },
    )
    invalid_rank = client.post(
        "/api/v1/strategies/feedback",
        json={
            "search_id": accepted["search_id"],
            "strategy_rank": 9,
            "rating": "not_relevant",
        },
    )

    assert_true(
        missing_get.status_code == 404,
        "A missing accepted search did not return HTTP 404.",
    )
    assert_true(
        missing_feedback.status_code == 404,
        "Feedback for a missing search did not return HTTP 404.",
    )
    assert_true(
        invalid_rank.status_code == 409,
        "Feedback for an undisplayed rank did not return HTTP 409.",
    )


def test_feedback_affects_next_search(
    client: TestClient,
) -> None:
    """The next API search should reload the newly stored feedback history."""

    status_code, payload = search_question(
        client
    )

    assert_true(
        status_code == 200,
        "The repeated strategy search did not return HTTP 200.",
    )
    assert_true(
        payload["strategies"][0]["history_adjustment"] > 0,
        "Stored positive feedback did not affect the next search.",
    )
    assert_true(
        "worked well"
        in payload["strategies"][0]["history_note"].lower(),
        "The repeated search did not expose the stored feedback history.",
    )


def test_openapi_and_regression_guards(
    client: TestClient,
) -> None:
    """OpenAPI should expose Stage 5C without breaking earlier endpoints."""

    openapi = client.get(
        "/openapi.json"
    )
    paths = openapi.json().get(
        "paths",
        {},
    )

    assert_true(
        {
            "/api/v1/strategies/search",
            "/api/v1/strategies/searches/{search_id}",
            "/api/v1/strategies/feedback",
        }.issubset(paths),
        "One or more Stage 5C endpoints were missing from OpenAPI.",
    )
    assert_true(
        client.get("/health").status_code == 200,
        "The Stage 5A health endpoint regressed.",
    )
    assert_true(
        "/api/v1/record/sessions" in paths,
        "The Stage 5B record endpoint disappeared from OpenAPI.",
    )


def main() -> None:
    """Run all Stage 5C API regression tests."""

    passed = 0
    total = 10

    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "strategy_api_test.db"
        )

        app = create_app(
            database_path,
            strategy_service_factory=(
                lambda path: FakeStrategyService(
                    path
                )
            ),
        )

        with TestClient(app) as client:
            accepted = test_accepted_search_persists(
                client,
                database_path,
            )
            passed += 1
            print("[PASS] accepted strategy search persistence")

            test_request_validation(
                client
            )
            passed += 1
            print("[PASS] strategy request validation")

            test_safety_screening_priority(
                client,
                database_path,
            )
            passed += 1
            print("[PASS] safety screening priority")

            test_weak_search_abstains(
                client,
                database_path,
            )
            passed += 1
            print("[PASS] weak retrieval abstention")

            test_get_accepted_search(
                client,
                accepted,
            )
            passed += 1
            print("[PASS] accepted search retrieval")

            feedback = test_feedback_creation_and_get(
                client,
                database_path,
                accepted,
            )
            passed += 1
            print("[PASS] feedback creation and retrieval")

            test_feedback_update_without_duplicate(
                client,
                database_path,
                accepted,
                feedback,
            )
            passed += 1
            print("[PASS] feedback update without duplicate")

            test_missing_and_invalid_feedback(
                client,
                accepted,
            )
            passed += 1
            print("[PASS] missing and invalid feedback handling")

            test_feedback_affects_next_search(
                client
            )
            passed += 1
            print("[PASS] stored feedback affects next search")

            test_openapi_and_regression_guards(
                client
            )
            passed += 1
            print("[PASS] Stage 5C OpenAPI and regression guards")

    print("\nAPI STRATEGY WORKFLOW TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")


if __name__ == "__main__":
    main()
