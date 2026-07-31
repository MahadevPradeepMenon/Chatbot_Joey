from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from app.extractor import extract_structured_record
from app.schemas import (
    AnxietyLevel,
    ConfidenceLevel,
    MoodZone,
    StructuredJoeyRecord,
)


MAX_FOLLOW_UP_QUESTIONS = 4

SKIP_ANSWERS = {
    "skip",
    "unknown",
    "i don't know",
    "i do not know",
    "don't know",
    "do not know",
    "not sure",
    "unsure",
    "no idea",
    "prefer not to say",
}


class ConversationStatus(str, Enum):
    """State of one Joey data-input conversation."""

    collecting_information = "collecting_information"
    ready_for_review = "ready_for_review"
    confirmed = "confirmed"
    rejected = "rejected"


@dataclass(frozen=True)
class ConversationTurn:
    """One parent answer linked to Joey's follow-up question."""

    question: str
    answer: str
    field_name: str


@dataclass
class JoeyConversationSession:
    """
    Hold one multi-turn Joey draft.

    The same StructuredJoeyRecord is updated after every answer.
    Nothing is automatically saved by this class.
    """

    original_note: str
    current_record: StructuredJoeyRecord
    status: ConversationStatus = (
        ConversationStatus.collecting_information
    )
    pending_field: str | None = None
    follow_up_question: str | None = None
    history: list[ConversationTurn] = field(default_factory=list)
    completed_fields: set[str] = field(default_factory=set)
    skipped_fields: set[str] = field(default_factory=set)

    @classmethod
    def start(cls, note: str) -> "JoeyConversationSession":
        """Create a new conversation from the first parent note."""

        clean_note = " ".join(note.split()).strip()

        if not clean_note:
            raise ValueError("The parent/carer note cannot be empty.")

        # Positional construction avoids a false-positive Pylance
        # warning about generated dataclass keyword parameters.
        session = cls(
            clean_note,
            extract_structured_record(clean_note),
        )
        session._select_next_question()
        return session

    def submit_answer(self, answer: str) -> StructuredJoeyRecord:
        """Merge one parent answer into the current draft."""

        if self.status != ConversationStatus.collecting_information:
            raise RuntimeError(
                "This conversation is no longer collecting information."
            )

        if not self.pending_field or not self.follow_up_question:
            raise RuntimeError("There is no active follow-up question.")

        clean_answer = " ".join(answer.split()).strip()

        if not clean_answer:
            raise ValueError("The follow-up answer cannot be empty.")

        field_name = self.pending_field
        question = self.follow_up_question

        self.history.append(
            ConversationTurn(
                question=question,
                answer=clean_answer,
                field_name=field_name,
            )
        )

        if clean_answer.lower() in SKIP_ANSWERS:
            self.skipped_fields.add(field_name)
        else:
            self._merge_answer(
                field_name=field_name,
                answer=clean_answer,
            )
            self.completed_fields.add(field_name)

        self.pending_field = None
        self.follow_up_question = None
        self._select_next_question()

        return self.current_record

    def confirm(self) -> None:
        """Mark the reviewed draft as parent-confirmed."""

        if self.status != ConversationStatus.ready_for_review:
            raise RuntimeError(
                "The draft must be ready for review before confirmation."
            )

        self.status = ConversationStatus.confirmed

    def reject(self) -> None:
        """Reject the draft without saving it."""

        if self.status == ConversationStatus.confirmed:
            raise RuntimeError(
                "A confirmed conversation cannot be rejected."
            )

        self.status = ConversationStatus.rejected

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation of the session."""

        record_data = self.current_record.model_dump(mode="json")

        return {
            "original_note": self.original_note,
            "status": self.status.value,
            "pending_field": self.pending_field,
            "follow_up_question": self.follow_up_question,
            "history": [asdict(turn) for turn in self.history],
            "completed_fields": sorted(self.completed_fields),
            "skipped_fields": sorted(self.skipped_fields),
            "structured_record": record_data,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "JoeyConversationSession":
        """Restore one validated conversation draft from stored JSON."""

        original_note = " ".join(
            str(
                data.get(
                    "original_note",
                    "",
                )
            ).split()
        ).strip()

        if not original_note:
            raise ValueError(
                "Stored conversation draft has no original note."
            )

        record_data = data.get(
            "structured_record"
        )

        if not isinstance(
            record_data,
            Mapping,
        ):
            raise ValueError(
                "Stored conversation draft has no structured record."
            )

        current_record = (
            StructuredJoeyRecord.model_validate(
                dict(record_data)
            )
        )

        status_value = str(
            data.get(
                "status",
                ConversationStatus.collecting_information.value,
            )
        ).strip()

        try:
            status = ConversationStatus(
                status_value
            )
        except ValueError as error:
            raise ValueError(
                "Stored conversation draft has an unsupported status."
            ) from error

        history_items = data.get(
            "history",
            [],
        )
        history: list[ConversationTurn] = []

        if isinstance(
            history_items,
            list,
        ):
            for item in history_items:
                if not isinstance(
                    item,
                    Mapping,
                ):
                    continue

                question = " ".join(
                    str(
                        item.get(
                            "question",
                            "",
                        )
                    ).split()
                ).strip()
                answer = " ".join(
                    str(
                        item.get(
                            "answer",
                            "",
                        )
                    ).split()
                ).strip()
                field_name = " ".join(
                    str(
                        item.get(
                            "field_name",
                            "",
                        )
                    ).split()
                ).strip()

                if (
                    question
                    and answer
                    and field_name
                ):
                    history.append(
                        ConversationTurn(
                            question=question,
                            answer=answer,
                            field_name=field_name,
                        )
                    )

        completed_values = data.get(
            "completed_fields",
            [],
        )
        skipped_values = data.get(
            "skipped_fields",
            [],
        )

        completed_fields = {
            str(value).strip()
            for value in completed_values
            if str(value).strip()
        } if isinstance(
            completed_values,
            (list, tuple, set),
        ) else set()

        skipped_fields = {
            str(value).strip()
            for value in skipped_values
            if str(value).strip()
        } if isinstance(
            skipped_values,
            (list, tuple, set),
        ) else set()

        pending_field_value = data.get(
            "pending_field"
        )
        follow_up_value = data.get(
            "follow_up_question"
        )

        pending_field = (
            str(pending_field_value).strip()
            if pending_field_value
            else None
        )
        follow_up_question = (
            str(follow_up_value).strip()
            if follow_up_value
            else None
        )

        return cls(
            original_note,
            current_record,
            status=status,
            pending_field=pending_field,
            follow_up_question=follow_up_question,
            history=history,
            completed_fields=completed_fields,
            skipped_fields=skipped_fields,
        )

    def _select_next_question(self) -> None:
        """Choose one useful unanswered question."""

        if len(self.history) >= MAX_FOLLOW_UP_QUESTIONS:
            self._mark_ready_for_review()
            return

        candidates = self._question_candidates()

        for field_name, question in candidates:
            if field_name in self.completed_fields:
                continue

            if field_name in self.skipped_fields:
                continue

            self.pending_field = field_name
            self.follow_up_question = question
            self.status = ConversationStatus.collecting_information
            self._update_record_follow_up(question)
            return

        self._mark_ready_for_review()

    def _question_candidates(self) -> list[tuple[str, str]]:
        """Build follow-up questions in safety-first priority order."""

        record = self.current_record
        candidates: list[tuple[str, str]] = []

        if "safety_concern" in record.risk_flags:
            candidates.append(
                (
                    "safety_status",
                    "Is the child safe now, and did they sustain any injury?",
                )
            )

        existing_field = infer_follow_up_field(
            record.follow_up_question
        )

        if (
            existing_field
            and record.follow_up_question
            and existing_field != "safety_status"
            and existing_follow_up_is_relevant(
                record=record,
                question=record.follow_up_question,
            )
        ):
            candidates.append(
                (
                    existing_field,
                    record.follow_up_question,
                )
            )

        if (
            record.anxiety_level == AnxietyLevel.unknown
            or not anxiety_was_explicitly_reported(
                self.original_note
            )
        ):
            candidates.append(
                (
                    "anxiety_level",
                    (
                        "How anxious did the child appear: "
                        "Minimal, Moderate, High, or Severe?"
                    ),
                )
            )

        if record.mood_zone == MoodZone.unknown:
            candidates.append(
                (
                    "mood",
                    (
                        "Which mood zone best fits the moment: "
                        "Red, Orange, Green, Blue, or Mixed?"
                    ),
                )
            )

        if not record.environment:
            candidates.append(
                (
                    "environment",
                    "Where did this happen?",
                )
            )

        if not record.possible_triggers:
            candidates.append(
                (
                    "possible_triggers",
                    (
                        "What happened just before the change "
                        "in behaviour or mood?"
                    ),
                )
            )

        return remove_duplicate_candidates(candidates)

    def _merge_answer(
        self,
        field_name: str,
        answer: str,
    ) -> None:
        """Apply a field-specific answer to the existing draft."""

        record = self.current_record
        updates: dict[str, Any] = {}

        if field_name == "anxiety_level":
            updates["anxiety_level"] = parse_anxiety_level(answer)

        elif field_name == "mood":
            zone, labels = parse_mood(answer)
            updates["mood_zone"] = zone
            updates["mood_labels"] = merge_unique(
                record.mood_labels,
                labels,
            )

        elif field_name == "environment":
            updates["environment"] = parse_environment(answer)

        elif field_name == "possible_triggers":
            extracted = extract_structured_record(answer)

            # Preserve both Joey's extracted trigger labels and
            # the parent's explicit follow-up answer.
            triggers = merge_unique(
                extracted.possible_triggers,
                [answer],
            )

            updates["possible_triggers"] = merge_unique(
                record.possible_triggers,
                triggers,
            )

        elif field_name == "safety_status":
            updates.update(parse_safety_answer(record, answer))

        elif field_name == "medication_context":
            updates.update(parse_medication_answer(record, answer))

        else:
            raise ValueError(
                f"Unsupported follow-up field: {field_name}"
            )

        updates["missing_information"] = remove_resolved_missing_items(
            current_items=record.missing_information,
            field_name=field_name,
        )

        updated_record = copy_record(record, updates)
        updated_record = refresh_confidence(updated_record)
        self.current_record = updated_record

    def _update_record_follow_up(
        self,
        question: str | None,
    ) -> None:
        self.current_record = copy_record(
            self.current_record,
            {"follow_up_question": question},
        )

    def _mark_ready_for_review(self) -> None:
        self.pending_field = None
        self.follow_up_question = None
        self.status = ConversationStatus.ready_for_review
        self._update_record_follow_up(None)


def infer_follow_up_field(
    question: str | None,
) -> str | None:
    """Infer which structured field an existing extractor question targets."""

    if not question:
        return None

    text = question.lower()

    if "safe now" in text or "sustain any injury" in text:
        return "safety_status"

    if "medication" in text or "healthcare professional" in text:
        return "medication_context"

    if "where did this happen" in text:
        return "environment"

    trigger_phrases = (
        "what happened just before",
        "what may have happened just before",
        "fabric",
        "label",
        "tightness",
        "temperature",
        "lights too bright",
        "flickering",
        "sound too loud",
        "unexpected",
        "difficult to escape",
        "smell the main difficulty",
        "other sensory triggers",
        "number of people",
        "the noise",
        "the space",
        "sign of pain",
        "illness",
        "tiredness",
        "sensory sensitivity",
        "part of using the toilet",
    )

    if any(phrase in text for phrase in trigger_phrases):
        return "possible_triggers"

    return None



def existing_follow_up_is_relevant(
    record: StructuredJoeyRecord,
    question: str,
) -> bool:
    """Ignore an extractor question that does not fit the record.

    The current baseline extractor can assign the toilet follow-up when
    no toileting language was present. This guard prevents that unrelated
    question from taking over the conversation.
    """

    text = question.lower()

    if "part of using the toilet" in text:
        return (
            record.activity == "toileting routine"
            or "Toilet Training" in record.strategy_categories
        )

    return True


def anxiety_was_explicitly_reported(note: str) -> bool:
    """Return True when the note directly describes anxiety level."""

    text = note.lower()
    indicators = (
        "anxious",
        "anxiety",
        "worried",
        "nervous",
        "fear",
        "scared",
        "panic",
        "panicked",
        "terrified",
        "calm",
        "not anxious",
    )

    return any(indicator in text for indicator in indicators)

def remove_duplicate_candidates(
    candidates: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Keep the first question for each field."""

    unique: list[tuple[str, str]] = []
    seen: set[str] = set()

    for field_name, question in candidates:
        if field_name in seen:
            continue

        seen.add(field_name)
        unique.append((field_name, question))

    return unique


def merge_unique(
    current_values: list[str],
    new_values: list[str],
) -> list[str]:
    """Merge text values case-insensitively without duplicates."""

    result = list(current_values)
    seen = {value.casefold() for value in current_values}

    for value in new_values:
        clean_value = " ".join(str(value).split()).strip()

        if not clean_value:
            continue

        key = clean_value.casefold()

        if key not in seen:
            result.append(clean_value)
            seen.add(key)

    return result


def parse_anxiety_level(answer: str) -> AnxietyLevel:
    """Interpret a parent answer as one AnxietyLevel enum."""

    text = answer.lower()

    if any(
        phrase in text
        for phrase in (
            "severe",
            "extreme",
            "panic",
            "panicked",
            "terrified",
        )
    ):
        return AnxietyLevel.severe

    if any(
        phrase in text
        for phrase in (
            "high",
            "very anxious",
            "very worried",
            "strong",
        )
    ):
        return AnxietyLevel.high

    if any(
        phrase in text
        for phrase in (
            "moderate",
            "medium",
            "somewhat",
            "some anxiety",
            "worried",
            "anxious",
        )
    ):
        return AnxietyLevel.moderate

    if any(
        phrase in text
        for phrase in (
            "minimal",
            "mild",
            "slight",
            "little",
            "calm",
            "not anxious",
            "none",
        )
    ):
        return AnxietyLevel.minimal

    raise ValueError(
        "Please answer with Minimal, Moderate, High, or Severe."
    )


MOOD_LABEL_TO_ZONE: dict[str, MoodZone] = {
    "angry": MoodZone.red,
    "scared": MoodZone.red,
    "enraged": MoodZone.red,
    "screaming": MoodZone.red,
    "freeze": MoodZone.red,
    "frozen": MoodZone.red,
    "meltdown": MoodZone.red,
    "shutdown": MoodZone.red,
    "worried": MoodZone.orange,
    "restless": MoodZone.orange,
    "annoyed": MoodZone.orange,
    "anxious": MoodZone.orange,
    "frustrated": MoodZone.orange,
    "confident": MoodZone.green,
    "happy": MoodZone.green,
    "calm": MoodZone.green,
    "balanced": MoodZone.green,
    "miserable": MoodZone.blue,
    "bored": MoodZone.blue,
    "upset": MoodZone.blue,
    "tired": MoodZone.blue,
    "drained": MoodZone.blue,
}


def parse_mood(answer: str) -> tuple[MoodZone, list[str]]:
    """Interpret a mood-zone answer and any emotion labels."""

    text = answer.lower()
    explicit_zones: list[MoodZone] = []

    for zone in (
        MoodZone.red,
        MoodZone.orange,
        MoodZone.green,
        MoodZone.blue,
        MoodZone.mixed,
    ):
        if zone.value.lower() in text:
            explicit_zones.append(zone)

    labels: list[str] = []
    inferred_zones: list[MoodZone] = []

    for label, zone in MOOD_LABEL_TO_ZONE.items():
        if label in text:
            labels.append(label.capitalize())
            inferred_zones.append(zone)

    all_zones = explicit_zones + inferred_zones
    distinct_zones = list(dict.fromkeys(all_zones))

    if MoodZone.mixed in distinct_zones or len(distinct_zones) > 1:
        return MoodZone.mixed, labels

    if len(distinct_zones) == 1:
        return distinct_zones[0], labels

    raise ValueError(
        "Please answer with Red, Orange, Green, Blue, Mixed, "
        "or a recognised mood such as anxious, calm, angry, or tired."
    )


def parse_environment(answer: str) -> str:
    """Normalise common Hey Joey environment descriptions."""

    text = answer.lower()

    environment_map = (
        (("school", "classroom", "teacher"), "school"),
        (("home", "bedroom", "bathroom", "kitchen"), "home"),
        (("bus", "car", "train", "transport"), "community/transport"),
        (("shop", "supermarket", "shopping"), "community/shop"),
        (("street", "park", "outside", "playground"), "community/outdoors"),
    )

    for keywords, normalised in environment_map:
        if any(keyword in text for keyword in keywords):
            return normalised

    return answer


def parse_safety_answer(
    record: StructuredJoeyRecord,
    answer: str,
) -> dict[str, Any]:
    """Record the parent's immediate-safety clarification."""

    text = answer.lower()
    flags = list(record.risk_flags)

    child_safe = any(
        phrase in text
        for phrase in (
            "safe now",
            "is safe",
            "they are safe",
            "he is safe",
            "she is safe",
        )
    )
    unsafe = any(
        phrase in text
        for phrase in (
            "not safe",
            "still unsafe",
            "immediate danger",
            "in danger",
        )
    )
    no_injury = any(
        phrase in text
        for phrase in (
            "no injury",
            "not injured",
            "wasn't injured",
            "was not injured",
            "no injuries",
        )
    )
    injury = any(
        phrase in text
        for phrase in (
            "was injured",
            "is injured",
            "an injury",
            "bleeding",
            "hurt their head",
            "hurt his head",
            "hurt her head",
        )
    ) and not no_injury

    if child_safe:
        flags = merge_unique(flags, ["parent_reported_safe_now"])

    if no_injury:
        flags = merge_unique(flags, ["parent_reported_no_injury"])

    if unsafe:
        flags = merge_unique(flags, ["immediate_danger_reported"])

    if injury:
        flags = merge_unique(flags, ["injury_reported"])

    return {"risk_flags": flags}


def parse_medication_answer(
    record: StructuredJoeyRecord,
    answer: str,
) -> dict[str, Any]:
    """Record whether medication was logged or raised as a concern."""

    text = answer.lower()
    flags = list(record.risk_flags)

    if any(
        phrase in text
        for phrase in (
            "just logging",
            "logging only",
            "recording only",
            "no concern",
        )
    ):
        flags = merge_unique(flags, ["medication_logging_only"])
    else:
        flags = merge_unique(
            flags,
            ["medication_concern_for_professional"],
        )

    return {"risk_flags": flags}


def remove_resolved_missing_items(
    current_items: list[str],
    field_name: str,
) -> list[str]:
    """Remove missing-information descriptions resolved by an answer."""

    keyword_map = {
        "environment": ("environment", "where"),
        "possible_triggers": (
            "trigger",
            "reason",
            "discomfort",
            "what happened",
        ),
        "safety_status": (
            "immediate danger",
            "injury",
        ),
        "medication_context": (
            "medication concerns",
            "healthcare professional",
        ),
    }

    keywords = keyword_map.get(field_name, ())

    return [
        item
        for item in current_items
        if not any(
            keyword in item.lower()
            for keyword in keywords
        )
    ]


def refresh_confidence(
    record: StructuredJoeyRecord,
) -> StructuredJoeyRecord:
    """Raise confidence when the main fields are now populated."""

    populated_core_fields = sum(
        (
            record.anxiety_level != AnxietyLevel.unknown,
            record.mood_zone != MoodZone.unknown,
            bool(record.environment),
            bool(record.possible_triggers),
        )
    )

    confidence = (
        ConfidenceLevel.high
        if populated_core_fields >= 3
        else ConfidenceLevel.medium
    )

    return copy_record(record, {"confidence": confidence})


def copy_record(
    record: StructuredJoeyRecord,
    updates: dict[str, Any],
) -> StructuredJoeyRecord:
    """Support both Pydantic v2 and v1 copy methods."""

    if hasattr(record, "model_copy"):
        return record.model_copy(update=updates)

    return record.copy(update=updates)