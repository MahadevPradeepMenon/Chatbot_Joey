"""Repository guard against committed secrets and private runtime data."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


# Resolve repository files relative to this test module so Git and ignore-rule
# checks behave consistently from local shells and CI working directories.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Allow only example environment templates to be tracked; real environment files
# may contain local configuration or secrets and are checked separately below.
ALLOWED_ENV_FILES = {
    ".env.example",
    ".env.production.example",
}
# Treat common local database and private-key file types as runtime-only artifacts
# that should never be committed to the repository.
FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
}
# Scan tracked text files for a small set of high-confidence credential formats;
# these expressions are deliberately narrow to reduce false-positive failures.
SECRET_PATTERNS = (
    re.compile("-" * 5 + r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY" + "-" * 5),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
)


# Run Git commands from the repository root and convert command failures into
# readable regression-test assertions.
def git_output(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.strip() or "Git command failed.")
    return completed.stdout


# Use `git ls-files` so safety checks inspect only content currently tracked by Git,
# not unrelated local files that happen to exist in the working directory.
def tracked_files() -> list[Path]:
    return [
        PROJECT_ROOT / item
        for item in git_output("ls-files").splitlines()
        if item.strip()
    ]


def test_no_private_runtime_files_are_tracked() -> None:
    # Collect every tracked private/runtime path before failing so one test run
    # reports the complete set of repository hygiene problems.
    violations: list[str] = []
    for path in tracked_files():
        # Normalise paths to repository-relative POSIX form for stable comparisons
        # across Windows, macOS and Linux CI environments.
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        name = path.name
        if name.startswith(".env") and name not in ALLOWED_ENV_FILES:
            violations.append(relative)
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            violations.append(relative)
        if relative.startswith(("data/local/", "data/private/")):
            violations.append(relative)
    if violations:
        raise AssertionError("Private runtime files are tracked: " + ", ".join(sorted(set(violations))))


def test_high_confidence_secret_scan() -> None:
    # Record filenames rather than secret values so failure output does not echo
    # potentially sensitive content into local or CI logs.
    findings: list[str] = []
    # Exclude this test itself because it intentionally contains example secret
    # patterns that would otherwise match its own scanner definitions.
    own_file = Path(__file__).resolve()
    for path in tracked_files():
        # Skip this scanner, non-files and very large tracked artifacts to keep the
        # repository guard fast and focused on likely text configuration/source files.
        if path.resolve() == own_file or not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        # Binary or non-UTF-8 files are ignored by this text-based secret scan.
        except UnicodeDecodeError:
            continue
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            findings.append(path.relative_to(PROJECT_ROOT).as_posix())
    if findings:
        raise AssertionError("Possible committed secrets found in: " + ", ".join(findings))


def test_gitignore_private_data_rules() -> None:
    # Probe representative private filenames to verify that `.gitignore` protects
    # environment files, local data, databases and deployment keys.
    for candidate in (
        ".env",
        ".env.production",
        "data/local/joey.db",
        "data/private/family.json",
        "temporary.sqlite3",
        "deployment.pem",
    ):
        # `--no-index` checks ignore rules even when the candidate file does not exist
        # in the working tree, making this a configuration test rather than a file test.
        completed = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", candidate],
            cwd=PROJECT_ROOT,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(f".gitignore does not protect: {candidate}")


# Confirm that sensitive/local paths are also excluded from Docker build context,
# preventing them from being copied into image layers accidentally.
def test_docker_context_exclusions() -> None:
    content = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    for required in ("data", "*.db", ".env", ".streamlit/secrets.toml"):
        if required not in content:
            raise AssertionError(f".dockerignore protection is missing: {required}")


def main() -> None:
# Run each repository-safety guard explicitly so standalone and CI output remains
# deterministic and easy to diagnose.
    tests = [
        ("no tracked private runtime files", test_no_private_runtime_files_are_tracked),
        ("high-confidence committed-secret scan", test_high_confidence_secret_scan),
        ("private-data gitignore rules", test_gitignore_private_data_rules),
        ("Docker build-context exclusions", test_docker_context_exclusions),
    ]
    passed = 0
    # Any failed guard stops the module with a non-zero exit status that the wider
    # CI suite can detect.
    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")
    print("\nREPOSITORY SAFETY TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


# Run the repository-safety regression guards only when executed directly.
if __name__ == "__main__":
    main()
