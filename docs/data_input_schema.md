# Joey Data Input Schema

## Goal

Joey should help parents/carers turn natural language notes into structured Hey Joey app data.

The parent/carer writes a free-text note, and Joey suggests structured fields such as anxiety level, mood zone, behaviours, triggers, environment, and Quick Track categories.

Joey must ask follow-up questions if important details are missing.

Joey must not save anything automatically. The parent/carer must review and confirm first.

---

## Input Example

Parent note:

"He was anxious before school, refused breakfast, and had a meltdown when I asked him to put his jumper on."

---

## Structured Output Fields

| Field | Description | Example |
|---|---|---|
| `entry_type` | Type of record Joey thinks this should become | journal_entry |
| `summary` | Short summary of what happened | Anxious morning before school with breakfast refusal and meltdown |
| `date` | Date of event if mentioned | 2026-07-08 |
| `time_of_day` | Morning, afternoon, evening, night, unknown | morning |
| `anxiety_level` | Minimal, Moderate, High, Severe, Unknown | High |
| `mood_zone` | Red, Orange, Green, Blue, Mixed, Unknown | Orange/Red |
| `mood_labels` | Specific emotions or states | anxious, frustrated, meltdown |
| `behaviours` | Observable behaviours | refused breakfast, meltdown |
| `activity` | Activity or situation | school preparation |
| `environment` | Where it happened | home |
| `possible_triggers` | Possible causes or triggers | school transition, clothing discomfort |
| `quick_track_suggestions` | Suggested Quick Track fields | Anxiety, Appetite, Meltdown/Shutdown |
| `strategy_categories` | Relevant Hey Joey strategy areas | Emotional Regulation, Sensory Processing |
| `risk_flags` | Safety concerns detected | none |
| `missing_information` | Important details not provided | jumper discomfort reason |
| `follow_up_question` | One useful question Joey should ask | Was the jumper uncomfortable because of fabric, label, tightness, or something else? |
| `confidence` | Low, Medium, High | Medium |
| `requires_parent_confirmation` | Always true | true |

---

## Mood Zone Mapping

| Mood Zone | Meaning | Example Labels |
|---|---|---|
| Red | High distress or dysregulation | anger, scared, enraged, screaming, freeze, meltdown, shutdown |
| Orange | Rising stress or unsettled | worried, restless, annoyed, anxious, frustrated |
| Green | Regulated or positive | confident, happy, calm, balanced |
| Blue | Low mood or low energy | miserable, bored, upset, tired, drained |

---

## Anxiety Levels

| Anxiety Level | Meaning |
|---|---|
| Minimal | Little or no anxiety described |
| Moderate | Noticeable worry or discomfort |
| High | Strong anxiety affecting behaviour |
| Severe | Extreme distress, panic, shutdown, meltdown, or safety concern |
| Unknown | Not enough information |

---

## Quick Track Suggestions

Possible Quick Track fields:

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

---

## Safety Rules

Joey must not:

- diagnose the child
- give medication advice
- suggest dosage changes
- claim certainty from limited data
- give emergency advice beyond signposting
- replace clinicians, therapists, or parents/carers
- save data without parent/carer confirmation