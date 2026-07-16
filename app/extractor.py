from app.schemas import (
    AnxietyLevel,
    ConfidenceLevel,
    MoodZone,
    StructuredJoeyRecord,
)


def contains_any(text: str, keywords: list[str]) -> bool:
    """Return True if any keyword appears in the text."""
    return any(keyword in text for keyword in keywords)


def extract_structured_record(note: str) -> StructuredJoeyRecord:
    """
    Rule-based prototype extractor for Joey.

    This takes a parent/carer free-text note and converts it into a
    structured Hey Joey-style record.

    This is not the final AI system. It is a safe baseline extractor.
    """

    text = note.lower()

    mood_labels = []
    behaviours = []
    possible_triggers = []
    quick_track_suggestions = []
    strategy_categories = []
    risk_flags = []
    missing_information = []

    anxiety_level = AnxietyLevel.unknown
    mood_zone = MoodZone.unknown
    confidence = ConfidenceLevel.medium

    time_of_day = "Unknown"
    activity = None
    environment = None
    follow_up_question = None

    # -------------------------
    # Time of day detection
    # -------------------------
    if contains_any(text, ["morning", "before school", "breakfast"]):
        time_of_day = "morning"
    elif contains_any(text, ["afternoon", "after school"]):
        time_of_day = "afternoon"
    elif contains_any(text, ["evening", "dinner", "bedtime"]):
        time_of_day = "evening"
    elif contains_any(text, ["night", "middle of the night"]):
        time_of_day = "night"

    # -------------------------
    # Environment detection
    # -------------------------
    if contains_any(text, ["home", "bedroom", "bathroom", "kitchen"]):
        environment = "home"
    elif contains_any(text, ["school", "classroom", "teacher"]):
        environment = "school"
    elif contains_any(text, ["shop", "supermarket", "bus", "car", "outside"]):
        environment = "community/outside"

    # -------------------------
    # Anxiety detection
    # -------------------------
    if contains_any(text, ["anxious", "worried", "panic", "nervous", "fear", "scared"]):
        mood_labels.append("Anxious")
        quick_track_suggestions.append("Anxiety")
        strategy_categories.append("Behavioural Challenges & Emotional Regulation")

        if contains_any(text, ["panic", "severe", "terrified"]):
            anxiety_level = AnxietyLevel.severe
        else:
            anxiety_level = AnxietyLevel.moderate

    # -------------------------
    # Meltdown / shutdown detection
    # -------------------------
    if contains_any(text, ["meltdown", "screaming", "screamed", "enraged"]):
        mood_labels.append("Meltdown")
        behaviours.append("meltdown")
        quick_track_suggestions.append("Meltdown/Shutdown")
        strategy_categories.append("Behavioural Challenges & Emotional Regulation")
        mood_zone = MoodZone.red
        anxiety_level = AnxietyLevel.high

    if contains_any(text, ["shutdown", "froze", "freeze", "wouldn't speak", "stopped responding"]):
        mood_labels.append("Shutdown")
        behaviours.append("shutdown")
        quick_track_suggestions.append("Meltdown/Shutdown")
        strategy_categories.append("Crisis Management & Safety")
        mood_zone = MoodZone.red
        anxiety_level = AnxietyLevel.high

    # -------------------------
    # Mood zone detection
    # -------------------------
    if contains_any(text, ["angry", "rage", "screaming", "meltdown", "shutdown", "scared"]):
        mood_zone = MoodZone.red

    elif contains_any(text, ["worried", "restless", "annoyed", "frustrated", "anxious"]):
        mood_zone = MoodZone.orange

    elif contains_any(text, ["happy", "calm", "confident", "balanced"]):
        mood_zone = MoodZone.green

    elif contains_any(text, ["tired", "drained", "bored", "miserable", "upset"]):
        mood_zone = MoodZone.blue

    # -------------------------
    # Behaviour detection
    # -------------------------
    if contains_any(text, ["refused", "refusing", "wouldn't", "would not"]):
        behaviours.append("refusal")

    if contains_any(text, ["crying", "cried", "tearful"]):
        behaviours.append("crying")

    if contains_any(text, ["hit", "kicked", "bit", "biting"]):
        behaviours.append("aggressive behaviour")
        strategy_categories.append("Behavioural Challenges & Emotional Regulation")

    # -------------------------
    # Safety detection
    # -------------------------
    if contains_any(text, ["head banging", "banged his head", "banged her head", "hurt himself", "hurt herself", "self-injury", "self harm"]):
        risk_flags.append("safety_concern")
        risk_flags.append("self_injury_mentioned")
        behaviours.append("self-injurious behaviour")
        quick_track_suggestions.append("Meltdown/Shutdown")
        strategy_categories.append("Crisis Management & Safety")
        anxiety_level = AnxietyLevel.severe
        mood_zone = MoodZone.red
        confidence = ConfidenceLevel.high
        missing_information.append("whether there is immediate danger")
        missing_information.append("whether injury occurred")
        follow_up_question = "Is the child safe now, and did they sustain any injury?"

    # -------------------------
    # Food / appetite detection
    # -------------------------
    if contains_any(text, ["breakfast", "lunch", "dinner", "meal", "food", "eat", "eating", "appetite"]):
        quick_track_suggestions.append("Appetite")
        quick_track_suggestions.append("Meal Entry")
        strategy_categories.append("Eating & Mealtime Challenges")

    if contains_any(text, ["gagged", "texture", "restricted diet", "picky", "refused food"]):
        possible_triggers.append("food texture or mealtime difficulty")
        strategy_categories.append("Eating & Mealtime Challenges")

    # -------------------------
    # Sleep / tiredness detection
    # -------------------------
    if contains_any(text, ["slept badly", "poor sleep", "woke up", "night waking", "bedtime", "tired", "drained"]):
        quick_track_suggestions.append("Sleep Quality & Duration")
        quick_track_suggestions.append("Energy Level")
        strategy_categories.append("Sleep & Bedtime Routines")

        if mood_zone == MoodZone.unknown:
            mood_zone = MoodZone.blue

    # -------------------------
    # School detection
    # -------------------------
    if contains_any(text, ["school", "teacher", "classroom", "homework", "phonics"]):
        activity = "school-related routine"
        possible_triggers.append("school transition or school-related demand")
        quick_track_suggestions.append("School Attendance")
        strategy_categories.append("School Success & Academic Collaboration")

    # -------------------------
    # Clothing / sensory detection
    # -------------------------
    if contains_any(text, ["jumper", "clothes", "clothing", "label", "seam", "fabric", "socks"]):
        possible_triggers.append("clothing or tactile discomfort")
        strategy_categories.append("Sensory Processing & Environmental Support")

        if follow_up_question is None:
            missing_information.append("reason for clothing discomfort")
            follow_up_question = (
                "Was the clothing uncomfortable because of the fabric, label, tightness, temperature, or something else?"
            )

    # -------------------------
    # Hygiene detection
    # -------------------------
    if contains_any(text, ["toothbrush", "toothbrushing", "brush teeth", "hair brushing", "bath", "shower", "washing"]):
        activity = "hygiene routine"
        possible_triggers.append("hygiene or self-care difficulty")
        strategy_categories.append("Personal Hygiene & Self-Care")

    # -------------------------
    # Medication mention detection
    # -------------------------
    if contains_any(text, ["medication", "medicine", "tablet", "dose", "dosage", "adderall", "ritalin"]):
        quick_track_suggestions.append("Medication Mention")
        risk_flags.append("medication_mentioned")
        missing_information.append("medication concerns should be discussed with a healthcare professional")

        if follow_up_question is None:
            follow_up_question = (
                "Was medication only being logged here, or is there a concern you want to discuss with a healthcare professional?"
            )

    # -------------------------
    # Default follow-up question
    # -------------------------
    if follow_up_question is None:
        if not possible_triggers:
            missing_information.append("possible trigger")
            follow_up_question = "Do you know what may have happened just before this?"
        elif environment is None:
            missing_information.append("environment")
            follow_up_question = "Where did this happen?"
        else:
            follow_up_question = "Would you like to save this as a journal entry?"

    # -------------------------
    # If anxiety is unknown but distress is clear
    # -------------------------
    if anxiety_level == AnxietyLevel.unknown:
        if contains_any(text, ["meltdown", "panic", "scared", "worried", "anxious"]):
            anxiety_level = AnxietyLevel.high
        elif contains_any(text, ["upset", "frustrated", "crying"]):
            anxiety_level = AnxietyLevel.moderate

    # -------------------------
    # Create summary
    # -------------------------
    summary = build_summary(
        time_of_day=time_of_day,
        behaviours=behaviours,
        mood_labels=mood_labels,
        possible_triggers=possible_triggers,
    )

    # Remove duplicates while keeping order
    mood_labels = deduplicate(mood_labels)
    behaviours = deduplicate(behaviours)
    possible_triggers = deduplicate(possible_triggers)
    quick_track_suggestions = deduplicate(quick_track_suggestions)
    strategy_categories = deduplicate(strategy_categories)
    risk_flags = deduplicate(risk_flags)
    missing_information = deduplicate(missing_information)

    return StructuredJoeyRecord(
        entry_type="journal_entry",
        summary=summary,
        date=None,
        time_of_day=time_of_day,
        anxiety_level=anxiety_level,
        mood_zone=mood_zone,
        mood_labels=mood_labels,
        behaviours=behaviours,
        activity=activity,
        environment=environment,
        possible_triggers=possible_triggers,
        quick_track_suggestions=quick_track_suggestions,
        strategy_categories=strategy_categories,
        risk_flags=risk_flags,
        missing_information=missing_information,
        follow_up_question=follow_up_question,
        confidence=confidence,
        requires_parent_confirmation=True,
    )


def build_summary(
    time_of_day: str,
    behaviours: list[str],
    mood_labels: list[str],
    possible_triggers: list[str],
) -> str:
    """Build a short parent-friendly summary."""

    parts = []

    if time_of_day != "Unknown":
        parts.append(f"{time_of_day.capitalize()} entry")

    if mood_labels:
        parts.append("mood/signals: " + ", ".join(deduplicate(mood_labels)))

    if behaviours:
        parts.append("behaviours: " + ", ".join(deduplicate(behaviours)))

    if possible_triggers:
        parts.append("possible triggers: " + ", ".join(deduplicate(possible_triggers)))

    if not parts:
        return "Parent/carer observation recorded with limited structured detail."

    return "; ".join(parts) + "."


def deduplicate(items: list[str]) -> list[str]:
    """Remove duplicate items while preserving order."""
    seen = set()
    result = []

    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


if __name__ == "__main__":
    test_note = (
        "He was anxious before school, refused breakfast, "
        "and had a meltdown when I asked him to put his jumper on."
    )

    result = extract_structured_record(test_note)
    print(result.model_dump())