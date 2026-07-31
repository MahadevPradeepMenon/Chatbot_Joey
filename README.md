# Hey Joey: Privacy-Aware Hybrid RAG Assistant

Hey Joey is a local-first, safety-aware support system that turns parent or carer observations into structured journal records and retrieves source-backed support strategies from an approved local document library.

The project is designed as an **AI-assisted system rather than a generic chatbot**. Deterministic extraction, safety screening, confirmation, persistence and operational controls remain explicit and testable; local semantic retrieval is used as one component inside that wider workflow.

- **Current release:** `v0.1.0`
- **Runtime:** Python 3.12, FastAPI, Streamlit, SQLite and Docker
- **External model API required:** No

> Hey Joey is an MSc/portfolio prototype. It is not a clinical, diagnostic, emergency or safeguarding service.

---

## Why This Project Exists

Parents and carers often record important observations in natural language, but unstructured notes are difficult to reuse for later reflection or support planning. Hey Joey demonstrates a system that can:

- capture a free-text observation;
- build and refine a structured record across several turns;
- require explicit confirmation before saving;
- retrieve relevant strategies from approved local documents;
- show the supporting evidence behind each suggestion;
- remember conversation and strategy-feedback history;
- abstain when the available evidence is too weak;
- run without a paid language-model API.

The result is a verifiable support-management workflow, not a free-form answer generator.

---

## System Overview

```mermaid
flowchart LR
    U[Parent or carer] --> UI[Streamlit chat interface]
    UI --> API[FastAPI backend]

    API --> RW[Record workflow]
    API --> SW[Strategy workflow]
    API --> CW[Conversation service]

    RW --> EX[Deterministic extraction]
    RW --> SG[Safety screening]
    RW --> CF[Review and confirmation]

    SW --> SG
    SW --> CTX[Privacy-safe context builder]
    SW --> HR[Hybrid retrieval]
    HR --> BM25[BM25 lexical search]
    HR --> SEM[Local semantic embeddings]
    HR --> RRF[Reciprocal Rank Fusion]
    RRF --> CONF[Confidence and abstention]
    CONF --> HIST[History-aware ranking]

    CF --> DB[(SQLite)]
    CW --> DB
    HIST --> DB
    HR --> DOCS[(Approved local strategy corpus)]
```

### Core design principle

```text
natural-language input
→ deterministic workflow logic
→ safety screening
→ local retrieval where relevant
→ explicit evidence and confidence
→ user confirmation
→ local persistence
```

The application can still perform its main record-management workflow without a generative model. Local embeddings improve retrieval, but they do not control safety, confirmation or database writes.

---

## Main Workflows

### 1. Record what happened

A parent or carer enters a natural-language observation. Joey then:

1. creates a structured draft;
2. identifies missing information;
3. asks a targeted follow-up question;
4. updates the same draft over multiple turns;
5. presents a final review;
6. saves only after explicit confirmation.

A structured record can include:

- entry type and summary;
- date and time of day;
- anxiety level;
- mood zone and mood labels;
- behaviours and activity;
- environment and possible triggers;
- Quick Track suggestions;
- relevant strategy categories;
- risk flags;
- missing information;
- confidence and confirmation state.

### 2. Ask for a strategy

A parent or carer asks for support relevant to a situation. Joey then:

1. screens the question for safety concerns;
2. builds a privacy-reduced contextual query;
3. searches the approved local strategy library;
4. combines BM25 and semantic rankings;
5. evaluates retrieval confidence;
6. abstains when the evidence is insufficient;
7. applies modest history-aware adjustments;
8. returns source-backed options with cautious wording;
9. stores optional feedback for later ranking decisions.

---

## Key Engineering Capabilities

| Capability | Implementation |
|---|---|
| Structured data capture | Deterministic extraction and multi-turn draft refinement |
| Safety | Rule-based screening takes priority over ordinary retrieval |
| Retrieval | Local BM25 plus local semantic embeddings |
| Fusion | Reciprocal Rank Fusion rather than raw-score mixing |
| Confidence | Evidence thresholds and explicit abstention behaviour |
| Personalisation | Stored strategy usage and feedback make limited ranking adjustments |
| Persistence | SQLite records, conversations, searches and feedback |
| Backend | Versioned FastAPI routes with OpenAPI documentation in local mode |
| Frontend | Streamlit chat client communicating through HTTP only |
| Containerisation | Separate API and frontend services using one production image |
| Configuration | Validated environment-based local and production settings |
| Observability | Text logs locally and redacted JSON logs in production mode |
| CI/CD | Python regression CI, Docker build CI and versioned GHCR releases |
| Privacy | Synthetic-only production-demo defaults and repository safety checks |

---

## Safety and Privacy Boundary

Hey Joey is designed to:

- avoid diagnosis and treatment claims;
- avoid medication or dosage recommendations;
- avoid advising medication changes;
- avoid claiming a certain cause;
- detect medication mentions without turning them into advice;
- detect direct safety or self-injury concerns;
- stop ordinary strategy retrieval when a safety concern takes priority;
- require confirmation before storing a structured record;
- avoid intentionally logging parent notes, answers or retrieved passages.

Safety screening is deterministic, but it cannot guarantee recognition of every indirect, ambiguous or unusual expression of risk.

### Data policies

The runtime supports two explicit policies:

| Policy | Intended use |
|---|---|
| `local_private` | Private local development on the user’s own machine |
| `synthetic_only` | Portfolio, production-style and recruiter-facing demonstrations |

Production defaults to:

```text
HEY_JOEY_DEMO_MODE=true
HEY_JOEY_DATA_POLICY=synthetic_only
HEY_JOEY_ALLOW_PRIVATE_DATA=false
```

Never place real child or family information, private SQLite databases, credentials or private documents in a public repository, screenshot, container image or hosted demo.

---

## Hybrid Retrieval Pipeline

The strategy pipeline combines:

- BM25 lexical retrieval;
- semantic embedding retrieval;
- Reciprocal Rank Fusion;
- strategy-level deduplication;
- privacy-safe contextual query construction;
- retrieval-confidence assessment;
- history-aware ranking adjustments.

### Semantic model

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model runs locally and produces normalised 384-dimensional `float32` embeddings. No paid API key is required.

### Why keep hybrid retrieval?

A semantic retriever can recognise conceptually similar wording, while BM25 preserves direct lexical evidence. Reciprocal Rank Fusion combines their rankings without pretending that cosine-similarity and BM25 scores share the same numerical scale.

### History-aware ranking

Stored feedback can make small, auditable adjustments when base retrieval results are close. For example:

- an active strategy can receive a modest positive adjustment;
- positive feedback can break a close tie;
- negative feedback can reduce a strategy’s score;
- an unseen strategy can be labelled as new.

Feedback never replaces the source-relevance score and is deliberately prevented from overwhelming retrieval evidence.

---

## Local Strategy Corpus

The prototype corpus snapshot contains:

- 10 approved Hey Joey strategy documents;
- 359 processed chunks;
- 257 strategy chunks;
- 102 context chunks.

Raw documents, processed text, generated chunks and embedding indexes are intentionally excluded from Git and from the container image. They are mounted or generated locally.

Place approved documents in:

```text
data/raw/strategies/
```

Then build the local embedding index:

```powershell
python -m rag.build_embedding_index
```

The record workflow does not depend on this corpus. Strategy search requires the approved corpus and generated local indexes.

---

## Persistence

SQLite is the project’s storage boundary. It persists:

- confirmed structured records;
- conversation sessions and messages;
- resumable workflow drafts;
- strategy searches and ranked results;
- strategy feedback and usage history.

Default local database path:

```text
data/local/joey.db
```

The database and private runtime folders are excluded from version control.

---

## API

The FastAPI backend exposes versioned workflow routes.

### System routes

```text
GET /health
GET /ready
GET /version
```

### Conversation routes

```text
POST /api/v1/conversations/sessions
GET  /api/v1/conversations/sessions/latest
GET  /api/v1/conversations/sessions/{session_id}
POST /api/v1/conversations/sessions/{session_id}/exchanges
```

### Record routes

```text
POST /api/v1/record/sessions
GET  /api/v1/record/sessions/{session_id}
POST /api/v1/record/sessions/{session_id}/messages
POST /api/v1/record/sessions/{session_id}/confirm
POST /api/v1/record/sessions/{session_id}/reject
```

### Strategy routes

```text
POST /api/v1/strategies/search
GET  /api/v1/strategies/searches/{search_id}
POST /api/v1/strategies/feedback
```

Interactive API documentation is available locally at:

```text
http://127.0.0.1:8000/docs
```

API documentation is disabled by default in production mode.

---

## Repository Structure

```text
Chatbot_Joey/
├── .github/workflows/
│   ├── ci.yml
│   ├── docker-ci.yml
│   └── release.yml
├── api/
│   ├── main.py
│   ├── models.py
│   └── routers/
├── app/
│   ├── settings.py
│   ├── logging_config.py
│   ├── api_client.py
│   ├── extractor.py
│   ├── conversation_manager.py
│   ├── conversation_persistence.py
│   ├── record_workflow_service.py
│   ├── strategy_workflow_service.py
│   ├── context_builder.py
│   └── streamlit_app.py
├── rag/
│   ├── bm25_retriever.py
│   ├── semantic_retriever.py
│   ├── hybrid_retriever.py
│   ├── retrieval_confidence.py
│   ├── strategy_history_ranker.py
│   └── history_aware_strategy_service.py
├── safety/
│   └── safety_guard.py
├── storage/
│   ├── database.py
│   ├── conversation_storage.py
│   ├── strategy_feedback.py
│   └── feedback_history_provider.py
├── evaluation/
│   ├── run_ci_suite.py
│   └── test_*.py
├── scripts/
│   └── apply_repository_safety.py
├── docs/
│   ├── production_configuration.md
│   └── container_release.md
├── assets/
├── data/
├── Dockerfile
├── compose.yaml
├── compose.production.yaml
├── requirements.txt
└── README.md
```

---

## Quick Start with Docker

Docker is the simplest way to run both services with the same environment used by the automated Docker build.

### 1. Start the application

From the project root:

```powershell
docker compose up --wait
```

The first build can take time because it installs the local embedding stack and preloads the sentence-transformer model.

### 2. Open the interfaces

```text
Streamlit: http://127.0.0.1:8501
FastAPI:   http://127.0.0.1:8000
API docs:  http://127.0.0.1:8000/docs
```

### 3. Stop the application

```powershell
docker compose down
```

Local Compose ports bind to `127.0.0.1` by default, so they are not exposed to other devices on the network.

---

## Local Python Setup

### 1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Start the API

```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

### 4. Start Streamlit in a second PowerShell window

```powershell
$env:HEY_JOEY_API_URL="http://127.0.0.1:8000"
python -m streamlit run app\streamlit_app.py
```

The Streamlit frontend uses the FastAPI HTTP boundary rather than importing backend workflow services directly.

---

## Production-Style Synthetic Demo

Create an untracked production environment file:

```powershell
Copy-Item .env.production.example .env.production
```

Validate the merged configuration:

```powershell
docker compose --env-file .env.production `
  -f compose.yaml `
  -f compose.production.yaml `
  config
```

Start the production-style configuration:

```powershell
docker compose --env-file .env.production `
  -f compose.yaml `
  -f compose.production.yaml `
  up --wait
```

The production override adds:

- CPU, memory and process limits;
- restart policies;
- JSON log rotation;
- Linux capability removal;
- `no-new-privileges`;
- a named persistent data volume;
- synthetic-only demonstration defaults;
- disabled API documentation by default.

See [`docs/production_configuration.md`](docs/production_configuration.md) for the complete configuration model.

---

## Evaluation

### Retrieval comparison

The same 10 synthetic support queries were used to compare the original deterministic baseline, semantic retrieval and hybrid retrieval with `top_k = 3`.

| Retriever | Hit@1 | Hit@3 | MRR | Average latency | Errors |
|---|---:|---:|---:|---:|---:|
| Rule-based baseline | 3/10 | 5/10 | 0.4000 | 0.000938 s | 0 |
| Semantic retrieval | 8/10 | 9/10 | 0.8333 | 0.065338 s | 0 |
| Hybrid retrieval | 7/10 | 9/10 | 0.8000 | 0.064551 s | 0 |

Semantic-only retrieval achieved the strongest rank-one result on this small synthetic set. Hybrid retrieval matched semantic retrieval at rank three and remains the application default because it combines semantic similarity with direct lexical evidence.

These results apply only to the designed 10-case synthetic evaluation. They do not establish universal retrieval quality or clinical effectiveness.

### Current regression suite

Release `v0.1.0` completed the local continuous-integration suite with:

```text
Discovered test modules: 21
Modules passed: 21/21
Status: PASS
```

The suite covers:

- FastAPI health, readiness and OpenAPI behaviour;
- record-session creation, follow-ups, confirmation and rejection;
- strategy search, safety priority, abstention and feedback;
- API-client failures and timeout handling;
- SQLite record, conversation and feedback persistence;
- context construction and multi-turn state;
- history-aware ranking;
- Streamlit-to-API integration;
- Docker and Compose configuration;
- production settings and repository safety;
- CI, Docker CI and release-pipeline configuration.

Run the complete suite with:

```powershell
python -m evaluation.run_ci_suite
```

Run repository privacy checks independently with:

```powershell
python -m evaluation.test_repository_safety
```

---

## Continuous Integration and Releases

The repository contains three GitHub Actions workflows.

### Joey CI

Runs the Python 3.12 compilation and regression suite on pushes and pull requests.

### Joey Docker CI

Validates the Compose configuration and builds the production Docker image for `linux/amd64` without publishing it. BuildKit layers are cached between runs.

### Joey Container Release

A semantic-version tag such as `v0.1.0` publishes a versioned image to GitHub Container Registry with:

```text
0.1.0
v0.1.0
sha-<commit>
latest
```

The release includes OCI source, revision and version labels, BuildKit provenance and an SBOM.

Create a release only from a clean, tested commit:

```powershell
git tag -a v0.1.0 -m "Hey Joey v0.1.0"
git push origin v0.1.0
```

See [`docs/container_release.md`](docs/container_release.md) for the release and package-visibility process.

---

## Production Safeguards Included

The current project includes production-style controls, but these controls do not make it suitable for processing real family data on a public server.

Implemented safeguards include:

- central validated runtime settings;
- safe production-demo defaults;
- explicit private-data decisions;
- loopback-only local port binding;
- non-root Docker execution;
- container CPU, memory and process limits;
- dropped Linux capabilities;
- `no-new-privileges`;
- health-aware service startup;
- bounded and rotated container logs;
- redacted application-owned JSON logs;
- disabled production API documentation;
- secret and private-file repository checks;
- versioned immutable container releases.

A real deployment involving identifiable family or child data would still require authentication, authorisation, transport encryption, encryption at rest, secrets management, backups, retention and deletion controls, audit trails, security testing, monitoring, incident response and formal privacy approval.

---

## Limitations

- Evaluation datasets are small and synthetic.
- Retrieval judgements are not yet based on an independent domain-expert study.
- Deterministic extraction may miss unusual phrasing, negation or indirect context.
- Follow-up questions may not always target the most important missing detail.
- Safety rules cannot recognise every possible risk expression.
- Strategy retrieval depends on a locally supplied approved corpus and generated indexes.
- Source-backed retrieval does not demonstrate clinical effectiveness.
- History-aware ranking has not been validated with real longitudinal users.
- SQLite is appropriate for the prototype but not a multi-user production database.
- The released container currently targets `linux/amd64`.
- No approved usability study with parents, carers or professionals has been completed.
- No live Hey Joey mobile application or production database integration was available.
- The public-demo configuration must remain synthetic-only.

---

## Remaining Work Before Real-World Deployment

The core engineering prototype is complete. Remaining work is primarily validation, governance and product integration:

1. conduct domain-expert retrieval review;
2. expand and independently label the evaluation set;
3. run an approved usability study;
4. add user authentication and role-based access control;
5. add encryption, managed secrets and audited backups;
6. define retention, deletion and data-subject processes;
7. complete privacy-impact and security assessments;
8. integrate with the real Hey Joey profile, journal and insights data contracts;
9. add production monitoring and incident-response procedures;
10. assess a controlled local generative rewriting component without weakening deterministic safety or evidence checks.

---

## Project Status

| Area | Status |
|---|---|
| Structured journal workflow | Complete |
| Multi-turn follow-up and confirmation | Complete |
| Deterministic safety layer | Complete |
| Local semantic and BM25 retrieval | Complete |
| Retrieval confidence and abstention | Complete |
| History-aware strategy feedback | Complete |
| SQLite persistence | Complete |
| Persistent conversation restoration | Complete |
| FastAPI backend | Complete |
| Streamlit API client | Complete |
| Docker and Docker Compose | Complete |
| Production-style configuration | Complete |
| Automated Python and Docker CI | Complete |
| Versioned GHCR release pipeline | Complete |
| Release `v0.1.0` | Complete |
| Real Hey Joey product integration | Not available |
| Public processing of real family data | Out of scope and not approved |

---

## Final Summary

Hey Joey demonstrates how local retrieval and AI-assisted processing can be integrated into a broader, explainable system rather than treated as the whole product.

The project combines deterministic structured extraction, safety-first workflow control, multi-turn conversations, hybrid retrieval, evidence-backed responses, confidence-based abstention, history-aware ranking, persistent storage, a versioned API, a separate web client, containerisation, automated regression testing, production-style safeguards and an immutable release pipeline—all without requiring a paid language-model API.
