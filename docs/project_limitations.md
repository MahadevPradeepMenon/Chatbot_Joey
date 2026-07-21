# Project Limitations

## Rule-Based Extraction

Structured extraction uses deterministic patterns rather than a
general-purpose language model.

This makes the process transparent and reproducible, but it may miss:

- unfamiliar language;
- indirect descriptions;
- spelling variations;
- complex temporal relationships;
- ambiguous context;
- behaviours not represented in the rules.

The extractor may also infer fields too strongly from limited wording.

## Synthetic Evaluation Data

The functional and retrieval evaluations use designed synthetic cases.

The results demonstrate performance on those predefined tests only.
They do not establish performance across all real parent observations.

## Small Retrieval Evaluation Set

The rule-based and semantic retrieval comparison contains ten queries.

This is sufficient for a prototype comparison but is not a large
independent benchmark.

## Keyword-Based Relevance Judgements

Expected retrieval relevance was assessed using predefined keywords
matched against strategy metadata.

Future evaluation should involve independent review by subject-matter
experts, parents or Hey Joey stakeholders.

## One Semantic Retrieval Miss

The semantic retriever achieved Hit@3 on nine of ten evaluation
queries, meaning one expected support area was not found within the
first three results.

This should be investigated through:

- improved query construction;
- corpus review;
- chunking refinement;
- alternative embedding models;
- hybrid semantic and keyword retrieval;
- expert-created relevance labels.

## No Clinical Validation

The project has not undergone:

- clinical evaluation;
- medical-device assessment;
- safeguarding certification;
- professional therapeutic validation;
- testing with real families at scale.

It must not be described as clinically effective.

## Strategy Corpus Scope

Retrieval is limited to the ten approved Hey Joey strategy collections
currently included in the local corpus.

Joey cannot retrieve support that is absent from those documents.

## No Generative Language Model

The current parent response is assembled deterministically from
structured fields and retrieved passages.

This limits conversational flexibility, but avoids paid API dependence,
reduces hallucination risk and keeps the central workflow verifiable.

## Local Command-Line Interface

The current prototype uses a terminal interface.

It has not yet been integrated into:

- Bubble;
- a production web application;
- a mobile application;
- a cloud backend;
- an organisational database.

## No Multi-Turn Field Editing

Joey asks a follow-up question, but the current MVP does not yet
automatically merge the answer into the existing structured record as
a full multi-turn state machine.

The rewrite option reruns the complete extraction process.

## Local Model Download

The embedding model must be downloaded during initial setup.

After installation, embedding and retrieval can operate locally, but
the first setup requires internet access.

## Privacy and Governance

The technical design keeps data local, but a production deployment
would still require:

- formal consent processes;
- access controls;
- retention and deletion policies;
- encryption;
- audit logging;
- safeguarding procedures;
- privacy-impact assessment;
- compliance review.

## Interpretation of Results

The completed evaluations support the conclusion that the MVP functions
as designed on its predefined test suite and that semantic retrieval
outperformed the original baseline on the comparison set.

They do not demonstrate universal accuracy, clinical benefit or
production readiness.