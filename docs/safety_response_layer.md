# Joey Safety and Response Layer

## Purpose

The safety and response layer helps convert Joey's structured extraction and retrieved strategy evidence into cautious parent or carer-facing output.

Its purpose is to keep safety handling explicit, deterministic and separate from ordinary support retrieval. The layer does not attempt diagnosis or treatment. Instead, it applies project-defined safety rules, preserves uncertainty, and limits ordinary strategy suggestions when a safety concern takes priority.

---

## Current Workflow

### Record-observation workflow

1. A parent or carer enters a free-text observation.
2. Joey creates a structured draft using deterministic extraction.
3. Safety-related information is represented in structured `risk_flags`.
4. Joey asks targeted follow-up questions when required.
5. Joey presents the structured draft for review.
6. The parent or carer explicitly confirms or rejects the draft.
7. A journal entry is saved only after explicit confirmation.

### Strategy-support workflow

1. A parent or carer asks a strategy question.
2. Joey performs deterministic safety screening before ordinary strategy retrieval.
3. If a safety concern takes priority, Joey returns safety-oriented signposting and does not continue with ordinary strategy recommendations.
4. If the question passes the safety screen, Joey builds a privacy-reduced contextual query.
5. The local retrieval pipeline searches the approved strategy corpus.
6. Retrieval confidence is assessed.
7. Joey abstains when the evidence is too weak.
8. When evidence is sufficient, Joey builds a cautious, source-backed strategy response.

This ordering is important: safety screening takes priority over ordinary retrieval rather than being applied only after strategies have already been selected.

---

## Core Safety Rules

Joey must not:

- diagnose a child;
- make treatment claims;
- provide medication or dosage recommendations;
- advise starting, stopping or changing medication;
- claim certainty about the cause of behaviour;
- present retrieved strategy content as clinical advice;
- replace parents, carers, clinicians, therapists or emergency services;
- automatically save a structured journal entry without explicit confirmation.

Joey should:

- use cautious, non-diagnostic wording;
- distinguish support information from professional advice;
- prioritise safety signposting when risk is detected;
- preserve uncertainty where the available evidence is limited;
- abstain from ordinary strategy suggestions when retrieval evidence is weak;
- retain source provenance for returned strategy content.

---

## Medication Handling

Medication references are treated as a safety-sensitive boundary.

Joey can record or acknowledge that medication was mentioned when this is relevant to the observation or conversation.

Joey must not:

- recommend starting medication;
- recommend stopping medication;
- recommend changing a dose;
- recommend changing the timing of a dose;
- interpret medication as the confirmed cause of a behaviour;
- compare medications as treatment options.

If a parent or carer raises a medication-related concern, the response should use cautious wording and direct them toward an appropriate healthcare professional rather than offering medical guidance.

Medication detection does not itself establish that an immediate safety concern is present. It is handled as a separate boundary that prevents Joey from drifting into medication advice.

---

## Safety Concern Handling

Direct references to possible harm, self-injury, injury or immediate danger should take priority over ordinary strategy retrieval.

Examples of safety-sensitive language can include:

- self-injury;
- hitting or hurting oneself;
- possible injury;
- immediate danger;
- language indicating that somebody may be unsafe.

When the safety layer identifies a concern:

1. ordinary strategy retrieval should be limited or stopped;
2. Joey should use clear, cautious safety-oriented wording;
3. the response should avoid implying that a retrieved strategy is an appropriate substitute for urgent or professional support;
4. the system should preserve the relevant safety information in its structured output where applicable.

The exact signposting depends on the project response rules. The system is not an emergency service and cannot assess the severity of a real-world situation.

---

## Structured Risk Flags

Safety-related extraction is represented using structured `risk_flags` rather than hidden model reasoning.

These flags allow later workflow components to inspect why a safety boundary may have been triggered.

The deterministic design supports:

- reproducible behaviour;
- direct regression testing;
- transparent inspection of rule failures;
- separation between safety decisions and retrieval ranking.

However, a structured flag should be treated as a project-defined signal rather than a clinical risk assessment.

---

## Response Construction

Parent-facing responses are assembled from explicit workflow state, structured fields and retrieved evidence.

The response layer should preserve the distinction between:

- structured extraction results;
- safety signposting;
- retrieved strategy evidence;
- confidence or abstention decisions;
- workflow instructions such as review or confirmation.

For strategy responses, returned content should be traceable to the approved local corpus through metadata such as:

- strategy code;
- strategy title;
- collection title;
- source filename;
- supporting passage.

The response layer should not invent unsupported strategy content merely to make an answer sound more conversational.

---

## Confirmation and Persistence

Explicit confirmation applies to the record-observation workflow.

A draft journal record is not written as a confirmed journal entry until the parent or carer has reviewed and confirmed it.

This protects against automatically storing a structured interpretation that the user has not accepted.

Strategy searches and optional strategy feedback have their own persistence rules and do not use the same journal-entry confirmation step.

---

## Relationship to Retrieval Confidence

Safety screening and retrieval confidence address different risks.

- **Safety screening** determines whether a question should proceed to ordinary strategy retrieval at all.
- **Retrieval confidence** determines whether the available source evidence is strong enough to support a strategy response.

A question can therefore pass the safety screen but still produce an abstention because retrieval evidence is weak.

This separation keeps safety decisions independent from retrieval ranking quality.

---

## Current Limitations

The safety layer is deterministic and rule-based.

It may:

- miss indirect, ambiguous or unusual expressions of harm;
- miss paraphrases that are not represented in the rules;
- over-flag benign words or contexts;
- interpret isolated keywords without enough surrounding context;
- fail to recognise the real-world severity of a situation.

The final synthetic extraction evaluation achieved 90.0% safety-classification accuracy, but recall was 60.0%. This shows that high overall accuracy did not prevent some positive safety cases from being missed.

The error analysis also identified:

- a missed paraphrase of self-injury;
- a false safety trigger associated with the word `tablet`.

These results reinforce that deterministic safety screening should not be treated as complete safeguarding or clinical risk assessment.

---

## Governance Boundary

The current implementation is an MSc prototype and does not provide:

- clinical validation;
- safeguarding certification;
- emergency triage;
- medical-device approval;
- professional risk assessment;
- guaranteed detection of harmful situations.

A real deployment involving identifiable child or family information would still require appropriate safeguarding procedures, privacy governance, authentication, access control, monitoring, audit processes and professional review.

---

## Main Implementation Files

```text
safety/safety_guard.py
app/extractor.py
app/response_builder.py
app/record_workflow_service.py
app/strategy_workflow_service.py
rag/retrieval_confidence.py
```

Relevant regression coverage includes:

```text
evaluation/test_retrieval_confidence.py
evaluation/test_api_record_workflow.py
evaluation/test_api_strategy_workflow.py
evaluation/test_repository_safety.py
```

---

## Current Safety Architecture

```text
parent/carer input
→ deterministic extraction or question screening
→ structured safety signals
→ safety decision
   ├─ safety concern → safety-oriented response / ordinary retrieval limited
   └─ no overriding concern
        → local strategy retrieval where relevant
        → confidence assessment
        → abstain or return source-backed support
→ explicit confirmation before journal-entry persistence
```

The system should therefore be described as a cautious, transparent support prototype with deterministic safety boundaries, not as a clinical or safeguarding system.
