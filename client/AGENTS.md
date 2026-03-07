# prefect-client Package Build

Build configuration for `prefect-client`, a lightweight subset of `prefect` published as a separate PyPI package. This directory does **not** contain source code — it selects files from `src/prefect/` and repackages them.

## Key Contracts

- **Dependency changes in root `pyproject.toml` that affect client-side code must be mirrored in `client/pyproject.toml`.** This is the most common source of build failures.
- **New imports in `src/prefect/` can break this build** if they pull in server-only dependencies. The build strips server code, so any import that reaches `server/database`, `server/models`, etc. from client-side code will fail.
- **The build is tested automatically on every PR** via `.github/workflows/prefect-client.yaml`.

## How It Works

`build_client.sh` copies `src/prefect/` into a temp directory, **deletes** server-only and CLI code, then builds with `client/pyproject.toml`. The resulting package has the same version as `prefect` but fewer dependencies.

### What gets removed

- `cli/` — entire CLI
- `server/` — database, models, orchestration, schemas, services, utilities (keeps only `server/api/`)
- `deployments/recipes/` and `deployments/templates/`
- `testing/`

## Build Triggers

- **PR created** — CI builds and smoke-tests
- **GitHub release published** — CI builds and publishes to PyPI (same version as `prefect`)
- **Manual** — `bash client/build_client.sh`

If the CI build fails, reproduce locally with `bash client/build_client.sh` and run the smoke tests (`client_flow.py`, `client_deploy.py`).

## Related

- `src/prefect/client/` → Actual client SDK source code
- Root `pyproject.toml` → Must stay in sync with `client/pyproject.toml` for shared dependencies
