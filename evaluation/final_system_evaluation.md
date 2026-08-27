# Joey Integrated MVP Development Evaluation

> **Status note:** This document records an earlier integrated MVP development and regression evaluation. It is retained as supporting engineering evidence, but it is **not** the final MSc dissertation experiment set. The final thesis experiments use three fixed 30-case synthetic datasets and are stored under `evaluation/final_thesis/`, together with the final experiment runner and result artefacts.

> In particular, the ten-query retrieval comparison reported below is a development evaluation. The final dissertation retrieval experiment compares Rule-based, BM25-only, Semantic-only and Hybrid RRF retrieval on 30 synthetic queries.

## Evaluation Purpose

This evaluation assesses the Joey MVP as an integrated local decision-support system and records development/regression evidence across the wider workflow rather than the final dissertation experiments alone.

The evaluated workflow is:

`free-text observation → deterministic structured extraction → safety screening → context selection → local strategy retrieval → source-backed response → parent/carer confirmation → optional local save`

The evaluation also covers the separate strategy-question workflow, multi-turn follow-up behaviour, synthetic context selection, history-aware ranking and the final Streamlit chatbot interface.

---

## System Scope

Joey is a local prototype designed to support parents and carers of neurodivergent children.

The MVP can:

- accept a natural-language observation;
- extract a structured journal draft;
- identify missing information;
- ask follow-up questions;
- require parent/carer confirmation before saving;
- search an approved local Hey Joey strategy library;
- return source-backed support options;
- apply safety restrictions when a note may involve harm or injury;
- use synthetic profile, journal and strategy-history context;
- modestly adjust close retrieval rankings using previous strategy feedback;
- provide a browser-based Streamlit chatbot interface.

Joey does not diagnose, prescribe treatment, replace professional advice or make final care decisions.

---

## Evaluation Data

All evaluation cases used synthetic parent/carer-style observations and support questions.

No real child, parent, carer or family records were used.

The evaluation datasets covered:

- school-related anxiety;
- mealtime difficulty;
- sensory discomfort;
- sleep and tiredness;
- friendship and social participation;
- communication difficulty;
- toilet training;
- hygiene;
- medication mentions;
- potential safety concerns;
- positive observations;
- multi-turn follow-up and confirmation;
- synthetic context selection;
- history-aware strategy ranking.

---

## Components Evaluated

The evaluation tested whether Joey could:

1. assign an expected mood zone;
2. assign a reasonable anxiety level;
3. identify relevant strategy categories;
4. suggest relevant Quick Track fields;
5. detect medication and safety-sensitive wording;
6. block ordinary strategy retrieval when a safety concern is detected;
7. retrieve relevant source-backed strategy evidence;
8. require parent/carer confirmation before saving;
9. update the same structured draft across multiple turns;
10. exclude sensitive fields from synthetic retrieval context;
11. use synthetic recent history and feedback without overwhelming the base retrieval ranking;
12. maintain separate chat histories for the two Streamlit workflows.

---

## Regression Results

### Python Compilation

The following command completed without compilation errors:

`python -m compileall app rag safety evaluation`

### Original End-to-End Evaluation

- Test cases passed: **6/6**
- Individual checks passed: **54/54**

The six cases covered:

- school and mealtime sensory difficulty;
- sleep and school context;
- noise sensitivity;
- medication mention;
- safety concern;
- positive observation.

Generated result files:

- `evaluation/end_to_end_results.csv`
- `evaluation/end_to_end_results.json`

### Integrated Semantic Evaluation

- Test cases passed: **7/7**
- Individual checks passed: **63/63**

The seven cases covered:

- sensory noise;
- sleep and bedtime;
- social anxiety;
- eating and mealtime;
- toilet training;
- communication;
- self-injury safety handling.

The self-injury case returned no ordinary strategy results and correctly activated safety-limited behaviour.

Generated result files:

- `evaluation/semantic_end_to_end_results.csv`
- `evaluation/semantic_end_to_end_results.json`

### Multi-Turn Conversation Evaluation

- Tests passed: **3/3**

Verified behaviours:

- sensory follow-up handling;
- environment and trigger follow-up handling;
- confirmation-state handling.

### Synthetic Context-Builder Evaluation

- Tests passed: **4/4**

Verified behaviours:

- sensitive fields were excluded;
- sensory questions selected relevant context;
- sleep questions selected sleep-related context;
- the final retrieval query contained both the current question and selected context.

### History-Aware Personalisation Evaluation

- Tests passed: **4/4**

Verified behaviours:

- an active strategy received a modest positive adjustment;
- positive feedback could break a close ranking tie;
- negative feedback reduced a strategy score;
- an unseen strategy was described as new.

---

## Development Retrieval Comparison (10 Queries)

A shared ten-case synthetic development dataset compared:

1. the original deterministic rule-based retriever;
2. local semantic-only retrieval;
3. Hybrid semantic and BM25 retrieval using Reciprocal Rank Fusion.

All three methods used the same queries, expected keywords and `top_k = 3` setting.

| Retriever | Hit@1 | Hit@3 | Mean Reciprocal Rank | Average latency | Errors |
|---|---:|---:|---:|---:|---:|
| Rule-based | 3/10 | 5/10 | 0.4000 | 0.000938 seconds | 0 |
| Semantic | 8/10 | 9/10 | 0.8333 | 0.065338 seconds | 0 |
| Hybrid | 7/10 | 9/10 | 0.8000 | 0.064551 seconds | 0 |

### Interpretation

Both embedding-based approaches substantially outperformed the original rule-based baseline on the designed ten-case evaluation set.

Semantic-only retrieval achieved the strongest rank-one performance and the highest Mean Reciprocal Rank.

Hybrid retrieval matched semantic retrieval for top-three coverage but was slightly weaker at rank one on this dataset.

This result shows that Hybrid RAG should be evaluated rather than assumed to be superior. Reciprocal Rank Fusion can promote results that perform strongly in both semantic and lexical retrieval, but this may also move an expected semantic result from first to second position.

The application retains Hybrid retrieval because it combines semantic similarity with direct lexical evidence. However, the evaluation does not claim that Hybrid retrieval was empirically best on this particular synthetic test set.

Detailed retrieval results are stored in:

- `evaluation/retrieval_comparison_results.csv`
- `evaluation/retrieval_comparison_results.json`
- `evaluation/retrieval_comparison_evaluation.md`


### Relationship to the final thesis retrieval experiment

The ten-query results above are retained as development evidence only. The final dissertation retrieval experiment is stored separately under `evaluation/final_thesis/` and uses 30 synthetic queries across ten strategy collections.

The final thesis comparison includes four methods:

| Retriever | Hit@1 | Hit@3 | MRR | Mean warm-run latency |
|---|---:|---:|---:|---:|
| Rule-based baseline | 40.0% | 50.0% | 0.4500 | 0.615 ms |
| BM25-only | 66.7% | 86.7% | 0.7611 | 4.316 ms |
| Semantic-only | 86.7% | 90.0% | 0.8833 | 28.765 ms |
| Hybrid RRF | 86.7% | 90.0% | 0.8833 | 30.142 ms |

Semantic-only and Hybrid RRF tied on the final synthetic ranking metrics. Hybrid RRF remained the application default because it combines lexical and semantic evidence without treating their raw scores as directly comparable.

---

## Successful Behaviours

The completed MVP demonstrated the following behaviours:

- structured records were generated consistently from natural-language observations;
- the same draft could be updated across several follow-up turns;
- parent/carer confirmation was required before saving;
- medication mentions were recorded without giving dosage or medication-change advice;
- safety-sensitive entries were distinguished from ordinary observations;
- ordinary strategy retrieval was blocked when a safety concern was detected;
- sensory, sleep, communication, social, eating and toileting strategy evidence could be retrieved from the approved local corpus;
- source information was shown with strategy responses;
- synthetic context excluded identifiers and medication details;
- strategy-history feedback produced only modest ranking adjustments;
- the final browser interface supported both observation recording and strategy questions;
- Joey and sender messages were visually separated using chat-style speech bubbles;
- each workflow maintained its own scrollable conversation history during the active Streamlit session.

---

## Current Streamlit Interface

The current prototype presents only the user-facing controls required for the chatbot workflow:

1. **Record what happened**
2. **Ask for a strategy**
3. one message composer;
4. the scrollable conversation;
5. Joey’s source-backed or safety-limited response.

The interface includes:

- the official Hey Joey logo;
- a segmented workflow selector;
- green Joey bubbles with white text;
- white sender bubbles with dark text;
- separate bubbles for follow-up questions and confirmation prompts;
- a scrollable message history;
- separate histories for both workflows;
- a full-width message composer and Send button.

The broader extraction, safety, context-selection, retrieval, ranking and save logic runs behind the interface.

---

## Safety Evaluation

Joey is designed to:

- avoid diagnosis;
- avoid medication recommendations;
- avoid dosage guidance;
- avoid advising medication changes;
- avoid claiming a certain cause;
- use cautious support language;
- prioritise safety wording when risk is detected;
- suppress ordinary strategy retrieval for safety-sensitive entries;
- require parent/carer confirmation before saving.

Safety detection remains deterministic and rule-based. It cannot guarantee that every indirect, unusual or ambiguous risk phrase will be recognised.

The system should therefore be treated as a support-management prototype rather than an emergency, medical or safeguarding service.

---

## Privacy and Data Handling

The prototype was developed and evaluated using synthetic data.

The local context builder excludes:

- names and direct identifiers;
- medication details;
- other fields not required for strategy retrieval.

Confirmed records are currently saved locally rather than transmitted to a live Hey Joey database.

Private runtime folders remain outside source control, including local records, processed strategy text, strategy chunks and generated indexes.

---

## Limitations

The main limitations are:

- evaluation datasets are small and synthetic;
- relevance is assessed through predefined keyword matching rather than independent domain-expert judgements;
- the deterministic extractor may miss unusual wording, negation or indirect context;
- follow-up questions may not always target the most important missing detail;
- the local safety rules cannot guarantee recognition of every risk expression;
- retrieval latency depends on the local computer and model-loading state;
- source-backed retrieval does not establish clinical effectiveness;
- history-aware ranking is based on synthetic context rather than long-term real-world use;
- conversations are persisted through the application storage layer and remain available across Streamlit sessions;
- confirmed records, conversations, strategy searches and feedback are stored locally in SQLite in the main FastAPI application;
- the legacy command-line interface still writes confirmed records to a private JSONL file for backwards-compatible development use;
- no live Bubble, mobile-app or production Hey Joey integration was available;
- no usability study with real parents, carers or professionals has yet been completed;
- automated configuration, Docker build and release validation have been completed, but the prototype has not undergone production security, load, privacy-impact or live operational testing.

---

## Local Prototype and Future Product Integration

The current system demonstrates the intended integration contract but is not connected to the live Hey Joey product.

In a future product implementation:

- confirmed structured records could feed Journal Entries;
- mood, anxiety, behaviour and trigger fields could feed Weekly Insights;
- approved Quick Track suggestions could populate tracking workflows;
- strategy searches could use the supported person’s recent journal context;
- strategy feedback could update future history-aware ranking;
- confirmed data could be migrated from local SQLite to an authorised production database with authentication, authorisation and permission controls.

The current synthetic context provider and local SQLite persistence layer demonstrate how these components could connect without requiring access to live family data.

---

## Overall Interpretation

The completed MVP demonstrates that a local, explainable and safety-aware system can transform parent/carer observations into structured journal drafts, ask targeted follow-up questions, retrieve source-backed support strategies, incorporate limited synthetic context and preserve human confirmation.

The regression results in this document show that the implemented workflows operate consistently across the predefined development tests.

The ten-query retrieval comparison is retained as historical development evidence. It showed stronger top-three coverage for embedding-based retrieval than for the original rule-based baseline, but it should not be interpreted as the final dissertation retrieval experiment. The final 30-query thesis evaluation is stored under `evaluation/final_thesis/` and reports Rule-based, BM25-only, Semantic-only and Hybrid RRF results separately.

Together, the regression and final thesis artefacts support the technical feasibility of Joey as a local support-management subsystem. They do not establish clinical effectiveness, universal retrieval accuracy or production readiness.

---

## Final Thesis Evaluation Artefacts

The final MSc experiments are preserved separately from the development/regression files described above.

```text
evaluation/final_thesis/
├── data/
│   ├── confidence_cases.json
│   ├── holdout_extraction_cases.csv
│   ├── holdout_extraction_dataset.xlsx
│   └── retrieval_final_cases.json
├── results/
│   ├── extraction_case_results.csv
│   ├── extraction_summary.csv
│   ├── retrieval_final_case_results.csv
│   ├── retrieval_final_results.json
│   ├── retrieval_final_summary.csv
│   ├── confidence_case_features.csv
│   ├── confidence_threshold_summary.csv
│   ├── confidence_pareto_frontier.csv
│   └── final_experiment_manifest.json
└── run_final_ml_experiments.py
```

The final thesis experiment runner reproduces the 30-case extraction evaluation, the 30-query four-method retrieval comparison, and the 30-query confidence/abstention analysis using the fixed synthetic datasets stored alongside it.

The older evaluation files directly under `evaluation/` remain useful as development and regression evidence, but they should not be used as the source for the final dissertation metrics.

---

## Engineering Completed Since the Initial Evaluation

The following items were originally identified as future work and were subsequently implemented for release `v0.1.0`:

- local SQLite persistence for confirmed records, conversations, strategy searches and feedback;
- retrieval-confidence handling with a clear abstention response when evidence is insufficient;
- structured strategy feedback and history-aware ranking;
- persistent conversation storage;
- a FastAPI backend, Docker and Docker Compose configuration, structured logging, health and readiness checks, GitHub Actions validation and a versioned container-release workflow.

---

## Future Work

Recommended future work now includes:

1. feeding confirmed fields into local Weekly Insights calculations;
2. implementing a formal live profile and journal-context adapter for future Hey Joey product integration;
3. expanding the synthetic datasets and obtaining domain-expert relevance judgements;
4. conducting an approved usability evaluation;
5. completing production authentication, authorisation, privacy, security, monitoring, backup, retention and incident-response assessments.

A local generative model could later be tested as a controlled response-rewriting component, but the deterministic and source-backed system should remain responsible for safety, retrieval evidence and final validation.
