from enum import Enum
from typing import Any, Mapping, Sequence

from app.schemas import StructuredJoeyRecord
from rag.joey_strategy_service import JoeyStrategyEvidence
from safety.safety_guard import (
    build_safety_notice,
    should_limit_strategy_suggestions,
)


def format_items(items: list[str]) -> str:
    """Format list items for parent-facing text."""

    if not items:
        return "None detected"

    return ", ".join(items)


def display_value(value: Any) -> str:
    """Convert enum and ordinary values into readable text."""

    if isinstance(value, Enum):
        return str(value.value)

    if value is None:
        return "Not identified"

    return str(value)


def get_strategy_value(
    strategy: JoeyStrategyEvidence | Mapping[str, Any],
    field_name: str,
    default: Any = None,
) -> Any:
    """
    Read a value from either semantic evidence or a legacy dictionary.
    """

    if isinstance(strategy, Mapping):
        return strategy.get(field_name, default)

    return getattr(strategy, field_name, default)


def shorten_passage(
    text: str,
    maximum_characters: int = 450,
) -> str:
    """Create a concise parent-facing passage preview."""

    clean_text = " ".join(text.split()).strip()

    if len(clean_text) <= maximum_characters:
        return clean_text

    shortened = clean_text[:maximum_characters].rsplit(
        " ",
        maxsplit=1,
    )[0]

    return f"{shortened}..."


def build_strategy_title(
    strategy: JoeyStrategyEvidence | Mapping[str, Any],
) -> str:
    """Build a readable title for semantic or legacy results."""

    strategy_code = get_strategy_value(
        strategy,
        "strategy_code",
    )

    strategy_title = get_strategy_value(
        strategy,
        "strategy_title",
    )

    # Compatibility with the original rule-based retriever.
    legacy_title = get_strategy_value(
        strategy,
        "title",
    )

    if strategy_code and strategy_title:
        return f"{strategy_code}: {strategy_title}"

    if strategy_title:
        return str(strategy_title)

    if legacy_title:
        return str(legacy_title)

    return "Relevant support strategy"


def build_parent_response(
    original_note: str,
    record: StructuredJoeyRecord,
    retrieved_strategies: Sequence[
        JoeyStrategyEvidence | Mapping[str, Any]
    ],
) -> str:
    """
    Build a parent/carer-facing Joey response.

    Joey explains the structured information it detected, presents
    source-backed strategy evidence where appropriate and asks the
    parent or carer to confirm the record before saving.

    The function does not diagnose, prescribe or save automatically.
    """

    lines: list[str] = []

    lines.append("JOEY RESPONSE")
    lines.append("=" * 60)

    safety_notice = build_safety_notice(record)

    if safety_notice:
        lines.append("")
        lines.append(safety_notice)

    lines.append("")
    lines.append("Here is what Joey noticed from your note:")

    lines.append(
        f"- Summary: {record.summary}"
    )

    lines.append(
        f"- Mood zone: "
        f"{display_value(record.mood_zone)}"
    )

    lines.append(
        f"- Anxiety level: "
        f"{display_value(record.anxiety_level)}"
    )

    lines.append(
        f"- Possible triggers: "
        f"{format_items(record.possible_triggers)}"
    )

    lines.append(
        f"- Behaviours/signals: "
        f"{format_items(record.behaviours + record.mood_labels)}"
    )

    lines.append("")
    lines.append("Suggested Quick Track fields:")

    if record.quick_track_suggestions:
        for item in record.quick_track_suggestions:
            lines.append(f"- {item}")
    else:
        lines.append("- None detected")

    lines.append("")
    lines.append("Follow-up question:")

    lines.append(
        record.follow_up_question
        or "Would you like to add more detail?"
    )

    if should_limit_strategy_suggestions(record):
        lines.append("")
        lines.append(
            "Because this note may involve a safety concern, "
            "Joey is not treating it as an ordinary strategy request."
        )

        lines.append(
            "Please follow the safety guidance above and seek "
            "appropriate urgent or professional support where needed."
        )

    else:
        lines.append("")
        lines.append(
            "Relevant source-backed support strategies:"
        )

        if retrieved_strategies:
            for strategy in retrieved_strategies[:3]:
                strategy_title = build_strategy_title(
                    strategy
                )

                collection_title = get_strategy_value(
                    strategy,
                    "collection_title",
                )

                source_file = get_strategy_value(
                    strategy,
                    "source_file",
                )

                passage = (
                    get_strategy_value(
                        strategy,
                        "passage",
                    )
                    or get_strategy_value(
                        strategy,
                        "text",
                    )
                    or get_strategy_value(
                        strategy,
                        "safe_suggestion",
                    )
                    or ""
                )

                lines.append("")
                lines.append(f"- {strategy_title}")

                if collection_title:
                    lines.append(
                        f"  Collection: {collection_title}"
                    )

                if passage:
                    lines.append(
                        "  Relevant guidance: "
                        f"{shorten_passage(str(passage))}"
                    )

                if source_file:
                    lines.append(
                        f"  Source: {source_file}"
                    )

            lines.append("")
            lines.append(
                "These passages were retrieved because they appear "
                "relevant to the information in the note. They are "
                "support options rather than instructions or medical advice."
            )

        else:
            lines.append(
                "- No sufficiently relevant strategy evidence "
                "was retrieved."
            )

    lines.append("")
    lines.append("Before saving:")

    lines.append(
        "Please review this structured record. You can save it, "
        "ignore it or rewrite the note."
    )

    lines.append("")
    lines.append(
        "Joey is a support tool. It does not diagnose, replace "
        "professional advice or make final decisions."
    )

    return "\n".join(lines)