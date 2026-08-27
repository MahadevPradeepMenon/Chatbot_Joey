"""Regression tests for retrieval-confidence handling."""

from __future__ import annotations

from dataclasses import dataclass

from app.extractor import extract_structured_record
from rag.retrieval_confidence import (
    ConfidenceLevel,
    assess_retrieval_confidence,
    build_abstention_message,
)
from safety.safety_guard import should_limit_strategy_suggestions


# Use a minimal immutable stand-in that satisfies the confidence module's
# evidence protocol without depending on the full history-aware retriever.
@dataclass(frozen=True)
class FakeEvidence:
    """Minimal history-aware evidence used by confidence tests."""

    original_score: float
    strategy_code: str | None
    strategy_title: str | None
    collection_title: str
    source_file: str
    theme: str | None
    passage: str


def evidence(
    *,
    score: float,
    title: str,
    collection: str,
    theme: str,
    passage: str,
) -> FakeEvidence:
    """Create synthetic source-backed evidence."""

    # Keep test evidence construction consistent so each case varies only the
    # score, metadata and passage needed for that scenario.
    return FakeEvidence(
        original_score=score,
        strategy_code=None,
        strategy_title=title,
        collection_title=collection,
        source_file="approved_strategy_document.txt",
        theme=theme,
        passage=passage,
    )


def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable test failure."""

    # A tiny assertion helper keeps this script runnable without an external
    # testing framework while still producing readable failures.
    if not condition:
        raise AssertionError(message)


def test_clear_sensory_question_is_accepted() -> None:
    """A clear sensory question should retain strategy evidence."""

    # Provide strongly overlapping sensory evidence with relatively high original
    # Hybrid scores to exercise the strong-confidence branch.
    items = [
        evidence(
            score=0.0318,
            title="Sensory Processing Support",
            collection="Sensory Processing",
            theme="noise sensitivity",
            passage=(
                "For loud classroom noise, consider reducing sensory "
                "demand and offering a calmer space when the child "
                "covers their ears."
            ),
        ),
        evidence(
            score=0.0290,
            title="Emotional Regulation Support",
            collection="Emotional Regulation",
            theme="distress",
            passage=(
                "Use calm language when sensory distress begins."
            ),
        ),
    ]

    # The clear sensory wording deliberately overlaps directly with the approved
    # evidence passage and metadata.
    decision = assess_retrieval_confidence(
        (
            "My child covers their ears and becomes overwhelmed "
            "by loud classroom noise."
        ),
        items,
    )

    assert_true(
        decision.level == ConfidenceLevel.strong,
        "The clear sensory case should be strong.",
    )
    assert_true(
        not decision.should_abstain,
        "The clear sensory case should not abstain.",
    )


# Confirm that a second clear support domain also reaches an answerable
# confidence level rather than overfitting the rule to sensory examples.
def test_clear_sleep_question_is_accepted() -> None:
    """A clear sleep question should retain strategy evidence."""

    items = [
        evidence(
            score=0.0305,
            title="Sleep and Bedtime Support",
            collection="Sleep",
            theme="bedtime settling",
            passage=(
                "Use a predictable bedtime routine and reduce "
                "stimulating activity before sleep."
            ),
        )
    ]

    decision = assess_retrieval_confidence(
        (
            "Bedtime takes a long time and my child will not "
            "settle to sleep."
        ),
        items,
    )

    assert_true(
        decision.level == ConfidenceLevel.strong,
        "The clear sleep case should be strong.",
    )
    assert_true(
        not decision.should_abstain,
        "The clear sleep case should not abstain.",
    )


# Exercise the boundary where a concise but specific support question may be
# moderate or strong, but should still remain answerable.
def test_specific_but_brief_question_is_moderate() -> None:
    """A brief but relevant question may be shown cautiously."""

    items = [
        evidence(
            score=0.0250,
            title="Sleep Support",
            collection="Sleep and Bedtime",
            theme="bedtime",
            passage=(
                "Support anxiety around bedtime with a predictable "
                "routine and gradual settling."
            ),
        )
    ]

    decision = assess_retrieval_confidence(
        "My child becomes anxious at bedtime.",
        items,
    )

    assert_true(
        decision.level in {
            ConfidenceLevel.strong,
            ConfidenceLevel.moderate,
        },
        "The bedtime question should remain answerable.",
    )
    assert_true(
        not decision.should_abstain,
        "The bedtime question should not abstain.",
    )


# Verify that a technically unrelated question is rejected even when retrieved
# evidence has a non-trivial original score.
def test_unrelated_question_abstains() -> None:
    """A non-support technical question should not receive strategies."""

    items = [
        evidence(
            score=0.0290,
            title="Sensory Processing Support",
            collection="Sensory Processing",
            theme="noise",
            passage=(
                "Reduce sensory demands and offer a calm space."
            ),
        )
    ]

    decision = assess_retrieval_confidence(
        "How do I repair a laptop battery connector?",
        items,
    )

    assert_true(
        decision.level == ConfidenceLevel.weak,
        "The unrelated case should be weak.",
    )
    assert_true(
        decision.should_abstain,
        "The unrelated case should abstain.",
    )


# Verify that arbitrary tokens cannot obtain a strategy merely because the
# retriever always ranks some candidate first.
def test_meaningless_input_abstains() -> None:
    """Meaningless tokens should not receive arbitrary strategies."""

    items = [
        evidence(
            score=0.0310,
            title="Communication Support",
            collection="Communication",
            theme="expressive communication",
            passage="Use visual communication supports.",
        )
    ]

    decision = assess_retrieval_confidence(
        "asdf qwerty zxcv",
        items,
    )

    assert_true(
        decision.level == ConfidenceLevel.weak,
        "Meaningless input should be weak.",
    )
    assert_true(
        decision.should_abstain,
        "Meaningless input should abstain.",
    )


# Explicitly test the no-evidence guard: an otherwise sensible question still
# must abstain when the approved collection returns nothing.
def test_empty_evidence_abstains() -> None:
    """No retrieved evidence should always produce abstention."""

    decision = assess_retrieval_confidence(
        "What may help with bedtime anxiety?",
        [],
    )

    assert_true(
        decision.should_abstain,
        "Empty evidence should abstain.",
    )


def test_safety_screening_remains_first() -> None:
    """Safety-sensitive questions must be limited before confidence."""

    # Run the production deterministic extractor so safety priority is checked
    # using the same structured risk flags as the application workflow.
    record = extract_structured_record(
        (
            "During a meltdown my child is hitting their head "
            "and may be injured. What strategy should I use?"
        )
    )

    # Safety limiting is asserted independently of retrieval confidence because
    # the safety layer should take precedence over ordinary strategy presentation.
    assert_true(
        should_limit_strategy_suggestions(record),
        "The safety-sensitive case was not limited.",
    )


def test_abstention_wording_is_cautious() -> None:
    """The user-facing message should explain the evidence limitation."""

    # Check the stable user-facing abstention wording for relevance explanation,
    # approved-source boundary and a request for additional context.
    message = build_abstention_message()

    assert_true(
        "sufficiently relevant strategy" in message,
        "The abstention message should explain weak relevance.",
    )
    assert_true(
        "approved local Hey Joey library" in message,
        "The message should identify the approved source boundary.",
    )
    assert_true(
        "Could you describe" in message,
        "The message should ask for useful additional detail.",
    )


def main() -> None:
    """Run all retrieval-confidence regression tests."""

    # Keep all regression functions in an explicit ordered list so the script can
    # report deterministic progress when run locally or through CI.
    tests = [
        (
            "clear sensory question",
            test_clear_sensory_question_is_accepted,
        ),
        (
            "clear sleep question",
            test_clear_sleep_question_is_accepted,
        ),
        (
            "specific brief question",
            test_specific_but_brief_question_is_moderate,
        ),
        (
            "unrelated question abstention",
            test_unrelated_question_abstains,
        ),
        (
            "meaningless input abstention",
            test_meaningless_input_abstains,
        ),
        (
            "empty evidence abstention",
            test_empty_evidence_abstains,
        ),
        (
            "safety screening priority",
            test_safety_screening_remains_first,
        ),
        (
            "abstention wording",
            test_abstention_wording_is_cautious,
        ),
    ]

    passed = 0

    # Execute sequentially; any assertion failure stops the module with a non-zero
    # exit status that the CI suite can detect.
    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")

    print("\nRETRIEVAL CONFIDENCE TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


# Run the retrieval-confidence regression tests only when executed directly.
if __name__ == "__main__":
    main()
