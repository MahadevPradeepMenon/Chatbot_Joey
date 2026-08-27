"""Regression tests for persistent Joey conversation storage."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.conversation_manager import (
    JoeyConversationSession,
)
from storage.conversation_storage import (
    ConversationRole,
    ConversationWorkflow,
    StoredConversationStatus,
    add_conversation_message,
    count_conversation_messages,
    count_conversation_sessions,
    create_conversation_session,
    create_conversation_tables,
    delete_conversation_session,
    get_conversation_session,
    list_conversation_sessions,
    update_conversation_session,
)


# Keep this regression module runnable as a standalone script without requiring
# an external testing framework.
def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable test failure."""

    if not condition:
        raise AssertionError(message)


def test_table_creation(
    database_path: Path,
) -> None:
    """The session and message tables should be created."""

    # Create the persistent-conversation schema at the injected temporary path so
    # the test does not touch the application's normal local database.
    path = create_conversation_tables(
        database_path
    )

    assert_true(
        path.exists(),
        "The conversation database was not created.",
    )


def test_separate_workflow_sessions(
    database_path: Path,
) -> tuple[int, int]:
    """Both chatbot workflows should receive separate sessions."""

    # Create one session for each supported workflow to verify that they receive
    # distinct persistent identifiers.
    record_id = create_conversation_session(
        "Record what happened",
        created_at="2026-07-30T18:00:00",
        database_path=database_path,
    )

    strategy_id = create_conversation_session(
        "Ask for a strategy",
        created_at="2026-07-30T18:01:00",
        database_path=database_path,
    )

    assert_true(
        record_id != strategy_id,
        "The two workflows should use separate session IDs.",
    )

    assert_true(
        count_conversation_sessions(
            database_path
        ) == 2,
        "Exactly two workflow sessions were expected.",
    )

    return record_id, strategy_id


def test_message_insertion_and_ordering(
    database_path: Path,
    record_id: int,
) -> None:
    """Messages should retain user/assistant order."""

    # Insert alternating assistant/user turns with fixed timestamps so sequence
    # numbering and role preservation can be checked deterministically.
    add_conversation_message(
        record_id,
        ConversationRole.assistant,
        "Tell me what happened.",
        message_type="greeting",
        created_at="2026-07-30T18:00:01",
        database_path=database_path,
    )

    add_conversation_message(
        record_id,
        ConversationRole.user,
        "The classroom became very noisy.",
        message_type="observation",
        created_at="2026-07-30T18:00:02",
        database_path=database_path,
    )

    add_conversation_message(
        record_id,
        ConversationRole.assistant,
        "Was the sound difficult to escape from?",
        message_type="follow_up_question",
        created_at="2026-07-30T18:00:03",
        database_path=database_path,
    )

    # Retrieve the complete session through the public storage API, including its
    # ordered child-message records.
    stored = get_conversation_session(
        record_id,
        database_path,
    )

    if stored is None:
        raise AssertionError(
            "The record conversation could not be retrieved."
        )

    assert_true(
        [
            message.sequence_number
            for message in stored.messages
        ] == [1, 2, 3],
        "Messages were not returned in sequence order.",
    )

    assert_true(
        [
            message.role
            for message in stored.messages
        ] == [
            ConversationRole.assistant,
            ConversationRole.user,
            ConversationRole.assistant,
        ],
        "Message roles were not preserved.",
    )


def test_conversation_retrieval(
    database_path: Path,
    strategy_id: int,
) -> None:
    """A strategy session should round-trip independently."""

    # Exercise the same storage API with string role values as well as enum values.
    add_conversation_message(
        strategy_id,
        "user",
        "What may help with bedtime anxiety?",
        message_type="strategy_question",
        database_path=database_path,
    )

    add_conversation_message(
        strategy_id,
        "assistant",
        "A predictable bedtime routine may be relevant.",
        message_type="strategy_response",
        database_path=database_path,
    )

    stored = get_conversation_session(
        strategy_id,
        database_path,
    )

    if stored is None:
        raise AssertionError(
            "The strategy conversation could not be retrieved."
        )

    assert_true(
        stored.workflow
        == ConversationWorkflow.ask_strategy,
        "The strategy workflow was not preserved.",
    )

    assert_true(
        len(stored.messages) == 2,
        "The strategy conversation should contain two messages.",
    )


def test_status_update(
    database_path: Path,
    record_id: int,
) -> None:
    """Conversation status should be updateable."""

    # Update only the persisted workflow status while leaving the rest of the
    # conversation session intact.
    update_conversation_session(
        record_id,
        status=StoredConversationStatus.ready_for_review,
        updated_at="2026-07-30T18:10:00",
        database_path=database_path,
    )

    stored = get_conversation_session(
        record_id,
        database_path,
    )

    if stored is None:
        raise AssertionError(
            "The updated conversation could not be retrieved."
        )

    assert_true(
        stored.status
        == StoredConversationStatus.ready_for_review,
        "The updated session status was not preserved.",
    )


def test_draft_state_preservation(
    database_path: Path,
    record_id: int,
) -> None:
    """The JoeyConversationSession snapshot should round-trip."""

    # Build a real conversation-manager draft and persist its serialised snapshot
    # so compatibility between conversation and storage layers is regression-tested.
    draft = JoeyConversationSession.start(
        "The classroom became loud and the child covered their ears."
    )

    draft_state = draft.to_dict()

    # Explicitly enable the draft-state update so the stored JSON snapshot can be
    # recovered on a later read.
    update_conversation_session(
        record_id,
        draft_state=draft_state,
        update_draft_state=True,
        database_path=database_path,
    )

    stored = get_conversation_session(
        record_id,
        database_path,
    )

    if stored is None:
        raise AssertionError(
            "The draft conversation could not be retrieved."
        )

    if stored.draft_state is None:
        raise AssertionError(
            "The draft state was not stored."
        )

    assert_true(
        stored.draft_state["original_note"]
        == draft.original_note,
        "The original draft note was not preserved.",
    )

    assert_true(
        "structured_record"
        in stored.draft_state,
        "The structured draft record was not preserved.",
    )


def test_workflow_isolation(
    database_path: Path,
    record_id: int,
    strategy_id: int,
) -> None:
    """Messages and filters must not leak between workflows."""

    # Query each workflow separately to prove that filters and attached messages do
    # not leak between the record and strategy conversation streams.
    record_sessions = list_conversation_sessions(
        workflow="Record what happened",
        database_path=database_path,
    )

    strategy_sessions = list_conversation_sessions(
        workflow="Ask for a strategy",
        database_path=database_path,
    )

    assert_true(
        [item.id for item in record_sessions]
        == [record_id],
        "The record workflow returned another workflow's session.",
    )

    assert_true(
        [item.id for item in strategy_sessions]
        == [strategy_id],
        "The strategy workflow returned another workflow's session.",
    )

    assert_true(
        len(record_sessions[0].messages) == 3,
        "The record conversation message count changed unexpectedly.",
    )

    assert_true(
        len(strategy_sessions[0].messages) == 2,
        "The strategy conversation message count changed unexpectedly.",
    )


def test_session_deletion_cascades(
    database_path: Path,
    strategy_id: int,
) -> None:
    """Deleting a session should also delete its messages."""

    # Capture the global message count before deletion so the foreign-key cascade
    # can be verified after removing one session.
    messages_before = count_conversation_messages(
        database_path
    )

    delete_conversation_session(
        strategy_id,
        database_path,
    )

    assert_true(
        get_conversation_session(
            strategy_id,
            database_path,
        )
        is None,
        "The deleted session was still retrievable.",
    )

    assert_true(
        count_conversation_sessions(
            database_path
        ) == 1,
        "Exactly one session should remain after deletion.",
    )

    assert_true(
        count_conversation_messages(
            database_path
        ) == messages_before - 2,
        "The deleted session's messages were not cascade-deleted.",
    )


def test_invalid_session_rejected(
    database_path: Path,
) -> None:
    """Messages cannot be added to a missing session."""

    # Use an intentionally missing session ID to confirm that orphan messages are
    # rejected rather than silently inserted.
    try:
        add_conversation_message(
            999,
            "user",
            "This should not be stored.",
            database_path=database_path,
        )
    except ValueError as error:
        assert_true(
            "not found" in str(error),
            "The missing-session message was unexpected.",
        )
    else:
        raise AssertionError(
            "A message was stored for a missing session."
        )


def main() -> None:
    """Run all persistent-conversation storage tests."""

    passed = 0
    total = 8

    # Run the storage checks against a disposable SQLite database so the regression
    # suite is isolated and repeatable.
    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "conversation_storage_test.db"
        )

        test_table_creation(
            database_path
        )
        passed += 1
        print("[PASS] conversation table creation")

        # Reuse the created workflow IDs throughout the remaining tests so ordering,
        # updates, isolation and deletion operate on the same persisted sessions.
        record_id, strategy_id = (
            test_separate_workflow_sessions(
                database_path
            )
        )
        passed += 1
        print("[PASS] separate workflow sessions")

        test_message_insertion_and_ordering(
            database_path,
            record_id,
        )
        passed += 1
        print("[PASS] message insertion and ordering")

        test_conversation_retrieval(
            database_path,
            strategy_id,
        )
        passed += 1
        print("[PASS] conversation retrieval")

        test_status_update(
            database_path,
            record_id,
        )
        passed += 1
        print("[PASS] conversation status update")

        test_draft_state_preservation(
            database_path,
            record_id,
        )
        passed += 1
        print("[PASS] draft-state preservation")

        test_workflow_isolation(
            database_path,
            record_id,
            strategy_id,
        )
        passed += 1
        print("[PASS] workflow isolation")

        test_session_deletion_cascades(
            database_path,
            strategy_id,
        )
        passed += 1
        print("[PASS] session deletion cascade")

        test_invalid_session_rejected(
            database_path
        )
        print("[PASS] invalid-session rejection")

    # The invalid-session check is an additional guard beyond the eight
    # required storage behaviours.
    # It is reported separately because it is not included in the primary pass total.
    # required storage behaviours.
    print("\nCONVERSATION STORAGE TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")
    print("Additional guard passed: invalid-session rejection")


# Run the conversation-storage regression suite only when executed directly.
if __name__ == "__main__":
    main()