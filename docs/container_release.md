# Versioned container releases

Stage 7D publishes an immutable, versioned Hey Joey production image to
GitHub Container Registry (GHCR). It does not deploy the application.

## Safety boundary

Publish only synthetic demonstration content. Never include identifiable
family records, parent notes, private SQLite databases, real `.env` files,
credentials, or private strategy documents in a public image.

The production safeguards from Stage 7C remain mandatory. Review
`.dockerignore`, `.gitignore`, and the repository-safety test before every
release.

## Release prerequisites

Before creating a version tag:

1. Commit and push all intended source changes.
2. Confirm `Joey CI` is green.
3. Confirm `Joey Docker CI` is green.
4. Run `python -m evaluation.run_ci_suite` locally and confirm `Status: PASS`.
5. Confirm the working tree is clean with `git status --short`.

## Publish the first release

Create an annotated semantic-version tag:

```powershell
git tag -a v0.1.0 -m "Hey Joey v0.1.0"
```

Push only that tag:

```powershell
git push origin v0.1.0
```

GitHub Actions then runs `Joey Container Release`. The workflow checks out
the tagged commit, validates the Docker Compose configuration, builds the
production Dockerfile, and publishes these GHCR tags:

- `0.1.0`
- `v0.1.0`
- `sha-<12-character-commit>`
- `latest`

The image also contains OCI source, revision, and version labels, plus
BuildKit provenance and an SBOM.

## Rebuild an existing release

Use the workflow's `Run workflow` control and enter an existing tag such as
`v0.1.0`. The checkout step fails if the tag does not exist, preventing a
branch from being published under an invented release number.

## Package visibility

A newly published GitHub Container Registry package may be private. Keep it
private until you have inspected the image and confirmed it contains only
synthetic demonstration material.

For a recruiter-facing demonstration, change the package visibility to
public only after that review. Public visibility applies to the container
package, not automatically to the repository.

## Pull the image

Replace both placeholders with lowercase values:

```powershell
docker pull ghcr.io/<github-username>/<repository-name>:0.1.0
```

A private package requires authentication with an account or token that has
permission to read the package.

## Remove an incorrect local tag

Deleting a local Git tag does not remove a published GHCR image:

```powershell
git tag -d v0.1.0
```

Deleting a remote tag also does not automatically delete the package
version:

```powershell
git push origin --delete v0.1.0
```

Package versions must be reviewed and removed separately in GitHub package
settings.
