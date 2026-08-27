from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from rag.hybrid_retriever import (
    HybridSearchResult,
    HybridStrategyRetriever,
)


# Freeze the integration-facing evidence object so retrieved source metadata
# cannot be mutated after conversion from the hybrid retriever.
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

    # Pydantic/schema enums are converted to their stored string value before
    # being added to the retrieval query.
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

    # Accept common collection types and normalise each non-empty item separately.
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
    """Convert either a Pydantic record or dictionary."""

    # Support plain dictionaries first, then Pydantic v2 and v1 model APIs.
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

    # Query fields are added only when they contain meaningful text, avoiding
    # empty labels that could add noise to retrieval.
    values = normalise_list(value)

    if values:
        parts.append(f"{label}: {', '.join(values)}")


def build_retrieval_query(
    record: Any,
    original_note: str | None = None,
) -> str:
    """
    Convert Joey's structured record into a retrieval-focused query.

    Dates, confirmation fields and confidence values are intentionally
    excluded because they do not describe the child's support needs.
    """

    # Convert the incoming structured record into one mapping before selecting
    # only support-relevant fields for retrieval.
    data = record_to_dict(record)
    query_parts: list[str] = []

    # Preserve the parent's original wording when available because it may contain
    # useful detail not captured by deterministic structured fields.
    if original_note:
        clean_note = " ".join(
            original_note.split()
        ).strip()

        if clean_note:
            query_parts.append(
                f"Original parent note: {clean_note}"
            )

    # Build a labelled, human-readable retrieval query from behavioural,
    # contextual and support-category fields while excluding administrative data.
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

    # Refuse retrieval when neither the note nor structured record contains
    # enough descriptive information to form a query.
    if not query_parts:
        raise ValueError(
            "The structured record does not contain enough "
            "information for strategy retrieval."
        )

    # Keep each labelled field on its own line so the generated query remains
    # inspectable while still being plain text for hybrid retrieval.
    return "\n".join(query_parts)


class JoeyStrategyService:
    """
    Connect Joey's structured records to the local hybrid retriever.
    """

    def __init__(self) -> None:
        # Reuse the local semantic + BM25 hybrid retriever behind a smaller
        # application-facing service interface.
        self.retriever = HybridStrategyRetriever()

    def retrieve_for_text(
        self,
        text: str,
        top_k: int = 3,
    ) -> list[JoeyStrategyEvidence]:
        """Retrieve strategies directly from parent-written text."""

        # Direct-text retrieval is kept strategy-only so contextual corpus chunks
        # are not returned as user-facing strategy evidence.
        results = self.retriever.search(
            query=text,
            top_k=top_k,
            strategy_only=True,
        )

        return self._convert_results(results)

    def retrieve_for_record(
        self,
        record: Any,
        original_note: str | None = None,
        top_k: int = 3,
    ) -> list[JoeyStrategyEvidence]:
        """Retrieve strategies from a Joey structured record."""

        # Structured-record retrieval first converts selected fields into the same
        # plain-text query interface consumed by the hybrid retriever.
        retrieval_query = build_retrieval_query(
            record,
            original_note=original_note,
        )

        results = self.retriever.search(
            query=retrieval_query,
            top_k=top_k,
            strategy_only=True,
        )

        return self._convert_results(results)

    @staticmethod
    def _convert_results(
        results: list[HybridSearchResult],
    ) -> list[JoeyStrategyEvidence]:
        """Convert retriever results into integration-safe evidence."""

        # Expose only the evidence fields needed by downstream Joey services while
        # preserving source, chunk and passage provenance from retrieval.
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

    # Preview formatting affects terminal display only and does not alter the
    # passage stored in evidence objects.
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
    """Test structured-record hybrid retrieval."""

    # Fixed sensory-related record exercises the same structured-query path used
    # by the application without requiring interactive input.
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

    # Display the generated retrieval query before running the hybrid search so
    # the record-to-query transformation can be inspected manually.
    query = build_retrieval_query(sample_record)

    print("\nSTRUCTURED RETRIEVAL QUERY")
    print("=" * 70)
    print(query)

    service = JoeyStrategyService()

    evidence = service.retrieve_for_record(
        sample_record,
        top_k=3,
    )

    print("\nRETRIEVED HYBRID STRATEGY EVIDENCE")
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
            f"| Hybrid score: {result.score:.6f}"
        )
        print(f"Strategy: {title}")
        print(f"Collection: {result.collection_title}")
        print(f"Source: {result.source_file}")
        print(
            f"Passage: {preview_text(result.passage)}"
        )


# Run the service smoke test only when this module is executed directly.
if __name__ == "__main__":
    main()
