# Dataset Extractor Review

## Purpose

This review checks how Joey's rule-based extractor performs on Dilyara's synthetic journal entries.

## What to Check

For each extracted record, review:

1. Is the summary accurate?
2. Is the anxiety level reasonable?
3. Is the mood zone reasonable?
4. Are behaviours correctly detected?
5. Are possible triggers useful?
6. Are Quick Track suggestions relevant?
7. Are strategy categories appropriate?
8. Is the follow-up question useful?
9. Are safety concerns flagged where needed?

## Initial Observations

To be completed after reviewing `data/processed/joey_extracted_records.csv`.

## Known Limitations

- The extractor is rule-based and keyword-dependent.
- It may miss patterns when parents use unexpected wording.
- It may over-detect some categories if keywords appear in unrelated contexts.
- It cannot understand nuance like a real LLM.
- This is a baseline before adding LLM/RAG support.