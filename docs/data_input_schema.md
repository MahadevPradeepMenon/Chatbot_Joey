# Joey Data Input Schema

## Goal

Joey helps parents and carers turn natural-language observations into structured Hey Joey app data.

A parent or carer writes a free-text note, and the deterministic extractor proposes structured fields such as anxiety level, mood zone, behaviours, triggers, environment, Quick Track categories and safety flags.

The structured output is a project-defined representation for the Hey Joey prototype. It is not a diagnosis or clinical assessment.

Joey should ask one targeted follow-up question when important information is missing.

Joey must not save a structured journal entry automatically. The parent or carer must review and explicitly confirm the draft first.

---

## Input Example

Parent note:

> He was anxious before school, refused breakfast, and had a meltdown when I asked him to put his jumper on.

---

## Example Structured Output

The current deterministic extractor can represent the example note approximately as:

```json
{
  "entry_type": "journal_entry",
  "summary": "Anxious morning before school with breakfast refusal and meltdown",
  "date": null,
  "time_of_day": "morning",
  "anxiety_level": "High",
  "mood_zone": "Red",
  "mood_labels": [
    "Anxious",
    "Meltdown",
    "Sensory discomfort"
  ],
  "behaviours": [
    "meltdown",
    "refusal"
  ],
  "activity": "school-related routine",
  "environment": "school",
  "possible_triggers": [
    "school transition or school-related demand",
    "clothing or tactile discomfort"
  ],
  "quick_track_suggestions": [
    "Anxiety",
    "Meltdown/Shutdown",
    "Appetite",
    "Meal Entry",
    "School Attendance",
    "Physical Discomfort"
  ],
  "risk_flags": [],
  "missing_information": [
    "reason for clothing discomfort"
  ],
  "follow_up_question": "Was the jumper uncomfortable because of the fabric, label, tightness, temperature, or something else?",
  "confidence": "Medium",
  "requires_parent_confirmation": true
}
```

This example reflects the current rule-based behaviour rather than an ideal human interpretation. For example, the keyword `school` can cause the deterministic environment mapping to select `school` even though the note says the event happened before school. This is a known contextual limitation of the extractor.

The exact wording of summaries, labels and follow-up questions may change as deterministic rules are refined.

---

## Structured Output Fields

| Field | Description | Example |
|---|---|---|
| `entry_type` | Type of record Joey proposes | `journal_entry` |
| `summary` | Short summary of what happened | Anxious morning before school with breakfast refusal and meltdown |
| `date` | Date of event when explicitly available | `null` if not provided |
| `time_of_day` | Morning, afternoon, evening, night or unknown | `morning` |
| `anxiety_level` | Project-defined anxiety category | `High` |
| `mood_zone` | Project-defined Hey Joey mood zone | `Red` |
| `mood_labels` | Specific emotions, states or observations identified by the rules | Anxious, Meltdown, Sensory discomfort |
| `behaviours` | Observable behaviours identified in the note | meltdown, refusal |
| `activity` | Activity or situation associated with the event | school-related routine |
| `environment` | Environment inferred by the deterministic rules | school |
| `possible_triggers` | Possible contextual triggers identified from the wording | school transition, clothing discomfort |
| `quick_track_suggestions` | Relevant Quick Track fields suggested from the note | Anxiety, Appetite, Meltdown/Shutdown |
| `strategy_categories` | Relevant Hey Joey strategy areas when applicable | Sensory Processing, Emotional Regulation |
| `risk_flags` | Structured safety-related signals detected by the rules | empty when no safety concern is detected |
| `missing_information` | Important information not available in the note | reason for clothing discomfort |
| `follow_up_question` | One targeted question about missing information | Was the jumper uncomfortable because of the fabric, label, tightness, temperature, or something else? |
| `confidence` | Operational confidence label used by the workflow | `Medium` |
| `requires_parent_confirmation` | Whether explicit review is required before journal persistence | `true` |

---

## Mood Zone Mapping

The mood-zone labels are project-defined Hey Joey categories used for structured extraction and evaluation.

| Mood Zone | Meaning | Example Labels |
|---|---|---|
| Red | High distress or dysregulation | anger, scared, enraged, screaming, freeze, meltdown, shutdown |
| Orange | Rising stress or unsettled state | worried, restless, annoyed, anxious, frustrated |
| Green | Regulated or positive state | confident, happy, calm, balanced |
| Blue | Low mood or low energy | miserable, bored, upset, tired, drained |
| Unknown | Not enough information to assign a zone | unclear or absent mood information |

The final thesis evaluation used Red, Orange, Green and Blue as the expected mood-zone classes. These labels should not be interpreted as clinical diagnoses.

---

## Anxiety Levels

The anxiety labels are also project-defined categories.

| Anxiety Level | Meaning |
|---|---|
| Minimal | Little or no anxiety described |
| Moderate | Noticeable worry or discomfort |
| High | Strong anxiety affecting behaviour |
| Severe | Extreme distress, panic, shutdown, meltdown or safety-related language |
| Unknown | Not enough information |

The deterministic extractor applies predefined rules and keywords. Negation, historical context, indirect descriptions and unfamiliar phrasing can therefore lead to incorrect labels.

---

## Quick Track Suggestions

Possible Quick Track fields include:

- Sleep Quality & Duration
- Energy Level
- Appetite
- Meal Entry
- Anxiety
- Mood
- Meltdown/Shutdown
- Physical Discomfort
- Screen Time
- School Attendance
- Bowel Movement
- Nausea
- Medication Mention

Quick Track suggestions are recommendations for structured tracking fields, not medical conclusions.

---

## Strategy Categories

The extractor can suggest relevant Hey Joey strategy areas based on the structured observation.

These categories help connect the record workflow to the wider local support corpus. Strategy retrieval itself is handled separately by the strategy workflow, which performs safety screening, hybrid retrieval and confidence assessment before returning ordinary strategy suggestions.

A suggested category does not mean a strategy is automatically appropriate or should be applied without review.

---

## Safety Rules

Joey must not:

- diagnose a child;
- make treatment claims;
- give medication or dosage recommendations;
- advise starting, stopping or changing medication;
- claim certainty about the cause of behaviour;
- present support content as a replacement for clinicians, therapists, parents, carers or emergency services;
- save a structured journal entry without explicit parent or carer confirmation.

If medication is mentioned, Joey may record that a medication mention occurred, but it should not infer causation or provide medication advice.

If direct language indicates possible self-injury, harm, injury or immediate danger, safety handling takes priority over ordinary strategy retrieval.

Safety detection is deterministic and may miss indirect or unusual wording or over-flag benign terms. Structured `risk_flags` are therefore project-defined safety signals rather than a clinical risk assessment.

---

## Follow-Up and Confirmation

When important information is missing, Joey should ask one targeted follow-up question rather than requesting several fields at once.

The record workflow can preserve and update the same draft across multiple turns.

A draft can progress through workflow states such as:

```text
active
→ ready_for_review
→ confirmed or rejected
```

Only a confirmed draft should be persisted as a completed journal entry.

---

## Current Limitations

The schema is populated by deterministic extraction rules. It may therefore:

- miss unfamiliar or paraphrased language;
- mis-handle negation;
- confuse historical and current events;
- infer context too strongly from isolated keywords;
- miss indirect safety language;
- over-flag ambiguous words;
- ask a follow-up question that is not the most important one.

These limitations are part of the final MSc evaluation and should be considered when interpreting structured output.

---

## Relationship to the MSc Thesis

The final thesis evaluates three extracted fields on 30 fixed synthetic observations:

- `anxiety_level`;
- `mood_zone`;
- safety status derived from the structured safety logic.

The reported results were:

| Field | Final result |
|---|---:|
| Anxiety accuracy | 53.3% |
| Mood-zone accuracy | 63.3% |
| Safety accuracy | 90.0% |
| Safety precision | 75.0% |
| Safety recall | 60.0% |
| Safety F1 | 0.6667 |
| Exact three-field accuracy | 46.7% |

The evaluation used synthetic parent or carer-style observations. No genuine child or family information was used, and the reference labels were project-defined rather than independently clinically validated.
