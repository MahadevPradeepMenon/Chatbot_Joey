from rag.joey_strategy_service import JoeyStrategyEvidence
from rag.strategy_history_ranker import (
    StrategyHistoryRanker,
    StrategyHistoryRecord,
)


# Build consistent synthetic retrieval evidence so each test can vary only the
# ranking/history fields relevant to the scenario being exercised.
def make_evidence(
    rank: int,
    score: float,
    code: str,
    title: str,
    collection: str,
) -> JoeyStrategyEvidence:
    # Use fixed source/theme/passage metadata to keep the fixture deterministic.
    return JoeyStrategyEvidence(
        rank=rank,
        score=score,
        strategy_code=code,
        strategy_title=title,
        collection_title=collection,
        source_file="synthetic.docx",
        theme="Synthetic",
        chunk_id=f"chunk-{rank}",
        passage="Synthetic source-backed passage.",
    )


# Verify that an already-active strategy receives a small positive history signal
# and exposes the corresponding parent-facing history note.
def test_active_strategy_receives_positive_adjustment() -> None:
    history = [
        StrategyHistoryRecord(
            strategy_code="B1",
            strategy_title="Recognising Sensory Overload",
            collection_title="Sensory Collection",
            source_file="synthetic.docx",
            lifecycle_status="active",
            latest_outcome="not_recorded",
            times_used=1,
        )
    ]

    # Inject only the synthetic history needed for this regression case.
    ranker = StrategyHistoryRanker(history)
    evidence = make_evidence(
        1,
        0.0300,
        "B1",
        "Recognising Sensory Overload",
        "Sensory Collection",
    )

    # Rerank a single matching strategy and inspect the applied adjustment/note.
    result = ranker.rerank([evidence])[0]

    assert result.history_adjustment > 0
    assert "already recorded as active" in result.history_note


# Confirm that a previously successful strategy can move ahead when two Hybrid
# relevance scores are close, without replacing relevance entirely.
def test_positive_feedback_can_break_close_tie() -> None:
    history = [
        StrategyHistoryRecord(
            strategy_code="A2",
            strategy_title="Early Warning Signs",
            collection_title="Sensory Collection",
            source_file="synthetic.docx",
            lifecycle_status="not_active",
            latest_outcome="worked_great",
            times_used=2,
        )
    ]

    ranker = StrategyHistoryRanker(history)

    higher_relevance = make_evidence(
        1,
        0.0310,
        "C1",
        "New Strategy",
        "Sensory Collection",
    )
    close_previous_success = make_evidence(
        2,
        0.0300,
        "A2",
        "Early Warning Signs",
        "Sensory Collection",
    )

    # Present the slightly higher-relevance unseen strategy first; the expected
# rerank tests whether positive history can break this close ordering.
    results = ranker.rerank(
        [higher_relevance, close_previous_success]
    )

    assert results[0].strategy_code == "A2"
    assert "worked well" in results[0].history_note


# Verify that strongly negative prior feedback applies a negative adjustment and
# is reflected in cautious explanatory wording.
def test_negative_feedback_reduces_score() -> None:
    history = [
        StrategyHistoryRecord(
            strategy_code="D3",
            strategy_title="Previous Strategy",
            collection_title="Sensory Collection",
            source_file="synthetic.docx",
            lifecycle_status="not_active",
            latest_outcome="disaster",
            times_used=1,
        )
    ]

    ranker = StrategyHistoryRanker(history)
    evidence = make_evidence(
        1,
        0.0300,
        "D3",
        "Previous Strategy",
        "Sensory Collection",
    )

    result = ranker.rerank([evidence])[0]

    assert result.history_adjustment < 0
    assert "did not work well" in result.history_note


# Ensure strategies with no matching history remain unadjusted and are described
# neutrally as new options.
def test_unseen_strategy_is_described_as_new() -> None:
    ranker = StrategyHistoryRanker([])
    evidence = make_evidence(
        1,
        0.0300,
        "X1",
        "Unseen Strategy",
        "Sensory Collection",
    )

    result = ranker.rerank([evidence])[0]

    assert result.history_adjustment == 0.0
    assert "new strategy option" in result.history_note


def main() -> None:
    # Keep the regression functions in a fixed ordered list so standalone and CI
    # execution produce deterministic progress output.
    tests = [
        test_active_strategy_receives_positive_adjustment,
        test_positive_feedback_can_break_close_tie,
        test_negative_feedback_reduces_score,
        test_unseen_strategy_is_described_as_new,
    ]

    # Any failed assertion stops the module with a non-zero exit status that the
    # wider CI runner can detect.
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("\n4/4 history-aware personalisation tests passed.")


# Run the history-aware personalisation regressions only when executed directly.
if __name__ == "__main__":
    main()

