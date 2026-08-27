from app.schemas import StructuredJoeyRecord


def has_safety_concern(record: StructuredJoeyRecord) -> bool:
    """Return True if Joey detected a safety-related concern."""
    # Only the risk flags explicitly treated as safety concerns trigger the
    # stronger safety pathway; other flags can be handled separately.
    safety_flags = {
        "safety_concern",
        "self_injury_mentioned",
    }

    # Check the structured extractor output rather than re-parsing the original note.
    return any(flag in safety_flags for flag in record.risk_flags)


def has_medication_mention(record: StructuredJoeyRecord) -> bool:
    """Return True if medication was mentioned."""
    # Medication is tracked as a separate boundary because it requires cautious
    # signposting but does not automatically imply an immediate safety concern.
    return "medication_mentioned" in record.risk_flags


def build_safety_notice(record: StructuredJoeyRecord) -> str | None:
    """
    Build a safety notice if the record contains safety-sensitive content.
    """

    # Safety concerns take priority over medication-only notices.
    if has_safety_concern(record):
        return (
            "Safety note: This entry may involve risk of harm or injury. "
            "If there is immediate danger or the child may be unsafe, seek urgent help. "
            "Consider speaking with a healthcare professional or relevant support service."
        )

    # Medication mentions are acknowledged without giving dosage, causality or
    # treatment advice, keeping the response within Joey's support boundaries.
    if has_medication_mention(record):
        return (
            "Medication note: Medication was mentioned in this observation. "
            "Joey can log that medication was mentioned, but it cannot give medication advice, "
            "suggest dosage changes, or say medication caused the behaviour. "
            "If you are concerned about medication or side effects, speak with a healthcare professional."
        )

    # Ordinary records do not need an additional safety notice.
    return None


def should_limit_strategy_suggestions(record: StructuredJoeyRecord) -> bool:
    """
    Return True when ordinary strategy suggestions should be limited.

    Safety-sensitive entries should prioritise safety signposting over ordinary guidance.
    """
    # Strategy limiting is intentionally narrower than notice generation:
    # medication-only mentions still allow ordinary strategies, while safety
    # concerns suppress them in favour of safety signposting.
    return has_safety_concern(record)
