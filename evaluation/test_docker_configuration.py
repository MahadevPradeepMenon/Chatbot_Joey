"""Static checks for the Hey Joey Docker configuration."""

from __future__ import annotations

from pathlib import Path


# Resolve Docker-related files relative to the repository so these static checks
# behave consistently from local shells and CI working directories.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Centralise project-file loading and fail clearly when a required Docker artifact
# is missing before any content assertions are attempted.
def read_project_file(relative_path: str) -> str:
    path = PROJECT_ROOT / relative_path

    if not path.exists():
        raise AssertionError(
            f"Required Docker file is missing: {relative_path}"
        )

    return path.read_text(encoding="utf-8")


# Keep the module runnable as a standalone regression script without requiring an
# external testing framework.
def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# Verify that the repository contains the minimum Docker, Compose, ignore and
# environment-template files needed for local container deployment.
def test_required_files() -> None:
    for relative_path in (
        "Dockerfile",
        "compose.yaml",
        ".dockerignore",
        ".env.example",
    ):
        assert_true(
            (PROJECT_ROOT / relative_path).exists(),
            f"{relative_path} is missing.",
        )


# Check the container base image matches the project Python version and that the
# final runtime switches away from root privileges.
def test_python_image_and_non_root_user() -> None:
    content = read_project_file("Dockerfile")

    assert_true(
        "FROM python:3.12-slim" in content,
        "The Dockerfile should use Python 3.12 slim.",
    )
    assert_true(
        "USER joey" in content,
        "The container should not run as root.",
    )


# Confirm the Docker build prepares the local sentence-embedding model ahead of
# runtime and exposes the model choice as a build argument.
def test_model_is_preloaded() -> None:
    content = read_project_file("Dockerfile")

    assert_true(
        "SentenceTransformer" in content,
        "The semantic model is not preloaded.",
    )
    assert_true(
        "EMBEDDING_MODEL" in content,
        "The embedding-model build argument is missing.",
    )


# Require separate API and frontend services while avoiding fixed container names,
# which would make parallel or renamed deployments harder to run.
def test_compose_services() -> None:
    content = read_project_file("compose.yaml")

    assert_true(
        "\n  api:\n" in content,
        "The API service is missing.",
    )
    assert_true(
        "\n  frontend:\n" in content,
        "The frontend service is missing.",
    )
    assert_true(
        "container_name:" not in content,
        "Fixed container names should not be used.",
    )


def test_internal_api_networking() -> None:
    content = read_project_file("compose.yaml")

    assert_true(
        "HEY_JOEY_API_URL: http://api:8000" in content,
        "The frontend is not using Docker service discovery.",
    )

    # Isolate the frontend Compose section before checking that it does not use
    # loopback addressing for backend communication inside Docker.
    frontend_section = content.split(
        "frontend:",
        maxsplit=1,
    )[1]

    assert_true(
        "http://127.0.0.1:8000" not in frontend_section,
        "The frontend must not call its own loopback interface.",
    )


# Verify startup ordering is health-aware and that both FastAPI and Streamlit expose
# the expected health endpoints used by Compose.
def test_health_aware_startup() -> None:
    content = read_project_file("compose.yaml")

    assert_true(
        "condition: service_healthy" in content,
        "The frontend does not wait for API readiness.",
    )
    assert_true(
        "http://127.0.0.1:8000/ready" in content,
        "The API readiness health check is missing.",
    )
    assert_true(
        "/_stcore/health" in content,
        "The Streamlit health check is missing.",
    )


# Check that mutable runtime data is mounted from the host while also being excluded
# from the immutable Docker image build context.
def test_runtime_data_mount() -> None:
    compose_content = read_project_file("compose.yaml")
    ignore_content = read_project_file(".dockerignore")

    assert_true(
        "source: ./data" in compose_content,
        "The existing data directory is not mounted.",
    )
    assert_true(
        "target: /app/data" in compose_content,
        "The data directory has the wrong target.",
    )
    assert_true(
        "\ndata\n" in f"\n{ignore_content}\n",
        "The data directory is not excluded from the image.",
    )


# Confirm container commands use production-style networking/process settings and
# do not enable development reload behaviour.
def test_production_commands() -> None:
    dockerfile = read_project_file("Dockerfile")
    compose_content = read_project_file("compose.yaml")

    assert_true(
        "0.0.0.0" in dockerfile,
        "The backend does not bind to all interfaces.",
    )
    assert_true(
        "--reload" not in compose_content,
        "Development reload should not run in containers.",
    )
    assert_true(
        "--workers" in compose_content,
        "The API worker count is not explicit.",
    )


def main() -> None:
    # Keep Docker configuration regressions in a fixed order for deterministic local
    # and CI progress output.
    tests = [
        ("required Docker files", test_required_files),
        (
            "pinned image and non-root user",
            test_python_image_and_non_root_user,
        ),
        ("semantic model preload", test_model_is_preloaded),
        ("separate Compose services", test_compose_services),
        ("internal API networking", test_internal_api_networking),
        ("health-aware startup", test_health_aware_startup),
        ("runtime data mount", test_runtime_data_mount),
        ("production container commands", test_production_commands),
    ]

    passed = 0

    # Any failed assertion stops the module with a non-zero exit status that the
    # wider CI runner can detect.
    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")

    print("\nDOCKER CONFIGURATION TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


# Run the Docker configuration regressions only when this module is executed directly.
if __name__ == "__main__":
    main()
