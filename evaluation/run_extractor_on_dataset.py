import json
from pathlib import Path
from collections import Counter

import pandas as pd

from app.extractor import extract_structured_record


# Resolve dataset and output paths relative to the repository so the evaluation
# script can be run from different working directories.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "synthetic_journal_entries.csv"
OUTPUT_CSV = PROJECT_ROOT / "data" / "processed" / "joey_extracted_records.csv"
OUTPUT_XLSX = PROJECT_ROOT / "data" / "processed" / "joey_extracted_records.xlsx"
OUTPUT_JSONL = PROJECT_ROOT / "data" / "processed" / "joey_extracted_records.jsonl"


# Candidate names cover the common free-text column labels used by journal-style
# datasets while preserving the original column name when a match is found.
TEXT_COLUMN_CANDIDATES = [
    "notes",
    "note",
    "journal_note",
    "journal entry",
    "journal_entry",
    "description",
    "text",
]


def find_text_column(df: pd.DataFrame) -> str | None:
    """Find the most likely free-text note column."""
    # Build a case-insensitive lookup without changing the DataFrame column names.
    lowercase_columns = {col.lower().strip(): col for col in df.columns}

    for candidate in TEXT_COLUMN_CANDIDATES:
        if candidate in lowercase_columns:
            return lowercase_columns[candidate]

    return None


def build_note_from_row(row: pd.Series) -> str:
    """
    If there is no single notes column, combine useful fields into one note.
    This makes the script robust to different CSV structures.
    """
    # When no dedicated note column exists, combine only fields that describe the
    # observed situation and are useful to the deterministic extractor.
    useful_fields = [
        "activity",
        "anxiety",
        "behaviour",
        "behavior",
        "environment",
        "mood",
        "notes",
        "note",
        "trigger",
        "resolution",
    ]

    parts = []

    for field in useful_fields:
        for col in row.index:
            if col.lower().strip() == field:
                value = row[col]
                # Skip missing and empty cells so the synthetic note contains only
                # meaningful source values.
                if pd.notna(value) and str(value).strip():
                    parts.append(f"{col}: {value}")

    return ". ".join(parts)


def flatten_list(value: list[str]) -> str:
    """Convert list values into a readable string for CSV."""
    return " | ".join(value)


def main() -> None:
    # Fail early if the expected synthetic evaluation dataset is unavailable.
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {INPUT_FILE}. "
            "Make sure synthetic_journal_entries.csv is inside data/raw/."
        )

    # Load the complete synthetic dataset once; each row is processed independently.
    df = pd.read_csv(INPUT_FILE)

    print(f"Loaded dataset: {INPUT_FILE}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    # Prefer a single free-text field when present; otherwise rows are converted
    # into notes from selected structured columns.
    text_column = find_text_column(df)

    if text_column:
        print(f"Using text column: {text_column}")
    else:
        print("No single notes column found. Combining available fields into one note.")

    output_rows = []
    jsonl_rows = []

    # Run the same application extractor on every dataset row so evaluation uses
    # the production extraction path rather than separate test logic.
    for index, row in df.iterrows():
        if text_column:
            note = row[text_column]
            if pd.isna(note):
                note = ""
            note = str(note)
        else:
            note = build_note_from_row(row)

        # Convert the note into the current StructuredJoeyRecord produced by the
        # deterministic extractor.
        record = extract_structured_record(note)
        # Use JSON-compatible Pydantic output so enum values and nested fields can
        # be written consistently to CSV, Excel and JSONL artifacts.
        record_dict = record.model_dump(mode="json")

        # Flatten list-valued fields for tabular inspection while retaining the
        # row index and original input note for traceability.
        output_row = {
            "source_row": index,
            "input_note": note,
            "summary": record_dict["summary"],
            "anxiety_level": record_dict["anxiety_level"],
            "mood_zone": record_dict["mood_zone"],
            "mood_labels": flatten_list(record_dict["mood_labels"]),
            "behaviours": flatten_list(record_dict["behaviours"]),
            "activity": record_dict["activity"],
            "environment": record_dict["environment"],
            "possible_triggers": flatten_list(record_dict["possible_triggers"]),
            "quick_track_suggestions": flatten_list(record_dict["quick_track_suggestions"]),
            "strategy_categories": flatten_list(record_dict["strategy_categories"]),
            "risk_flags": flatten_list(record_dict["risk_flags"]),
            "missing_information": flatten_list(record_dict["missing_information"]),
            "follow_up_question": record_dict["follow_up_question"],
            "confidence": record_dict["confidence"],
            "requires_parent_confirmation": record_dict["requires_parent_confirmation"],
        }

        output_rows.append(output_row)

        # JSONL keeps the complete structured record nested under each original row
        # so machine-readable output does not lose list structure.
        jsonl_rows.append(
            {
                "source_row": index,
                "input_note": note,
                "structured_record": record_dict,
            }
        )

    # Create the processed-output directory before writing any evaluation artifacts.
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # Save the same extracted rows in CSV and Excel for convenient manual review.
    output_df = pd.DataFrame(output_rows)
    output_df.to_csv(OUTPUT_CSV, index=False)
    output_df.to_excel(OUTPUT_XLSX, index=False)

    # Write one complete evaluation record per JSONL line for reproducible parsing.
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for item in jsonl_rows:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print()
    print(f"Saved CSV output to: {OUTPUT_CSV}")
    print(f"Saved Excel output to: {OUTPUT_XLSX}")
    print(f"Saved JSONL output to: {OUTPUT_JSONL}")

    print()
    print("Extraction summary:")

    print("Anxiety levels:")
    print(output_df["anxiety_level"].value_counts(dropna=False))

    print()
    print("Mood zones:")
    print(output_df["mood_zone"].value_counts(dropna=False))

    print()
    print("Risk flags:")
    # Re-expand the flattened risk flag column to summarise how often each flag
    # was produced across the dataset.
    risk_counter = Counter()

    for flags in output_df["risk_flags"]:
        if isinstance(flags, str) and flags.strip():
            for flag in flags.split(" | "):
                risk_counter[flag] += 1

    if risk_counter:
        for flag, count in risk_counter.items():
            print(f"{flag}: {count}")
    else:
        print("No risk flags detected.")


# Run the dataset extraction evaluation only when this module is executed directly.
if __name__ == "__main__":
    main()
