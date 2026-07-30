from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from rag.joey_strategy_service import JoeyStrategyEvidence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_FILE = (
    PROJECT_ROOT
    / "data"
    / "synthetic"
    / "synthetic_strategy_history.json"
)

TITLE_NORMALISER = re.compile(r"[^a-z0-9]+")

STATUS_ADJUSTMENTS: dict[str, float] = {
    "active": 0.0025,
    "paused": -0.0005,
    "archived": -0.0010,
    "deleted": -0.0010,
}

OUTCOME_ADJUSTMENTS: dict[str, float] = {
    "worked_great": 0.0020,
    "worked_somewhat": 0.0010,
    "not_relevant": -0.0010,
    "disaster": -0.0015,
    "not_recorded": 0.0,
}


@dataclass(frozen=True)
class StrategyHistoryRecord:
    """Synthetic or database-backed history for one strategy."""

    strategy_code: str | None
    strategy_title: str
    collection_title: str | None
    source_file: str | None
    lifecycle_status: str
    latest_outcome: str
    times_used: int

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "StrategyHistoryRecord":
        return cls(
            strategy_code=data.get("strategy_code"),
            strategy_title=str(
                data.get("strategy_title", "")
            ).strip(),
            collection_title=(
                str(data.get("collection_title")).strip()
                if data.get("collection_title")
                else None
            ),
            source_file=(
                str(data.get("source_file")).strip()
                if data.get("source_file")
                else None
            ),
            lifecycle_status=str(
                data.get(
                    "lifecycle_status",
                    "not_active",
                )
            ).strip().lower(),
            latest_outcome=str(
                data.get(
                    "latest_outcome",
                    "not_recorded",
                )
            ).strip().lower(),
            times_used=max(
                int(
                    data.get(
                        "times_used",
                        0,
                    )
                ),
                0,
            ),
        )


@dataclass(frozen=True)
class HistoryAwareStrategyEvidence:
    """One Hybrid result with a transparent history adjustment."""

    rank: int
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
    lifecycle_status: str
    latest_outcome: str
    times_used: int
    history_note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise_title(
    title: str | None,
) -> str:
    """Normalise titles for cautious fallback matching."""

    if not title:
        return ""

    return TITLE_NORMALISER.sub(
        " ",
        title.lower(),
    ).strip()


def load_strategy_history(
    path: Path = DEFAULT_HISTORY_FILE,
) -> list[StrategyHistoryRecord]:
    """Load synthetic strategy history records."""

    if not path.exists():
        raise FileNotFoundError(
            f"Synthetic strategy history not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    records = data.get(
        "strategy_history",
        data,
    )

    if not isinstance(
        records,
        list,
    ):
        raise ValueError(
            "The strategy history file must contain a list "
            "or a 'strategy_history' list."
        )

    return [
        StrategyHistoryRecord.from_dict(
            record
        )
        for record in records
    ]


class StrategyHistoryRanker:
    """
    Apply small, transparent adjustments to Hybrid results.

    History never replaces relevance. Adjustments are deliberately small
    and are intended only to order otherwise similar candidates.
    """

    def __init__(
        self,
        history_records: Iterable[
            StrategyHistoryRecord
        ] | None = None,
    ) -> None:
        self.history_records = list(
            history_records
            if history_records is not None
            else load_strategy_history()
        )

    def rerank(
        self,
        evidence: list[
            JoeyStrategyEvidence
        ],
    ) -> list[
        HistoryAwareStrategyEvidence
    ]:
        """Return evidence ranked by relevance plus history signals."""

        scored: list[
            tuple[
                float,
                JoeyStrategyEvidence,
                StrategyHistoryRecord | None,
                float,
                str,
            ]
        ] = []

        for item in evidence:
            history = self.find_history(
                item
            )
            adjustment = (
                self.calculate_adjustment(
                    history
                )
            )
            personalised_score = (
                item.score
                + adjustment
            )
            note = self.build_history_note(
                history
            )

            scored.append(
                (
                    personalised_score,
                    item,
                    history,
                    adjustment,
                    note,
                )
            )

        scored.sort(
            key=lambda row: (
                row[0],
                row[1].score,
                -row[1].rank,
            ),
            reverse=True,
        )

        results: list[
            HistoryAwareStrategyEvidence
        ] = []

        for new_rank, (
            personalised_score,
            item,
            history,
            adjustment,
            note,
        ) in enumerate(
            scored,
            start=1,
        ):
            results.append(
                HistoryAwareStrategyEvidence(
                    rank=new_rank,
                    original_rank=item.rank,
                    original_score=item.score,
                    history_adjustment=(
                        adjustment
                    ),
                    personalised_score=(
                        personalised_score
                    ),
                    strategy_code=(
                        item.strategy_code
                    ),
                    strategy_title=(
                        item.strategy_title
                    ),
                    collection_title=(
                        item.collection_title
                    ),
                    source_file=(
                        item.source_file
                    ),
                    theme=item.theme,
                    chunk_id=item.chunk_id,
                    passage=item.passage,
                    lifecycle_status=(
                        history.lifecycle_status
                        if history
                        else "not_active"
                    ),
                    latest_outcome=(
                        history.latest_outcome
                        if history
                        else "not_recorded"
                    ),
                    times_used=(
                        history.times_used
                        if history
                        else 0
                    ),
                    history_note=note,
                )
            )

        return results

    def find_history(
        self,
        item: JoeyStrategyEvidence,
    ) -> StrategyHistoryRecord | None:
        """Find the best matching history record."""

        exact_matches: list[
            StrategyHistoryRecord
        ] = []

        for record in self.history_records:
            code_matches = (
                bool(item.strategy_code)
                and bool(
                    record.strategy_code
                )
                and item.strategy_code
                == record.strategy_code
            )
            collection_matches = (
                bool(
                    record.collection_title
                )
                and item.collection_title
                == record.collection_title
            )
            source_matches = (
                bool(record.source_file)
                and item.source_file
                == record.source_file
            )
            title_matches = (
                normalise_title(
                    item.strategy_title
                )
                == normalise_title(
                    record.strategy_title
                )
            )

            if code_matches and (
                collection_matches
                or source_matches
            ):
                exact_matches.append(
                    record
                )
                continue

            if title_matches and (
                collection_matches
                or source_matches
            ):
                exact_matches.append(
                    record
                )
                continue

            if title_matches:
                exact_matches.append(
                    record
                )

        if not exact_matches:
            return None

        exact_matches.sort(
            key=lambda record: (
                record.lifecycle_status
                == "active",
                record.latest_outcome
                == "worked_great",
                record.latest_outcome
                == "worked_somewhat",
                record.times_used,
            ),
            reverse=True,
        )

        return exact_matches[0]

    @staticmethod
    def calculate_adjustment(
        history: StrategyHistoryRecord
        | None,
    ) -> float:
        """Calculate a bounded history adjustment."""

        if history is None:
            return 0.0

        status_adjustment = (
            STATUS_ADJUSTMENTS.get(
                history.lifecycle_status,
                0.0,
            )
        )
        outcome_adjustment = (
            OUTCOME_ADJUSTMENTS.get(
                history.latest_outcome,
                0.0,
            )
        )
        usage_adjustment = min(
            history.times_used,
            3,
        ) * 0.0001

        adjustment = (
            status_adjustment
            + outcome_adjustment
            + usage_adjustment
        )

        return max(
            min(
                adjustment,
                0.0048,
            ),
            -0.0025,
        )

    @staticmethod
    def build_history_note(
        history: StrategyHistoryRecord
        | None,
    ) -> str:
        """Create cautious parent-friendly history wording."""

        if history is None:
            return (
                "This appears to be a new strategy option "
                "in the available history."
            )

        messages: list[str] = []

        if (
            history.lifecycle_status
            == "active"
        ):
            messages.append(
                "This strategy is already recorded as active."
            )
        elif (
            history.lifecycle_status
            == "paused"
        ):
            messages.append(
                "This strategy is recorded as paused."
            )
        elif history.lifecycle_status in {
            "archived",
            "deleted",
        }:
            messages.append(
                "This strategy was previously removed or archived."
            )

        if (
            history.latest_outcome
            == "worked_great"
        ):
            messages.append(
                "The latest confirmed feedback reported that "
                "it worked well."
            )
        elif (
            history.latest_outcome
            == "worked_somewhat"
        ):
            messages.append(
                "The latest confirmed feedback reported that "
                "it helped somewhat."
            )
        elif (
            history.latest_outcome
            == "not_relevant"
        ):
            messages.append(
                "The latest confirmed feedback reported that "
                "it was not relevant for that situation."
            )
        elif (
            history.latest_outcome
            == "disaster"
        ):
            messages.append(
                "The latest confirmed feedback reported that "
                "it did not work well. It should not be "
                "presented as a first option without parent review."
            )

        if history.times_used > 0:
            messages.append(
                f"It has {history.times_used} confirmed use "
                f"{'record' if history.times_used == 1 else 'records'}."
            )

        if not messages:
            return (
                "This strategy has a history record, but no "
                "confirmed outcome has been recorded."
            )

        return " ".join(messages)
