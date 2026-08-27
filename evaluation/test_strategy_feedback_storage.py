"""Regression tests for strategy-search and feedback storage."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from storage.strategy_feedback import (
    StrategyFeedbackRating,
    count_strategy_feedback,
    count_strategy_searches,
    create_strategy_feedback_tables,
    feedback_label,
    get_strategy_search,
    list_strategy_feedback,
    normalise_feedback_rating,
    save_strategy_feedback,
    save_strategy_search,
)


# Use a minimal immutable evidence fixture that matches the fields expected by
# strategy-search persistence without depending on the live retrieval service.
@dataclass(frozen=True)
class FakeEvidence:
    """Synthetic history-aware strategy evidence."""

    original_rank: int
    original_score: float
    history_adjustment: float
    personalised_score: float
    strategy_code: str | None
    strategy_title: str | None
    collection_title: str
    source_file: str
    theme: str | None
    chunk_id: str
    passage: str


def sample_evidence() -> list[FakeEvidence]:
    """Return two synthetic displayed strategies."""

    # Return two deterministic displayed strategies so search ordering, identity,
    # scores and feedback linkage can be checked after storage.
    return [
        FakeEvidence(
            original_rank=1,
            original_score=0.0318,
            history_adjustment=0.0010,
            personalised_score=0.0328,
            strategy_code="SP-01",
            strategy_title="Sensory Processing Support",
            collection_title="Sensory Processing",
            source_file="sensory_support.txt",
            theme="noise sensitivity",
            chunk_id="sensory-001",
            passage=(
                "Reduce sensory demand and offer a calmer space."
            ),
        ),
        FakeEvidence(
            original_rank=2,
            original_score=0.0291,
            history_adjustment=0.0,
            personalised_score=0.0291,
            strategy_code="ER-02",
            strategy_title="Emotional Regulation Support",
            collection_title="Emotional Regulation",
            source_file="emotional_regulation.txt",
            theme="distress",
            chunk_id="regulation-002",
            passage=(
                "Use calm language and reduce demands during distress."
            ),
        ),
    ]


def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable test failure."""

    # Keep this regression module runnable as a standalone script without requiring
    # an external testing framework.
    if not condition:
        raise AssertionError(message)


def test_table_creation(
    database_path: Path,
) -> None:
    """All strategy-feedback tables should be created."""

    # Create the strategy-search and feedback tables at the injected temporary path
    # rather than touching the application's normal local database.
    created = create_strategy_feedback_tables(
        database_path
    )

    assert_true(
        created.exists(),
        "The SQLite database was not created.",
    )


def test_search_and_results_saved(
    database_path: Path,
) -> int:
    """A search and all displayed strategies should be stored."""

    # Persist one search together with the exact strategies shown to the user so
    # later feedback can be linked to a specific displayed rank.
    search_id = save_strategy_search(
        question=(
            "What may help when classroom noise "
            "becomes overwhelming?"
        ),
        retrieval_query=(
            "classroom noise sensory processing support"
        ),
        evidence=sample_evidence(),
        confidence_level="strong",
        source="strategy_feedback_test",
        created_at="2026-07-30T17:00:00",
        database_path=database_path,
    )

    assert_true(
        search_id == 1,
        "The first search should have ID 1.",
    )

    assert_true(
        count_strategy_searches(
            database_path
        ) == 1,
        "The stored search count should be 1.",
    )

    return search_id


def test_search_round_trip(
    database_path: Path,
    search_id: int,
) -> None:
    """Stored question, query and result order should round-trip."""

    # Read the search back through the public storage API to verify result ordering
    # and stored retrieval metadata survive the SQLite round trip.
    stored = get_strategy_search(
        search_id,
        database_path,
    )

    if stored is None:
        raise AssertionError(
            "The stored search could not be retrieved."
        )

    assert_true(
        stored["confidence_level"] == "strong",
        "The confidence level was not preserved.",
    )

    assert_true(
        len(stored["evidence"]) == 2,
        "Both displayed strategies were not preserved.",
    )

    assert_true(
        stored["evidence"][0]["strategy_code"] == "SP-01",
        "The first displayed strategy was not preserved.",
    )


def test_valid_feedback_saved(
    database_path: Path,
    search_id: int,
) -> int:
    """A supported user-facing rating should be stored."""

    # Save feedback against the first displayed strategy using the same user-facing
    # rating label accepted by the application workflow.
    feedback_id = save_strategy_feedback(
        search_id=search_id,
        strategy_rank=1,
        rating="worked well",
        comment="Helpful during a noisy lesson.",
        created_at="2026-07-30T17:05:00",
        database_path=database_path,
    )

    assert_true(
        feedback_id == 1,
        "The first feedback record should have ID 1.",
    )

    assert_true(
        count_strategy_feedback(
            database_path
        ) == 1,
        "The feedback count should be 1.",
    )

    return feedback_id


def test_feedback_round_trip(
    database_path: Path,
) -> None:
    """Stored feedback should retain strategy identity and label."""

    # Retrieve the joined feedback view so strategy identity, internal enum value
    # and parent-facing display label can be checked together.
    items = list_strategy_feedback(
        database_path=database_path,
    )

    assert_true(
        len(items) == 1,
        "Exactly one feedback record was expected.",
    )

    item = items[0]

    assert_true(
        item.strategy_code == "SP-01",
        "The strategy identity was not preserved.",
    )

    assert_true(
        item.rating
        == StrategyFeedbackRating.worked_well,
        "The internal rating was not preserved.",
    )

    assert_true(
        item.rating_label == "Worked well",
        "The parent-facing label was not preserved.",
    )


def test_feedback_update_is_not_duplicate(
    database_path: Path,
    search_id: int,
) -> None:
    """Changing feedback should update the existing result record."""

    # Re-save feedback for the same search/rank pair to confirm the existing row is
    # updated rather than duplicated.
    save_strategy_feedback(
        search_id=search_id,
        strategy_rank=1,
        rating="helped somewhat",
        comment=None,
        created_at="2026-07-30T17:06:00",
        database_path=database_path,
    )

    assert_true(
        count_strategy_feedback(
            database_path
        ) == 1,
        "Updating feedback should not create a duplicate.",
    )

    item = list_strategy_feedback(
        database_path=database_path,
    )[0]

    assert_true(
        item.rating
        == StrategyFeedbackRating.helped_somewhat,
        "The feedback rating was not updated.",
    )


def test_invalid_rating_rejected(
    database_path: Path,
    search_id: int,
) -> None:
    """Unsupported ratings must not be stored."""

    # Exercise validation with an unsupported rating and confirm no invalid value
    # is silently accepted.
    try:
        save_strategy_feedback(
            search_id=search_id,
            strategy_rank=1,
            rating="maybe",
            database_path=database_path,
        )
    except ValueError as error:
        assert_true(
            "Unsupported feedback rating" in str(error),
            "The invalid-rating message was unexpected.",
        )
    else:
        raise AssertionError(
            "An unsupported feedback rating was stored."
        )


def test_invalid_strategy_rank_rejected(
    database_path: Path,
    search_id: int,
) -> None:
    """Feedback must reference a displayed strategy."""

    # Use a rank that was never displayed for this search to verify referential
    # validation between feedback and stored search results.
    try:
        save_strategy_feedback(
            search_id=search_id,
            strategy_rank=9,
            rating="not relevant",
            database_path=database_path,
        )
    except ValueError as error:
        assert_true(
            "does not belong" in str(error),
            "The invalid-rank message was unexpected.",
        )
    else:
        raise AssertionError(
            "Feedback was stored for an unknown strategy rank."
        )


def test_rating_normalisation() -> None:
    """User labels and stored values should normalise consistently."""

    # Check both directions of the rating boundary: user-facing labels normalise
    # to stored enum values, and stored values map back to display labels.
    assert_true(
        normalise_feedback_rating(
            "Did not work well"
        )
        == StrategyFeedbackRating.did_not_work_well,
        "The user-facing negative rating was not normalised.",
    )

    assert_true(
        feedback_label(
            "not_relevant"
        )
        == "Not relevant",
        "The stored rating did not produce its display label.",
    )


def main() -> None:
    """Run strategy-feedback storage regression tests."""

    passed = 0
    total = 8

    # Run all persistence tests against a disposable SQLite database so the suite
    # is isolated and repeatable.
    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "strategy_feedback_test.db"
        )

        test_table_creation(
            database_path
        )
        passed += 1
        print("[PASS] feedback table creation")

        search_id = test_search_and_results_saved(
            database_path
        )
        passed += 1
        print("[PASS] strategy search and results save")

        test_search_round_trip(
            database_path,
            search_id,
        )
        passed += 1
        print("[PASS] strategy search round trip")

        test_valid_feedback_saved(
            database_path,
            search_id,
        )
        passed += 1
        print("[PASS] valid strategy feedback save")

        test_feedback_round_trip(
            database_path
        )
        passed += 1
        print("[PASS] strategy feedback round trip")

        test_feedback_update_is_not_duplicate(
            database_path,
            search_id,
        )
        passed += 1
        print("[PASS] feedback update without duplicate")

        test_invalid_rating_rejected(
            database_path,
            search_id,
        )
        passed += 1
        print("[PASS] invalid feedback rating rejection")

        test_invalid_strategy_rank_rejected(
            database_path,
            search_id,
        )
        passed += 1
        print("[PASS] invalid strategy rank rejection")

    # Rating normalisation is a pure in-memory check, so it runs after the temporary
    # database context has been closed.
    test_rating_normalisation()
    print("[PASS] rating normalisation")
    total += 1
    passed += 1

    print("\nSTRATEGY FEEDBACK STORAGE TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")


# Run the strategy-feedback storage regression suite only when executed directly.
if __name__ == "__main__":
    main()
