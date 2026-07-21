from email.mime import text
import re

from app.schemas import (
    AnxietyLevel,
    ConfidenceLevel,
    MoodZone,
    StructuredJoeyRecord,
)


def contains_any(text: str, keywords: list[str]) -> bool:
    """Return True if any keyword or phrase appears in the text."""
    return any(keyword in text for keyword in keywords)

def contains_self_injury_pattern(text: str) -> bool:
    """Detect common descriptions of self-injurious behaviour."""

    patterns = [
        r"\bhead[\s-]*bang(?:ing|ed|s)?\b",
        (
            r"\b(?:hit|hits|hitting|bang|bangs|banged|banging|"
            r"strike|strikes|struck|striking)\b"
            r".{0,30}"
            r"\b(?:their|his|her|own)\s+head\b"
        ),
        (
            r"\b(?:hurt|hurting|injure|injured|injuring)\s+"
            r"(?:themself|themselves|himself|herself)\b"
        ),
        r"\bself[\s-]?(?:injury|injurious|harm)\b",
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def contains_injury_concern(text: str) -> bool:
    """Detect language suggesting that an injury may have occurred."""

    patterns = [
        r"\b(?:may|might|could)\s+be\s+injured\b",
        r"\b(?:is|was|seems|appears)\s+injured\b",
        r"\bsustained an injury\b",
        r"\b(?:bleeding|unconscious|passed out)\b",
        r"\b(?:cannot|can't)\s+wake\b",
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def add_unique(items: list[str], value: str) -> None:
    """Add a value to a list only if it is not already present."""
    if value not in items:
        items.append(value)


def add_many(items: list[str], values: list[str]) -> None:
    """Add multiple unique values to a list."""
    for value in values:
        add_unique(items, value)


def upgrade_mood_zone(current: MoodZone, candidate: MoodZone) -> MoodZone:
    """
    Upgrade mood zone only when the new zone is more urgent.

    Priority:
    Unknown < Green < Blue < Orange < Red
    """

    priority = {
        MoodZone.unknown: 0,
        MoodZone.green: 1,
        MoodZone.blue: 2,
        MoodZone.orange: 3,
        MoodZone.red: 4,
    }

    if priority[candidate] > priority[current]:
        return candidate

    return current


def upgrade_anxiety_level(
    current: AnxietyLevel,
    candidate: AnxietyLevel,
) -> AnxietyLevel:
    """
    Upgrade anxiety level only when the new level is more serious.
    """

    priority = {
        AnxietyLevel.unknown: 0,
        AnxietyLevel.minimal: 1,
        AnxietyLevel.moderate: 2,
        AnxietyLevel.high: 3,
        AnxietyLevel.severe: 4,
    }

    if priority[candidate] > priority[current]:
        return candidate

    return current


def extract_structured_record(note: str) -> StructuredJoeyRecord:
    """
    Rule-based prototype extractor for Joey.

    This takes a parent/carer free-text note and converts it into a
    structured Hey Joey-style record.

    This is still not the final AI system.
    It is an improved baseline extractor after dataset review.
    """

    text = note.lower()

    self_injury_detected = (
    contains_self_injury_pattern(text)
    or contains_any(
        text,
        [
            "hurt himself",
            "hurt herself",
            "hurt themselves",
        ],
    )
)

    injury_concern_detected = contains_injury_concern(
    text
)

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

    if contains_any(text, ["home", "bedroom", "bathroom", "kitchen", "living room"]):
        environment = "home"
    elif contains_any(text, ["school", "classroom", "teacher"]):
        environment = "school"
    elif contains_any(text, ["shop", "supermarket"]):
        environment = "community/shop"
    elif contains_any(text, ["bus", "car", "outside"]):
        environment = "community/transport"

    # -------------------------
    # Anxiety and panic detection
    # -------------------------

    if contains_any(
        text,
        ["anxious", "worried", "nervous", "fear", "scared", "impatient"],
    ):
        add_unique(mood_labels, "Anxious")
        add_unique(quick_track_suggestions, "Anxiety")
        add_unique(strategy_categories, "Behavioural Challenges & Emotional Regulation")

        anxiety_level = upgrade_anxiety_level(
            anxiety_level,
            AnxietyLevel.moderate,
        )
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

    if contains_any(text, ["panic", "panicked", "terrified"]):
        add_unique(mood_labels, "Panic")
        add_unique(quick_track_suggestions, "Anxiety")
        add_unique(strategy_categories, "Behavioural Challenges & Emotional Regulation")

        anxiety_level = upgrade_anxiety_level(
            anxiety_level,
            AnxietyLevel.severe,
        )
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.red)

    # -------------------------
    # Meltdown / shutdown detection
    # -------------------------

    if contains_any(text, ["meltdown", "screaming", "screamed", "enraged"]):
        add_unique(mood_labels, "Meltdown")
        add_unique(behaviours, "meltdown")
        add_unique(quick_track_suggestions, "Meltdown/Shutdown")
        add_unique(strategy_categories, "Behavioural Challenges & Emotional Regulation")

        anxiety_level = upgrade_anxiety_level(
            anxiety_level,
            AnxietyLevel.high,
        )
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.red)

    if contains_any(
        text,
        ["shutdown", "froze", "freeze", "wouldn't speak", "stopped responding"],
    ):
        add_unique(mood_labels, "Shutdown")
        add_unique(behaviours, "shutdown")
        add_unique(quick_track_suggestions, "Meltdown/Shutdown")
        add_unique(strategy_categories, "Crisis Management & Safety")

        anxiety_level = upgrade_anxiety_level(
            anxiety_level,
            AnxietyLevel.high,
        )
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.red)

    # -------------------------
    # General emotional state detection
    # -------------------------

    if contains_any(text, ["angry", "rage", "distress", "distressed"]):
        add_unique(mood_labels, "Distressed")
        add_unique(quick_track_suggestions, "Mood")
        add_unique(strategy_categories, "Behavioural Challenges & Emotional Regulation")

        anxiety_level = upgrade_anxiety_level(
            anxiety_level,
            AnxietyLevel.high,
        )
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

    if contains_any(text, ["frustrated", "irritable", "annoyed", "upset"]):
        add_unique(mood_labels, "Frustrated/Upset")
        add_unique(quick_track_suggestions, "Mood")
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

    if contains_any(text, ["happy", "calm", "confident", "balanced"]):
        add_unique(mood_labels, "Calm/Positive")

        if mood_zone == MoodZone.unknown:
            mood_zone = MoodZone.green
            anxiety_level = AnxietyLevel.minimal

    # -------------------------
    # Tiredness / sleep detection
    # -------------------------

    if contains_any(
        text,
        [
            "slept badly",
            "poor sleep",
            "woke up",
            "night waking",
            "bedtime",
            "tired",
            "drained",
            "long day",
        ],
    ):
        add_unique(mood_labels, "Tired")
        add_unique(quick_track_suggestions, "Sleep Quality & Duration")
        add_unique(quick_track_suggestions, "Energy Level")
        add_unique(strategy_categories, "Sleep & Bedtime Routines")

        if mood_zone in [MoodZone.unknown, MoodZone.green]:
            mood_zone = MoodZone.blue

    # -------------------------
    # Behaviour detection
    # -------------------------

    if contains_any(text, ["refused", "refusing", "wouldn't", "would not"]):
        add_unique(behaviours, "refusal")
        add_unique(strategy_categories, "Behavioural Challenges & Emotional Regulation")

        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

    if contains_any(text, ["crying", "cried", "tearful"]):
        add_unique(behaviours, "crying")
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

    if contains_any(
    text,
    ["hit", "hitting", "kicked", "bit", "biting"],
):
        if self_injury_detected:
            add_unique(
            behaviours,
            "self-injurious behaviour",
        )
        else:
            add_unique(
            behaviours,
            "aggressive behaviour",
        )

            add_unique(
            strategy_categories,
            "Behavioural Challenges & Emotional Regulation",
        )

        mood_zone = upgrade_mood_zone(
        mood_zone,
        MoodZone.red,
    )

    if contains_any(text, ["hide", "hiding", "wanted to hide"]):
        add_unique(behaviours, "avoidance/hiding")
        add_unique(mood_labels, "Overwhelmed")
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

    # -------------------------
    # Safety detection
    # -------------------------

    if self_injury_detected or injury_concern_detected:
        add_unique(
        risk_flags,
        "safety_concern",
    )

        if self_injury_detected:
            add_unique(
            risk_flags,
            "self_injury_mentioned",
        )

            add_unique(
            behaviours,
            "self-injurious behaviour",
        )

        add_unique(
        quick_track_suggestions,
        "Meltdown/Shutdown",
    )

        add_unique(
        strategy_categories,
        "Crisis Management & Safety",
    )

        anxiety_level = upgrade_anxiety_level(
        anxiety_level,
        AnxietyLevel.severe,
    )

        mood_zone = upgrade_mood_zone(
        mood_zone,
        MoodZone.red,
    )

    confidence = ConfidenceLevel.high

    add_unique(
        missing_information,
        "whether there is immediate danger",
    )

    add_unique(
        missing_information,
        "whether injury occurred",
    )

    follow_up_question = (
        "Is the child safe now, and did they sustain any injury?"
    )
    # -------------------------
    # Food / appetite detection
    # -------------------------

    if contains_any(
        text,
        ["breakfast", "lunch", "dinner", "meal", "food", "eat", "eating", "appetite"],
    ):
        add_unique(quick_track_suggestions, "Appetite")
        add_unique(quick_track_suggestions, "Meal Entry")
        add_unique(strategy_categories, "Eating & Mealtime Challenges")

        if activity is None:
            activity = "mealtime"

    if contains_any(text, ["lunch was late", "breakfast was late", "dinner was late"]):
        add_unique(possible_triggers, "delayed meal or hunger")
        add_unique(strategy_categories, "Eating & Mealtime Challenges")

    if contains_any(text, ["gagged", "texture", "restricted diet", "picky", "refused food"]):
        add_unique(possible_triggers, "food texture or mealtime difficulty")
        add_unique(strategy_categories, "Eating & Mealtime Challenges")

    # -------------------------
    # School and routine detection
    # -------------------------

    if contains_any(text, ["school", "teacher", "classroom", "homework", "phonics"]):
        activity = "school-related routine"
        add_unique(possible_triggers, "school transition or school-related demand")
        add_unique(quick_track_suggestions, "School Attendance")
        add_unique(strategy_categories, "School Success & Academic Collaboration")

    if contains_any(
        text,
        ["school bus", "bus was late", "schedule change", "schedule was hard"],
    ):
        add_unique(possible_triggers, "unexpected schedule change")
        add_unique(strategy_categories, "Executive Function & Organisation")
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

    # -------------------------
    # Transition difficulty detection
    # -------------------------

    if contains_any(
        text,
        [
            "transition",
            "change",
            "without warning",
            "no warning",
            "visitor arrived",
            "stopping play",
            "stop play",
            "start the bedtime routine",
            "bedtime routine",
            "schedule change",
            "routine",
        ],
    ):
        add_unique(possible_triggers, "transition or unexpected change")
        add_unique(strategy_categories, "Executive Function & Organisation")
        add_unique(strategy_categories, "Behavioural Challenges & Emotional Regulation")
        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

        if activity is None and contains_any(text, ["visitor arrived", "visitor"]):
            activity = "unexpected visitor"
        elif activity is None and contains_any(text, ["stopping play", "stop play"]):
            activity = "transition away from play"
        elif activity is None and contains_any(text, ["bedtime"]):
            activity = "bedtime routine"

    # -------------------------
    # Sensory processing detection
    # -------------------------

    if contains_any(
        text,
        [
            "shirt tag",
            "tag",
            "jumper",
            "clothes",
            "clothing",
            "label",
            "seam",
            "fabric",
            "socks",
        ],
    ):
        add_unique(possible_triggers, "clothing or tactile discomfort")
        add_unique(strategy_categories, "Sensory Processing & Environmental Support")
        add_unique(quick_track_suggestions, "Physical Discomfort")
        add_unique(mood_labels, "Sensory discomfort")

        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

        add_unique(missing_information, "reason for clothing discomfort")

        if follow_up_question is None:
            follow_up_question = (
                "Was the clothing uncomfortable because of the fabric, label, tightness, temperature, or something else?"
            )

    if contains_any(text, ["lights", "light", "bright", "squinting"]):
        add_unique(possible_triggers, "visual sensitivity or bright lighting")
        add_unique(strategy_categories, "Sensory Processing & Environmental Support")
        add_unique(quick_track_suggestions, "Physical Discomfort")
        add_unique(mood_labels, "Sensory discomfort")

        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

        if follow_up_question is None:
            follow_up_question = "Were the lights too bright, flickering, or difficult in another way?"

    if contains_any(text, ["smell", "cooking", "overwhelming"]):
        add_unique(possible_triggers, "smell sensitivity or sensory overwhelm")
        add_unique(strategy_categories, "Sensory Processing & Environmental Support")
        add_unique(mood_labels, "Overwhelmed")

        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

        if follow_up_question is None:
            follow_up_question = "Was the smell the main difficulty, or were there other sensory triggers as well?"

    if contains_any(text, ["vacuum", "too loud", "loud", "noise", "noisy"]):
        add_unique(possible_triggers, "noise sensitivity")
        add_unique(strategy_categories, "Sensory Processing & Environmental Support")
        add_unique(quick_track_suggestions, "Physical Discomfort")
        add_unique(mood_labels, "Sensory discomfort")

        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

        if follow_up_question is None:
            follow_up_question = "Was the sound too loud, unexpected, or difficult to escape from?"

    if contains_any(text, ["too many people", "crowded", "busy shop", "shop made"]):
        add_unique(possible_triggers, "crowded or socially overwhelming environment")
        add_unique(strategy_categories, "Sensory Processing & Environmental Support")
        add_unique(strategy_categories, "Friendship & Social Skills")
        add_unique(mood_labels, "Overwhelmed")

        mood_zone = upgrade_mood_zone(mood_zone, MoodZone.orange)

        if follow_up_question is None:
            follow_up_question = "Was the difficulty mainly the number of people, the noise, the space, or something else?"

    # -------------------------
    # Physical discomfort detection
    # -------------------------

    if contains_any(text, ["cold", "unwell", "ill", "sick", "sensitive than usual", "more sensitive"]):
        add_unique(possible_triggers, "physical discomfort or illness")
        add_unique(quick_track_suggestions, "Physical Discomfort")
        add_unique(mood_labels, "Physically uncomfortable")

        if mood_zone == MoodZone.unknown:
            mood_zone = MoodZone.blue

        if follow_up_question is None:
            follow_up_question = "Was there any sign of pain, illness, tiredness, or sensory sensitivity?"

    # -------------------------
    # Toilet training detection
    # -------------------------

    if contains_any(
    text,
    [
        "toilet",
        "toileting",
        "potty",
        "use the loo",
        "using the loo",
        "wetting",
        "soiling",
        "toilet accident",
        "bathroom accident",
        "urinate",
        "bowel movement",
    ],
):
        if activity is None:
            activity = "toileting routine"

        add_unique(
        possible_triggers,
        "toilet use or toileting routine",
    )

        add_unique(
        quick_track_suggestions,
        "Toileting",
    )

        add_unique(
        strategy_categories,
        "Toilet Training",
    )

    if follow_up_question is None:
        follow_up_question = (
            "What part of using the toilet seemed most difficult: "
            "entering the bathroom, sitting, sensory discomfort, "
            "communication, or something else?"
        )

    # -------------------------
    # Hygiene detection
    # -------------------------

    if contains_any(
        text,
        ["toothbrush", "toothbrushing", "brush teeth", "hair brushing", "bath", "shower", "washing"],
    ):
        activity = "hygiene routine"
        add_unique(possible_triggers, "hygiene or self-care difficulty")
        add_unique(strategy_categories, "Personal Hygiene & Self-Care")

    # -------------------------
    # Medication mention detection
    # -------------------------

    if contains_any(
        text,
        ["medication", "medicine", "tablet", "dose", "dosage", "adderall", "ritalin"],
    ):
        add_unique(quick_track_suggestions, "Medication Mention")
        add_unique(risk_flags, "medication_mentioned")
        add_unique(
            missing_information,
            "medication concerns should be discussed with a healthcare professional",
        )

        if follow_up_question is None:
            follow_up_question = (
                "Was medication only being logged here, or is there a concern you want to discuss with a healthcare professional?"
            )

    # -------------------------
    # Default follow-up question
    # -------------------------

    if follow_up_question is None:
        if possible_triggers:
            follow_up_question = "Would you like to add any more detail about what happened just before this?"
        elif environment is None:
            add_unique(missing_information, "environment")
            follow_up_question = "Where did this happen?"
        else:
            add_unique(missing_information, "possible trigger")
            follow_up_question = "Do you know what may have happened just before this?"

    # -------------------------
    # Final fallback
    # -------------------------

    if anxiety_level == AnxietyLevel.unknown and mood_zone in [MoodZone.orange, MoodZone.red]:
        anxiety_level = AnxietyLevel.moderate
        
    summary = build_summary(
        time_of_day=time_of_day,
        behaviours=behaviours,
        mood_labels=mood_labels,
        possible_triggers=possible_triggers,
    )

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
        parts.append("mood/signals: " + ", ".join(mood_labels))

    if behaviours:
        parts.append("behaviours: " + ", ".join(behaviours))

    if possible_triggers:
        parts.append("possible triggers: " + ", ".join(possible_triggers))

    if not parts:
        return "Parent/carer observation recorded with limited structured detail."

    return "; ".join(parts) + "."


if __name__ == "__main__":
    test_note = (
        "He was anxious before school, refused breakfast, "
        "and had a meltdown when I asked him to put his jumper on."
    )

    result = extract_structured_record(test_note)
    print(result.model_dump())