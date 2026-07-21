from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from rag.semantic_retriever import (
    SemanticSearchResult,
    SemanticStrategyRetriever,
)


@dataclass(frozen=True)
class JoeyStrategyEvidence:
    """Source-backed strategy evidence returned to Joey."""

    rank: int
    score: float
    strategy_code: str | None
    strategy_title: str | None
    collection_title: str
    source_file: str
    theme: str | None
    chunk_id: str
    passage: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise_value(value: Any) -> str:
    """Convert schema values and enums into readable text."""

    if value is None:
        return ""

    if isinstance(value, Enum):
        value = value.value

    return str(value).strip()


def normalise_list(value: Any) -> list[str]:
    """Convert a schema field into a clean list of strings."""

    if value is None:
        return []

    if isinstance(value, str):
        clean_value = value.strip()
        return [clean_value] if clean_value else []

    if isinstance(value, (list, tuple, set)):
        values: list[str] = []

        for item in value:
            clean_item = normalise_value(item)

            if clean_item:
                values.append(clean_item)

        return values

    clean_value = normalise_value(value)
    return [clean_value] if clean_value else []


def record_to_dict(record: Any) -> dict[str, Any]:
    """
    Convert either a Pydantic record or dictionary into a dictionary.
    """

    if isinstance(record, Mapping):
        return dict(record)

    if hasattr(record, "model_dump"):
        return dict(record.model_dump())

    if hasattr(record, "dict"):
        return dict(record.dict())

    raise TypeError(
        "The structured record must be a dictionary "
        "or a Pydantic model."
    )


def add_query_field(
    parts: list[str],
    label: str,
    value: Any,
) -> None:
    """Add a non-empty field to the retrieval query."""

    values = normalise_list(value)

    if values:
        parts.append(
            f"{label}: {', '.join(values)}"
        )


def build_retrieval_query(
    record: Any,
    original_note: str | None = None,
) -> str:
    """
    Convert Joey's structured record into a retrieval-focused query.

    Dates, confirmation fields and confidence values are intentionally
    excluded because they do not describe the child's support needs.
    """

    data = record_to_dict(record)

    query_parts: list[str] = []

    if original_note:
        clean_note = " ".join(
        original_note.split()
    ).strip()

    if clean_note:
        query_parts.append(
            f"Original parent note: {clean_note}"
        )

    add_query_field(
        query_parts,
        "Parent observation",
        data.get("summary"),
    )

    add_query_field(
        query_parts,
        "Behaviours",
        data.get("behaviours"),
    )

    add_query_field(
        query_parts,
        "Possible triggers",
        data.get("possible_triggers"),
    )

    add_query_field(
        query_parts,
        "Mood",
        data.get("mood_labels"),
    )

    add_query_field(
        query_parts,
        "Mood zone",
        data.get("mood_zone"),
    )

    add_query_field(
        query_parts,
        "Anxiety level",
        data.get("anxiety_level"),
    )

    add_query_field(
        query_parts,
        "Activity",
        data.get("activity"),
    )

    add_query_field(
        query_parts,
        "Environment",
        data.get("environment"),
    )

    add_query_field(
        query_parts,
        "Relevant support categories",
        data.get("strategy_categories"),
    )

    if not query_parts:
        raise ValueError(
            "The structured record does not contain enough "
            "information for strategy retrieval."
        )

    return "\n".join(query_parts)


class JoeyStrategyService:
    """
    Connect Joey's structured records to the local semantic retriever.
    """

    def __init__(self) -> None:
        self.retriever = SemanticStrategyRetriever()

    def retrieve_for_text(
        self,
        text: str,
        top_k: int = 3,
    ) -> list[JoeyStrategyEvidence]:
        """Retrieve strategies directly from parent-written text."""

        results = self.retriever.search(
            query=text,
            top_k=top_k,
            strategy_only=True,
            deduplicate_strategies=True,
        )

        return self._convert_results(results)

    def retrieve_for_record(
    self,
    record: Any,
    original_note: str | None = None,
    top_k: int = 3,
) -> list[JoeyStrategyEvidence]:
        """Retrieve strategies from a Joey structured record."""

        retrieval_query = build_retrieval_query(
            record,
            original_note=original_note,
)

        results = self.retriever.search(
            query=retrieval_query,
            top_k=top_k,
            strategy_only=True,
            deduplicate_strategies=True,
        )

        return self._convert_results(results)

    @staticmethod
    def _convert_results(
        results: list[SemanticSearchResult],
    ) -> list[JoeyStrategyEvidence]:
        """Convert retriever results into integration-safe evidence."""

        return [
            JoeyStrategyEvidence(
                rank=result.rank,
                score=result.score,
                strategy_code=result.strategy_code,
                strategy_title=result.strategy_title,
                collection_title=result.collection_title,
                source_file=result.source_file,
                theme=result.theme,
                chunk_id=result.chunk_id,
                passage=result.text,
            )
            for result in results
        ]


def preview_text(
    text: str,
    maximum_characters: int = 400,
) -> str:
    """Create a readable terminal preview."""

    clean_text = " ".join(text.split())

    if len(clean_text) <= maximum_characters:
        return clean_text

    shortened = clean_text[
        :maximum_characters
    ].rsplit(
        " ",
        maxsplit=1,
    )[0]

    return f"{shortened}..."


def main() -> None:
    """Test structured-record retrieval before CLI integration."""

    sample_record = {
        "summary": (
            "The child covered their ears and became "
            "overwhelmed when the classroom became noisy."
        ),
        "anxiety_level": "High",
        "mood_zone": "Red",
        "mood_labels": [
            "overwhelmed",
            "distressed",
        ],
        "behaviours": [
            "covered ears",
            "wanted to leave",
        ],
        "activity": "classroom activity",
        "environment": "school",
        "possible_triggers": [
            "loud classroom noise",
        ],
        "strategy_categories": [
            "sensory processing",
            "emotional regulation",
        ],
    }

    query = build_retrieval_query(
        sample_record
    )

    print("\nSTRUCTURED RETRIEVAL QUERY")
    print("=" * 70)
    print(query)

    service = JoeyStrategyService()

    evidence = service.retrieve_for_record(
        sample_record,
        top_k=3,
    )

    print("\nRETRIEVED STRATEGY EVIDENCE")
    print("=" * 70)

    for result in evidence:
        title = (
            f"{result.strategy_code}: "
            f"{result.strategy_title}"
            if result.strategy_code
            else result.strategy_title
        )

        print(
            f"\nRank {result.rank} "
            f"| Score: {result.score:.4f}"
        )
        print(f"Strategy: {title}")
        print(
            f"Collection: "
            f"{result.collection_title}"
        )
        print(f"Source: {result.source_file}")
        print(
            f"Passage: "
            f"{preview_text(result.passage)}"
        )


if __name__ == "__main__":
    main()