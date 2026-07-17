# Joey Extractor Version Comparison

## Purpose

This document compares two versions of Joey's rule-based extractor.

The goal is to show how the system improved after running the extractor on Dilyara's synthetic journal dataset and reviewing the errors.

---

## Dataset

The extractor was tested on a synthetic journal dataset containing 50 parent/carer-style observations.

The dataset was used to evaluate whether Joey could convert free-text observations into structured fields such as:

- anxiety level
- mood zone
- mood labels
- behaviours
- possible triggers
- Quick Track suggestions
- strategy categories
- risk flags
- follow-up questions

---

## Version 1: Baseline Extractor

The first extractor used simple keyword rules.

### Mood Zone Results

| Mood Zone | Count |
|---|---:|
| Unknown | 31 |
| Blue | 9 |
| Red | 8 |
| Orange | 2 |

### Risk Flags

No risk flags were detected.

### Interpretation

The baseline extractor successfully processed the dataset and generated structured outputs.

However, 31 out of 50 entries were classified as `Unknown`, showing that the first version did not recognise many common parent/carer language patterns.

The first version missed several types of observations, including:

- sensory discomfort
- unexpected schedule changes
- transition difficulties
- crowded or overwhelming environments
- physical discomfort
- panic or distress phrased indirectly

---

## Version 2: Improved Extractor

The second extractor added rules based on the weaknesses found during review.

New rules were added for:

- clothing tags and tactile discomfort
- bright lights and visual sensitivity
- smells and sensory overwhelm
- loud sounds and noise sensitivity
- crowded places
- unexpected visitors
- school bus delays and schedule changes
- stopping play and bedtime transitions
- physical discomfort or illness
- stronger panic detection

### Anxiety Level Results

| Anxiety Level | Count |
|---|---:|
| Moderate | 31 |
| High | 11 |
| Severe | 8 |

### Mood Zone Results

| Mood Zone | Count |
|---|---:|
| Orange | 34 |
| Red | 16 |

### Risk Flags

No risk flags were detected.

---

## Comparison

| Metric | Version 1 | Version 2 |
|---|---:|---:|
| Unknown mood zones | 31 | 0 |
| Orange mood zones | 2 | 34 |
| Red mood zones | 8 | 16 |
| Risk flags detected | 0 | 0 |

---

## Evaluation Summary

The improved extractor showed stronger coverage than the baseline extractor.

The biggest improvement was that `Unknown` mood classifications were reduced from 31 to 0.

This shows that the extractor became better at recognising common parent/carer descriptions, especially sensory discomfort, transition difficulties, environmental overwhelm, and panic-related observations.

However, Version 2 may now be more assertive. All entries were classified as either `Orange` or `Red`, so future work should check whether some lower-severity entries should be classified as `Blue`, `Green`, or `Unknown`.

---

## Limitations

The extractor is still rule-based and keyword-dependent.

It may:

- miss new wording that is not covered by the rules
- over-classify mild observations as higher concern
- fail to understand context or nuance
- detect categories without fully understanding the situation
- require manual review before use in a real app

The system should therefore be treated as a prototype baseline, not a clinical or diagnostic tool.

---

## Thesis Relevance

This evaluation demonstrates an iterative AI engineering workflow:

1. Build a baseline system.
2. Test it on a dataset.
3. Review errors.
4. Improve the rules.
5. Compare before and after performance.
6. Document limitations and next steps.

This supports the thesis aim of building a safe, structured, and explainable data-input assistant for the Hey Joey app.