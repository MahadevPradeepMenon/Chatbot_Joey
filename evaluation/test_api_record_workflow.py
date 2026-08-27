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


# Keep this regression module runnable as a standalone script without requiring
# an external testing framework.
def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable API regression-test failure."""

    if not condition:
        raise AssertionError(message)


# Centralise record-session creation so multiple tests use the same API path and
# default synthetic observation when setting up workflow state.
def create_record_session(
    client: TestClient,
    note: str = (
        "The child became upset in a noisy classroom and "
        "covered their ears."
    ),
) -> dict:
    """Create one API journal conversation and return its payload."""

    # Exercise the real FastAPI route through TestClient and submit the observation
    # using the same JSON contract as the frontend client.
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

    # Bound the follow-up loop so a workflow regression cannot leave the test
    # hanging indefinitely if review readiness is never reached.
    attempts = 0

    # Repeatedly answer outstanding follow-up questions with a neutral response
    # until the deterministic workflow reaches ready_for_review.
    while payload["status"] == "active":
        attempts += 1

        if attempts > 5:
            raise AssertionError(
                "The record workflow did not reach review state."
            )

        # Submit each follow-up to the existing persistent session rather than
        # creating a new conversation.
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

    # Create a draft through the public API and verify that this alone does not
    # write a confirmed journal entry.
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


# Verify request-model validation rejects observations that contain only
# whitespace before any workflow state is created.
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
    # Decode the persisted session payload so identity and draft contents can be
    # compared with the original POST response.
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

    # Some notes may already be review-ready after deterministic extraction; in
    # that case there is no follow-up message to test.
    if payload["status"] != "active":
        return payload

    # Capture the persistent message count before the follow-up so the test can
    # prove the exchange was appended to the same conversation.
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


# Confirm that the API enforces the explicit review boundary and will not save an
# active draft directly as a journal entry.
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

    # Ensure the draft has completed information collection before testing the
    # confirmation endpoint.
    ready = advance_to_review(
        client,
        payload,
    )
    # Record the journal count immediately before confirmation so exactly-once
    # persistence can be asserted.
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

    # Retrieve the created journal row directly to verify API source provenance.
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

    # Repeat the same confirmation request to verify idempotency at the workflow
    # boundary and prevent duplicate journal records.
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


# Verify that rejecting a review-ready draft changes conversation state without
# creating a journal entry.
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

    # Exercise both a completely missing session ID and a valid session belonging
    # to the wrong workflow so 404 and 409 behaviours remain distinct.
    missing = client.get(
        "/api/v1/record/sessions/99999"
    )

    assert_true(
        missing.status_code == 404,
        "A missing record session did not return HTTP 404.",
    )

    # Create a real strategy-workflow session in the same temporary database to
    # verify that record routes reject cross-workflow IDs.
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

    # Use the generated OpenAPI document as a contract check for all Stage 5B
    # record-workflow routes.
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

    # Run the entire API workflow suite against a disposable SQLite database so
    # the tests are isolated from normal application data and repeatable in CI.
    with tempfile.TemporaryDirectory() as directory_name:
        database_path = (
            Path(directory_name)
            / "api_record_workflow_test.db"
        )
        # Inject the temporary database into the FastAPI application factory used
        # by all record-workflow tests in this run.
        application = create_app(
            database_path
        )

        # Keeping one TestClient open preserves a single application lifespan and
        # shared temporary database across the workflow sequence.
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

            # Retain one Stage 5A liveness check as a regression guard while testing
            # the newer Stage 5B record endpoints.
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


# Run the Stage 5B record-workflow API regressions only when executed directly.
if __name__ == "__main__":
    main()
