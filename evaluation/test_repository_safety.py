"""Repository guard against committed secrets and private runtime data."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ENV_FILES = {
    ".env.example",
    ".env.production.example",
}
FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
}
SECRET_PATTERNS = (
    re.compile("-" * 5 + r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY" + "-" * 5),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
)


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


def tracked_files() -> list[Path]:
    return [
        PROJECT_ROOT / item
        for item in git_output("ls-files").splitlines()
        if item.strip()
    ]


def test_no_private_runtime_files_are_tracked() -> None:
    violations: list[str] = []
    for path in tracked_files():
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
    findings: list[str] = []
    own_file = Path(__file__).resolve()
    for path in tracked_files():
        if path.resolve() == own_file or not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            findings.append(path.relative_to(PROJECT_ROOT).as_posix())
    if findings:
        raise AssertionError("Possible committed secrets found in: " + ", ".join(findings))


def test_gitignore_private_data_rules() -> None:
    for candidate in (
        ".env",
        ".env.production",
        "data/local/joey.db",
        "data/private/family.json",
        "temporary.sqlite3",
        "deployment.pem",
    ):
        completed = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", candidate],
            cwd=PROJECT_ROOT,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(f".gitignore does not protect: {candidate}")


def test_docker_context_exclusions() -> None:
    content = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    for required in ("data", "*.db", ".env", ".streamlit/secrets.toml"):
        if required not in content:
            raise AssertionError(f".dockerignore protection is missing: {required}")


def main() -> None:
    tests = [
        ("no tracked private runtime files", test_no_private_runtime_files_are_tracked),
        ("high-confidence committed-secret scan", test_high_confidence_secret_scan),
        ("private-data gitignore rules", test_gitignore_private_data_rules),
        ("Docker build-context exclusions", test_docker_context_exclusions),
    ]
    passed = 0
    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")
    print("\nREPOSITORY SAFETY TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


if __name__ == "__main__":
    main()
