# Joey CLI Interface

## Purpose

The Joey CLI interface allows a user to enter a parent/carer observation and receive a structured Joey record.

This supports the project goal of transforming free-text notes into structured Hey Joey-style data.

---

## Workflow

1. Parent/carer enters a free-text observation.
2. Joey applies the rule-based extractor.
3. Joey displays the structured record.
4. Joey asks a follow-up question.
5. Joey requires confirmation before saving.
6. Confirmed records are saved locally only.

---

## Privacy Note

Confirmed records are saved to:

`data/local/confirmed_joey_records.jsonl`

This folder is ignored by Git using `.gitignore`.

This prevents manually entered notes from being accidentally pushed to GitHub.

---

## Example Input

`He was anxious before school, refused breakfast, and had a meltdown when I asked him to put his jumper on.`

## Expected Output

Joey should identify:

- anxiety
- meltdown
- school transition
- food/appetite issue
- clothing or tactile discomfort
- relevant Quick Track suggestions
- relevant strategy categories
- a follow-up question about clothing discomfort

---

## Current Limitations

- This is a terminal prototype, not the final app interface.
- The extraction is still rule-based.
- The user can confirm or rewrite the note, but detailed field-by-field editing is not yet implemented.
- The system does not yet retrieve Hey Joey strategy content using RAG.