import json
from datetime import datetime
from pathlib import Path

from app.extractor import extract_structured_record


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_OUTPUT_DIR = PROJECT_ROOT / "data" / "local"
CONFIRMED_RECORDS_FILE = LOCAL_OUTPUT_DIR / "confirmed_joey_records.jsonl"


def display_record(record) -> None:
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
    print(f"{record.follow_up_question}")

    print("\nParent/carer confirmation required:")
    print(f"{record.requires_parent_confirmation}")


def print_list(items: list[str]) -> None:
    """Print a list neatly."""
    if not items:
        print("- None detected")
        return

    for item in items:
        print(f"- {item}")


def save_confirmed_record(original_note: str, record) -> None:
    """Save confirmed record locally as JSONL."""

    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    saved_item = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "original_note": original_note,
        "structured_record": record.model_dump(mode="json"),
    }

    with open(CONFIRMED_RECORDS_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(saved_item, ensure_ascii=False) + "\n")


def run_joey_cli() -> None:
    """Run Joey's simple command-line interface."""

    print("\nWelcome to Joey CLI")
    print("Type a parent/carer observation and Joey will structure it.")
    print("Type 'exit' to stop.\n")

    while True:
        note = input("Parent/carer note: ").strip()

        if note.lower() in ["exit", "quit", "q"]:
            print("\nExiting Joey CLI.")
            break

        if not note:
            print("Please enter a note, or type 'exit' to stop.")
            continue

        record = extract_structured_record(note)
        display_record(record)

        print("\n" + "-" * 60)
        print("Confirmation")
        print("-" * 60)
        print("Joey has not saved anything yet.")
        print("Choose:")
        print("1 = save this structured record")
        print("2 = do not save")
        print("3 = rewrite the note and run Joey again")

        choice = input("Your choice: ").strip()

        if choice == "1":
            save_confirmed_record(note, record)
            print(f"\nSaved locally to: {CONFIRMED_RECORDS_FILE}")

        elif choice == "2":
            print("\nRecord was not saved.")

        elif choice == "3":
            revised_note = input("\nRewrite the note: ").strip()

            if revised_note:
                revised_record = extract_structured_record(revised_note)
                display_record(revised_record)

                confirm_revised = input("\nSave revised record? yes/no: ").strip().lower()

                if confirm_revised in ["yes", "y"]:
                    save_confirmed_record(revised_note, revised_record)
                    print(f"\nSaved locally to: {CONFIRMED_RECORDS_FILE}")
                else:
                    print("\nRevised record was not saved.")
            else:
                print("\nNo revised note entered. Nothing saved.")

        else:
            print("\nInvalid choice. Nothing was saved.")


if __name__ == "__main__":
    run_joey_cli()