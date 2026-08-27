"""Static regression checks for Joey's Docker CI workflow."""

from __future__ import annotations

import re
from pathlib import Path


# Resolve the Docker CI workflow path relative to the repository so these static
# checks behave consistently from local shells and GitHub-hosted runners.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = (
    PROJECT_ROOT
    / ".github"
    / "workflows"
    / "docker-ci.yml"
)


# Centralise workflow loading so every regression check reads the same docker-ci.yml file.
def workflow_text() -> str:
    """Read the required Docker CI workflow."""

    # Treat a missing workflow as a configuration failure before running any
    # content-based checks.
    if not WORKFLOW_PATH.exists():
        raise AssertionError(
            "The Docker CI workflow is missing."
        )

    return WORKFLOW_PATH.read_text(
        encoding="utf-8"
    )


# Keep this configuration module runnable as a standalone regression script without
# requiring an external test framework.
def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise one readable workflow-test failure."""

    if not condition:
        raise AssertionError(message)


def test_expected_triggers_and_paths() -> None:
    """Docker CI should run only for relevant changes or manual dispatch."""

    content = workflow_text()

    # Require automatic push/pull-request execution plus manual dispatch for
    # reproducible on-demand Docker validation.
    for trigger in (
        "push:",
        "pull_request:",
        "workflow_dispatch:",
    ):
        assert_true(
            trigger in content,
            f"The Docker CI trigger is missing: {trigger}",
        )

    # Verify path filters cover the Docker build inputs and workflow definition so
    # expensive image validation runs only when relevant files change.
    for path in (
        '"Dockerfile"',
        '"compose.yaml"',
        '"requirements.txt"',
        '"api/**"',
        '"app/**"',
        '".github/workflows/docker-ci.yml"',
    ):
        assert_true(
            path in content,
            f"The Docker CI path filter is missing: {path}",
        )

    # Explicitly reject the privileged pull_request_target event for this validation
    # workflow because it is unnecessary and increases trust requirements.
    assert_true(
        "pull_request_target:" not in content,
        "The privileged pull_request_target trigger must not be used.",
    )


def test_least_privilege_permissions() -> None:
    """The workflow token should remain read-only."""

    content = workflow_text()

    # Use a whitespace-tolerant regular expression so formatting changes do not hide
    # whether the workflow token remains read-only.
    assert_true(
        re.search(
            r"permissions:\s*\n\s+contents:\s+read",
            content,
        )
        is not None,
        "Docker CI does not use read-only contents permission.",
    )


def test_actions_are_sha_pinned() -> None:
    """Every external action should use one immutable full commit SHA."""

    content = workflow_text()

    # Extract external action names and revisions so each can be checked for
    # immutable full commit-SHA pinning.
    action_references = re.findall(
        r"uses:\s+([^@\s]+)@([0-9a-fA-F]+)",
        content,
    )

    assert_true(
        len(action_references) == 3,
        "Docker CI should use checkout, setup-buildx and build-push.",
    )

    # Validate every discovered action reference rather than checking only one.
    for action_name, revision in action_references:
        assert_true(
            len(revision) == 40,
            f"{action_name} is not pinned to a full commit SHA.",
        )


def test_compose_validation() -> None:
    """Compose should be checked before the expensive image build."""

    content = workflow_text()

    # Compare string positions to prove Compose syntax validation happens before the
    # more expensive Docker image build step.
    compose_position = content.find(
        "docker compose config --quiet"
    )
    build_position = content.find(
        "docker/build-push-action@"
    )

    assert_true(
        compose_position >= 0,
        "The Compose validation command is missing.",
    )
    assert_true(
        build_position >= 0,
        "The Docker build action is missing.",
    )
    assert_true(
        compose_position < build_position,
        "Compose must be validated before the image build.",
    )


# Confirm the workflow builds the same Dockerfile, context and target platform used
# for production-style validation rather than a separate test image.
def test_production_build_settings() -> None:
    """The workflow should validate the actual production image."""

    content = workflow_text()

    # Require cancellation, timeout, disk cleanup and disabled metadata outputs so
    # the comparatively expensive Docker job remains bounded and lean.
    for setting in (
        "context: .",
        "file: ./Dockerfile",
        "platforms: linux/amd64",
        "tags: chatbot-joey:ci",
    ):
        assert_true(
            setting in content,
            f"The production build setting is missing: {setting}",
        )


# Enforce build-only CI behaviour: validation may construct the image locally but
# must not authenticate to or publish into a container registry.
def test_image_is_not_published() -> None:
    """Stage 7B must build but never publish or authenticate to a registry."""

    content = workflow_text()

    assert_true(
        "push: false" in content,
        "The validation workflow must not publish the image.",
    )
    assert_true(
        "docker/login-action@" not in content,
        "Docker CI must not log into a container registry.",
    )
    assert_true(
        "secrets." not in content,
        "Docker CI should not require repository secrets.",
    )


# Check that BuildKit reuses the GitHub Actions cache for faster repeated image
# validation while keeping one explicit cache scope.
def test_build_cache_configuration() -> None:
    """BuildKit should use the GitHub Actions cache backend."""

    content = workflow_text()

    assert_true(
        "cache-from: type=gha,scope=joey-production-image"
        in content,
        "The BuildKit cache restore configuration is missing.",
    )
    assert_true(
        "cache-to: type=gha,mode=max,scope=joey-production-image"
        in content,
        "The BuildKit cache save configuration is missing.",
    )


def test_resource_and_metadata_controls() -> None:
    """The expensive build should be bounded and avoid unnecessary outputs."""

    content = workflow_text()

    for setting in (
        "cancel-in-progress: true",
        "timeout-minutes: 60",
        "Reclaim runner disk space",
        "docker system prune --all --force",
        "provenance: false",
        "sbom: false",
    ):
        assert_true(
            setting in content,
            f"The Docker CI control is missing: {setting}",
        )

    assert_true(
        "continue-on-error:" not in content,
        "Docker build failures must not be silently ignored.",
    )


def main() -> None:
    """Run all Stage 7B Docker CI configuration checks."""

    # Keep Docker CI regression checks in a fixed order for deterministic local and
    # hosted-runner output.
    tests = [
        (
            "relevant automatic and manual triggers",
            test_expected_triggers_and_paths,
        ),
        (
            "least-privilege token permissions",
            test_least_privilege_permissions,
        ),
        (
            "immutable action references",
            test_actions_are_sha_pinned,
        ),
        (
            "Compose validation order",
            test_compose_validation,
        ),
        (
            "production image settings",
            test_production_build_settings,
        ),
        (
            "build-only registry policy",
            test_image_is_not_published,
        ),
        (
            "GitHub Actions BuildKit cache",
            test_build_cache_configuration,
        ),
        (
            "Docker CI resource controls",
            test_resource_and_metadata_controls,
        ),
    ]

    passed = 0

    # Any failed assertion stops the module with a non-zero exit status that the
    # wider CI suite can detect.
    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")

    print("\nDOCKER CI CONFIGURATION TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


# Run the Docker CI configuration regressions only when executed directly.
if __name__ == "__main__":
    main()
