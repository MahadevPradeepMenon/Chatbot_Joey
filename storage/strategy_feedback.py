"""SQLite storage for Hey Joey strategy searches and feedback."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from storage.database import (
    DEFAULT_DATABASE_PATH,
    create_database,
)


class StrategyFeedbackRating(str, Enum):
    """Supported feedback values stored in SQLite."""

    worked_well = "worked_well"
    helped_somewhat = "helped_somewhat"
    not_relevant = "not_relevant"
    did_not_work_well = "did_not_work_well"


FEEDBACK_LABELS: dict[StrategyFeedbackRating, str] = {
    StrategyFeedbackRating.worked_well: "Worked well",
    StrategyFeedbackRating.helped_somewhat: "Helped somewhat",
    StrategyFeedbackRating.not_relevant: "Not relevant",
    StrategyFeedbackRating.did_not_work_well: "Did not work well",
}

FEEDBACK_ALIASES: dict[str, StrategyFeedbackRating] = {
    "worked well": StrategyFeedbackRating.worked_well,
    "worked_well": StrategyFeedbackRating.worked_well,
    "worked great": StrategyFeedbackRating.worked_well,
    "helped somewhat": StrategyFeedbackRating.helped_somewhat,
    "helped_somewhat": StrategyFeedbackRating.helped_somewhat,
    "worked somewhat": StrategyFeedbackRating.helped_somewhat,
    "not relevant": StrategyFeedbackRating.not_relevant,
    "not_relevant": StrategyFeedbackRating.not_relevant,
    "did not work well": StrategyFeedbackRating.did_not_work_well,
    "did_not_work_well": StrategyFeedbackRating.did_not_work_well,
    "didn't work well": StrategyFeedbackRating.did_not_work_well,
}


@dataclass(frozen=True)
class StoredStrategyResult:
    """One strategy displayed during a stored search."""

    id: int
    search_id: int
    display_rank: int
    original_rank: int
    strategy_code: str | None
    strategy_title: str | None
    collection_title: str
    source_file: str
    theme: str | None
    chunk_id: str
    original_score: float
    history_adjustment: float
    personalised_score: float
    passage: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StoredStrategyFeedback:
    """One stored feedback record."""

    id: int
    search_id: int
    search_result_id: int
    strategy_rank: int
    strategy_code: str | None
    strategy_title: str | None
    collection_title: str
    source_file: str
    rating: StrategyFeedbackRating
    rating_label: str
    comment: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rating"] = self.rating.value
        return data


def _database_path(
    database_path: str | Path | None,
) -> Path:
    """Resolve the strategy-feedback database path."""

    if database_path is None:
        return DEFAULT_DATABASE_PATH

    return Path(database_path)


@contextmanager
def _connection(
    database_path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """Open and always close a SQLite connection."""

    path = _database_path(database_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        path,
        timeout=10.0,
    )
    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_strategy_feedback_tables(
    database_path: str | Path | None = None,
) -> Path:
    """Create strategy search, result and feedback tables."""

    path = create_database(
        database_path
    )

    with _connection(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                question TEXT NOT NULL,
                retrieval_query TEXT NOT NULL,
                confidence_level TEXT NOT NULL,
                strategy_count INTEGER NOT NULL
                    CHECK (strategy_count >= 0),
                evidence_json TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER NOT NULL,
                display_rank INTEGER NOT NULL
                    CHECK (display_rank >= 1),
                original_rank INTEGER NOT NULL
                    CHECK (original_rank >= 1),
                strategy_code TEXT,
                strategy_title TEXT,
                collection_title TEXT NOT NULL,
                source_file TEXT NOT NULL,
                theme TEXT,
                chunk_id TEXT NOT NULL,
                original_score REAL NOT NULL,
                history_adjustment REAL NOT NULL,
                personalised_score REAL NOT NULL,
                passage TEXT NOT NULL,
                FOREIGN KEY (search_id)
                    REFERENCES strategy_searches(id)
                    ON DELETE CASCADE,
                UNIQUE (search_id, display_rank)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER NOT NULL,
                search_result_id INTEGER NOT NULL UNIQUE,
                rating TEXT NOT NULL
                    CHECK (
                        rating IN (
                            'worked_well',
                            'helped_somewhat',
                            'not_relevant',
                            'did_not_work_well'
                        )
                    ),
                comment TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (search_id)
                    REFERENCES strategy_searches(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (search_result_id)
                    REFERENCES strategy_search_results(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_strategy_searches_created_at
            ON strategy_searches(created_at)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_strategy_results_identity
            ON strategy_search_results(
                strategy_code,
                strategy_title,
                collection_title,
                source_file
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_strategy_feedback_created_at
            ON strategy_feedback(created_at)
            """
        )

    return path


def _required_text(
    value: Any,
    field_name: str,
) -> str:
    """Validate one required text value."""

    text = str(value or "").strip()

    if not text:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return text


def _optional_text(
    value: Any,
) -> str | None:
    """Return optional trimmed text."""

    text = str(value or "").strip()
    return text or None


def normalise_feedback_rating(
    rating: StrategyFeedbackRating | str,
) -> StrategyFeedbackRating:
    """Convert a user-facing label or stored value into an enum."""

    if isinstance(
        rating,
        StrategyFeedbackRating,
    ):
        return rating

    clean = " ".join(
        str(rating or "")
        .strip()
        .lower()
        .replace("-", " ")
        .split()
    )

    result = FEEDBACK_ALIASES.get(
        clean
    )

    if result is None:
        allowed = ", ".join(
            label.lower()
            for label in FEEDBACK_LABELS.values()
        )
        raise ValueError(
            "Unsupported feedback rating. "
            f"Use one of: {allowed}."
        )

    return result


def feedback_label(
    rating: StrategyFeedbackRating | str,
) -> str:
    """Return the parent-facing label for a rating."""

    normalised = normalise_feedback_rating(
        rating
    )
    return FEEDBACK_LABELS[normalised]


def _evidence_dict(
    item: Any,
    display_rank: int,
) -> dict[str, Any]:
    """Convert one history-aware evidence item for SQLite storage."""

    return {
        "display_rank": display_rank,
        "original_rank": max(
            int(
                getattr(
                    item,
                    "original_rank",
                    display_rank,
                )
            ),
            1,
        ),
        "strategy_code": _optional_text(
            getattr(
                item,
                "strategy_code",
                None,
            )
        ),
        "strategy_title": _optional_text(
            getattr(
                item,
                "strategy_title",
                None,
            )
        ),
        "collection_title": _required_text(
            getattr(
                item,
                "collection_title",
                None,
            ),
            "evidence.collection_title",
        ),
        "source_file": _required_text(
            getattr(
                item,
                "source_file",
                None,
            ),
            "evidence.source_file",
        ),
        "theme": _optional_text(
            getattr(
                item,
                "theme",
                None,
            )
        ),
        "chunk_id": _required_text(
            getattr(
                item,
                "chunk_id",
                None,
            ),
            "evidence.chunk_id",
        ),
        "original_score": float(
            getattr(
                item,
                "original_score",
                0.0,
            )
        ),
        "history_adjustment": float(
            getattr(
                item,
                "history_adjustment",
                0.0,
            )
        ),
        "personalised_score": float(
            getattr(
                item,
                "personalised_score",
                getattr(
                    item,
                    "original_score",
                    0.0,
                ),
            )
        ),
        "passage": _required_text(
            getattr(
                item,
                "passage",
                None,
            ),
            "evidence.passage",
        ),
    }


def save_strategy_search(
    question: str,
    retrieval_query: str,
    evidence: Iterable[Any],
    confidence_level: str,
    source: str = "streamlit_chat_interface",
    created_at: str | None = None,
    database_path: str | Path | None = None,
) -> int:
    """Store one accepted strategy search and all displayed evidence."""

    path = create_strategy_feedback_tables(
        database_path
    )
    evidence_rows = [
        _evidence_dict(
            item,
            display_rank=index,
        )
        for index, item in enumerate(
            evidence,
            start=1,
        )
    ]

    if not evidence_rows:
        raise ValueError(
            "At least one displayed strategy is required."
        )

    created_timestamp = (
        created_at
        or datetime.now().isoformat(
            timespec="seconds"
        )
    )

    evidence_json = json.dumps(
        evidence_rows,
        ensure_ascii=False,
    )

    with _connection(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO strategy_searches (
                created_at,
                source,
                question,
                retrieval_query,
                confidence_level,
                strategy_count,
                evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_timestamp,
                _required_text(
                    source,
                    "source",
                ),
                _required_text(
                    question,
                    "question",
                ),
                _required_text(
                    retrieval_query,
                    "retrieval_query",
                ),
                _required_text(
                    confidence_level,
                    "confidence_level",
                ).lower(),
                len(evidence_rows),
                evidence_json,
            ),
        )

        if cursor.lastrowid is None:
            raise RuntimeError(
                "SQLite did not return a strategy-search ID."
            )

        search_id = int(
            cursor.lastrowid
        )

        for row in evidence_rows:
            connection.execute(
                """
                INSERT INTO strategy_search_results (
                    search_id,
                    display_rank,
                    original_rank,
                    strategy_code,
                    strategy_title,
                    collection_title,
                    source_file,
                    theme,
                    chunk_id,
                    original_score,
                    history_adjustment,
                    personalised_score,
                    passage
                )
                VALUES (
                    :search_id,
                    :display_rank,
                    :original_rank,
                    :strategy_code,
                    :strategy_title,
                    :collection_title,
                    :source_file,
                    :theme,
                    :chunk_id,
                    :original_score,
                    :history_adjustment,
                    :personalised_score,
                    :passage
                )
                """,
                {
                    "search_id": search_id,
                    **row,
                },
            )

    return search_id


def save_strategy_feedback(
    search_id: int,
    strategy_rank: int,
    rating: StrategyFeedbackRating | str,
    comment: str | None = None,
    created_at: str | None = None,
    database_path: str | Path | None = None,
) -> int:
    """
    Insert or update feedback for one displayed strategy.

    One feedback record is retained per displayed strategy. Repeating
    feedback updates the previous choice rather than creating duplicates.
    """

    if search_id < 1:
        raise ValueError(
            "search_id must be at least 1."
        )

    if strategy_rank < 1:
        raise ValueError(
            "strategy_rank must be at least 1."
        )

    normalised_rating = normalise_feedback_rating(
        rating
    )
    path = create_strategy_feedback_tables(
        database_path
    )
    created_timestamp = (
        created_at
        or datetime.now().isoformat(
            timespec="seconds"
        )
    )

    with _connection(path) as connection:
        result_row = connection.execute(
            """
            SELECT id
            FROM strategy_search_results
            WHERE search_id = ?
              AND display_rank = ?
            """,
            (
                search_id,
                strategy_rank,
            ),
        ).fetchone()

        if result_row is None:
            raise ValueError(
                "The selected strategy does not belong to "
                "the stored search."
            )

        search_result_id = int(
            result_row["id"]
        )

        connection.execute(
            """
            INSERT INTO strategy_feedback (
                search_id,
                search_result_id,
                rating,
                comment,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(search_result_id)
            DO UPDATE SET
                rating = excluded.rating,
                comment = excluded.comment,
                created_at = excluded.created_at,
                search_id = excluded.search_id
            """,
            (
                search_id,
                search_result_id,
                normalised_rating.value,
                _optional_text(comment),
                created_timestamp,
            ),
        )

        feedback_row = connection.execute(
            """
            SELECT id
            FROM strategy_feedback
            WHERE search_result_id = ?
            """,
            (search_result_id,),
        ).fetchone()

        if feedback_row is None:
            raise RuntimeError(
                "SQLite did not return the strategy-feedback ID."
            )

        return int(
            feedback_row["id"]
        )


def get_strategy_search(
    search_id: int,
    database_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return one stored search and its displayed strategies."""

    path = create_strategy_feedback_tables(
        database_path
    )

    with _connection(path) as connection:
        search_row = connection.execute(
            """
            SELECT *
            FROM strategy_searches
            WHERE id = ?
            """,
            (search_id,),
        ).fetchone()

        if search_row is None:
            return None

        result_rows = connection.execute(
            """
            SELECT *
            FROM strategy_search_results
            WHERE search_id = ?
            ORDER BY display_rank
            """,
            (search_id,),
        ).fetchall()

    search = dict(search_row)
    search["evidence"] = [
        dict(row)
        for row in result_rows
    ]

    try:
        search["evidence_snapshot"] = json.loads(
            search.pop("evidence_json")
        )
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        search["evidence_snapshot"] = []

    return search


def list_strategy_feedback(
    limit: int = 50,
    database_path: str | Path | None = None,
) -> list[StoredStrategyFeedback]:
    """Return recent strategy feedback, newest first."""

    if limit < 1:
        raise ValueError(
            "limit must be at least 1."
        )

    path = create_strategy_feedback_tables(
        database_path
    )

    with _connection(path) as connection:
        rows = connection.execute(
            """
            SELECT
                feedback.id,
                feedback.search_id,
                feedback.search_result_id,
                results.display_rank AS strategy_rank,
                results.strategy_code,
                results.strategy_title,
                results.collection_title,
                results.source_file,
                feedback.rating,
                feedback.comment,
                feedback.created_at
            FROM strategy_feedback AS feedback
            JOIN strategy_search_results AS results
              ON results.id = feedback.search_result_id
            ORDER BY feedback.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    feedback_items: list[StoredStrategyFeedback] = []

    for row in rows:
        rating = StrategyFeedbackRating(
            row["rating"]
        )
        feedback_items.append(
            StoredStrategyFeedback(
                id=int(row["id"]),
                search_id=int(row["search_id"]),
                search_result_id=int(
                    row["search_result_id"]
                ),
                strategy_rank=int(
                    row["strategy_rank"]
                ),
                strategy_code=row["strategy_code"],
                strategy_title=row["strategy_title"],
                collection_title=str(
                    row["collection_title"]
                ),
                source_file=str(
                    row["source_file"]
                ),
                rating=rating,
                rating_label=FEEDBACK_LABELS[rating],
                comment=row["comment"],
                created_at=str(
                    row["created_at"]
                ),
            )
        )

    return feedback_items


def count_strategy_searches(
    database_path: str | Path | None = None,
) -> int:
    """Return the number of stored accepted strategy searches."""

    path = create_strategy_feedback_tables(
        database_path
    )

    with _connection(path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS item_count
            FROM strategy_searches
            """
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "SQLite did not return the search count."
        )

    return int(
        row["item_count"]
    )


def count_strategy_feedback(
    database_path: str | Path | None = None,
) -> int:
    """Return the number of stored feedback records."""

    path = create_strategy_feedback_tables(
        database_path
    )

    with _connection(path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS item_count
            FROM strategy_feedback
            """
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "SQLite did not return the feedback count."
        )

    return int(
        row["item_count"]
    )


def main() -> None:
    """Create tables and print local strategy-feedback counts."""

    path = create_strategy_feedback_tables()

    print("HEY JOEY STRATEGY FEEDBACK STORAGE")
    print("=" * 60)
    print(f"Database: {path}")
    print(
        "Stored strategy searches: "
        f"{count_strategy_searches(path)}"
    )
    print(
        "Stored feedback records: "
        f"{count_strategy_feedback(path)}"
    )


if __name__ == "__main__":
    main()
