from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AnxietyLevel(str, Enum):
    """Project-defined anxiety categories used by the structured extractor."""

    minimal = "Minimal"
    moderate = "Moderate"
    high = "High"
    severe = "Severe"
    unknown = "Unknown"


class MoodZone(str, Enum):
    """Hey Joey mood-zone categories supported by the structured record."""

    red = "Red"
    orange = "Orange"
    green = "Green"
    blue = "Blue"
    mixed = "Mixed"
    unknown = "Unknown"


class ConfidenceLevel(str, Enum):
    """Confidence categories used for structured extraction."""

    low = "Low"
    medium = "Medium"
    high = "High"


class StructuredJoeyRecord(BaseModel):
    """Validated structure produced from a parent or carer free-text observation."""

    entry_type: str = Field(
        default="journal_entry",
        description="Suggested Hey Joey record type."
    )

    summary: str = Field(
        description="Short parent-friendly summary of the note."
    )

    date: Optional[str] = Field(
        default=None,
        description="Date of the event if known. ISO format preferred."
    )

    time_of_day: Optional[str] = Field(
        default="Unknown",
        description="Morning, afternoon, evening, night, or unknown."
    )

    anxiety_level: AnxietyLevel = Field(
        default=AnxietyLevel.unknown,
        description="Suggested anxiety level."
    )

    mood_zone: MoodZone = Field(
        default=MoodZone.unknown,
        description="Suggested mood zone."
    )

    mood_labels: List[str] = Field(
        default_factory=list,
        description="Specific emotional labels detected from the note."
    )

    behaviours: List[str] = Field(
        default_factory=list,
        description="Observable behaviours described in the note."
    )

    activity: Optional[str] = Field(
        default=None,
        description="Main activity or situation."
    )

    environment: Optional[str] = Field(
        default=None,
        description="Where the event happened."
    )

    possible_triggers: List[str] = Field(
        default_factory=list,
        description="Possible triggers, stated cautiously."
    )

    quick_track_suggestions: List[str] = Field(
        default_factory=list,
        description="Suggested Hey Joey Quick Track fields."
    )

    strategy_categories: List[str] = Field(
        default_factory=list,
        description="Relevant Hey Joey strategy categories."
    )

    risk_flags: List[str] = Field(
        default_factory=list,
        description="Safety or escalation concerns."
    )

    missing_information: List[str] = Field(
        default_factory=list,
        description="Important missing details."
    )

    follow_up_question: Optional[str] = Field(
        default=None,
        description="One useful follow-up question for the parent/carer."
    )

    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.medium,
        description="Confidence in the structured extraction."
    )

    requires_parent_confirmation: bool = Field(
        default=True,
        description="Joey must never save automatically."
    )
