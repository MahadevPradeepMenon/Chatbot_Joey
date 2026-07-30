"""Convert stored SQLite feedback into history-aware ranking records."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rag.strategy_history_ranker import (
    StrategyHistoryRecord,
    normalise_title,
)
from storage.strategy_feedback import (
    StrategyFeedbackRating,
    StoredStrategyFeedback,
    list_strategy_feedback,
)


RATING_TO_HISTORY_OUTCOME: dict[
    StrategyFeedbackRating,
    str,
] = {
    StrategyFeedbackRating.worked_well: "worked_great",
    StrategyFeedbackRating.helped_somewhat: "worked_somewhat",
    StrategyFeedbackRating.not_relevant: "not_relevant",
    StrategyFeedbackRating.did_not_work_well: "disaster",
}



@dataclass
class _FeedbackAggregate:
    """Typed accumulator for one strategy's stored feedback."""

    latest: StoredStrategyFeedback
    times_used: int = 0


def _clean(value: str | None) -> str:
    """Return a cautious normalised comparison value."""

    return " ".join(
        str(value or "").strip().lower().split()
    )


def strategy_identity(
    strategy_code: str | None,
    strategy_title: str | None,
    collection_title: str | None,
    source_file: str | None,
) -> tuple[str, str, str, str]:
    """Return a stable identity for stored or synthetic history."""

    return (
        _clean(strategy_code),
        normalise_title(strategy_title),
        _clean(collection_title),
        _clean(source_file),
    )


def records_match(
    first: StrategyHistoryRecord,
    second: StrategyHistoryRecord,
) -> bool:
    """Use the same cautious identity logic as the history ranker."""

    first_code = _clean(first.strategy_code)
    second_code = _clean(second.strategy_code)

    code_matches = (
        bool(first_code)
        and bool(second_code)
        and first_code == second_code
    )

    title_matches = (
        normalise_title(first.strategy_title)
        == normalise_title(second.strategy_title)
    )

    collection_matches = (
        bool(first.collection_title)
        and bool(second.collection_title)
        and _clean(first.collection_title)
        == _clean(second.collection_title)
    )

    source_matches = (
        bool(first.source_file)
        and bool(second.source_file)
        and _clean(first.source_file)
        == _clean(second.source_file)
    )

    if code_matches and (
        collection_matches
        or source_matches
    ):
        return True

    if title_matches and (
        collection_matches
        or source_matches
    ):
        return True

    return bool(title_matches)


def feedback_to_outcome(
    rating: StrategyFeedbackRating,
) -> str:
    """Map one stored rating to the ranker's existing outcome language."""

    return RATING_TO_HISTORY_OUTCOME[rating]


def load_stored_feedback_history(
    database_path: str | Path | None = None,
    limit: int = 1000,
) -> list[StrategyHistoryRecord]:
    """
    Aggregate stored feedback into one history record per strategy.

    Feedback is returned newest first by the storage layer. The first
    feedback encountered for a strategy therefore becomes its latest
    outcome, while all matching records contribute to times_used.
    """

    feedback_items = list_strategy_feedback(
        limit=limit,
        database_path=database_path,
    )

    grouped: OrderedDict[
        tuple[str, str, str, str],
        _FeedbackAggregate,
    ] = OrderedDict()

    for item in feedback_items:
        identity = strategy_identity(
            item.strategy_code,
            item.strategy_title,
            item.collection_title,
            item.source_file,
        )

        if identity not in grouped:
            grouped[identity] = _FeedbackAggregate(
                latest=item,
            )

        grouped[identity].times_used += 1

    records: list[StrategyHistoryRecord] = []

    for group in grouped.values():
        latest = group.latest

        strategy_title = (
            latest.strategy_title
            or latest.collection_title
        )

        records.append(
            StrategyHistoryRecord(
                strategy_code=latest.strategy_code,
                strategy_title=strategy_title,
                collection_title=latest.collection_title,
                source_file=latest.source_file,
                lifecycle_status="not_active",
                latest_outcome=feedback_to_outcome(
                    latest.rating
                ),
                times_used=group.times_used,
            )
        )

    return records


def merge_strategy_history(
    base_records: Iterable[StrategyHistoryRecord],
    stored_records: Iterable[StrategyHistoryRecord],
) -> list[StrategyHistoryRecord]:
    """
    Merge stored feedback into synthetic or product history.

    Stored feedback is authoritative for the latest outcome. Existing
    lifecycle status is preserved because feedback does not itself mean
    that a strategy is active, paused or archived.
    """

    merged = list(base_records)

    for stored in stored_records:
        matching_index: int | None = None

        for index, existing in enumerate(
            merged
        ):
            if records_match(
                existing,
                stored,
            ):
                matching_index = index
                break

        if matching_index is None:
            merged.append(stored)
            continue

        existing = merged[
            matching_index
        ]

        merged[matching_index] = (
            StrategyHistoryRecord(
                strategy_code=(
                    existing.strategy_code
                    or stored.strategy_code
                ),
                strategy_title=(
                    existing.strategy_title
                    or stored.strategy_title
                ),
                collection_title=(
                    existing.collection_title
                    or stored.collection_title
                ),
                source_file=(
                    existing.source_file
                    or stored.source_file
                ),
                lifecycle_status=(
                    existing.lifecycle_status
                ),
                latest_outcome=(
                    stored.latest_outcome
                ),
                times_used=max(
                    existing.times_used,
                    stored.times_used,
                ),
            )
        )

    return merged