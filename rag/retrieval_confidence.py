"""Evidence-quality assessment for Hey Joey strategy retrieval."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Protocol


# Use simple lowercase alphanumeric tokenisation so overlap calculations remain
# deterministic and easy to explain.
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SPACE_PATTERN = re.compile(r"\s+")

# Common words that do not help distinguish one support need from another.
# Removing these words keeps the confidence signal focused on support-specific content.
STOP_WORDS = {
    "a",
    "about",
    "after",
    "again",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "around",
    "as",
    "at",
    "be",
    "because",
    "before",
    "being",
    "but",
    "by",
    "can",
    "child",
    "children",
    "could",
    "do",
    "does",
    "for",
    "from",
    "get",
    "gets",
    "getting",
    "going",
    "had",
    "has",
    "have",
    "having",
    "he",
    "help",
    "her",
    "here",
    "him",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "me",
    "might",
    "my",
    "of",
    "on",
    "or",
    "our",
    "please",
    "she",
    "should",
    "some",
    "something",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
}

# Small, transparent normalisation map for common support-domain wording.
# The mapping is intentionally limited so token equivalence remains inspectable.
TOKEN_ALIASES = {
    "anxious": "anxiety",
    "anxieties": "anxiety",
    "behaviour": "behavior",
    "behaviours": "behavior",
    "behavioral": "behavior",
    "behavioural": "behavior",
    "bedtimes": "bedtime",
    "communicating": "communication",
    "communicate": "communication",
    "conversations": "conversation",
    "distressed": "distress",
    "distressing": "distress",
    "eating": "food",
    "foods": "food",
    "friendships": "friendship",
    "friends": "friendship",
    "hygienic": "hygiene",
    "meltdowns": "meltdown",
    "noises": "noise",
    "noisy": "noise",
    "sensitivities": "sensitivity",
    "sleeping": "sleep",
    "slept": "sleep",
    "socially": "social",
    "toileting": "toilet",
    "toilets": "toilet",
    "washing": "wash",
}


# Confidence is expressed as a small categorical evidence-quality scale rather
# than as a calibrated probability.
class ConfidenceLevel(str, Enum):
    """Internal evidence-quality categories."""

    strong = "strong"
    moderate = "moderate"
    weak = "weak"


# A structural protocol lets this module assess different evidence dataclasses
# without depending on one concrete retrieval-result implementation.
class StrategyEvidenceLike(Protocol):
    """
    Read-only fields required from strategy evidence.

    Properties allow Pylance to recognise frozen dataclasses such as
    HistoryAwareStrategyEvidence and the synthetic test evidence as
    structurally compatible with this protocol.
    """

    @property
    def original_score(self) -> float:
        """Return the original Hybrid retrieval score."""
        ...

    @property
    def strategy_code(self) -> str | None:
        """Return the optional approved strategy code."""
        ...

    @property
    def strategy_title(self) -> str | None:
        """Return the optional strategy title."""
        ...

    @property
    def collection_title(self) -> str:
        """Return the approved collection title."""
        ...

    @property
    def source_file(self) -> str:
        """Return the source document filename."""
        ...

    @property
    def theme(self) -> str | None:
        """Return the optional strategy theme."""
        ...

    @property
    def passage(self) -> str:
        """Return the source-backed strategy passage."""
        ...


# Freeze confidence decisions so the evidence-quality assessment is immutable
# after it has been calculated.
@dataclass(frozen=True)
class RetrievalConfidenceDecision:
    """Transparent decision about whether evidence should be shown."""

    level: ConfidenceLevel
    should_abstain: bool
    reason: str
    query_token_count: int
    evidence_count: int
    top_original_score: float
    top_overlap_count: int
    top_overlap_ratio: float
    overlapping_evidence_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return a serialisable decision for tests and future logging."""

        return asdict(self)


def _normalise_token(token: str) -> str:
    """Normalise one token using cautious aliases and light stemming."""

    clean = token.lower().strip()

    if not clean:
        return ""

    # Apply explicit domain aliases before light suffix handling.
    if clean in TOKEN_ALIASES:
        return TOKEN_ALIASES[clean]

    # Light plural normalisation. Avoid aggressive stemming because
    # explainability is more important than maximum recall here.
    # Only a few transparent suffix rules are applied before a second alias lookup.
    # explainability is more important than maximum recall here.
    if len(clean) > 4 and clean.endswith("ies"):
        clean = clean[:-3] + "y"
    elif len(clean) > 4 and clean.endswith("es"):
        clean = clean[:-2]
    elif len(clean) > 3 and clean.endswith("s"):
        clean = clean[:-1]

    return TOKEN_ALIASES.get(clean, clean)


def content_tokens(text: str | None) -> set[str]:
    """Return meaningful, normalised tokens from user or evidence text."""

    # Tokenise first, then remove stop words and normalise the remaining content terms.
    raw_tokens = TOKEN_PATTERN.findall(
        str(text or "").lower()
    )

    tokens = {
        _normalise_token(token)
        for token in raw_tokens
        if token not in STOP_WORDS
    }

    # Filter again after normalisation because aliases/stemming can produce words
    # that should still be excluded from the overlap signal.
    return {
        token
        for token in tokens
        if token
        and token not in STOP_WORDS
        and len(token) > 1
    }


def evidence_text(item: StrategyEvidenceLike) -> str:
    """Combine source-backed fields used only for overlap assessment."""

    # Assess overlap against both passage text and provenance/strategy metadata so
    # a relevant collection or title can contribute to the evidence match.
    values = [
        item.strategy_code,
        item.strategy_title,
        item.collection_title,
        item.theme,
        item.source_file,
        item.passage,
    ]

    return SPACE_PATTERN.sub(
        " ",
        " ".join(
            str(value)
            for value in values
            if value
        ),
    ).strip()


def _overlap_metrics(
    query_tokens: set[str],
    item: StrategyEvidenceLike,
) -> tuple[int, float]:
    """Return overlap count and bounded ratio for one evidence item."""

    if not query_tokens:
        return 0, 0.0

    # Compare normalised content-token sets so repeated words do not inflate overlap.
    item_tokens = content_tokens(
        evidence_text(item)
    )
    overlap_count = len(
        query_tokens.intersection(item_tokens)
    )

    # Cap the denominator so longer natural-language questions are not
    # unfairly penalised for containing additional useful detail.
    # The ratio therefore measures overlap against at most eight query content tokens.
    # unfairly penalised for containing additional useful detail.
    denominator = max(
        min(len(query_tokens), 8),
        1,
    )

    return (
        overlap_count,
        overlap_count / denominator,
    )


def assess_retrieval_confidence(
    question: str,
    evidence: Iterable[StrategyEvidenceLike],
) -> RetrievalConfidenceDecision:
    """
    Decide whether retrieved evidence is suitable to present.

    This is an explainable abstention rule, not a probability estimate.
    It uses the original Hybrid score so history adjustments cannot turn
    weak retrieval evidence into apparently strong evidence.
    """

    # Normalise whitespace and materialise the evidence iterable once so the same
    # ordered evidence can be reused for all confidence calculations.
    clean_question = SPACE_PATTERN.sub(
        " ",
        str(question or ""),
    ).strip()
    items = list(evidence)
    query_tokens = content_tokens(
        clean_question
    )

    # Empty questions always abstain because there is no user evidence to match.
    if not clean_question:
        return RetrievalConfidenceDecision(
            level=ConfidenceLevel.weak,
            should_abstain=True,
            reason="The strategy question was empty.",
            query_token_count=0,
            evidence_count=len(items),
            top_original_score=0.0,
            top_overlap_count=0,
            top_overlap_ratio=0.0,
            overlapping_evidence_count=0,
        )

    # No retrieved evidence also forces abstention, regardless of the question.
    if not items:
        return RetrievalConfidenceDecision(
            level=ConfidenceLevel.weak,
            should_abstain=True,
            reason=(
                "The approved local collection returned no "
                "strategy evidence."
            ),
            query_token_count=len(query_tokens),
            evidence_count=0,
            top_original_score=0.0,
            top_overlap_count=0,
            top_overlap_ratio=0.0,
            overlapping_evidence_count=0,
        )

    # Calculate transparent lexical-overlap signals for every retrieved evidence item.
    overlap_rows = [
        _overlap_metrics(
            query_tokens,
            item,
        )
        for item in items
    ]

    # Confidence uses the leading retrieved item plus a count of how many returned
    # items have any direct overlap with the question.
    top_overlap_count, top_overlap_ratio = overlap_rows[0]
    overlapping_evidence_count = sum(
        count > 0
        for count, _ in overlap_rows
    )

    # Use the original Hybrid retrieval score rather than any later history-based
    # adjustment so personalisation cannot strengthen weak underlying evidence.
    top_original_score = max(
        float(items[0].original_score),
        0.0,
    )

    # Very short or content-free questions should not be answered merely
    # because the retriever can always rank something first.
    # Fewer than two meaningful content tokens is treated as insufficient context.
    # because the retriever can always rank something first.
    if len(query_tokens) < 2:
        return RetrievalConfidenceDecision(
            level=ConfidenceLevel.weak,
            should_abstain=True,
            reason=(
                "The question did not contain enough specific "
                "support information."
            ),
            query_token_count=len(query_tokens),
            evidence_count=len(items),
            top_original_score=top_original_score,
            top_overlap_count=top_overlap_count,
            top_overlap_ratio=round(
                top_overlap_ratio,
                4,
            ),
            overlapping_evidence_count=(
                overlapping_evidence_count
            ),
        )

    # Strong evidence requires substantial direct overlap, or a combination of
    # moderate overlap and a sufficiently high original Hybrid score.
    strong = (
        top_overlap_count >= 3
        or (
            top_overlap_count >= 2
            and top_original_score >= 0.024
        )
        or (
            top_overlap_ratio >= 0.40
            and top_original_score >= 0.022
        )
    )

    if strong:
        return RetrievalConfidenceDecision(
            level=ConfidenceLevel.strong,
            should_abstain=False,
            reason=(
                "The leading source has strong query overlap and "
                "a sufficiently high original Hybrid score."
            ),
            query_token_count=len(query_tokens),
            evidence_count=len(items),
            top_original_score=top_original_score,
            top_overlap_count=top_overlap_count,
            top_overlap_ratio=round(
                top_overlap_ratio,
                4,
            ),
            overlapping_evidence_count=(
                overlapping_evidence_count
            ),
        )

    # Moderate evidence accepts a weaker match only when supported by the original
    # Hybrid score or corroborating overlap across multiple evidence items.
    moderate = (
        (
            top_overlap_count >= 1
            and top_original_score >= 0.021
        )
        or (
            overlapping_evidence_count >= 2
            and top_original_score >= 0.019
        )
    )

    if moderate:
        return RetrievalConfidenceDecision(
            level=ConfidenceLevel.moderate,
            should_abstain=False,
            reason=(
                "The evidence has a usable but limited match. "
                "It may be shown with cautious wording."
            ),
            query_token_count=len(query_tokens),
            evidence_count=len(items),
            top_original_score=top_original_score,
            top_overlap_count=top_overlap_count,
            top_overlap_ratio=round(
                top_overlap_ratio,
                4,
            ),
            overlapping_evidence_count=(
                overlapping_evidence_count
            ),
        )

    # Anything that fails the strong and moderate rules abstains rather than
    # presenting a strategy with weak direct support.
    return RetrievalConfidenceDecision(
        level=ConfidenceLevel.weak,
        should_abstain=True,
        reason=(
            "The retrieved evidence did not have enough direct "
            "support overlap to justify presenting a strategy."
        ),
        query_token_count=len(query_tokens),
        evidence_count=len(items),
        top_original_score=top_original_score,
        top_overlap_count=top_overlap_count,
        top_overlap_ratio=round(
            top_overlap_ratio,
            4,
        ),
        overlapping_evidence_count=overlapping_evidence_count,
    )


# Keep abstention wording separate from the scoring rule so the user-facing
# response remains consistent wherever weak evidence is handled.
def build_abstention_message() -> str:
    """Return cautious user-facing wording for weak retrieval evidence."""

    return (
        "I could not find a sufficiently relevant strategy in the "
        "approved local Hey Joey library from the information provided. "
        "Could you describe what happens, where it happens and what "
        "seems to happen beforehand?"
    )

