# Project Limitations

## Rule-Based Extraction

Structured extraction uses deterministic rules, keywords and text patterns rather than a general-purpose generative language model.

This makes the process transparent and reproducible, but the final evaluation showed that performance can fall when language varies beyond the predefined rules. Error patterns included:

- negation;
- historical context;
- indirect descriptions of distress;
- positive or resolved wording;
- unfamiliar paraphrases;
- ambiguous context;
- spelling or wording variation not represented in the rules.

The extractor may also infer a field too strongly from a limited keyword match. In the final 30-case extraction evaluation, anxiety classification achieved 53.3% accuracy and mood-zone classification achieved 63.3% accuracy. Safety classification was stronger at 90.0% accuracy, although recall was 60.0%, showing that some positive safety cases were still missed.

## Synthetic Evaluation Data

The final thesis experiments use fixed synthetic evaluation datasets rather than genuine child or family information.

The extraction, retrieval and confidence datasets each contain 30 designed cases. These datasets support controlled and reproducible technical evaluation, but they may not represent the full linguistic and contextual variation found in real parent or carer observations.

The results therefore demonstrate behaviour on the evaluated synthetic cases only. They do not establish performance across all real-world users or situations.

## Small Evaluation Sets

Each final experiment contains 30 cases.

For retrieval, the same 30 synthetic queries across the ten strategy collections were used to compare:

- Rule-based retrieval;
- BM25-only retrieval;
- Semantic-only retrieval;
- Hybrid Reciprocal Rank Fusion retrieval.

This is sufficient for a prototype comparison, but it is not a large independent benchmark. Small changes in the test set could materially affect the reported percentages.

Future work should use larger datasets with independently created and reviewed labels.

## Researcher-Assigned Relevance Labels

Retrieval relevance was evaluated at the Hey Joey strategy-collection level. Each synthetic query had an expected collection, and a retrieved result was considered relevant when its source chunk belonged to that collection.

These expected labels were created for the project rather than independently judged by multiple domain experts. Collection-level relevance is also a simplification because more than one collection may sometimes contain useful support for the same query.

Future evaluation should include independent relevance judgements from subject-matter experts, Hey Joey stakeholders, and, where ethically approved, parents or carers.

## Retrieval Errors Remain

Semantic-only and Hybrid RRF retrieval both achieved 86.7% Hit@1 and 90.0% Hit@3 on the final 30-query retrieval dataset. This means the expected collection was not found within the first three results for three of the 30 queries.

The error analysis identified failures involving informal or paraphrased queries, including examples related to toilet training, communication and social anxiety.

Possible areas for future investigation include:

- improved query construction;
- corpus review;
- chunking refinement;
- alternative embedding models;
- revised metadata weighting;
- larger candidate pools;
- expert-created relevance labels.

Hybrid RRF matched Semantic-only retrieval on the final dataset but did not improve the ranking metrics further, so hybrid retrieval should not be assumed to outperform the strongest individual retriever in every setting.

## Confidence and Abstention Trade-Off

The confidence layer can abstain when retrieval evidence is weak, but confidence thresholds introduce a trade-off between coverage and reliability.

In the final 30-query confidence evaluation:

- the current configuration / overlap threshold of at least 1 produced 66.7% coverage and 76.7% overall decision accuracy;
- an overlap threshold of at least 2 produced 46.7% coverage and the highest tested overall decision accuracy of 83.3%;
- an overlap threshold of at least 3 produced 23.3% coverage and 73.3% overall decision accuracy.

A stricter threshold therefore does not automatically improve the system. Excessive abstention can reduce usefulness even when accuracy among answered queries increases.

The tested confidence signals are operational heuristics rather than calibrated probabilities.

## No Clinical Validation

The project has not undergone:

- clinical evaluation;
- medical-device assessment;
- safeguarding certification;
- professional therapeutic validation;
- controlled testing with real families;
- validation of clinical outcomes.

The system must not be described as clinically effective, diagnostic or therapeutic.

Project-defined anxiety, mood-zone and safety labels are used for computational evaluation and should not be interpreted as clinical diagnoses.

## Strategy Corpus Scope

Retrieval is limited to the ten approved Hey Joey strategy documents included in the local corpus.

The processed corpus contains 359 chunks, including 257 strategy chunks and 102 contextual chunks. Strategy retrieval can only return support represented in the supplied source material.

Joey cannot retrieve strategies that are absent from the corpus, and the usefulness of retrieval depends on the quality, coverage and maintenance of the approved documents.

## No Generative Response Model

The current workflow does not depend on an external generative language-model API.

Structured extraction is deterministic, safety screening is rule-based, strategy retrieval uses local lexical and sentence-embedding methods, and parent-facing responses are assembled from structured fields and retrieved source passages.

This limits conversational flexibility and natural-language rewriting, but it also keeps the main workflow inspectable, avoids paid model-API dependence and reduces the risk of unsupported generated content.

A future controlled generative rewriting component would require separate evaluation and should not be allowed to weaken deterministic safety, evidence or confirmation boundaries.

## Prototype Interface and Product Integration

The current prototype includes:

- a Streamlit frontend;
- a FastAPI backend;
- persistent SQLite storage;
- HTTP-based separation between frontend and backend;
- Docker and Docker Compose support.

It has not been integrated into:

- the live Hey Joey mobile application;
- a production organisational database;
- a deployed multi-user cloud service;
- the final Hey Joey profile, journal or insights data contracts.

The Streamlit interface demonstrates the workflow but is not a finished consumer product.

## Multi-Turn Workflow Limitations

The current system supports multi-turn record refinement, persistent conversation history, resumable draft state, explicit review and confirmation, and strategy-feedback persistence.

However, the follow-up logic remains deterministic and may not always ask for the most important missing detail. The workflow is based on predefined fields and rules rather than open-ended conversational reasoning.

Further work should evaluate:

- follow-up-question quality;
- user correction and editing behaviour;
- interruption and resume scenarios;
- longer conversations;
- conflicting user answers;
- usability with real users under an approved study.

## Local Model Download and Runtime Requirements

Semantic retrieval uses the local `sentence-transformers/all-MiniLM-L6-v2` model.

For a local Python setup, the model must be downloaded during initial setup if it is not already available in the local cache. Docker builds preload the model into the image during the build process.

After the model and indexes are available locally, normal retrieval does not require an external model API. Initial installation or image building may still require internet access to obtain dependencies and model files.

## Privacy and Governance

The prototype includes privacy-oriented engineering controls such as local processing, repository secret checks, synthetic-only production-demo defaults, non-root containers and redacted application logging.

These controls do not make the system ready for processing identifiable family data on a public service.

A real deployment involving private child or family information would still require, at minimum:

- authentication and authorisation;
- transport encryption;
- encryption at rest;
- managed secrets;
- formal consent and privacy processes;
- retention and deletion policies;
- backup and recovery procedures;
- audit trails;
- security testing;
- monitoring and incident response;
- safeguarding procedures;
- privacy-impact assessment;
- organisational and regulatory approval.

## Interpretation of Results

The completed thesis evaluations support the conclusion that the prototype is technically feasible on its fixed synthetic datasets.

The results show that:

- deterministic extraction is transparent but sensitive to linguistic variation;
- BM25 improves over the original rule-based retrieval baseline;
- Semantic-only retrieval produced the strongest improvement in ranking quality;
- Hybrid RRF matched Semantic-only retrieval on the final 30-query dataset;
- confidence-based abstention can improve decision accuracy at the cost of reduced coverage.

These findings do not demonstrate universal accuracy, clinical benefit, real-world effectiveness or production readiness.

The project should therefore be interpreted as an evaluated MSc decision-support prototype rather than a validated clinical or production system.
