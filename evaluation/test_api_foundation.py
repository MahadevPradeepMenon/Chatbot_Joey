"""Regression tests for the Stage 5A FastAPI foundation."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.dependencies import (
    REQUIRED_DATABASE_TABLES,
    inspect_database_readiness,
)
from api.main import (
    API_VERSION,
    APPLICATION_VERSION,
    SERVICE_NAME,
    create_app,
)


def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a readable test failure."""

    if not condition:
        raise AssertionError(message)


def test_health_endpoint(
    client: TestClient,
) -> None:
    """The liveness endpoint should be cheap and stable."""

    response = client.get(
        "/health"
    )

    assert_true(
        response.status_code == 200,
        "The health endpoint did not return HTTP 200.",
    )

    payload = response.json()

    assert_true(
        payload == {
            "status": "ok",
            "service": SERVICE_NAME,
            "api_version": API_VERSION,
        },
        "The health response payload was unexpected.",
    )


def test_version_endpoint(
    client: TestClient,
) -> None:
    """The API should expose application and contract versions."""

    response = client.get(
        "/version"
    )
    payload = response.json()

    assert_true(
        response.status_code == 200,
        "The version endpoint did not return HTTP 200.",
    )
    assert_true(
        payload["application_version"]
        == APPLICATION_VERSION,
        "The application version was not preserved.",
    )
    assert_true(
        payload["api_version"]
        == API_VERSION,
        "The HTTP API version was not preserved.",
    )
    assert_true(
        payload["docs_path"] == "/docs",
        "The documentation path was unexpected.",
    )


def test_readiness_endpoint(
    client: TestClient,
) -> None:
    """The readiness endpoint should confirm the complete local schema."""

    response = client.get(
        "/ready"
    )
    payload = response.json()

    assert_true(
        response.status_code == 200,
        "The readiness endpoint did not return HTTP 200.",
    )
    assert_true(
        payload["status"] == "ready",
        "The API did not report a ready state.",
    )
    assert_true(
        payload["database_ready"] is True,
        "The local database was not reported as ready.",
    )
    assert_true(
        payload["required_table_count"]
        == len(REQUIRED_DATABASE_TABLES),
        "The readiness table count was unexpected.",
    )
    assert_true(
        payload["missing_tables"] == [],
        "The ready database unexpectedly reported missing tables.",
    )


def test_lifespan_creates_all_tables(
    database_path: Path,
) -> None:
    """Application startup should initialise every current storage table."""

    readiness = inspect_database_readiness(
        database_path
    )

    assert_true(
        readiness.ready,
        "FastAPI lifespan did not initialise the complete database.",
    )
    assert_true(
        set(REQUIRED_DATABASE_TABLES).issubset(
            set(readiness.available_tables)
        ),
        "One or more required SQLite tables were not created.",
    )


def test_openapi_contract(
    client: TestClient,
) -> None:
    """OpenAPI should include each Stage 5A system endpoint."""

    response = client.get(
        "/openapi.json"
    )
    payload = response.json()
    paths = payload.get(
        "paths",
        {},
    )

    assert_true(
        response.status_code == 200,
        "The OpenAPI document was unavailable.",
    )
    assert_true(
        {
            "/health",
            "/ready",
            "/version",
        }.issubset(paths),
        "The Stage 5A endpoints were missing from OpenAPI.",
    )


def test_documentation_endpoint(
    client: TestClient,
) -> None:
    """The local Swagger UI should be available for manual testing."""

    response = client.get(
        "/docs"
    )

    assert_true(
        response.status_code == 200,
        "The Swagger documentation endpoint was unavailable.",
    )
    assert_true(
        "text/html" in response.headers.get(
            "content-type",
            "",
        ),
        "The documentation endpoint did not return HTML.",
    )


def test_unknown_route(
    client: TestClient,
) -> None:
    """Unknown API routes should return the standard HTTP 404 response."""

    response = client.get(
        "/does-not-exist"
    )

    assert_true(
        response.status_code == 404,
        "An unknown route did not return HTTP 404.",
    )


def test_app_factory_database_isolation(
    directory: Path,
) -> None:
    """Two application instances should support different SQLite files."""

    first_path = directory / "first.db"
    second_path = directory / "second.db"

    first_app = create_app(
        first_path
    )
    second_app = create_app(
        second_path
    )

    with TestClient(first_app) as first_client:
        assert_true(
            first_client.get(
                "/ready"
            ).status_code == 200,
            "The first isolated app was not ready.",
        )

    with TestClient(second_app) as second_client:
        assert_true(
            second_client.get(
                "/ready"
            ).status_code == 200,
            "The second isolated app was not ready.",
        )

    assert_true(
        first_path.exists()
        and second_path.exists(),
        "The isolated application databases were not created.",
    )
    assert_true(
        first_path != second_path,
        "The application factories unexpectedly shared one path.",
    )

    for path in (
        first_path,
        second_path,
    ):
        connection = sqlite3.connect(
            path
        )
        try:
            row = connection.execute(
                "SELECT COUNT(*) FROM journal_entries"
            ).fetchone()
        finally:
            connection.close()

        assert_true(
            row is not None
            and int(row[0]) == 0,
            "An isolated API test database contained journal data.",
        )


def main() -> None:
    """Run the Stage 5A API foundation tests."""

    passed = 0
    total = 8

    with tempfile.TemporaryDirectory() as directory_name:
        directory = Path(
            directory_name
        )
        database_path = (
            directory
            / "api_foundation_test.db"
        )
        application = create_app(
            database_path
        )

        with TestClient(
            application
        ) as client:
            test_health_endpoint(
                client
            )
            passed += 1
            print("[PASS] health endpoint")

            test_version_endpoint(
                client
            )
            passed += 1
            print("[PASS] version endpoint")

            test_readiness_endpoint(
                client
            )
            passed += 1
            print("[PASS] readiness endpoint")

            test_lifespan_creates_all_tables(
                database_path
            )
            passed += 1
            print("[PASS] lifespan database initialisation")

            test_openapi_contract(
                client
            )
            passed += 1
            print("[PASS] OpenAPI contract")

            test_documentation_endpoint(
                client
            )
            passed += 1
            print("[PASS] Swagger documentation endpoint")

            test_unknown_route(
                client
            )
            passed += 1
            print("[PASS] unknown-route handling")

        test_app_factory_database_isolation(
            directory
        )
        passed += 1
        print("[PASS] application factory database isolation")

    print("\nAPI FOUNDATION TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")


if __name__ == "__main__":
    main()
