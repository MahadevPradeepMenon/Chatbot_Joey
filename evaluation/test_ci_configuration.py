"""Static regression checks for the Joey GitHub Actions workflow."""

from __future__ import annotations

import re
from pathlib import Path


# Resolve the workflow path relative to the repository so the static CI checks
# work consistently from local shells and GitHub-hosted runners.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = (
    PROJECT_ROOT
    / ".github"
    / "workflows"
    / "ci.yml"
)


# Centralise workflow loading so every regression check reads the same ci.yml file.
def workflow_text() -> str:
    """Read the required CI workflow."""

    # Treat a missing workflow as a test failure rather than allowing later string
    # checks to operate on absent configuration.
    if not WORKFLOW_PATH.exists():
        raise AssertionError(
            "The GitHub Actions workflow is missing."
        )

    return WORKFLOW_PATH.read_text(
        encoding="utf-8"
    )


# Keep the configuration checks runnable as a standalone regression script without
# requiring an external test framework.
def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise one readable workflow-test failure."""

    if not condition:
        raise AssertionError(message)


def test_expected_triggers() -> None:
    """CI should run automatically and also support manual execution."""

    content = workflow_text()

    # Require the three intended entry points: automatic pushes, pull requests and
    # manual workflow dispatch.
    for trigger in (
        "push:",
        "pull_request:",
        "workflow_dispatch:",
    ):
        assert_true(
            trigger in content,
            f"The CI trigger is missing: {trigger}",
        )

    # Explicitly reject the more privileged pull_request_target event because it can
    # expose repository permissions to untrusted pull-request code.
    assert_true(
        "pull_request_target:" not in content,
        "The privileged pull_request_target trigger must not be used.",
    )


def test_least_privilege_permissions() -> None:
    """The workflow token should receive read-only repository access."""

    content = workflow_text()

    # Use a whitespace-tolerant regular expression so formatting changes do not hide
    # whether the workflow token is limited to read-only repository contents.
    assert_true(
        re.search(
            r"permissions:\s*\n\s+contents:\s+read",
            content,
        )
        is not None,
        "The workflow does not use read-only contents permission.",
    )


def test_actions_are_sha_pinned() -> None:
    """External actions should be referenced by immutable full SHAs."""

    content = workflow_text()

    # Extract action names and revisions so each external action can be checked for
    # immutable 40-character commit-SHA pinning.
    action_references = re.findall(
        r"uses:\s+([^@\s]+)@([0-9a-fA-F]+)",
        content,
    )

    assert_true(
        len(action_references) >= 2,
        "The checkout and Python setup actions were not found.",
    )

    # Validate every discovered action reference rather than checking only the first.
    for action_name, revision in action_references:
        assert_true(
            len(revision) == 40,
            f"{action_name} is not pinned to a full commit SHA.",
        )


# Verify that CI matches the project Python version and uses dependency caching tied
# to requirements.txt so cache invalidation follows dependency changes.
def test_python_and_cache_configuration() -> None:
    """The hosted runner should match Joey's Python version and cache pip."""

    content = workflow_text()

    assert_true(
        'python-version: "3.12"' in content,
        "The workflow is not pinned to Python 3.12.",
    )
    assert_true(
        "cache: pip" in content,
        "Pip dependency caching is not configured.",
    )
    assert_true(
        "cache-dependency-path: requirements.txt"
        in content,
        "The pip cache is not tied to requirements.txt.",
    )


# Confirm that CI installs CPU-targeted PyTorch packages, avoiding unnecessary CUDA
# downloads for the local inference configuration used by Hey Joey.
def test_cpu_only_dependency_installation() -> None:
    """CI should avoid downloading CUDA packages for local CPU inference."""

    content = workflow_text()

    assert_true(
        "https://download.pytorch.org/whl/cpu"
        in content,
        "The CPU-only PyTorch package index is missing.",
    )
    assert_true(
        '"torch==2.12.1"' in content,
        "The CI PyTorch version is not explicit.",
    )


def test_quality_commands() -> None:
    """Compilation, dependency checks and the project suite should all run."""

    content = workflow_text()

    # Require dependency validation, bytecode compilation and the project regression
    # suite so CI covers both static syntax and runtime checks.
    for command in (
        "python -m pip check",
        "python -m compileall api app rag safety storage evaluation",
        "python -m evaluation.run_ci_suite",
    ):
        assert_true(
            command in content,
            f"The CI command is missing: {command}",
        )


# Check workflow controls that limit wasted runner time and ensure failures are not
# silently ignored.
def test_resource_controls() -> None:
    """Stale runs should cancel and individual jobs should have a timeout."""

    content = workflow_text()

    assert_true(
        "cancel-in-progress: true" in content,
        "Stale CI runs are not cancelled.",
    )
    assert_true(
        "timeout-minutes: 30" in content,
        "The CI job does not have the expected timeout.",
    )
    assert_true(
        "continue-on-error:" not in content,
        "CI failures must not be silently ignored.",
    )


def main() -> None:
    """Run all GitHub Actions configuration checks."""

    # Keep configuration checks in a fixed order for deterministic local and CI output.
    tests = [
        ("push, pull request and manual triggers", test_expected_triggers),
        ("least-privilege token permissions", test_least_privilege_permissions),
        ("immutable action references", test_actions_are_sha_pinned),
        ("Python and pip cache configuration", test_python_and_cache_configuration),
        ("CPU-only dependency installation", test_cpu_only_dependency_installation),
        ("compile and regression commands", test_quality_commands),
        ("CI resource controls", test_resource_controls),
    ]

    passed = 0

    # Any failed assertion stops the module with a non-zero exit status that the
    # wider CI suite can detect.
    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")

    print("\nCI CONFIGURATION TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


# Run the GitHub Actions configuration regressions only when executed directly.
if __name__ == "__main__":
    main()
