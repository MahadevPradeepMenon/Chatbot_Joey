"""Runtime smoke tests for the Dockerised Hey Joey services."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


API_BASE_URL = "http://127.0.0.1:8000"
FRONTEND_HEALTH_URL = (
    "http://127.0.0.1:8501/_stcore/health"
)


def fetch_text(url: str) -> str:
    try:
        with urllib.request.urlopen(
            url,
            timeout=15,
        ) as response:
            return response.read().decode("utf-8")
    except (
        urllib.error.URLError,
        TimeoutError,
    ) as error:
        raise AssertionError(
            "The Docker service could not be reached at "
            f"{url}. Run 'docker compose up --build --wait' first."
        ) from error


def fetch_json(url: str) -> dict[str, Any]:
    text = fetch_text(url)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"The endpoint did not return valid JSON: {url}"
        ) from error

    if not isinstance(payload, dict):
        raise AssertionError(
            f"The endpoint did not return a JSON object: {url}"
        )

    return payload


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_api_health() -> None:
    payload = fetch_json(f"{API_BASE_URL}/health")

    assert_true(
        payload.get("status") == "ok",
        "The API health status was not ok.",
    )


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


def test_streamlit_health() -> None:
    response = fetch_text(
        FRONTEND_HEALTH_URL
    ).strip().lower()

    assert_true(
        response == "ok",
        "The Streamlit health endpoint did not return ok.",
    )


def main() -> None:
    tests = [
        ("Docker API health", test_api_health),
        ("Docker API readiness", test_api_readiness),
        ("Docker Streamlit health", test_streamlit_health),
    ]

    passed = 0

    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")

    print("\nDOCKER RUNTIME TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


if __name__ == "__main__":
    main()
