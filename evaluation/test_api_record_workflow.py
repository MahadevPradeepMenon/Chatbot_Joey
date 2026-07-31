"""Regression tests for the Stage 5B record-workflow API."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app
from storage.conversation_storage import (
    ConversationWorkflow,
    create_conversation_session,
)
from storage.database import (
    count_journal_entries,
    get_journal_entry,
)


def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable API regression-test failure."""

    if not condition:
        raise AssertionError(message)


def create_record_session(
    client: TestClient,
    note: str = (
        "The child became upset in a noisy classroom and "
        "covered their ears."
    ),
) -> dict:
    """Create one API journal conversation and return its payload."""

    response = client.post(
        "/api/v1/record/sessions",
        json={
            "note": note,
        },
    )

    assert_true(
        response.status_code == 201,
        "The record session was not created with HTTP 201.",
    )

    return response.json()


def advance_to_review(
    client: TestClient,
    payload: dict,
) -> dict:
    """Skip unanswered details until the deterministic draft is review-ready."""

    attempts = 0

    while payload["status"] == "active":
        attempts += 1

        if attempts > 5:
            raise AssertionError(
                "The record workflow did not reach review state."
            )

        response = client.post(
            (
                "/api/v1/record/sessions/"
                f"{payload['session_id']}/messages"
            ),
            json={
                "message": "not sure",
            },
        )

        assert_true(
            response.status_code == 200,
            "A follow-up answer did not return HTTP 200.",
        )
        payload = response.json()

    assert_true(
        payload["status"] == "ready_for_review",
        "The draft did not reach ready_for_review.",
    )

    return payload


def test_create_session(
    client: TestClient,
    database_path: Path,
) -> dict:
    """The first observation should create a draft but not a journal entry."""

    payload = create_record_session(
        client
    )

    assert_true(
        payload["workflow"] == "record_observation",
        "The created workflow value was unexpected.",
    )
    assert_true(
        payload["status"] in {
            "active",
            "ready_for_review",
        },
        "The created draft had an unexpected status.",
    )
    assert_true(
        payload["draft"] is not None,
        "The created response did not contain a draft.",
    )
    assert_true(
        payload["messages"][0]["role"] == "user",
        "The first persistent message should be the parent note.",
    )
    assert_true(
        payload["assistant_messages"],
        "Joey did not return an initial response.",
    )
    assert_true(
        count_journal_entries(
            database_path
        ) == 0,
        "Creating a draft should not save a journal entry.",
    )

    return payload


def test_whitespace_note_rejected(
    client: TestClient,
) -> None:
    """Whitespace-only observations should fail request validation."""

    response = client.post(
        "/api/v1/record/sessions",
        json={
            "note": "   ",
        },
    )

    assert_true(
        response.status_code == 422,
        "A whitespace-only note did not return HTTP 422.",
    )


def test_get_session(
    client: TestClient,
    payload: dict,
) -> None:
    """The created conversation should round-trip through GET."""

    response = client.get(
        (
            "/api/v1/record/sessions/"
            f"{payload['session_id']}"
        )
    )
    restored = response.json()

    assert_true(
        response.status_code == 200,
        "The record session GET did not return HTTP 200.",
    )
    assert_true(
        restored["session_id"]
        == payload["session_id"],
        "The GET endpoint returned another session.",
    )
    assert_true(
        restored["draft"]["original_note"]
        == payload["draft"]["original_note"],
        "The original note changed during persistence.",
    )


def test_follow_up_message(
    client: TestClient,
    payload: dict,
) -> dict:
    """One answer should update the same draft and ordered message history."""

    if payload["status"] != "active":
        return payload

    before_count = len(
        payload["messages"]
    )
    response = client.post(
        (
            "/api/v1/record/sessions/"
            f"{payload['session_id']}/messages"
        ),
        json={
            "message": "not sure",
        },
    )
    updated = response.json()

    assert_true(
        response.status_code == 200,
        "The follow-up endpoint did not return HTTP 200.",
    )
    assert_true(
        updated["session_id"]
        == payload["session_id"],
        "The follow-up answer created another session.",
    )
    assert_true(
        len(updated["messages"])
        > before_count,
        "The follow-up exchange was not persisted.",
    )
    assert_true(
        updated["draft"]["history"],
        "The draft did not preserve the follow-up answer.",
    )

    return updated


def test_confirmation_requires_review(
    client: TestClient,
) -> None:
    """An active draft must not bypass the review state."""

    payload = create_record_session(
        client,
        note="The child seemed upset.",
    )

    if payload["status"] != "active":
        return

    response = client.post(
        (
            "/api/v1/record/sessions/"
            f"{payload['session_id']}/confirm"
        )
    )

    assert_true(
        response.status_code == 409,
        "An active draft was confirmed before review.",
    )


def test_confirmation_saves_once(
    client: TestClient,
    database_path: Path,
    payload: dict,
) -> dict:
    """Explicit confirmation should create exactly one journal entry."""

    ready = advance_to_review(
        client,
        payload,
    )
    before_count = count_journal_entries(
        database_path
    )
    response = client.post(
        (
            "/api/v1/record/sessions/"
            f"{ready['session_id']}/confirm"
        )
    )
    confirmed = response.json()

    assert_true(
        response.status_code == 200,
        "The confirm endpoint did not return HTTP 200.",
    )
    assert_true(
        confirmed["status"] == "confirmed",
        "The conversation was not marked confirmed.",
    )
    assert_true(
        confirmed["next_action"] == "completed",
        "The confirmed conversation did not report completion.",
    )
    assert_true(
        isinstance(
            confirmed["journal_entry_id"],
            int,
        ),
        "The confirmed response had no journal-entry ID.",
    )
    assert_true(
        count_journal_entries(
            database_path
        ) == before_count + 1,
        "Explicit confirmation did not create exactly one journal entry.",
    )

    saved = get_journal_entry(
        confirmed["journal_entry_id"],
        database_path,
    )

    if saved is None:
        raise AssertionError(
            "The confirmed journal entry could not be retrieved."
        )

    assert_true(
        saved["source"] == "fastapi_record_workflow",
        "The journal entry did not preserve the API source.",
    )

    duplicate = client.post(
        (
            "/api/v1/record/sessions/"
            f"{ready['session_id']}/confirm"
        )
    )

    assert_true(
        duplicate.status_code == 409,
        "A duplicate confirmation did not return HTTP 409.",
    )
    assert_true(
        count_journal_entries(
            database_path
        ) == before_count + 1,
        "Duplicate confirmation created another journal entry.",
    )

    return confirmed


def test_rejection_does_not_save(
    client: TestClient,
    database_path: Path,
) -> None:
    """Rejecting a reviewed draft must not create a journal entry."""

    payload = advance_to_review(
        client,
        create_record_session(
            client,
            note=(
                "The child became frustrated during an activity."
            ),
        ),
    )
    before_count = count_journal_entries(
        database_path
    )
    response = client.post(
        (
            "/api/v1/record/sessions/"
            f"{payload['session_id']}/reject"
        )
    )
    rejected = response.json()

    assert_true(
        response.status_code == 200,
        "The reject endpoint did not return HTTP 200.",
    )
    assert_true(
        rejected["status"] == "rejected",
        "The rejected conversation status was not preserved.",
    )
    assert_true(
        rejected["journal_entry_id"] is None,
        "A rejected draft unexpectedly had a journal-entry ID.",
    )
    assert_true(
        count_journal_entries(
            database_path
        ) == before_count,
        "Rejecting a draft created a journal entry.",
    )


def test_missing_and_wrong_workflow(
    client: TestClient,
    database_path: Path,
) -> None:
    """Missing IDs and strategy-session IDs should fail predictably."""

    missing = client.get(
        "/api/v1/record/sessions/99999"
    )

    assert_true(
        missing.status_code == 404,
        "A missing record session did not return HTTP 404.",
    )

    strategy_id = create_conversation_session(
        ConversationWorkflow.ask_strategy,
        database_path=database_path,
    )
    wrong_workflow = client.get(
        f"/api/v1/record/sessions/{strategy_id}"
    )

    assert_true(
        wrong_workflow.status_code == 409,
        "A strategy-session ID did not return HTTP 409.",
    )


def test_openapi_record_contract(
    client: TestClient,
) -> None:
    """Swagger/OpenAPI should expose every Stage 5B route."""

    response = client.get(
        "/openapi.json"
    )
    paths = response.json().get(
        "paths",
        {},
    )
    required_paths = {
        "/api/v1/record/sessions",
        "/api/v1/record/sessions/{session_id}",
        "/api/v1/record/sessions/{session_id}/messages",
        "/api/v1/record/sessions/{session_id}/confirm",
        "/api/v1/record/sessions/{session_id}/reject",
    }

    assert_true(
        response.status_code == 200,
        "The OpenAPI document was unavailable.",
    )
    assert_true(
        required_paths.issubset(
            paths
        ),
        "One or more Stage 5B routes were missing from OpenAPI.",
    )


def main() -> None:
    """Run all Stage 5B record-workflow API tests."""

    passed = 0
    total = 10

    with tempfile.TemporaryDirectory() as directory_name:
        database_path = (
            Path(directory_name)
            / "api_record_workflow_test.db"
        )
        application = create_app(
            database_path
        )

        with TestClient(
            application
        ) as client:
            payload = test_create_session(
                client,
                database_path,
            )
            passed += 1
            print("[PASS] record-session creation")

            test_whitespace_note_rejected(
                client
            )
            passed += 1
            print("[PASS] whitespace-note validation")

            test_get_session(
                client,
                payload,
            )
            passed += 1
            print("[PASS] record-session retrieval")

            payload = test_follow_up_message(
                client,
                payload,
            )
            passed += 1
            print("[PASS] follow-up message persistence")

            test_confirmation_requires_review(
                client
            )
            passed += 1
            print("[PASS] confirmation review boundary")

            test_confirmation_saves_once(
                client,
                database_path,
                payload,
            )
            passed += 1
            print("[PASS] explicit confirmation and idempotency")

            test_rejection_does_not_save(
                client,
                database_path,
            )
            passed += 1
            print("[PASS] rejection without journal save")

            test_missing_and_wrong_workflow(
                client,
                database_path,
            )
            passed += 1
            print("[PASS] missing and wrong-workflow handling")

            test_openapi_record_contract(
                client
            )
            passed += 1
            print("[PASS] record-workflow OpenAPI contract")

            health = client.get(
                "/health"
            )
            assert_true(
                health.status_code == 200,
                "The Stage 5A health endpoint regressed.",
            )
            passed += 1
            print("[PASS] Stage 5A health regression guard")

    print("\nAPI RECORD WORKFLOW TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")


if __name__ == "__main__":
    main()
