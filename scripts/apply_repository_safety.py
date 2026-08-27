"""Idempotently add Hey Joey private-data rules to .gitignore."""

from __future__ import annotations

from pathlib import Path


# Resolve repository-relative paths from this script so it can be run from any
# current working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"

# Marker lines make the generated block easy to detect and prevent duplicate
# entries when the script is run more than once.
START_MARKER = "# BEGIN HEY JOEY PRIVATE RUNTIME DATA"
END_MARKER = "# END HEY JOEY PRIVATE RUNTIME DATA"

# Keep local runtime data, database files and private key material out of Git
# while explicitly allowing the example environment files to remain tracked.
RULES = (
    START_MARKER,
    ".env",
    ".env.*",
    "!.env.example",
    "!.env.production.example",
    "data/local/",
    "data/private/",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.pem",
    "*.key",
    "stage7c_context.zip",
    END_MARKER,
)


def main() -> None:
    """Append the safety block once without replacing existing rules."""

    # Preserve any existing .gitignore content; an absent file is treated as empty.
    existing = (
        GITIGNORE_PATH.read_text(encoding="utf-8")
        if GITIGNORE_PATH.exists()
        else ""
    )

    # The start marker is the idempotency check: once present, no further write
    # is needed and existing repository rules remain untouched.
    if START_MARKER in existing:
        print("Hey Joey repository-safety rules are already present.")
        return

    # Remove only trailing whitespace before appending the generated block.
    prefix = existing.rstrip()
    content = "\n".join(RULES)

    # Add a separating blank line when the file already contains rules.
    if prefix:
        updated = f"{prefix}\n\n{content}\n"
    else:
        updated = f"{content}\n"

    # Write with a stable UTF-8/newline format for reproducible repository files.
    GITIGNORE_PATH.write_text(
        updated,
        encoding="utf-8",
        newline="\n",
    )
    print(f"Updated: {GITIGNORE_PATH}")


# Allow direct execution while keeping the module safe to import.
if __name__ == "__main__":
    main()

