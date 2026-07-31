"""Run Joey's deterministic regression suite for local and GitHub CI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"

# This test needs live containers and is run after `docker compose up --wait`,
# not inside the ordinary Python regression job.
EXCLUDED_TEST_FILES = {
    "test_docker_runtime.py",
}


def discover_test_modules() -> list[str]:
    """Discover script-style evaluation tests in stable filename order."""

    modules: list[str] = []

    for path in sorted(
        EVALUATION_DIR.glob(
            "test_*.py"
        )
    ):
        if path.name in EXCLUDED_TEST_FILES:
            continue

        modules.append(
            f"evaluation.{path.stem}"
        )

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

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            module_name,
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.stdout:
        print(
            completed.stdout.rstrip(),
            flush=True,
        )

    if completed.stderr:
        print(
            completed.stderr.rstrip(),
            file=sys.stderr,
            flush=True,
        )

    return completed.returncode


def main() -> None:
    """Run every discovered deterministic test and report one CI summary."""

    modules = discover_test_modules()
    failures: list[str] = []

    print("JOEY CONTINUOUS INTEGRATION SUITE")
    print("=" * 72)
    print(
        f"Discovered test modules: {len(modules)}"
    )

    for module_name in modules:
        return_code = run_module(
            module_name
        )

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

    if failures:
        print("\nFailed modules:")

        for module_name in failures:
            print(
                f"- {module_name}"
            )

        raise SystemExit(1)

    print("Status: PASS")


if __name__ == "__main__":
    main()
