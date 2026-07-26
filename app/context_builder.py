from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_FILE = PROJECT_ROOT / "data" / "synthetic" / "synthetic_user_context.json"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")

SENSITIVE_KEYS = {
    "name", "child_name", "supported_person_name", "carer_name",
    "email", "date_of_birth", "dob", "phone", "address",
    "postcode", "medication_name", "dosage",
}

TOPIC_KEYWORDS = {
    "sensory": {"sensory", "noise", "noisy", "sound", "loud", "ears", "lights", "bright", "crowded", "overwhelmed", "overload"},
    "school": {"school", "classroom", "teacher", "lesson", "assembly", "homework", "transition"},
    "sleep": {"sleep", "slept", "bedtime", "night", "awake", "waking", "tired", "fatigue"},
    "social": {"friend", "friends", "social", "playground", "conversation", "group", "peer"},
    "communication": {"communication", "communicate", "speaking", "language", "instructions", "visual", "choice"},
    "behaviour": {"behaviour", "meltdown", "shutdown", "screaming", "hitting", "kicking", "biting", "throwing", "refused"},
    "eating": {"food", "eating", "meal", "mealtime", "appetite", "breakfast", "lunch", "dinner"},
    "toileting": {"toilet", "toileting", "bathroom", "bowel", "bladder"},
    "hygiene": {"hygiene", "washing", "shower", "bath", "teeth", "toothbrush", "dressing"},
    "safety": {"unsafe", "danger", "injury", "self-harm", "self harming", "hit head", "crisis"},
}

@dataclass(frozen=True)
class ContextSelection:
    question: str
    detected_topics: list[str]
    profile_items: list[str]
    journal_items: list[str]
    quick_track_items: list[str]
    active_strategy_items: list[str]
    omitted_sensitive_fields: list[str]
    context_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def tokenise(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.lower()))


def detect_topics(text: str) -> list[str]:
    query_tokens = tokenise(text)
    detected = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        keyword_tokens = set()
        for keyword in keywords:
            keyword_tokens.update(tokenise(keyword))
        if query_tokens.intersection(keyword_tokens):
            detected.append(topic)
    return detected


def load_synthetic_context(path: Path = DEFAULT_CONTEXT_FILE) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Synthetic context file not found: {path}")
    with path.open('r', encoding='utf-8') as file:
        return json.load(file)


class SyntheticContextBuilder:
    """Select minimal, relevant, confirmed and privacy-safe context."""

    def __init__(self, context_data: dict[str, Any] | None = None) -> None:
        self.context_data = context_data if context_data is not None else load_synthetic_context()

    def build(self, question: str) -> ContextSelection:
        clean_question = ' '.join(question.split()).strip()
        if not clean_question:
            raise ValueError('The strategy question cannot be empty.')

        topics = detect_topics(clean_question)
        question_tokens = tokenise(clean_question)
        omitted = self._find_sensitive_fields()

        profile = self._select_profile_items(topics, question_tokens)
        journals = self._select_records(self.context_data.get('journal_entries', []), topics, question_tokens, 3)
        quick_track = self._select_records(self.context_data.get('quick_track_entries', []), topics, question_tokens, 2)
        strategies = self._select_active_strategies(topics, question_tokens)
        context_text = self._format_context(profile, journals, quick_track, strategies)

        return ContextSelection(
            question=clean_question,
            detected_topics=topics,
            profile_items=profile,
            journal_items=journals,
            quick_track_items=quick_track,
            active_strategy_items=strategies,
            omitted_sensitive_fields=omitted,
            context_text=context_text,
        )

    def _find_sensitive_fields(self) -> list[str]:
        found = set()
        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key.lower() in SENSITIVE_KEYS:
                        found.add(key)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(self.context_data)
        return sorted(found)

    def _select_profile_items(self, topics: list[str], question_tokens: set[str]) -> list[str]:
        profile = self.context_data.get('profile', {})
        candidates = []
        for field_name, label in (
            ('strengths', 'Strength'),
            ('support_needs', 'Support need'),
            ('sensory_preferences', 'Sensory preference'),
            ('communication_preferences', 'Communication preference'),
        ):
            for item in profile.get(field_name, []):
                if isinstance(item, str):
                    candidates.append({'summary': f'{label}: {item}', 'topics': []})
                else:
                    candidates.append({'summary': f"{label}: {item.get('summary', '')}", 'topics': item.get('topics', [])})
        ranked = self._score_candidates(candidates, topics, question_tokens)
        return [item['summary'] for item in ranked[:4] if item['summary'].strip()]

    def _select_records(self, records: list[dict[str, Any]], topics: list[str], question_tokens: set[str], maximum_items: int) -> list[str]:
        confirmed = [record for record in records if record.get('confirmed') is True]
        ranked = self._score_candidates(confirmed, topics, question_tokens)
        return [str(record.get('summary', '')).strip() for record in ranked[:maximum_items] if str(record.get('summary', '')).strip()]

    def _select_active_strategies(self, topics: list[str], question_tokens: set[str]) -> list[str]:
        active = [item for item in self.context_data.get('active_strategies', []) if str(item.get('status', '')).lower() == 'active']
        ranked = self._score_candidates(active, topics, question_tokens)
        return [str(item.get('title', '')).strip() for item in ranked[:3] if str(item.get('title', '')).strip()]

    @staticmethod
    def _score_candidates(candidates: list[dict[str, Any]], topics: list[str], question_tokens: set[str]) -> list[dict[str, Any]]:
        ranked = []
        for position, candidate in enumerate(candidates):
            summary = str(candidate.get('summary', ''))
            candidate_topics = {str(topic).lower() for topic in candidate.get('topics', [])}
            topic_overlap = len(candidate_topics.intersection(topics))
            lexical_overlap = len(tokenise(summary).intersection(question_tokens))
            score = topic_overlap * 10 + lexical_overlap

            if not topics and lexical_overlap == 0:
                continue
            # When Joey has detected a clear topic, only include
            # records tagged with at least one matching topic.
            if topics and topic_overlap == 0:
                continue
            ranked.append((score, -position, candidate))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [candidate for _, _, candidate in ranked]

    @staticmethod
    def _format_context(profile: list[str], journals: list[str], quick_track: list[str], strategies: list[str]) -> str:
        sections = []
        if profile:
            sections.append('Relevant confirmed profile context:\n' + '\n'.join(f'- {item}' for item in profile))
        if journals:
            sections.append('Relevant confirmed recent observations:\n' + '\n'.join(f'- {item}' for item in journals))
        if quick_track:
            sections.append('Relevant confirmed tracked observations:\n' + '\n'.join(f'- {item}' for item in quick_track))
        if strategies:
            sections.append('Currently active relevant strategies:\n' + '\n'.join(f'- {item}' for item in strategies))
        return '\n\n'.join(sections) if sections else 'No relevant confirmed historical context was selected for this question.'
