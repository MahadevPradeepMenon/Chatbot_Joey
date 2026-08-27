"""Runtime smoke tests for the Dockerised Hey Joey services."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


# These smoke tests target the host ports exposed by Docker Compose after the
# containers have been started and reported healthy.
API_BASE_URL = "http://127.0.0.1:8000"
FRONTEND_HEALTH_URL = (
    "http://127.0.0.1:8501/_stcore/health"
)


# Use Python's standard-library HTTP client so the runtime smoke test does not add
# another dependency beyond the application environment itself.
def fetch_text(url: str) -> str:
    try:
        # Apply a finite timeout so an unavailable or unhealthy container fails the
        # regression promptly instead of hanging indefinitely.
        with urllib.request.urlopen(
            url,
            timeout=15,
        ) as response:
            return response.read().decode("utf-8")
    # Convert connection and timeout failures into a clear assertion that also
    # reminds the developer how to start the Docker stack before running this test.
    except (
        urllib.error.URLError,
        TimeoutError,
    ) as error:
        raise AssertionError(
            "The Docker service could not be reached at "
            f"{url}. Run 'docker compose up --build --wait' first."
        ) from error


# Layer JSON validation on top of fetch_text so API smoke tests can share the same
# connection handling while still enforcing an object-shaped response contract.
def fetch_json(url: str) -> dict[str, Any]:
    text = fetch_text(url)

    # Parse the raw response explicitly so malformed backend output produces a
    # targeted regression failure rather than a later key-access error.
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"The endpoint did not return valid JSON: {url}"
        ) from error

    # The health/readiness endpoints are expected to return JSON objects, not lists
    # or scalar values.
    if not isinstance(payload, dict):
        raise AssertionError(
            f"The endpoint did not return a JSON object: {url}"
        )

    return payload


# Keep the module runnable as a standalone smoke-test script without requiring an
# external testing framework.
def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# Verify the running FastAPI container responds on the exposed host port and reports
# its lightweight liveness state as ok.
def test_api_health() -> None:
    payload = fetch_json(f"{API_BASE_URL}/health")

    assert_true(
        payload.get("status") == "ok",
        "The API health status was not ok.",
    )


# Readiness is stricter than liveness: it confirms the API reports itself ready and
# that the mounted SQLite storage is available inside the running container.
def test_api_readiness() -> None:
    payload = fetch_json(f"{API_BASE_URL}/ready")

    assert_true(
        payload.get("status") == "ready",
        "The API readiness status was not ready.",
    )
    assert_true(
        payload.get("database_ready") is True,
        "The mounted SQLite database was not ready.",
    )


# Check Streamlit's built-in health endpoint through the frontend container's
# exposed host port.
def test_streamlit_health() -> None:
    # Normalise surrounding whitespace and case before comparing the simple health
    # response returned by Streamlit.
    response = fetch_text(
        FRONTEND_HEALTH_URL
    ).strip().lower()

    assert_true(
        response == "ok",
        "The Streamlit health endpoint did not return ok.",
    )


def main() -> None:
    # Run the three live-container smoke checks in a fixed order for deterministic
    # local and Docker CI output.
    tests = [
        ("Docker API health", test_api_health),
        ("Docker API readiness", test_api_readiness),
        ("Docker Streamlit health", test_streamlit_health),
    ]

    passed = 0

    # Any failed assertion stops the script with a non-zero exit status that the
    # Docker CI job can detect.
    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")

    print("\nDOCKER RUNTIME TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


# Run the live Docker smoke tests only when this module is executed directly.
if __name__ == "__main__":
    main()
