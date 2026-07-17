# Dataset Extractor Review

## Purpose

This review checks how Joey's rule-based extractor performs on Dilyara's synthetic journal entries.

The aim is to evaluate whether Joey can convert parent/carer free-text observations into structured records containing mood zone, anxiety level, behaviours, possible triggers, Quick Track suggestions, strategy categories, and follow-up questions.

---

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

---

## Version 1 Results: Baseline Extractor

The first rule-based extractor successfully processed the synthetic journal dataset and generated structured Joey records.

The first run produced the following mood zone distribution:

- Unknown: 31 entries
- Blue: 9 entries
- Red: 8 entries
- Orange: 2 entries

No risk flags were detected in the first run.

### Version 1 Interpretation

The first version showed that the baseline pipeline worked, because it could process the dataset and produce structured outputs.

However, many entries were classified as `Unknown`. This showed that the initial keyword rules were too limited and missed common parent/carer wording.

Examples of missed patterns included:

- sensory discomfort, such as clothing tags, bright lights, smells, and loud sounds
- transition difficulties, such as stopping play, unexpected visitors, schedule changes, and bedtime routines
- physical discomfort, such as having a cold or being more sensitive than usual
- crowded or overwhelming environments
- panic or distress language that did not always use the exact word "anxious"

---

## Version 2 Results: Improved Extractor

After reviewing the first extraction output, the extractor rules were improved.

The updated extractor added rules for:

- sensory discomfort
- transition difficulty
- unexpected changes
- physical discomfort
- stronger panic detection
- crowded or socially overwhelming environments
- better follow-up questions

After improving the extractor rules, the mood zone distribution changed from:

- Unknown: 31
- Blue: 9
- Red: 8
- Orange: 2

to:

- Orange: 34
- Red: 16

The number of `Unknown` classifications was reduced to 0, showing that the revised rules improved coverage across the synthetic dataset.

The anxiety level distribution after improvement was:

- Moderate: 31
- High: 11
- Severe: 8

No risk flags were detected. This suggests that the dataset did not contain explicit self-injury or immediate safety-risk language.

### Version 2 Interpretation

The improved extractor performs better than the baseline because it recognises more parent/carer language patterns, including sensory discomfort, transition difficulty, unexpected changes, panic, bedtime issues, and environmental overwhelm.

However, the improved extractor may now be more assertive, as all records were classified as either `Orange` or `Red`. Further evaluation is needed to check whether some mild entries should remain `Blue`, `Green`, or `Unknown`.

---

## Known Limitations

- The extractor is rule-based and keyword-dependent.
- It may miss patterns when parents/carers use unexpected wording.
- It may over-detect some categories if keywords appear in unrelated contexts.
- It cannot understand nuance like a real LLM.
- It does not yet retrieve Hey Joey strategy content.
- It does not yet generate full parent-facing guidance.
- It should not be treated as a diagnostic or medical system.

---

## Next Improvement Actions

The next stage should focus on turning the structured output into a more user-facing Joey response.

This should include:

- presenting the extracted structured record clearly
- asking one useful follow-up question
- asking the parent/carer to confirm or edit before saving
- preparing the system for later RAG-based strategy retrieval

## Formal Version Comparison

A separate comparison file was created at:

`evaluation/extractor_version_comparison.md`

This records the Version 1 and Version 2 extractor results, including mood-zone distribution, anxiety-level distribution, interpretation, limitations, and thesis relevance.