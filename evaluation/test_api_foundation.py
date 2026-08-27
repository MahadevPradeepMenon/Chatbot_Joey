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


# Keep this regression module runnable as a standalone script without requiring
# an external testing framework.
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

    # Exercise the lightweight liveness endpoint through FastAPI's in-process
    # TestClient rather than starting a separate HTTP server.
    response = client.get(
        "/health"
    )

    assert_true(
        response.status_code == 200,
        "The health endpoint did not return HTTP 200.",
    )

    # Decode the JSON body so both status code and contract fields are verified.
    payload = response.json()

    assert_true(
        payload == {
            "status": "ok",
            "service": SERVICE_NAME,
            "api_version": API_VERSION,
        },
        "The health response payload was unexpected.",
    )


# Verify that deployment/application version metadata remains exposed through a
# stable HTTP contract.
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


# Readiness is stricter than liveness: it confirms the local database schema is
# complete enough for the application to serve requests.
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

    # Inspect the same database after TestClient startup to confirm the FastAPI
    # lifespan initialiser created every required storage table.
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

    # Use the generated OpenAPI document as a contract check that all system
    # endpoints remain registered on the application.
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

    # Confirm that the local Swagger UI remains available for manual API inspection.
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

    # Exercise FastAPI's normal missing-route behaviour to guard against accidental
    # catch-all routing.
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

    # Give each application factory call a distinct database path to prove that
    # app instances do not share SQLite state implicitly.
    first_path = directory / "first.db"
    second_path = directory / "second.db"

    # Build two independent FastAPI application instances using the same factory.
    first_app = create_app(
        first_path
    )
    second_app = create_app(
        second_path
    )

    # Entering TestClient triggers each application's lifespan startup and schema
    # initialisation before readiness is checked.
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

    # Open both SQLite files directly to confirm isolation extends to stored data,
    # not just differing filesystem paths.
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

    # Run the API foundation suite against disposable database files so tests are
    # isolated from normal application data and repeatable in CI.
    with tempfile.TemporaryDirectory() as directory_name:
        directory = Path(
            directory_name
        )
        database_path = (
            directory
            / "api_foundation_test.db"
        )
        # Inject the temporary database into the application factory used by all
        # endpoint checks in this test run.
        application = create_app(
            database_path
        )

        # Keeping one TestClient open across endpoint checks reuses a single active
        # application lifespan and database instance.
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

        # Run the factory-isolation check outside the shared TestClient so it can
        # create and start two additional independent applications.
        test_app_factory_database_isolation(
            directory
        )
        passed += 1
        print("[PASS] application factory database isolation")

    print("\nAPI FOUNDATION TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")


# Run the FastAPI foundation regressions only when this module is executed directly.
if __name__ == "__main__":
    main()
