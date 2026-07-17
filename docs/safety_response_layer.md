# Joey Safety and Response Layer

## Purpose

The safety and response layer turns Joey's structured extraction and retrieved strategy support into a safer parent/carer-facing response.

This layer is designed to make Joey cautious, explainable, and appropriate for a neurodivergent family support context.

---

## Workflow

1. Parent/carer enters a free-text note.
2. Joey extracts a structured record.
3. Joey retrieves relevant strategy support.
4. The safety layer checks for sensitive flags.
5. Joey builds a parent-facing response.
6. Parent/carer confirms before anything is saved.

---

## Safety Rules

Joey must not:

- diagnose the child
- give medication advice
- suggest medication dosage changes
- claim certainty about causes
- replace parents, carers, clinicians, or therapists
- save anything automatically

---

## Medication Handling

If medication is mentioned, Joey can log that medication was mentioned.

Joey must not:

- suggest stopping medication
- suggest starting medication
- suggest dosage changes
- say medication caused a behaviour

Safe wording should direct the parent/carer to a healthcare professional if they are concerned.

---

## Safety Concern Handling

If a note mentions self-injury, possible harm, injury, or immediate danger, Joey should prioritise safety signposting.

Safety-sensitive entries should not be treated as ordinary strategy recommendations.

---

## Current Limitations

- Safety detection is currently rule-based.
- It may miss indirect wording.
- It may over-flag some entries.
- Human review and parent/carer confirmation remain required.
- This is a prototype support tool, not a clinical system.