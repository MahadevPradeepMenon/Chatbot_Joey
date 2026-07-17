from app.schemas import StructuredJoeyRecord


def has_safety_concern(record: StructuredJoeyRecord) -> bool:
    """Return True if Joey detected a safety-related concern."""
    safety_flags = {
        "safety_concern",
        "self_injury_mentioned",
    }

    return any(flag in safety_flags for flag in record.risk_flags)


def has_medication_mention(record: StructuredJoeyRecord) -> bool:
    """Return True if medication was mentioned."""
    return "medication_mentioned" in record.risk_flags


def build_safety_notice(record: StructuredJoeyRecord) -> str | None:
    """
    Build a safety notice if the record contains safety-sensitive content.
    """

    if has_safety_concern(record):
        return (
            "Safety note: This entry may involve risk of harm or injury. "
            "If there is immediate danger or the child may be unsafe, seek urgent help. "
            "Consider speaking with a healthcare professional or relevant support service."
        )

    if has_medication_mention(record):
        return (
            "Medication note: Medication was mentioned in this observation. "
            "Joey can log that medication was mentioned, but it cannot give medication advice, "
            "suggest dosage changes, or say medication caused the behaviour. "
            "If you are concerned about medication or side effects, speak with a healthcare professional."
        )

    return None


def should_limit_strategy_suggestions(record: StructuredJoeyRecord) -> bool:
    """
    Return True when ordinary strategy suggestions should be limited.

    Safety-sensitive entries should prioritise safety signposting over ordinary guidance.
    """
    return has_safety_concern(record)