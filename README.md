# Hey Joey: Context-Aware Hybrid RAG Assistant

A local-first, safety-aware conversational support system designed for future integration with the Hey Joey application.

The prototype helps parents and carers:

- record natural-language observations;
- turn those observations into structured journal drafts;
- answer follow-up questions across multiple turns;
- review and confirm information before it is saved;
- ask for support strategies;
- receive source-backed suggestions from an approved local strategy library.

The system runs locally and does not require a paid language-model API.

---

## Project Goal

Hey Joey is not intended to be “just another chatbot”.

It is a local AI-assisted support-management subsystem built around a clear workflow:

```text
free-text observation
→ deterministic structured extraction
→ safety screening
→ context selection
→ local Hybrid RAG retrieval
→ history-aware ranking
→ source-backed response
→ parent/carer confirmation
→ optional local save
```

The system is designed so that AI-assisted retrieval is only one component. Core extraction, safety, confirmation and save behaviour remain explicit and verifiable.

---

## Main User Workflows

### 1. Record what happened

A parent or carer can describe an observation in natural language.

Joey then:

1. extracts a structured journal draft;
2. identifies missing information;
3. asks a targeted follow-up question;
4. updates the same draft across several turns;
5. presents a final summary;
6. requires confirmation before saving.

### 2. Ask for a strategy

A parent or carer can ask what support strategy may be relevant.

Joey then:

1. screens the question for safety concerns;
2. selects privacy-safe synthetic context;
3. searches the local approved strategy library;
4. combines semantic and BM25 retrieval;
5. applies modest history-aware ranking adjustments;
6. returns source-backed support options;
7. uses cautious language rather than presenting medical advice.

---

## Final Streamlit Interface

The final prototype presents only the controls needed for the chatbot experience:

- **Record what happened**
- **Ask for a strategy**
- one message composer
- one Send button
- a scrollable conversation history

The interface includes:

- the official Hey Joey logo;
- a segmented workflow selector;
- green Joey speech bubbles with white text;
- white sender speech bubbles with dark text;
- separate bubbles for follow-up questions and confirmations;
- separate chat histories for both workflows;
- a scrollable conversation area;
- a full-width message composer.

The extraction, safety, context, retrieval, personalisation and save logic runs in the background.

---

## Structured Record

Joey converts parent/carer observations into a `StructuredJoeyRecord`.

Current fields include:

- entry type
- summary
- date
- time of day
- anxiety level
- mood zone
- mood labels
- behaviours
- activity
- environment
- possible triggers
- Quick Track suggestions
- strategy categories
- risk flags
- missing information
- follow-up question
- confidence
- confirmation requirement

Every record requires parent/carer confirmation before saving.

---

## Safety Behaviour

Joey is designed to:

- avoid diagnosis;
- avoid treatment claims;
- avoid medication recommendations;
- avoid dosage guidance;
- avoid advising medication changes;
- avoid claiming a certain cause;
- use cautious support language;
- detect medication mentions without turning them into advice;
- detect safety or self-injury concerns;
- block ordinary strategy retrieval when a safety concern is detected;
- prioritise urgent or professional support wording;
- require confirmation before saving.

Safety screening is deterministic and cannot guarantee recognition of every indirect or unusual risk phrase.

Joey is a support-management prototype. It is not a clinical, diagnostic, emergency or safeguarding service.

---

## Local Strategy Corpus

The local strategy corpus contains:

- 10 approved Hey Joey strategy documents;
- 359 processed chunks;
- 257 strategy chunks;
- 102 context chunks.

The corpus is stored and processed locally.

Private raw, processed and indexed files are excluded from version control.

---

## Genuine Hybrid RAG

The final retrieval pipeline combines:

- local BM25 lexical retrieval;
- local semantic embedding retrieval;
- Reciprocal Rank Fusion;
- strategy-level deduplication;
- privacy-safe contextual query construction;
- history-aware ranking adjustments.

### Semantic model

The semantic retriever uses:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Index characteristics:

- 384-dimensional embeddings;
- `float32`;
- normalised vectors;
- local inference.

No paid API key is required.

### Reciprocal Rank Fusion

Hybrid retrieval combines semantic and lexical rankings rather than combining raw scores directly.

This avoids treating BM25 scores and cosine-similarity scores as though they are on the same scale.

---

## Synthetic Context

The current prototype uses synthetic context to demonstrate how Joey could later integrate with the wider Hey Joey application.

Context can include:

- recent journal themes;
- active strategies;
- previous strategy feedback;
- relevant profile preferences.

The context builder excludes:

- names and direct identifiers;
- medication details;
- fields not needed for retrieval.

This demonstrates the integration contract without requiring real family data or live product access.

---

## History-Aware Personalisation

The history-aware ranking layer can modestly adjust close retrieval results.

Examples:

- an active strategy may receive a small positive adjustment;
- positive feedback may break a close ranking tie;
- negative feedback may reduce a score;
- a previously unseen strategy can be labelled as new.

Personalisation does not replace the base Hybrid retrieval score and is deliberately limited so that synthetic history cannot overwhelm source relevance.

---

## Evaluation

### Three-way retrieval comparison

The same 10 synthetic support queries were used to compare:

1. the original deterministic rule-based retriever;
2. semantic-only retrieval;
3. Hybrid BM25 and semantic retrieval.

All three methods used the same expected keywords and `top_k = 3`.

| Retriever | Hit@1 | Hit@3 | MRR | Average latency | Errors |
|---|---:|---:|---:|---:|---:|
| Rule-based baseline | 3/10 | 5/10 | 0.4000 | 0.000938 s | 0 |
| Semantic retrieval | 8/10 | 9/10 | 0.8333 | 0.065338 s | 0 |
| Hybrid retrieval | 7/10 | 9/10 | 0.8000 | 0.064551 s | 0 |

### Interpretation

Both embedding-based approaches substantially outperformed the rule-based baseline on the designed synthetic test set.

Semantic-only retrieval achieved the strongest rank-one performance.

Hybrid retrieval matched semantic retrieval for top-three coverage but was slightly weaker at rank one.

The application still retains Hybrid retrieval because it combines semantic similarity with direct lexical evidence. The evaluation does not claim that Hybrid retrieval was empirically best on this specific test set.

These results apply only to the designed 10-case synthetic evaluation and do not establish universal retrieval accuracy.

### Integrated regression results

The completed regression suite produced:

- **6/6** original end-to-end cases passed;
- **54/54** original end-to-end checks passed;
- **7/7** integrated semantic end-to-end cases passed;
- **63/63** integrated semantic functional checks passed;
- **3/3** multi-turn conversation tests passed;
- **4/4** synthetic context-builder tests passed;
- **4/4** history-aware personalisation tests passed;
- Python compilation completed without errors.

Accurate wording:

> The integrated Joey MVP passed all seven predefined synthetic end-to-end test cases and all 63 functional checks.

This does not mean the system is universally accurate.

---

## Project Structure

```text
Chatbot_Joey/
│
├── app/
│   ├── schemas.py
│   ├── extractor.py
│   ├── conversation_manager.py
│   ├── response_builder.py
│   ├── context_builder.py
│   ├── joey_cli.py
│   └── streamlit_app.py
│
├── rag/
│   ├── document_loader.py
│   ├── strategy_chunker.py
│   ├── build_embedding_index.py
│   ├── semantic_retriever.py
│   ├── bm25_retriever.py
│   ├── hybrid_retriever.py
│   ├── joey_strategy_service.py
│   ├── context_aware_strategy_service.py
│   ├── strategy_history_ranker.py
│   └── history_aware_strategy_service.py
│
├── safety/
│   └── safety_guard.py
│
├── evaluation/
│   ├── end_to_end_test_cases.json
│   ├── end_to_end_results.csv
│   ├── end_to_end_results.json
│   ├── semantic_end_to_end_test_cases.json
│   ├── semantic_end_to_end_results.csv
│   ├── semantic_end_to_end_results.json
│   ├── retrieval_comparison_cases.json
│   ├── retrieval_comparison_results.csv
│   ├── retrieval_comparison_results.json
│   ├── retrieval_comparison_evaluation.md
│   ├── final_system_evaluation.md
│   ├── run_end_to_end_evaluation.py
│   ├── run_semantic_end_to_end_evaluation.py
│   ├── run_retrieval_comparison.py
│   ├── test_multi_turn_conversation.py
│   ├── test_context_builder.py
│   └── test_history_aware_strategy.py
│
├── assets/
│   └── hey_joey_logo.png
│
├── data/
│   ├── local/
│   ├── raw/
│   │   └── strategies/
│   ├── processed/
│   │   ├── strategies_text/
│   │   └── strategy_chunks/
│   └── indexes/
│
├── requirements.txt
└── README.md
```

Private runtime data folders are excluded from Git.

---

## Installation

Create and activate a virtual environment.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Main dependencies include:

- Pydantic
- pandas
- openpyxl
- python-docx
- pypdf
- sentence-transformers
- NumPy
- Streamlit

---

## Preparing the Local Strategy Index

Place approved strategy documents in:

```text
data/raw/strategies/
```

Process the documents using the project’s document-loading and chunking scripts.

Build the embedding index:

```powershell
python -m rag.build_embedding_index
```

The generated local text, chunks and indexes are excluded from version control.

---

## Running the Application

### Streamlit chatbot

From the project root:

```powershell
python -m streamlit run app\streamlit_app.py
```

The Streamlit interface is a polished local chatbot prototype for the Hey Joey application.

### CLI workflow

```powershell
python -m app.joey_cli
```

### Hybrid retrieval demonstration

```powershell
python -m rag.hybrid_retriever
```

### Context-aware retrieval demonstration

```powershell
python -m rag.context_aware_strategy_service
```

### History-aware retrieval demonstration

```powershell
python -m rag.history_aware_strategy_service
```

---

## Running the Evaluations

Run commands from the project root.

### Compile all Python modules

```powershell
python -m compileall app rag safety evaluation
```

### Original end-to-end evaluation

```powershell
python -m evaluation.run_end_to_end_evaluation
```

Expected verified result:

```text
Cases passed: 6/6
Checks passed: 54/54
```

### Integrated semantic end-to-end evaluation

```powershell
python -m evaluation.run_semantic_end_to_end_evaluation
```

Expected verified result:

```text
Cases passed: 7/7
Checks passed: 63/63
```

### Three-way retrieval comparison

```powershell
python -m evaluation.run_retrieval_comparison
```

Use the module command above rather than:

```powershell
python evaluation\run_retrieval_comparison.py
```

Running the file directly may prevent Python from resolving the top-level `app` package.

### Multi-turn conversation tests

```powershell
python -m evaluation.test_multi_turn_conversation
```

Expected verified result:

```text
3/3 multi-turn conversation tests passed.
```

### Synthetic context-builder tests

```powershell
python -m evaluation.test_context_builder
```

Expected verified result:

```text
4/4 synthetic context-builder tests passed.
```

### History-aware personalisation tests

```powershell
python -m evaluation.test_history_aware_strategy
```

Expected verified result:

```text
4/4 history-aware personalisation tests passed.
```

---

## Local Saving

Confirmed structured records are saved locally to:

```text
data/local/confirmed_joey_records.jsonl
```

Nothing is saved automatically.

The parent/carer must confirm the final draft before the local save action occurs.

The current save format demonstrates the workflow but is not a production database integration.

---

## Privacy

The prototype is local-first.

The repository excludes:

```text
data/local/
data/raw/strategies/
data/processed/strategies_text/
data/processed/strategy_chunks/
data/indexes/
```

No real child or family data should be committed.

Evaluation uses synthetic observations and synthetic context.

---

## Current Status

| Objective | Status |
|---|---|
| Deterministic structured extraction | Complete |
| Safety screening | Complete |
| Confirmation-before-save workflow | Complete |
| Local semantic retrieval | Complete |
| Local BM25 retrieval | Complete |
| Reciprocal Rank Fusion | Complete |
| Genuine Hybrid RAG | Complete |
| Multi-turn conversation | Complete |
| Privacy-safe synthetic context | Complete |
| History-aware personalisation | Complete |
| Source-backed strategy responses | Complete |
| Final three-way retrieval evaluation | Complete |
| Full regression suite | Complete |
| Polished Streamlit chatbot interface | Complete |
| Live Hey Joey product integration | Not available |
| Production deployment | Future work |

---

## Limitations

The current prototype has several important limitations:

- evaluation datasets are small and synthetic;
- retrieval relevance uses predefined keyword matching rather than independent expert judgement;
- the deterministic extractor may miss unusual phrasing, negation or indirect context;
- follow-up questions may not always target the most important missing detail;
- safety rules cannot guarantee recognition of every risk expression;
- retrieval latency depends on the local machine and model state;
- source-backed retrieval does not demonstrate clinical effectiveness;
- history-aware ranking currently uses synthetic data;
- chat history is held in Streamlit session state rather than persistent storage;
- confirmed records use JSONL rather than a production database;
- no live Bubble, mobile-app or Hey Joey database integration was available;
- no approved usability study with real parents, carers or professionals has been completed;
- no production security, load, monitoring or privacy-impact assessment has been completed.

---

## Future Work

Recommended future objectives include:

1. replace or supplement JSONL with SQLite;
2. feed confirmed structured fields into local Weekly Insights calculations;
3. add a retrieval-confidence threshold;
4. return a clear “no sufficiently relevant approved source found” response when evidence is weak;
5. collect structured feedback after strategy suggestions;
6. persist and reopen chat sessions;
7. create a formal profile and journal-context adapter;
8. expand the synthetic test set;
9. obtain domain-expert relevance judgements;
10. conduct an approved usability evaluation;
11. add FastAPI and Docker;
12. add structured logging, health checks and deployment testing.

A local generative model could later be tested as a controlled rewriting component. Safety rules, evidence selection and final validation should remain deterministic.

---

## Final Summary

Hey Joey demonstrates a complete local support-management workflow rather than a simple chatbot demo.

It combines:

- deterministic extraction;
- safety-aware decision logic;
- multi-turn state management;
- privacy-safe context selection;
- local semantic retrieval;
- local BM25 retrieval;
- Reciprocal Rank Fusion;
- source-backed responses;
- modest history-aware personalisation;
- confirmation-before-save;
- a polished Streamlit chat interface.

The project shows how an AI-assisted component can be integrated into a broader, explainable and verifiable system without relying on a paid API.
