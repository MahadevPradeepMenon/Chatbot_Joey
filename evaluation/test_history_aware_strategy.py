from rag.joey_strategy_service import JoeyStrategyEvidence
from rag.strategy_history_ranker import (
    StrategyHistoryRanker,
    StrategyHistoryRecord,
)


def make_evidence(
    rank: int,
    score: float,
    code: str,
    title: str,
    collection: str,
) -> JoeyStrategyEvidence:
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

    ranker = StrategyHistoryRanker(history)
    evidence = make_evidence(
        1,
        0.0300,
        "B1",
        "Recognising Sensory Overload",
        "Sensory Collection",
    )

    result = ranker.rerank([evidence])[0]

    assert result.history_adjustment > 0
    assert "already recorded as active" in result.history_note


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

    results = ranker.rerank(
        [higher_relevance, close_previous_success]
    )

    assert results[0].strategy_code == "A2"
    assert "worked well" in results[0].history_note


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
    tests = [
        test_active_strategy_receives_positive_adjustment,
        test_positive_feedback_can_break_close_tie,
        test_negative_feedback_reduces_score,
        test_unseen_strategy_is_described_as_new,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("\n4/4 history-aware personalisation tests passed.")


if __name__ == "__main__":
    main()
