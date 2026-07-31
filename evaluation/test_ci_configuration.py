"""Static regression checks for the Joey GitHub Actions workflow."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = (
    PROJECT_ROOT
    / ".github"
    / "workflows"
    / "ci.yml"
)


def workflow_text() -> str:
    """Read the required CI workflow."""

    if not WORKFLOW_PATH.exists():
        raise AssertionError(
            "The GitHub Actions workflow is missing."
        )

    return WORKFLOW_PATH.read_text(
        encoding="utf-8"
    )


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

    for trigger in (
        "push:",
        "pull_request:",
        "workflow_dispatch:",
    ):
        assert_true(
            trigger in content,
            f"The CI trigger is missing: {trigger}",
        )

    assert_true(
        "pull_request_target:" not in content,
        "The privileged pull_request_target trigger must not be used.",
    )


def test_least_privilege_permissions() -> None:
    """The workflow token should receive read-only repository access."""

    content = workflow_text()

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

    action_references = re.findall(
        r"uses:\s+([^@\s]+)@([0-9a-fA-F]+)",
        content,
    )

    assert_true(
        len(action_references) >= 2,
        "The checkout and Python setup actions were not found.",
    )

    for action_name, revision in action_references:
        assert_true(
            len(revision) == 40,
            f"{action_name} is not pinned to a full commit SHA.",
        )


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

    for command in (
        "python -m pip check",
        "python -m compileall api app rag safety storage evaluation",
        "python -m evaluation.run_ci_suite",
    ):
        assert_true(
            command in content,
            f"The CI command is missing: {command}",
        )


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

    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")

    print("\nCI CONFIGURATION TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


if __name__ == "__main__":
    main()
