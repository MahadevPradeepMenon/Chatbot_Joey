# Security Policy

## Project status

Hey Joey is an MSc and portfolio prototype. It is not currently approved for
clinical, diagnostic, emergency, safeguarding, or production use with
identifiable child, family, parent, or carer data.

## Supported versions

| Version | Supported |
| --- | --- |
| `0.1.x` | Yes |
| Earlier untagged prototypes | No |

Security fixes are applied to the latest supported release line only.

## Reporting a vulnerability

Do not publish sensitive vulnerability details, credentials, personal data, or
private records in a public GitHub issue.

Report security concerns privately to the repository owner through an
appropriate private contact channel associated with the project or repository.

Include:

- a clear description of the issue;
- affected files, routes, services, or versions;
- reproduction steps using synthetic data;
- expected and actual behaviour;
- potential impact;
- suggested mitigation, where known.

Do not include real family records, parent notes, child information, API keys,
tokens, passwords, private `.env` files, or database contents.

## Data-handling rules

Public development, screenshots, tests, demonstrations, and container releases
must use synthetic or explicitly authorised data only.

The following must never be committed or included in public build contexts:

- real `.env` files;
- SQLite databases containing runtime records;
- `data/private/` or equivalent private data directories;
- private keys, certificates, passwords, or access tokens;
- identifiable parent, carer, child, or family information;
- confidential strategy documents that are not authorised for publication.

Repository safety tests and ignore rules help reduce accidental exposure, but
they do not replace human review.

## Current security controls

The prototype includes:

- environment-based runtime configuration;
- safe production defaults;
- credential redaction in structured logs;
- production resource and process limits;
- Docker log rotation;
- reduced Linux container privileges;
- health and readiness endpoints;
- secret and private-file repository checks;
- Docker build-context exclusions;
- pinned GitHub Actions dependencies;
- least-privilege GitHub Actions permissions;
- immutable, versioned container releases.

## Known production gaps

Before real-world deployment, the system still requires:

- authentication and role-based authorisation;
- encryption in transit and at rest;
- secure secret management;
- tenant and user isolation;
- backup, restore, and disaster-recovery procedures;
- audit logging and security monitoring;
- retention and deletion controls;
- dependency and container vulnerability management;
- rate limiting and abuse protection;
- formal threat modelling and penetration testing;
- privacy, safeguarding, and data-protection review;
- incident-response procedures.

## Responsible testing

Use only systems and data you own or have explicit permission to test. Avoid
actions that expose data, disrupt services, degrade availability, or affect
other users.
