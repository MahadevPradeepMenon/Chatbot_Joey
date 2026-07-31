"""Idempotently add Hey Joey private-data rules to .gitignore."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"
START_MARKER = "# BEGIN HEY JOEY PRIVATE RUNTIME DATA"
END_MARKER = "# END HEY JOEY PRIVATE RUNTIME DATA"
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

    existing = (
        GITIGNORE_PATH.read_text(encoding="utf-8")
        if GITIGNORE_PATH.exists()
        else ""
    )

    if START_MARKER in existing:
        print("Hey Joey repository-safety rules are already present.")
        return

    prefix = existing.rstrip()
    content = "\n".join(RULES)

    if prefix:
        updated = f"{prefix}\n\n{content}\n"
    else:
        updated = f"{content}\n"

    GITIGNORE_PATH.write_text(
        updated,
        encoding="utf-8",
        newline="\n",
    )
    print(f"Updated: {GITIGNORE_PATH}")


if __name__ == "__main__":
    main()
