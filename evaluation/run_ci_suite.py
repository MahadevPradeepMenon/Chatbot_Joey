"""Run Joey's deterministic regression suite for local and GitHub CI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


# Resolve the evaluation directory relative to the repository so the CI runner
# behaves consistently whether executed locally or inside GitHub Actions.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"

# This test needs live containers and is run after `docker compose up --wait`,
# not inside the ordinary Python regression job.
# Keeping it excluded prevents the normal suite from depending on a running Docker stack.
# not inside the ordinary Python regression job.
EXCLUDED_TEST_FILES = {
    "test_docker_runtime.py",
}


def discover_test_modules() -> list[str]:
    """Discover script-style evaluation tests in stable filename order."""

    # Discover tests dynamically so new script-style regression modules are picked
    # up automatically without maintaining a separate hard-coded list.
    modules: list[str] = []

    # Sort filenames to keep execution order deterministic across local and CI runs.
    for path in sorted(
        EVALUATION_DIR.glob(
            "test_*.py"
        )
    ):
        # Skip modules that require external runtime conditions handled elsewhere.
        if path.name in EXCLUDED_TEST_FILES:
            continue

        # Convert each test file path into a Python module name for `python -m` execution.
        modules.append(
            f"evaluation.{path.stem}"
        )

    # Treat an empty discovery result as a configuration failure rather than a pass.
    if not modules:
        raise RuntimeError(
            "No CI regression test modules were discovered."
        )

    return modules


def run_module(
    module_name: str,
) -> int:
    """Run one regression module and stream its captured output."""

    print(
        f"\n{'=' * 72}\n"
        f"RUNNING: {module_name}\n"
        f"{'=' * 72}",
        flush=True,
    )

    # Execute each regression module in a fresh Python subprocess using the same
    # interpreter and repository root as the CI runner itself.
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            module_name,
        ],
        cwd=PROJECT_ROOT,
        text=True,
        # Capture stdout/stderr so each module's output can be replayed clearly
        # while still allowing the suite to inspect its return code.
        capture_output=True,
        check=False,
    )

    # Replay captured standard output immediately to preserve useful test diagnostics.
    if completed.stdout:
        print(
            completed.stdout.rstrip(),
            flush=True,
        )

    # Keep error output on stderr so CI logs preserve the original stream distinction.
    if completed.stderr:
        print(
            completed.stderr.rstrip(),
            file=sys.stderr,
            flush=True,
        )

    return completed.returncode


def main() -> None:
    """Run every discovered deterministic test and report one CI summary."""

    # Discover the current deterministic regression modules once at the start of the run.
    modules = discover_test_modules()
    failures: list[str] = []

    print("JOEY CONTINUOUS INTEGRATION SUITE")
    print("=" * 72)
    print(
        f"Discovered test modules: {len(modules)}"
    )

    # Run every module even if an earlier one fails so the final report captures
    # the complete set of regression failures in a single CI run.
    for module_name in modules:
        return_code = run_module(
            module_name
        )

        # Record non-zero subprocess exits while allowing remaining tests to continue.
        if return_code != 0:
            failures.append(
                module_name
            )

    print("\nCI SUITE RESULTS")
    print("=" * 72)
    print(
        f"Modules passed: "
        f"{len(modules) - len(failures)}/{len(modules)}"
    )

    # Any failed module causes the overall CI command to exit with status 1.
    if failures:
        print("\nFailed modules:")

        for module_name in failures:
            print(
                f"- {module_name}"
            )

        # A non-zero process exit allows GitHub Actions and local scripts to detect failure.
        raise SystemExit(1)

    print("Status: PASS")


# Run the regression suite only when this module is executed directly.
if __name__ == "__main__":
    main()
