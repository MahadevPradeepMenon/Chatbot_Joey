"""Regression tests for SQLite feedback-aware strategy ranking."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from rag.context_aware_strategy_service import (
    ContextAwareStrategyService,
)
from rag.history_aware_strategy_service import (
    HistoryAwareStrategyService,
)
from rag.joey_strategy_service import (
    JoeyStrategyEvidence,
)
from rag.strategy_history_ranker import (
    StrategyHistoryRanker,
    StrategyHistoryRecord,
)
from storage.feedback_history_provider import (
    load_stored_feedback_history,
    merge_strategy_history,
)
from storage.strategy_feedback import (
    save_strategy_feedback,
    save_strategy_search,
)


# Use a minimal immutable evidence shape that matches the storage API expected by
# strategy-search persistence without depending on the full application service.
@dataclass(frozen=True)
class FakeDisplayedEvidence:
    """Evidence shape accepted by strategy-search storage."""

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


# Build deterministic evidence for the persisted-search side of the test workflow.
def displayed_evidence(
    code: str,
    title: str,
    score: float,
) -> FakeDisplayedEvidence:
    return FakeDisplayedEvidence(
        original_rank=1,
        original_score=score,
        history_adjustment=0.0,
        personalised_score=score,
        strategy_code=code,
        strategy_title=title,
        collection_title="Sensory Processing",
        source_file="sensory_support.txt",
        theme="noise sensitivity",
        chunk_id=f"{code}-chunk",
        passage="Synthetic approved support passage.",
    )


# Build matching JoeyStrategyEvidence objects for the reranking side of the tests.
def retrieval_evidence(
    rank: int,
    score: float,
    code: str,
    title: str,
) -> JoeyStrategyEvidence:
    return JoeyStrategyEvidence(
        rank=rank,
        score=score,
        strategy_code=code,
        strategy_title=title,
        collection_title="Sensory Processing",
        source_file="sensory_support.txt",
        theme="noise sensitivity",
        chunk_id=f"{code}-chunk",
        passage="Synthetic approved support passage.",
    )


def assert_true(
    condition: bool,
    message: str,
) -> None:
    # Keep the module runnable as a standalone regression script without requiring
    # an external testing framework.
    if not condition:
        raise AssertionError(message)


def save_feedback_example(
    database_path: Path,
    code: str,
    title: str,
    rating: str,
) -> int:
    # Persist the exact displayed strategy first so feedback can be linked to the
    # same search/result rank in SQLite.
    search_id = save_strategy_search(
        question="What may help with loud classroom noise?",
        retrieval_query="loud classroom noise sensory support",
        evidence=[
            displayed_evidence(
                code,
                title,
                0.0300,
            )
        ],
        confidence_level="strong",
        source="stored_feedback_ranking_test",
        database_path=database_path,
    )

    # Save one rating against display rank 1, exercising the same storage path used
    # by the application feedback workflow.
    save_strategy_feedback(
        search_id=search_id,
        strategy_rank=1,
        rating=rating,
        database_path=database_path,
    )

    return search_id


# Verify that the user-facing "worked well" rating is converted into the history
# ranker's internal worked_great outcome label.
def test_worked_well_mapping(
    database_path: Path,
) -> None:
    save_feedback_example(
        database_path,
        "SP-01",
        "Sensory Processing Support",
        "worked well",
    )

    records = load_stored_feedback_history(
        database_path
    )

    assert_true(
        records[0].latest_outcome
        == "worked_great",
        "Worked well was not mapped to worked_great.",
    )


# Add a second feedback record for the same strategy and confirm newest-first
# aggregation plus cumulative usage counting.
def test_latest_feedback_and_usage_count(
    database_path: Path,
) -> None:
    save_feedback_example(
        database_path,
        "SP-01",
        "Sensory Processing Support",
        "not relevant",
    )

    records = load_stored_feedback_history(
        database_path
    )
    # Locate the aggregated record by stable strategy code before checking outcome
    # and use-count behaviour.
    matching = next(
        record
        for record in records
        if record.strategy_code == "SP-01"
    )

    assert_true(
        matching.latest_outcome
        == "not_relevant",
        "The newest stored feedback was not used.",
    )
    assert_true(
        matching.times_used == 2,
        "The stored feedback use count should be 2.",
    )


# Confirm that stored feedback updates the latest outcome while preserving the
# lifecycle state supplied by the base/synthetic history record.
def test_merge_preserves_lifecycle(
    database_path: Path,
) -> None:
    stored = load_stored_feedback_history(
        database_path
    )
    base = [
        StrategyHistoryRecord(
            strategy_code="SP-01",
            strategy_title="Sensory Processing Support",
            collection_title="Sensory Processing",
            source_file="sensory_support.txt",
            lifecycle_status="active",
            latest_outcome="not_recorded",
            times_used=0,
        )
    ]

    # Merge persisted feedback into the existing lifecycle-aware history model.
    merged = merge_strategy_history(
        base,
        stored,
    )
    matching = next(
        record
        for record in merged
        if record.strategy_code == "SP-01"
    )

    assert_true(
        matching.lifecycle_status
        == "active",
        "Stored feedback should not replace lifecycle status.",
    )
    assert_true(
        matching.latest_outcome
        == "not_relevant",
        "Stored feedback should replace the latest outcome.",
    )


# Verify that positive history can reorder two closely scored retrieval results
# while still operating as a small adjustment on top of Hybrid relevance.
def test_positive_feedback_breaks_close_tie() -> None:
    history = [
        StrategyHistoryRecord(
            strategy_code="B",
            strategy_title="Second Strategy",
            collection_title="Sensory Processing",
            source_file="sensory_support.txt",
            lifecycle_status="not_active",
            latest_outcome="worked_great",
            times_used=1,
        )
    ]

    ranker = StrategyHistoryRanker(
        history
    )
    results = ranker.rerank(
        [
            retrieval_evidence(
                1,
                0.0300,
                "A",
                "First Strategy",
            ),
            retrieval_evidence(
                2,
                0.0290,
                "B",
                "Second Strategy",
            ),
        ]
    )

    assert_true(
        results[0].strategy_code == "B",
        "Positive feedback did not break the close tie.",
    )
    assert_true(
        results[0].history_adjustment > 0,
        "Positive feedback should produce a positive adjustment.",
    )


# Check that not-relevant feedback produces a negative score adjustment and a
# matching explanatory history note.
def test_not_relevant_reduces_score() -> None:
    history = StrategyHistoryRecord(
        strategy_code="A",
        strategy_title="First Strategy",
        collection_title="Sensory Processing",
        source_file="sensory_support.txt",
        lifecycle_status="not_active",
        latest_outcome="not_relevant",
        times_used=1,
    )

    adjustment = (
        StrategyHistoryRanker.calculate_adjustment(
            history
        )
    )

    assert_true(
        adjustment < 0,
        "Not relevant should reduce the ranking score.",
    )

    note = StrategyHistoryRanker.build_history_note(
        history
    )

    assert_true(
        "not relevant" in note.lower(),
        "The history note should describe not-relevant feedback.",
    )


# Check that strongly negative feedback maps to a negative reranking adjustment.
def test_did_not_work_well_reduces_score() -> None:
    history = StrategyHistoryRecord(
        strategy_code="A",
        strategy_title="First Strategy",
        collection_title="Sensory Processing",
        source_file="sensory_support.txt",
        lifecycle_status="not_active",
        latest_outcome="disaster",
        times_used=1,
    )

    adjustment = (
        StrategyHistoryRanker.calculate_adjustment(
            history
        )
    )

    assert_true(
        adjustment < 0,
        "Did not work well should reduce the ranking score.",
    )


# Provide a deterministic context-aware retrieval result so service-level tests
# can isolate feedback reloading and reranking behaviour from live retrieval.
class FakeBaseService:
    """Return a deterministic context-aware retrieval result."""

    def retrieve(
        self,
        question: str,
        top_k: int = 6,
    ) -> SimpleNamespace:
        evidence = [
            retrieval_evidence(
                1,
                0.0300,
                "A",
                "First Strategy",
            ),
            retrieval_evidence(
                2,
                0.0290,
                "B",
                "Second Strategy",
            ),
        ]

        return SimpleNamespace(
            question=question,
            context=SimpleNamespace(),
            retrieval_query=question,
            evidence=evidence[:top_k],
        )


# Confirm that persisted history is requested on every search rather than cached
# for the lifetime of the history-aware service.
def test_service_loads_feedback_each_search() -> None:
    loader_calls = 0

    # Count loader calls explicitly so the test can prove per-request feedback reloads.
    def loader() -> list[
        StrategyHistoryRecord
    ]:
        nonlocal loader_calls
        loader_calls += 1

        return [
            StrategyHistoryRecord(
                strategy_code="B",
                strategy_title="Second Strategy",
                collection_title="Sensory Processing",
                source_file="sensory_support.txt",
                lifecycle_status="not_active",
                latest_outcome="worked_great",
                times_used=1,
            )
        ]

    # Inject the fake base service, empty base history and counting loader to keep
    # the regression deterministic and independent of the real SQLite path.
    service = HistoryAwareStrategyService(
        base_service=cast(
            ContextAwareStrategyService,
            FakeBaseService(),
        ),
        history_ranker=StrategyHistoryRanker(
            history_records=[]
        ),
        stored_history_loader=loader,
    )

    # Perform two searches so both reranking outcome and loader call frequency can
    # be asserted independently.
    first = service.retrieve(
        "noise support",
        top_k=2,
        candidate_pool=2,
    )
    second = service.retrieve(
        "noise support",
        top_k=2,
        candidate_pool=2,
    )

    assert_true(
        first.evidence[0].strategy_code
        == "B",
        "Stored feedback was not applied by the service.",
    )
    assert_true(
        second.evidence[0].strategy_code
        == "B",
        "Stored feedback was not reloaded for the next search.",
    )
    assert_true(
        loader_calls == 2,
        "Stored feedback should be loaded before every search.",
    )


def main() -> None:
    passed = 0
    tests_total = 7

    # Use an isolated temporary SQLite database so storage regressions do not touch
    # the project's normal local data.
    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "stored_feedback_ranking.db"
        )

        test_worked_well_mapping(
            database_path
        )
        passed += 1
        print("[PASS] worked-well feedback mapping")

        test_latest_feedback_and_usage_count(
            database_path
        )
        passed += 1
        print("[PASS] latest feedback and usage count")

        test_merge_preserves_lifecycle(
            database_path
        )
        passed += 1
        print("[PASS] stored and synthetic history merge")

    # The remaining tests are pure in-memory reranking/service checks and therefore
    # do not need the temporary database created above.
    test_positive_feedback_breaks_close_tie()
    passed += 1
    print("[PASS] positive feedback close-tie ranking")

    test_not_relevant_reduces_score()
    passed += 1
    print("[PASS] not-relevant score reduction")

    test_did_not_work_well_reduces_score()
    passed += 1
    print("[PASS] did-not-work-well score reduction")

    test_service_loads_feedback_each_search()
    passed += 1
    print("[PASS] service reloads stored feedback")

    print("\nSTORED FEEDBACK RANKING TEST RESULTS")
    print("=" * 60)
    print(
        f"Tests passed: {passed}/{tests_total}"
    )


# Run the stored-feedback ranking regressions only when executed directly.
if __name__ == "__main__":
    main()
