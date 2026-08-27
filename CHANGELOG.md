# Changelog

All notable changes to Hey Joey are documented in this file.

The project follows semantic versioning for tagged releases.

## [Unreleased]

### Added

- MSc thesis-oriented repository documentation identifying the code used for
  structured extraction, retrieval comparison, and confidence evaluation.

### Changed

- Updated project documentation to reflect the final hybrid retrieval,
  confidence, safety, and production-style architecture.
- Updated the README with the final thesis evaluation results.
- Strengthened repository and Docker build-context exclusions for SQLite
  runtime files and certificate material.

### Planned

- Recruiter-facing screenshots and demonstration evidence.
- Formal retrieval and workflow evaluation write-up.
- MSc report, presentation, and viva material.
- Authentication, authorisation, encryption, monitoring, and backup controls
  before any real-world deployment involving private data.

## [0.1.0] - 2026-07-31

### Added

- Local-first parent-note capture and structured journal-record workflow.
- Deterministic extraction, follow-up questions, review, confirmation, and
  persistence.
- SQLite storage for records, conversations, strategy searches, and feedback.
- Hybrid BM25 and local semantic strategy retrieval.
- Retrieval confidence handling and abstention for weak evidence.
- Source-backed strategy results with retrieved evidence.
- History-aware strategy ranking using stored feedback.
- Persistent multi-turn conversations.
- Safety-priority response handling and project limitations documentation.
- Streamlit user interface.
- FastAPI backend with health, readiness, version, record, strategy, feedback,
  and conversation routes.
- Dockerfile and Docker Compose configuration for API and frontend services.
- Production configuration profiles, JSON logging, credential redaction,
  resource limits, log rotation, reduced container privileges, and production
  data-volume controls.
- Repository checks for secrets, private runtime files, databases, keys, and
  unsafe Docker build-context content.
- Python regression workflow in GitHub Actions.
- Docker build-validation workflow in GitHub Actions.
- Versioned GitHub Container Registry release workflow.
- Versioned `v0.1.0` container release with version, commit, and `latest` tags.
  `latest` tags.
- Automated regression suite covering 21 test modules.

### Changed

- Refactored the prototype into a separated Streamlit frontend and FastAPI
  backend.
- Replaced earlier temporary storage assumptions with persistent SQLite
  storage.
- Centralised runtime configuration through environment-based settings.
- Updated the README to describe the completed `v0.1.0` system.

### Security and privacy

- Production-style and public demonstration configurations default to
  synthetic-data-only operation.
- Real `.env` files, SQLite databases, private runtime directories, keys, and
  credentials are excluded from version control and Docker build contexts.
- Production use with identifiable family or child data remains out of scope
  until additional security, privacy, governance, and operational controls are
  implemented.
