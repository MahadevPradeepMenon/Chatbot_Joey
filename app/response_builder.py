from app.schemas import StructuredJoeyRecord
from safety.safety_guard import (
    build_safety_notice,
    should_limit_strategy_suggestions,
)


def format_items(items: list[str]) -> str:
    """Format list items for parent-facing text."""
    if not items:
        return "None detected"

    return ", ".join(items)


def build_parent_response(
    original_note: str,
    record: StructuredJoeyRecord,
    retrieved_strategies: list[dict],
) -> str:
    """
    Build a parent/carer-facing Joey response.

    This does not diagnose, prescribe, or save automatically.
    It explains what Joey noticed and asks for confirmation.
    """

    lines = []

    lines.append("JOEY RESPONSE")
    lines.append("=" * 60)

    safety_notice = build_safety_notice(record)

    if safety_notice:
        lines.append("")
        lines.append(safety_notice)

    lines.append("")
    lines.append("Here is what Joey noticed from your note:")
    lines.append(f"- Summary: {record.summary}")
    lines.append(f"- Mood zone: {record.mood_zone.value}")
    lines.append(f"- Anxiety level: {record.anxiety_level.value}")
    lines.append(f"- Possible triggers: {format_items(record.possible_triggers)}")
    lines.append(f"- Behaviours/signals: {format_items(record.behaviours + record.mood_labels)}")

    lines.append("")
    lines.append("Suggested Quick Track fields:")
    for item in record.quick_track_suggestions:
        lines.append(f"- {item}")

    if not record.quick_track_suggestions:
        lines.append("- None detected")

    lines.append("")
    lines.append("Follow-up question:")
    lines.append(record.follow_up_question or "Would you like to add more detail?")

    if should_limit_strategy_suggestions(record):
        lines.append("")
        lines.append(
            "Because this note may involve safety concerns, Joey is not treating this as an ordinary strategy recommendation."
        )
    else:
        lines.append("")
        lines.append("Relevant support areas:")
        if retrieved_strategies:
            for strategy in retrieved_strategies[:3]:
                lines.append(f"- {strategy['title']}: {strategy['safe_suggestion']}")
        else:
            lines.append("- No strategy support areas were retrieved.")

    lines.append("")
    lines.append("Before saving:")
    lines.append(
        "Please review this structured record. You can save it, ignore it, or rewrite the note."
    )

    lines.append("")
    lines.append(
        "Joey is a support tool. It does not diagnose, replace professional advice, or make final decisions."
    )

    return "\n".join(lines)