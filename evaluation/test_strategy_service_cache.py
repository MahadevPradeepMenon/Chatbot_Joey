"""Regression test for caching the local semantic retrieval service."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, Request

import api.routers.strategies as strategies_module


# Use a lightweight sentinel object so the test can detect whether the dependency
# returns the same service instance without constructing the real semantic stack.
class FakeCachedService:
    """Minimal sentinel retrieval service."""


# Keep this regression module runnable as a standalone script without requiring
# an external testing framework.
def assert_true(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)


def test_real_strategy_service_is_cached() -> None:
    """The expensive local semantic service should be constructed once."""

    # Track how many times the replacement builder is invoked; correct caching means
    # this count should remain one across repeated dependency calls.
    build_calls = 0
    service = FakeCachedService()

    # Replace the expensive real builder with a deterministic function that returns
    # the same sentinel service and records each construction attempt.
    def fake_builder(
        database_path: Path,
    ) -> FakeCachedService:
        nonlocal build_calls
        del database_path
        build_calls += 1
        return service

    # Build a minimal FastAPI application carrying the same state attribute inspected
    # by the strategy-service dependency.
    application = FastAPI()
    application.state.strategy_service_factory = None

    # Construct the smallest valid HTTP ASGI scope needed to create a Request object
    # for direct dependency invocation without starting a server.
    scope = {
        "type": "http",
        "app": application,
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
        "root_path": "",
        "http_version": "1.1",
    }
    request = Request(scope)

    # Preserve the module-level builder so the test can restore global state even
    # if an assertion or dependency call fails.
    original_builder = (
        strategies_module.build_strategy_retrieval_service
    )

    # Use a disposable database path because the dependency accepts a database path
    # even though the fake builder deliberately ignores it.
    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "strategy_cache_test.db"
        )

        # Temporarily monkey-patch the production builder to isolate cache behaviour.
        try:
            strategies_module.build_strategy_retrieval_service = (
                fake_builder
            )

            # Call the dependency twice with the same request/app state and database
            # path; the second call should reuse the cached instance.
            first = strategies_module._strategy_service(
                request,
                database_path,
            )
            second = strategies_module._strategy_service(
                request,
                database_path,
            )
        # Always restore the original builder so this regression cannot leak modified
        # module state into later tests.
        finally:
            strategies_module.build_strategy_retrieval_service = (
                original_builder
            )

    # Identity checks prove that both dependency calls return the exact sentinel
    # instance created by the fake builder, not merely equivalent objects.
    assert_true(
        first is service,
        "The first dependency call returned the wrong service.",
    )
    assert_true(
        second is service,
        "The cached service was not reused.",
    )
    assert_true(
        build_calls == 1,
        "The expensive strategy service was constructed more than once.",
    )


# Provide a simple standalone entry point compatible with the project CI runner.
def main() -> None:
    test_real_strategy_service_is_cached()
    print("[PASS] local strategy service cache")
    print("\nSTRATEGY SERVICE CACHE TEST RESULTS")
    print("=" * 60)
    print("Tests passed: 1/1")


# Run the strategy-service cache regression only when this module is executed directly.
if __name__ == "__main__":
    main()
