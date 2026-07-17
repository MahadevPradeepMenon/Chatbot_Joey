import json
from pathlib import Path
from typing import Any

from app.extractor import extract_structured_record
from app.schemas import StructuredJoeyRecord


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_FILE = PROJECT_ROOT / "data" / "processed" / "strategy_knowledge_base.json"


def load_strategy_library() -> list[dict[str, Any]]:
    """Load the local strategy knowledge base."""

    if not STRATEGY_FILE.exists():
        raise FileNotFoundError(
            f"Strategy file not found: {STRATEGY_FILE}. "
            "Create data/processed/strategy_knowledge_base.json first."
        )

    with open(STRATEGY_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def build_retrieval_text(record: StructuredJoeyRecord, original_note: str = "") -> str:
    """Build searchable text from the structured record."""

    parts = [
        original_note,
        record.summary,
        record.anxiety_level.value,
        record.mood_zone.value,
        record.activity or "",
        record.environment or "",
        " ".join(record.mood_labels),
        " ".join(record.behaviours),
        " ".join(record.possible_triggers),
        " ".join(record.quick_track_suggestions),
        " ".join(record.strategy_categories),
        " ".join(record.risk_flags),
    ]

    return " ".join(parts).lower()


def score_strategy(
    strategy: dict[str, Any],
    record: StructuredJoeyRecord,
    retrieval_text: str,
) -> tuple[int, list[str]]:
    """Score a strategy against Joey's structured record."""

    score = 0
    evidence = []

    strategy_category = strategy.get("category", "").lower()
    strategy_keywords = strategy.get("keywords", [])

    # Strong score for exact category match.
    for category in record.strategy_categories:
        if category.lower() == strategy_category:
            score += 5
            evidence.append(f"matched strategy category: {category}")

    # Keyword matches from note and structured fields.
    for keyword in strategy_keywords:
        if keyword.lower() in retrieval_text:
            score += 2
            evidence.append(f"matched keyword: {keyword}")

    # Safety boost.
    if record.risk_flags and "crisis" in strategy_category:
        score += 10
        evidence.append("safety/risk flag present")

    # Mood-zone boost.
    if record.mood_zone.value == "Red" and "emotional" in strategy_category:
        score += 2
        evidence.append("red mood zone suggests emotional regulation support")

    return score, evidence


def retrieve_strategies(
    record: StructuredJoeyRecord,
    original_note: str = "",
    top_k: int = 4,
) -> list[dict[str, Any]]:
    """
    Retrieve relevant strategy entries for a structured Joey record.

    This is a local retrieval baseline.
    It can later be upgraded to embedding-based RAG.
    """

    strategies = load_strategy_library()
    retrieval_text = build_retrieval_text(record, original_note)

    scored_results = []

    for strategy in strategies:
        score, evidence = score_strategy(strategy, record, retrieval_text)

        if score > 0:
            scored_results.append(
                {
                    "score": score,
                    "id": strategy["id"],
                    "title": strategy["title"],
                    "category": strategy["category"],
                    "when_to_use": strategy["when_to_use"],
                    "safe_suggestion": strategy["safe_suggestion"],
                    "safety_note": strategy["safety_note"],
                    "evidence": evidence,
                }
            )

    scored_results.sort(key=lambda item: item["score"], reverse=True)

    return scored_results[:top_k]


def display_retrieved_strategies(strategies: list[dict[str, Any]]) -> None:
    """Display retrieved strategies in a readable format."""

    print("\n" + "=" * 60)
    print("RETRIEVED STRATEGY SUPPORT")
    print("=" * 60)

    if not strategies:
        print("\nNo relevant strategies were retrieved.")
        return

    for index, strategy in enumerate(strategies, start=1):
        print(f"\n{index}. {strategy['title']}")
        print(f"Category: {strategy['category']}")
        print(f"Score: {strategy['score']}")
        print(f"When to use: {strategy['when_to_use']}")
        print(f"Safe suggestion: {strategy['safe_suggestion']}")
        print(f"Safety note: {strategy['safety_note']}")

        print("Evidence:")
        for item in strategy["evidence"]:
            print(f"- {item}")


if __name__ == "__main__":
    test_note = (
        "He was anxious before school, refused breakfast, "
        "and had a meltdown when I asked him to put his jumper on."
    )

    record = extract_structured_record(test_note)
    retrieved = retrieve_strategies(record, original_note=test_note)

    print("Input note:")
    print(test_note)

    print("\nStructured record:")
    print(record.model_dump())

    display_retrieved_strategies(retrieved)