"""Static checks for Joey's versioned container-release workflow."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = (
    PROJECT_ROOT
    / ".github"
    / "workflows"
    / "release.yml"
)
DOCUMENTATION_PATH = (
    PROJECT_ROOT
    / "docs"
    / "container_release.md"
)


def workflow_text() -> str:
    """Return the required release workflow text."""

    if not WORKFLOW_PATH.exists():
        raise AssertionError(
            "The container-release workflow is missing."
        )

    return WORKFLOW_PATH.read_text(encoding="utf-8")


def documentation_text() -> str:
    """Return the required release-process documentation."""

    if not DOCUMENTATION_PATH.exists():
        raise AssertionError(
            "The container-release documentation is missing."
        )

    return DOCUMENTATION_PATH.read_text(encoding="utf-8")


def assert_true(condition: bool, message: str) -> None:
    """Raise one readable Stage 7D validation failure."""

    if not condition:
        raise AssertionError(message)


def test_release_only_triggers() -> None:
    """Publishing should be limited to version tags or manual rebuilds."""

    content = workflow_text()

    for required in (
        "push:",
        "tags:",
        '"v*.*.*"',
        "workflow_dispatch:",
        "release_tag:",
        "required: true",
    ):
        assert_true(
            required in content,
            f"The release trigger setting is missing: {required}",
        )

    for forbidden in (
        "pull_request:",
        "pull_request_target:",
        "branches:",
        "schedule:",
    ):
        assert_true(
            forbidden not in content,
            f"The release workflow must not contain: {forbidden}",
        )


def test_release_permissions() -> None:
    """The token should read source and write packages only."""

    content = workflow_text()

    assert_true(
        re.search(
            r"permissions:\s*\n"
            r"\s+contents:\s+read\s*\n"
            r"\s+packages:\s+write",
            content,
        )
        is not None,
        "Release permissions must be contents: read and packages: write.",
    )

    for forbidden in (
        "actions: write",
        "id-token: write",
        "pull-requests: write",
        "security-events: write",
    ):
        assert_true(
            forbidden not in content,
            f"Unexpected release permission found: {forbidden}",
        )


def test_immutable_action_references() -> None:
    """Every external action should use one complete commit SHA."""

    content = workflow_text()

    references = re.findall(
        r"uses:\s+([^@\s]+)@([0-9a-fA-F]+)",
        content,
    )

    assert_true(
        len(references) == 4,
        "Release CI should use checkout, Buildx, login and build-push.",
    )

    for action_name, revision in references:
        assert_true(
            len(revision) == 40,
            f"{action_name} is not pinned to a full commit SHA.",
        )


def test_immutable_source_checkout() -> None:
    """Manual publishing should rebuild an existing tag, not a branch."""

    content = workflow_text()

    for required in (
        "Check out immutable release source",
        "inputs.release_tag || github.ref",
        "persist-credentials: false",
    ):
        assert_true(
            required in content,
            f"Immutable checkout protection is missing: {required}",
        )


def test_semantic_version_and_image_normalisation() -> None:
    """Tags should be validated and GHCR names should be lowercase."""

    content = workflow_text()

    assert_true(
        r"^v[0-9]+\.[0-9]+\.[0-9]+$" in content,
        "Strict vMAJOR.MINOR.PATCH validation is missing.",
    )
    assert_true(
        r"${GITHUB_REPOSITORY,,}" in content,
        "The GHCR image name is not converted to lowercase.",
    )
    assert_true(
        'commit_sha="$(git rev-parse HEAD)"' in content,
        "Release metadata is not anchored to the checked-out commit.",
    )


def test_registry_authentication() -> None:
    """Publishing should use GHCR and the repository-scoped token."""

    content = workflow_text()

    for required in (
        "DOCKER_REGISTRY: ghcr.io",
        "docker/login-action@",
        "username: ${{ github.actor }}",
        "password: ${{ secrets.GITHUB_TOKEN }}",
    ):
        assert_true(
            required in content,
            f"GHCR authentication setting is missing: {required}",
        )

    for forbidden in (
        "DOCKERHUB_TOKEN",
        "GHCR_TOKEN",
        "PERSONAL_ACCESS_TOKEN",
        "password: ghp_",
        "password: github_pat_",
    ):
        assert_true(
            forbidden not in content,
            f"A custom or hard-coded registry credential was found: {forbidden}",
        )


def test_versioned_image_tags_and_labels() -> None:
    """Every image should have traceable version and commit metadata."""

    content = workflow_text()

    for required in (
        "outputs.image }}:${{ steps.release.outputs.version",
        "outputs.image }}:${{ steps.release.outputs.tag",
        "outputs.image }}:sha-${{ steps.release.outputs.short_sha",
        "outputs.image }}:latest",
        "org.opencontainers.image.source=",
        "org.opencontainers.image.revision=",
        "org.opencontainers.image.version=",
    ):
        assert_true(
            required in content,
            f"Release image metadata is missing: {required}",
        )


def test_production_publish_settings() -> None:
    """The production Dockerfile should be published with attestations."""

    content = workflow_text()

    for required in (
        "docker compose config --quiet",
        "context: .",
        "file: ./Dockerfile",
        "platforms: linux/amd64",
        "push: true",
        "provenance: mode=max",
        "sbom: true",
    ):
        assert_true(
            required in content,
            f"Production publish setting is missing: {required}",
        )


def test_cache_and_execution_controls() -> None:
    """Release builds should be bounded, cached and never ignored."""

    content = workflow_text()

    for required in (
        "cancel-in-progress: false",
        "timeout-minutes: 60",
        "cache-from: type=gha,scope=joey-production-image",
        "cache-to: type=gha,mode=max,scope=joey-production-image",
        "set -euo pipefail",
    ):
        assert_true(
            required in content,
            f"Release execution control is missing: {required}",
        )

    assert_true(
        "continue-on-error:" not in content,
        "Release failures must not be silently ignored.",
    )


def test_release_documentation() -> None:
    """The repository should explain the intentional release process."""

    content = documentation_text()

    for required in (
        "git tag -a v0.1.0",
        "git push origin v0.1.0",
        "Joey Container Release",
        "GitHub Container Registry",
        "synthetic",
        "private",
    ):
        assert_true(
            required.lower() in content.lower(),
            f"Release documentation is missing: {required}",
        )


def main() -> None:
    """Run all Stage 7D workflow checks."""

    tests = [
        ("release-only triggers", test_release_only_triggers),
        ("least-privilege release permissions", test_release_permissions),
        ("immutable action references", test_immutable_action_references),
        ("immutable source checkout", test_immutable_source_checkout),
        (
            "semantic version and image normalisation",
            test_semantic_version_and_image_normalisation,
        ),
        ("repository-scoped GHCR login", test_registry_authentication),
        (
            "traceable image tags and labels",
            test_versioned_image_tags_and_labels,
        ),
        ("production publish settings", test_production_publish_settings),
        ("release cache and execution controls", test_cache_and_execution_controls),
        ("container-release documentation", test_release_documentation),
    ]

    passed = 0

    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")

    print("\nCONTAINER RELEASE CONFIGURATION TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


if __name__ == "__main__":
    main()
