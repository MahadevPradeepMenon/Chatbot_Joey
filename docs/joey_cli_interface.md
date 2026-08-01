# Joey CLI Interface

## Status

This document describes the **legacy command-line development interface** implemented in `app/joey_cli.py`.

The current `v0.1.0` application interface is Streamlit communicating with the FastAPI backend over HTTP. The main application stores confirmed records, conversations, strategy searches and feedback in SQLite.

The CLI remains in the repository as an earlier development artefact and a simple way to exercise the deterministic extraction workflow without running the web services.

---

## Legacy CLI Purpose

The CLI accepts a parent or carer observation and produces a structured Joey record.

It demonstrates the original project goal of transforming free-text notes into structured Hey Joey-style data.

---

## Legacy CLI Workflow

1. The parent or carer enters a free-text observation.
2. Joey applies the rule-based extractor.
3. Joey displays the structured record.
4. Joey asks a follow-up question.
5. Joey requires confirmation before saving.
6. The confirmed record is saved locally by the CLI.

---

## Legacy CLI Persistence

The CLI stores confirmed records in:

`data/local/confirmed_joey_records.jsonl`

This private runtime path is excluded from version control.

This JSONL file belongs only to the legacy CLI. It is not the persistence mechanism used by the current Streamlit and FastAPI application, which uses SQLite.

---

## Example Input

`He was anxious before school, refused breakfast, and had a meltdown when I asked him to put his jumper on.`

## Expected Legacy Output

The CLI should identify relevant structured information such as:

- anxiety;
- meltdown;
- school transition;
- food or appetite concerns;
- clothing or tactile discomfort;
- a follow-up question about missing context.

---

## Limitations

- The CLI is a terminal development interface, not the current user interface.
- Extraction remains deterministic and rule-based.
- Detailed field-by-field editing is limited.
- The CLI predates the current hybrid BM25 and semantic strategy-retrieval workflow.
- The CLI does not use the current FastAPI service boundary or SQLite persistence layer.
- It should be used only with synthetic or explicitly authorised data.

For the maintained system architecture, see `docs/architecture.md`.
