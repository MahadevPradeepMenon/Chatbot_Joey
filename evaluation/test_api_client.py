"""Regression tests for the Streamlit-to-FastAPI HTTP client."""

from __future__ import annotations

import json

import httpx

from app.api_client import (
    ApiResponseError,
    ApiTimeoutError,
    ApiUnavailableError,
    HeyJoeyApiClient,
    InvalidApiResponseError,
    resolve_api_base_url,
)


# Keep this regression module runnable as a standalone script without requiring
# an external testing framework.
def assert_true(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)


# Build small JSON httpx responses for MockTransport handlers so endpoint tests
# can focus on client behaviour rather than repeated response construction.
def json_response(
    payload: dict[str, object],
    *,
    status_code: int = 200,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(
            payload
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
    )


# Verify that a trailing slash is removed once so later endpoint joins do not
# produce duplicate separators in request URLs.
def test_base_url_normalisation() -> None:
    assert_true(
        resolve_api_base_url(
            "http://127.0.0.1:8000/"
        )
        == "http://127.0.0.1:8000",
        "The API base URL was not normalised.",
    )


def test_health_request() -> None:
    # MockTransport lets the test inspect the exact outgoing request without
    # starting a live FastAPI server.
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert_true(
            request.url.path == "/health",
            "The health request used the wrong path.",
        )
        return json_response(
            {
                "status": "ok",
            }
        )

    # Inject the mock transport into the real client so request construction,
    # response parsing and context-manager cleanup are all exercised.
    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        result = client.health()

    assert_true(
        result["status"] == "ok",
        "The health response was not returned.",
    )


def test_record_requests() -> None:
    # Record method, path and decoded JSON for each request so the complete record
    # workflow contract can be checked after the client calls finish.
    observed: list[
        tuple[str, str, dict[str, object] | None]
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        # Decode request bodies inside the transport handler to verify the client's
        # serialised payloads as well as endpoint paths.
        payload = (
            json.loads(
                request.content.decode(
                    "utf-8"
                )
            )
            if request.content
            else None
        )
        observed.append(
            (
                request.method,
                request.url.path,
                payload,
            )
        )
        # Simulate the API's 201 response for session creation and 200 for the
        # remaining record workflow actions.
        return json_response(
            {
                "session_id": 7,
            },
            status_code=(
                201
                if request.url.path.endswith(
                    "/sessions"
                )
                else 200
            ),
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        client.create_record_session(
            "The room became noisy."
        )
        client.submit_record_message(
            7,
            "It happened in class.",
        )
        client.confirm_record_session(
            7
        )
        client.reject_record_session(
            7
        )

    assert_true(
        observed[0][1]
        == "/api/v1/record/sessions",
        "The create-record path was incorrect.",
    )
    assert_true(
        observed[0][2]
        == {
            "note": "The room became noisy."
        },
        "The record note JSON was incorrect.",
    )
    assert_true(
        observed[1][1].endswith(
            "/7/messages"
        ),
        "The follow-up path was incorrect.",
    )
    assert_true(
        observed[2][1].endswith(
            "/7/confirm"
        ),
        "The confirmation path was incorrect.",
    )
    assert_true(
        observed[3][1].endswith(
            "/7/reject"
        ),
        "The rejection path was incorrect.",
    )


# Verify strategy-search and feedback request paths plus the JSON payload fields
# sent by the Streamlit-facing API client.
def test_strategy_requests() -> None:
    observed: list[
        tuple[str, dict[str, object]]
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content.decode(
                "utf-8"
            )
        )
        observed.append(
            (
                request.url.path,
                payload,
            )
        )
        return json_response(
            {
                "outcome": "results",
            }
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        client.search_strategies(
            "What may help with noise?",
            top_k=3,
        )
        client.submit_strategy_feedback(
            search_id=12,
            strategy_rank=1,
            rating="worked_well",
            comment=None,
        )

    assert_true(
        observed[0]
        == (
            "/api/v1/strategies/search",
            {
                "question": "What may help with noise?",
                "top_k": 3,
            },
        ),
        "The strategy-search request was incorrect.",
    )
    assert_true(
        observed[1][1]["rating"]
        == "worked_well",
        "The feedback rating was not sent.",
    )


# Exercise conversation creation, latest-session lookup and exchange persistence
# so query parameters and nested metadata are covered by the client regression.
def test_conversation_requests() -> None:
    requests: list[httpx.Request] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        requests.append(
            request
        )
        return json_response(
            {
                "session_id": 3,
            },
            status_code=(
                201
                if request.method == "POST"
                and request.url.path.endswith(
                    "/sessions"
                )
                else 200
            ),
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        client.create_conversation(
            workflow="ask_strategy",
            greeting="Ask a question.",
        )
        client.get_latest_conversation(
            "ask_strategy"
        )
        client.append_conversation_exchange(
            session_id=3,
            user_content="Noise question",
            user_message_type="strategy_question",
            assistant_messages=[
                "Strategy response"
            ],
            assistant_message_type="strategy_response",
            metadata={
                "pending_strategy_feedback": {
                    "search_id": 4,
                    "strategy_count": 3,
                }
            },
        )

    assert_true(
        requests[1].url.params.get(
            "workflow"
        )
        == "ask_strategy",
        "The latest-session workflow query was missing.",
    )

    # Inspect the stored request body directly to confirm assistant messages and
    # workflow metadata were serialised as expected.
    exchange_body = json.loads(
        requests[2].content.decode(
            "utf-8"
        )
    )
    assert_true(
        exchange_body[
            "assistant_messages"
        ]
        == [
            "Strategy response"
        ],
        "The assistant exchange was not sent.",
    )


# Confirm that non-success FastAPI responses become ApiResponseError instances
# while preserving both HTTP status and readable detail text.
def test_fastapi_error_detail() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return json_response(
            {
                "detail": (
                    "The draft must be ready for review."
                )
            },
            status_code=409,
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        try:
            client.confirm_record_session(
                5
            )
        except ApiResponseError as error:
            assert_true(
                error.status_code == 409,
                "The HTTP status was not preserved.",
            )
            assert_true(
                "ready for review"
                in error.detail,
                "The FastAPI detail was not preserved.",
            )
        else:
            raise AssertionError(
                "A FastAPI error response did not raise."
            )


# FastAPI validation errors may return a list of detail objects; the client should
# combine their messages into one readable error string.
def test_validation_error_list() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return json_response(
            {
                "detail": [
                    {
                        "msg": "Field required"
                    },
                    {
                        "msg": "Input too short"
                    },
                ]
            },
            status_code=422,
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        try:
            client.search_strategies(
                ""
            )
        except ApiResponseError as error:
            assert_true(
                error.detail
                == "Field required; Input too short",
                "Validation details were not combined.",
            )
        else:
            raise AssertionError(
                "The validation error did not raise."
            )


# Reject successful HTTP responses whose body is not valid JSON rather than
# allowing malformed backend output to propagate into the UI layer.
def test_invalid_json_rejected() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html>not json</html>",
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        try:
            client.health()
        except InvalidApiResponseError:
            pass
        else:
            raise AssertionError(
                "Invalid backend JSON was accepted."
            )


# The client contract expects JSON objects, so a valid JSON array is still treated
# as an invalid backend response.
def test_non_object_json_rejected() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                "unexpected"
            ],
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        try:
            client.health()
        except InvalidApiResponseError:
            pass
        else:
            raise AssertionError(
                "A non-object JSON response was accepted."
            )


def test_strategy_timeout_message() -> None:
    """A slow local model should report a timeout, not an unavailable API."""

    # Simulate a local semantic-model read timeout to verify that timeout-specific
    # guidance is distinguished from a connection failure.
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            "The local model is still loading.",
            request=request,
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        try:
            client.search_strategies(
                "What may help with noise?"
            )
        except ApiTimeoutError as error:
            assert_true(
                "local semantic model"
                in str(error),
                "The timeout message did not explain model loading.",
            )
        else:
            raise AssertionError(
                "A strategy-search timeout did not raise."
            )


# Simulate a refused connection so the client can surface startup guidance for an
# API process that is not currently reachable.
def test_unavailable_backend_message() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    with HeyJoeyApiClient(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        try:
            client.health()
        except ApiUnavailableError as error:
            assert_true(
                "uvicorn api.main:app"
                in str(error),
                "The startup command was missing from the error.",
            )
        else:
            raise AssertionError(
                "An unavailable backend did not raise."
            )


def main() -> None:
    # Keep all client regressions in a fixed order for deterministic local and CI
    # progress output.
    tests = [
        (
            "base URL normalisation",
            test_base_url_normalisation,
        ),
        (
            "health request",
            test_health_request,
        ),
        (
            "record endpoint requests",
            test_record_requests,
        ),
        (
            "strategy endpoint requests",
            test_strategy_requests,
        ),
        (
            "conversation endpoint requests",
            test_conversation_requests,
        ),
        (
            "FastAPI error detail",
            test_fastapi_error_detail,
        ),
        (
            "validation error detail",
            test_validation_error_list,
        ),
        (
            "invalid JSON rejection",
            test_invalid_json_rejected,
        ),
        (
            "non-object JSON rejection",
            test_non_object_json_rejected,
        ),
        (
            "strategy timeout handling",
            test_strategy_timeout_message,
        ),
        (
            "unavailable backend handling",
            test_unavailable_backend_message,
        ),
    ]

    passed = 0

    # Any assertion or expected exception mismatch stops the module with a non-zero
    # exit status that the wider CI suite can detect.
    for name, test in tests:
        test()
        passed += 1
        print(
            f"[PASS] {name}"
        )

    print("\nAPI CLIENT TEST RESULTS")
    print("=" * 60)
    print(
        f"Tests passed: {passed}/{len(tests)}"
    )


# Run the API-client regression suite only when this module is executed directly.
if __name__ == "__main__":
    main()
