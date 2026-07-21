import json
from datetime import datetime
from pathlib import Path

from app.extractor import extract_structured_record
from app.response_builder import build_parent_response
from app.schemas import StructuredJoeyRecord
from rag.joey_strategy_service import (
    JoeyStrategyEvidence,
    JoeyStrategyService,
    preview_text,
)
from safety.safety_guard import should_limit_strategy_suggestions


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_OUTPUT_DIR = PROJECT_ROOT / "data" / "local"
CONFIRMED_RECORDS_FILE = (
    LOCAL_OUTPUT_DIR / "confirmed_joey_records.jsonl"
)


def print_list(items: list[str]) -> None:
    """Print a list neatly."""

    if not items:
        print("- None detected")
        return

    for item in items:
        print(f"- {item}")


def display_record(
    record: StructuredJoeyRecord,
) -> None:
    """Display Joey's structured output in a parent-friendly way."""

    print("\n" + "=" * 60)
    print("JOEY STRUCTURED RECORD")
    print("=" * 60)

    print(f"\nSummary:\n{record.summary}")

    print("\nCore fields:")
    print(f"- Entry type: {record.entry_type}")
    print(f"- Time of day: {record.time_of_day}")
    print(f"- Anxiety level: {record.anxiety_level.value}")
    print(f"- Mood zone: {record.mood_zone.value}")
    print(f"- Confidence: {record.confidence.value}")

    print("\nMood labels:")
    print_list(record.mood_labels)

    print("\nBehaviours:")
    print_list(record.behaviours)

    print("\nActivity:")
    print(f"- {record.activity or 'Not detected'}")

    print("\nEnvironment:")
    print(f"- {record.environment or 'Not detected'}")

    print("\nPossible triggers:")
    print_list(record.possible_triggers)

    print("\nQuick Track suggestions:")
    print_list(record.quick_track_suggestions)

    print("\nStrategy categories:")
    print_list(record.strategy_categories)

    print("\nRisk flags:")
    print_list(record.risk_flags)

    print("\nMissing information:")
    print_list(record.missing_information)

    print("\nJoey follow-up question:")
    print(
        record.follow_up_question
        or "Would you like to add more detail?"
    )

    print("\nParent/carer confirmation required:")
    print(record.requires_parent_confirmation)


def display_semantic_strategies(
    strategies: list[JoeyStrategyEvidence],
) -> None:
    """Display source-backed semantic retrieval evidence."""

    print("\n" + "=" * 60)
    print("RETRIEVED STRATEGY EVIDENCE")
    print("=" * 60)

    if not strategies:
        print("\nNo strategy evidence was retrieved.")
        return

    for strategy in strategies:
        if strategy.strategy_code and strategy.strategy_title:
            title = (
                f"{strategy.strategy_code}: "
                f"{strategy.strategy_title}"
            )
        else:
            title = (
                strategy.strategy_title
                or "Relevant support strategy"
            )

        print("\n" + "-" * 60)
        print(
            f"Rank {strategy.rank} "
            f"| Similarity: {strategy.score:.4f}"
        )
        print(f"Strategy: {title}")
        print(f"Collection: {strategy.collection_title}")
        print(f"Source: {strategy.source_file}")

        if strategy.theme:
            print(f"Theme: {strategy.theme}")

        print(
            f"Passage: "
            f"{preview_text(strategy.passage)}"
        )


def save_confirmed_record(
    original_note: str,
    record: StructuredJoeyRecord,
) -> None:
    """Save a parent-confirmed record locally as JSONL."""

    LOCAL_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved_item = {
        "saved_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "original_note": original_note,
        "structured_record": record.model_dump(
            mode="json"
        ),
    }

    with CONFIRMED_RECORDS_FILE.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                saved_item,
                ensure_ascii=False,
            )
            + "\n"
        )


def process_note(
    note: str,
    strategy_service: JoeyStrategyService,
) -> tuple[
    StructuredJoeyRecord,
    list[JoeyStrategyEvidence],
]:
    """
    Run the complete Joey workflow for one parent observation.

    The workflow performs extraction, safety checking, semantic
    retrieval and parent-response generation without saving.
    """

    record = extract_structured_record(note)
    display_record(record)

    retrieved_strategies: list[
        JoeyStrategyEvidence
    ] = []

    if should_limit_strategy_suggestions(record):
        print("\n" + "=" * 60)
        print("STRATEGY RETRIEVAL")
        print("=" * 60)
        print(
            "\nStrategy retrieval was limited because "
            "the record may involve a safety concern."
        )

    else:
        try:
            retrieved_strategies = (
                strategy_service.retrieve_for_record(
                    record,
                    original_note=note,
                    top_k=3,
                )
            )

            display_semantic_strategies(
                retrieved_strategies
            )

        except Exception as error:
            print("\n" + "=" * 60)
            print("STRATEGY RETRIEVAL")
            print("=" * 60)

            print(
                "\nJoey could not retrieve strategy evidence "
                f"for this note: {error}"
            )

            print(
                "The structured record can still be reviewed "
                "and saved."
            )

    parent_response = build_parent_response(
        original_note=note,
        record=record,
        retrieved_strategies=retrieved_strategies,
    )

    print("\n" + parent_response)

    return record, retrieved_strategies


def run_joey_cli() -> None:
    """Run Joey's local command-line interface."""

    print("\nWelcome to Joey CLI")
    print(
        "Type a parent/carer observation and Joey "
        "will structure it."
    )
    print("Type 'exit' to stop.\n")

    print("Loading Joey's local strategy system...")

    try:
        strategy_service = JoeyStrategyService()
    except Exception as error:
        print(
            "\nJoey could not load the local semantic index."
        )
        print(f"Reason: {error}")
        print(
            "\nRun this command before starting Joey:"
        )
        print(
            "python -m rag.build_embedding_index"
        )
        return

    print("Joey's local strategy system is ready.\n")

    while True:
        note = input(
            "Parent/carer note: "
        ).strip()

        if note.lower() in {
            "exit",
            "quit",
            "q",
        }:
            print("\nExiting Joey CLI.")
            break

        if not note:
            print(
                "Please enter a note, or type "
                "'exit' to stop."
            )
            continue

        record, _ = process_note(
            note,
            strategy_service,
        )

        print("\n" + "-" * 60)
        print("Confirmation")
        print("-" * 60)
        print("Joey has not saved anything yet.")
        print("Choose:")
        print("1 = save this structured record")
        print("2 = do not save")
        print(
            "3 = rewrite the note and run Joey again"
        )

        choice = input(
            "Your choice: "
        ).strip()

        if choice == "1":
            save_confirmed_record(
                note,
                record,
            )

            print(
                "\nSaved locally to: "
                f"{CONFIRMED_RECORDS_FILE}"
            )

        elif choice == "2":
            print("\nRecord was not saved.")

        elif choice == "3":
            revised_note = input(
                "\nRewrite the note: "
            ).strip()

            if revised_note:
                revised_record, _ = process_note(
                    revised_note,
                    strategy_service,
                )

                confirm_revised = input(
                    "\nSave revised record? yes/no: "
                ).strip().lower()

                if confirm_revised in {
                    "yes",
                    "y",
                }:
                    save_confirmed_record(
                        revised_note,
                        revised_record,
                    )

                    print(
                        "\nSaved locally to: "
                        f"{CONFIRMED_RECORDS_FILE}"
                    )
                else:
                    print(
                        "\nRevised record was not saved."
                    )
            else:
                print(
                    "\nNo revised note entered. "
                    "Nothing was saved."
                )

        else:
            print(
                "\nInvalid choice. Nothing was saved."
            )


if __name__ == "__main__":
    run_joey_cli()