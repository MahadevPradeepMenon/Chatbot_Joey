"""Regression tests for application-level conversation persistence."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.conversation_manager import (
    ConversationStatus,
    JoeyConversationSession,
)
from app.conversation_persistence import (
    load_or_create_workflow_state,
    persist_chat_exchange,
    persist_record_workflow_state,
    persist_strategy_workflow_state,
)
from storage.conversation_storage import (
    StoredConversationStatus,
    get_conversation_session,
)


# Keep this regression module runnable as a standalone script without requiring
# an external testing framework.
def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable regression-test failure."""

    if not condition:
        raise AssertionError(message)


def test_new_workflow_creates_greeting(
    database_path: Path,
) -> int:
    """The first load should create one session and greeting."""

    # The first workflow load should create persistent state and store exactly one
    # assistant greeting for the record workflow.
    state = load_or_create_workflow_state(
        "Record what happened",
        "Tell me what happened.",
        database_path=database_path,
    )

    assert_true(
        len(state.history) == 1,
        "The new workflow should contain one greeting.",
    )
    assert_true(
        state.history[0]["role"]
        == "assistant",
        "The greeting should belong to Joey.",
    )

    return state.session_id


def test_chat_exchange_round_trip(
    database_path: Path,
    session_id: int,
) -> None:
    """A complete user/assistant exchange should persist in order."""

    # Persist the user turn and both assistant messages as one ordered exchange so
    # the complete visible conversation can be reconstructed after restart.
    persist_chat_exchange(
        session_id=session_id,
        user_content="The classroom became very noisy.",
        assistant_messages=[
            "I created a draft.",
            "Where did this happen?",
        ],
        user_message_type="observation",
        assistant_message_type="record_response",
        database_path=database_path,
    )

    # Reload the latest record-workflow session rather than creating a new greeting
    # when persisted state is already available.
    restored = load_or_create_workflow_state(
        "Record what happened",
        "Unused greeting.",
        database_path=database_path,
    )

    assert_true(
        restored.session_id == session_id,
        "The latest workflow session was not restored.",
    )
    assert_true(
        [
            item["role"]
            for item in restored.history
        ] == [
            "assistant",
            "user",
            "assistant",
            "assistant",
        ],
        "The persisted chat order was not preserved.",
    )


def test_active_draft_restoration(
    database_path: Path,
    session_id: int,
) -> JoeyConversationSession:
    """An unfinished Joey draft should survive a restart."""

    # Create a real in-progress conversation-manager session so persistence is
    # tested against the same draft object used by the application workflow.
    draft = JoeyConversationSession.start(
        "The classroom became loud and the child covered their ears."
    )

    # Save the active draft snapshot against the existing persistent chat session.
    persist_record_workflow_state(
        session_id=session_id,
        record_session=draft,
        database_path=database_path,
    )

    restored = load_or_create_workflow_state(
        "Record what happened",
        "Unused greeting.",
        database_path=database_path,
    )

    if restored.record_session is None:
        raise AssertionError(
            "The unfinished draft was not restored."
        )

    assert_true(
        restored.record_session.original_note
        == draft.original_note,
        "The restored original note changed.",
    )
    assert_true(
        restored.record_session.pending_field
        == draft.pending_field,
        "The pending follow-up field changed.",
    )

    return draft


def test_ready_for_review_restoration(
    database_path: Path,
    session_id: int,
    draft: JoeyConversationSession,
) -> None:
    """A review-ready draft should remain review-ready."""

    # Move the same draft into the review state and clear the pending follow-up so
    # restoration can verify workflow status as well as record content.
    draft.status = (
        ConversationStatus.ready_for_review
    )
    draft.pending_field = None
    draft.follow_up_question = None

    persist_record_workflow_state(
        session_id=session_id,
        record_session=draft,
        database_path=database_path,
    )

    restored = load_or_create_workflow_state(
        "Record what happened",
        "Unused greeting.",
        database_path=database_path,
    )

    if restored.record_session is None:
        raise AssertionError(
            "The review-ready draft was not restored."
        )

    assert_true(
        restored.record_session.status
        == ConversationStatus.ready_for_review,
        "The review-ready state was not preserved.",
    )


def test_completed_draft_not_resumed(
    database_path: Path,
    session_id: int,
    draft: JoeyConversationSession,
) -> None:
    """Confirmed or rejected drafts must not reopen as active drafts."""

    # Mark the draft complete to confirm that persisted completed conversations are
    # retained for history but are not reopened as editable drafts.
    draft.status = ConversationStatus.confirmed

    persist_record_workflow_state(
        session_id=session_id,
        record_session=draft,
        database_path=database_path,
    )

    # Inspect the underlying stored status directly before testing application-level
    # restoration behaviour for the completed workflow.
    stored = get_conversation_session(
        session_id,
        database_path=database_path,
    )

    if stored is None:
        raise AssertionError(
            "The completed conversation was not found."
        )

    assert_true(
        stored.status
        == StoredConversationStatus.confirmed,
        "The confirmed storage status was not preserved.",
    )

    restored = load_or_create_workflow_state(
        "Record what happened",
        "Unused greeting.",
        database_path=database_path,
    )

    assert_true(
        restored.record_session is None,
        "A confirmed draft should not reopen for editing.",
    )


def test_draft_clear_operation(
    database_path: Path,
    session_id: int,
) -> None:
    """A reset command should intentionally clear the draft snapshot."""

    # Explicitly request draft removal rather than relying on None alone; the clear
    # flag distinguishes an intentional reset from an omitted update.
    persist_record_workflow_state(
        session_id=session_id,
        record_session=None,
        clear_draft=True,
        database_path=database_path,
    )

    stored = get_conversation_session(
        session_id,
        database_path=database_path,
    )

    if stored is None:
        raise AssertionError(
            "The reset conversation was not found."
        )

    assert_true(
        stored.draft_state is None,
        "The reset operation did not clear the stored draft.",
    )
    assert_true(
        stored.status
        == StoredConversationStatus.active,
        "The reset conversation should return to active status.",
    )


def test_strategy_metadata_round_trip(
    database_path: Path,
) -> None:
    """Pending strategy feedback should survive an app restart."""

    state = load_or_create_workflow_state(
        "Ask for a strategy",
        "Ask which strategy may help.",
        database_path=database_path,
    )

    # Store lightweight strategy-feedback metadata separately from journal draft
    # state so it can survive a strategy-workflow restart.
    pending = {
        "search_id": 42,
        "strategy_count": 3,
    }

    # Persist pending feedback against the strategy workflow session for later reload.
    persist_strategy_workflow_state(
        session_id=state.session_id,
        pending_feedback=pending,
        database_path=database_path,
    )

    restored = load_or_create_workflow_state(
        "Ask for a strategy",
        "Unused greeting.",
        database_path=database_path,
    )

    assert_true(
        restored.metadata[
            "pending_strategy_feedback"
        ] == pending,
        "Pending strategy feedback metadata was not restored.",
    )


def test_workflow_isolation(
    database_path: Path,
    record_session_id: int,
) -> None:
    """Record and strategy workflows must retain different IDs."""

    # Load the strategy workflow independently and verify it does not reuse or
    # restore state belonging to the record workflow.
    strategy = load_or_create_workflow_state(
        "Ask for a strategy",
        "Ask which strategy may help.",
        database_path=database_path,
    )

    assert_true(
        strategy.session_id
        != record_session_id,
        "Both workflows unexpectedly shared one session.",
    )
    assert_true(
        strategy.record_session is None,
        "A strategy workflow should never restore a journal draft.",
    )


def main() -> None:
    """Run all Stage 4B persistence regression tests."""

    passed = 0
    total = 8

    # Run all persistence checks against a disposable SQLite database so the suite
    # is isolated from normal application data and repeatable in CI.
    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "conversation_persistence_test.db"
        )

        # Reuse the same record-workflow session across successive tests so restart,
        # draft-state transitions and clearing are exercised as one lifecycle.
        session_id = test_new_workflow_creates_greeting(
            database_path
        )
        passed += 1
        print("[PASS] new workflow greeting creation")

        test_chat_exchange_round_trip(
            database_path,
            session_id,
        )
        passed += 1
        print("[PASS] chat exchange round trip")

        draft = test_active_draft_restoration(
            database_path,
            session_id,
        )
        passed += 1
        print("[PASS] active draft restoration")

        test_ready_for_review_restoration(
            database_path,
            session_id,
            draft,
        )
        passed += 1
        print("[PASS] review-ready draft restoration")

        test_completed_draft_not_resumed(
            database_path,
            session_id,
            draft,
        )
        passed += 1
        print("[PASS] completed draft not resumed")

        test_draft_clear_operation(
            database_path,
            session_id,
        )
        passed += 1
        print("[PASS] explicit draft clearing")

        test_strategy_metadata_round_trip(
            database_path
        )
        passed += 1
        print("[PASS] strategy metadata round trip")

        test_workflow_isolation(
            database_path,
            session_id,
        )
        passed += 1
        print("[PASS] persistent workflow isolation")

    print("\nCONVERSATION PERSISTENCE TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")


# Run the application-level persistence regressions only when executed directly.
if __name__ == "__main__":
    main()