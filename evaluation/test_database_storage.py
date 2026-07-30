"""Regression tests for Hey Joey SQLite journal storage."""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.schemas import (
    AnxietyLevel,
    ConfidenceLevel,
    MoodZone,
    StructuredJoeyRecord,
)
from storage.database import (
    count_journal_entries,
    create_database,
    get_journal_entry,
    list_journal_entries,
    save_confirmed_record,
    save_confirmed_session,
)


class FakeStatus(str, Enum):
    collecting_information = "collecting_information"
    confirmed = "confirmed"


@dataclass
class FakeTurn:
    question: str
    answer: str
    field_name: str


@dataclass
class FakeSession:
    status: FakeStatus
    original_note: str
    current_record: StructuredJoeyRecord
    history: list[FakeTurn]


def sample_record(
    summary: str = "The child became distressed in a noisy classroom.",
) -> StructuredJoeyRecord:
    """Return a complete synthetic record for database tests."""

    return StructuredJoeyRecord(
        summary=summary,
        date="2026-07-30",
        time_of_day="Morning",
        anxiety_level=AnxietyLevel.high,
        mood_zone=MoodZone.orange,
        mood_labels=[
            "Distressed",
        ],
        behaviours=[
            "Covered ears",
        ],
        activity="classroom activity",
        environment="school classroom",
        possible_triggers=[
            "loud classroom noise",
        ],
        quick_track_suggestions=[
            "Mood",
            "Physical Discomfort",
        ],
        strategy_categories=[
            "Sensory Processing",
        ],
        risk_flags=[],
        missing_information=[],
        follow_up_question=None,
        confidence=ConfidenceLevel.high,
        requires_parent_confirmation=True,
    )


def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable test failure."""

    if not condition:
        raise AssertionError(message)


def test_database_creation(
    database_path: Path,
) -> None:
    """The SQLite file and table should be created."""

    created_path = create_database(
        database_path
    )

    assert_true(
        created_path.exists(),
        "The SQLite database file was not created.",
    )

    connection = sqlite3.connect(
        created_path
    )

    try:
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'journal_entries'
            """
        ).fetchone()
    finally:
        connection.close()

    assert_true(
        row is not None,
        "The journal_entries table was not created.",
    )


def test_record_insert_and_count(
    database_path: Path,
) -> int:
    """A confirmed record should be inserted and counted."""

    entry_id = save_confirmed_record(
        record=sample_record(),
        original_note=(
            "The classroom became loud and "
            "the child covered their ears."
        ),
        conversation_history=[
            {
                "question": (
                    "How anxious did the child appear?"
                ),
                "answer": "High",
                "field_name": "anxiety_level",
            }
        ],
        source="database_regression_test",
        saved_at="2026-07-30T12:00:00",
        database_path=database_path,
    )

    assert_true(
        entry_id == 1,
        "The first stored entry should have ID 1.",
    )

    assert_true(
        count_journal_entries(
            database_path
        ) == 1,
        "The stored record count should be 1.",
    )

    return entry_id


def test_record_round_trip(
    database_path: Path,
    entry_id: int,
) -> None:
    """Stored scalar and list fields should round-trip correctly."""

    stored = get_journal_entry(
        entry_id,
        database_path,
    )

    if stored is None:
        raise AssertionError(
            "The saved journal entry could not be retrieved."
        )

    assert_true(
        stored["mood_zone"] == "Orange",
        "The mood zone was not preserved.",
    )

    assert_true(
        stored["anxiety_level"] == "High",
        "The anxiety level was not preserved.",
    )

    assert_true(
        stored["possible_triggers"]
        == ["loud classroom noise"],
        "Possible triggers were not preserved.",
    )

    assert_true(
        stored["conversation_history"][0]["answer"]
        == "High",
        "Conversation history was not preserved.",
    )

    assert_true(
        stored["structured_record"]["summary"]
        == (
            "The child became distressed "
            "in a noisy classroom."
        ),
        "The complete structured record was not preserved.",
    )


def test_recent_entry_order(
    database_path: Path,
) -> None:
    """Recent-entry retrieval should return newest IDs first."""

    second_id = save_confirmed_record(
        record=sample_record(
            "The child settled more easily at bedtime."
        ),
        original_note=(
            "The child settled more easily "
            "at bedtime."
        ),
        conversation_history=[],
        source="database_regression_test",
        saved_at="2026-07-30T12:05:00",
        database_path=database_path,
    )

    entries = list_journal_entries(
        limit=2,
        database_path=database_path,
    )

    assert_true(
        [item["id"] for item in entries]
        == [second_id, 1],
        "Journal entries were not returned newest first.",
    )


def test_unconfirmed_session_rejected(
    database_path: Path,
) -> None:
    """An unconfirmed conversation must never be stored."""

    session = FakeSession(
        status=FakeStatus.collecting_information,
        original_note="A synthetic unconfirmed note.",
        current_record=sample_record(),
        history=[],
    )

    try:
        save_confirmed_session(
            session,
            database_path=database_path,
        )
    except ValueError as error:
        assert_true(
            "not been confirmed" in str(error),
            "The rejection message was unexpected.",
        )
    else:
        raise AssertionError(
            "An unconfirmed session was stored."
        )


def test_confirmed_session_saved(
    database_path: Path,
) -> None:
    """A confirmed conversation session should be stored."""

    session = FakeSession(
        status=FakeStatus.confirmed,
        original_note=(
            "The room became noisy and "
            "the child covered their ears."
        ),
        current_record=sample_record(),
        history=[
            FakeTurn(
                question="Where did this happen?",
                answer="In the classroom.",
                field_name="environment",
            )
        ],
    )

    entry_id = save_confirmed_session(
        session,
        source="database_session_test",
        database_path=database_path,
    )

    stored = get_journal_entry(
        entry_id,
        database_path,
    )

    if stored is None:
        raise AssertionError(
            "The confirmed session was not saved."
        )

    assert_true(
        stored["conversation_history"][0]["field_name"]
        == "environment",
        "The session history field was not preserved.",
    )


def main() -> None:
    """Run the local SQLite storage regression tests."""

    tests_passed = 0
    test_count = 6

    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "test_joey.db"
        )

        test_database_creation(
            database_path
        )
        tests_passed += 1
        print("[PASS] database creation")

        entry_id = test_record_insert_and_count(
            database_path
        )
        tests_passed += 1
        print("[PASS] record insert and count")

        test_record_round_trip(
            database_path,
            entry_id,
        )
        tests_passed += 1
        print("[PASS] structured record round trip")

        test_recent_entry_order(
            database_path
        )
        tests_passed += 1
        print("[PASS] recent entry ordering")

        test_unconfirmed_session_rejected(
            database_path
        )
        tests_passed += 1
        print("[PASS] unconfirmed session rejection")

        test_confirmed_session_saved(
            database_path
        )
        tests_passed += 1
        print("[PASS] confirmed session save")

    print("\nSQLITE STORAGE TEST RESULTS")
    print("=" * 60)
    print(
        f"Tests passed: {tests_passed}/{test_count}"
    )


if __name__ == "__main__":
    main()
