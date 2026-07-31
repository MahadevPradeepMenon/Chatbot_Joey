# Hey Joey production configuration

Stage 7C separates safe local development from production-style operation without adding a cloud dependency.

## Configuration model

`app/settings.py` is the single runtime configuration boundary for the FastAPI backend and Streamlit frontend. It validates environment, data policy, paths, API URL, logging and API-documentation settings.

The supported environments are `local`, `test` and `production`. The supported data policies are:

- `local_private`: local-only private records may be stored in the configured SQLite database.
- `synthetic_only`: only invented demonstration content should be entered.

Production defaults to `synthetic_only`, JSON logs and disabled API documentation. Enabling production private-data mode requires an explicit `HEY_JOEY_ALLOW_PRIVATE_DATA=true` decision and is not appropriate for a public portfolio demo.

## Local run

Copy `.env.example` to `.env` only when defaults need to be changed. Then use the normal command:

```powershell
docker compose up --wait
```

The default ports bind to `127.0.0.1`, so they are available only from the same computer.

## Production-style synthetic demo

Create an untracked runtime file:

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

Start it:

```powershell
docker compose --env-file .env.production `
  -f compose.yaml `
  -f compose.production.yaml `
  up --wait
```

The production override adds CPU, memory and process limits, log rotation, Linux capability removal, `no-new-privileges`, a named persistent data volume and synthetic-demo settings.

## Logging policy

Application-owned production logs are JSON. Joey logs lifecycle events only and does not intentionally log parent notes, answers, retrieved passages or strategy-feedback comments. Credential-like values are redacted if they appear in a Joey-owned log message. Docker also rotates container logs using a maximum size and file count.

## Repository safety

Run the idempotent safety helper once after extracting Stage 7C:

```powershell
python -m scripts.apply_repository_safety
```

Then run:

```powershell
python -m evaluation.test_repository_safety
```

The test rejects tracked environment files, SQLite databases, private keys, private runtime-data folders and several high-confidence credential formats. It also verifies `.gitignore` and `.dockerignore` protections.

## Public-demo boundary

A portfolio demo must use invented records only. Do not deploy the local SQLite database, parent notes, child names, school details, contact details, medical identifiers or any other real family information.
