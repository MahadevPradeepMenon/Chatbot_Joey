"""Regression test for caching the local semantic retrieval service."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, Request

import api.routers.strategies as strategies_module


class FakeCachedService:
    """Minimal sentinel retrieval service."""


def assert_true(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)


def test_real_strategy_service_is_cached() -> None:
    """The expensive local semantic service should be constructed once."""

    build_calls = 0
    service = FakeCachedService()

    def fake_builder(
        database_path: Path,
    ) -> FakeCachedService:
        nonlocal build_calls
        del database_path
        build_calls += 1
        return service

    application = FastAPI()
    application.state.strategy_service_factory = None

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

    original_builder = (
        strategies_module.build_strategy_retrieval_service
    )

    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "strategy_cache_test.db"
        )

        try:
            strategies_module.build_strategy_retrieval_service = (
                fake_builder
            )

            first = strategies_module._strategy_service(
                request,
                database_path,
            )
            second = strategies_module._strategy_service(
                request,
                database_path,
            )
        finally:
            strategies_module.build_strategy_retrieval_service = (
                original_builder
            )

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


def main() -> None:
    test_real_strategy_service_is_cached()
    print("[PASS] local strategy service cache")
    print("\nSTRATEGY SERVICE CACHE TEST RESULTS")
    print("=" * 60)
    print("Tests passed: 1/1")


if __name__ == "__main__":
    main()
