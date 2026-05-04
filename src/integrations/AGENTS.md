# Prefect Integrations

Official integrations extending Prefect with external services and platforms. Each integration is a separate PyPI package with its own version, dependencies, and test suite.

## Key Contracts

- **All integrations are pre-1.0.** Bump the minor version for breaking changes.
- **New integrations require discussion first.** Contributors should open an issue before submitting a PR to add a new integration. In general, users should create a separate repo for their integrations.
- **Released by pushing a tag** in the format `prefect-<name>-<semver>` (e.g., `prefect-dbt-0.7.20`).
- **Integrations use the latest released `prefect` from PyPI by default.** Only use an editable install of core Prefect when you're actively developing an interface in core that the integration will consume directly.
- Use blocks for credentials — never hardcode secrets in flows.

## Integration Layout

Each integration follows a consistent structure:

```
prefect-<name>/
├── prefect_<name>/       # Source code (blocks, tasks, workers)
├── tests/                # Integration-specific tests
├── pyproject.toml        # Package config and dependencies
├── justfile              # Task runner commands
└── README.md
```

## Essential Commands

All commands run from inside an integration directory (e.g., `src/integrations/prefect-aws/`):

```bash
uv run pytest                         # Run all tests for the integration
uv run pytest tests/ -k test_name     # Run specific test
just api-ref                          # Generate API reference docs
```

From the repo root, run scripts that need an integration extra:

```bash
uv run --extra aws repros/1234.py     # Run a script with prefect-aws installed
```

## Release Commands

Run from the repo root:

```bash
just unreleased-integrations                  # List integrations with commits since their last release tag
just prepare-integration-release <pkg>        # Generate release notes for an integration (e.g., prefect-aws)
```

## Integration Settings

Integrations that need runtime-configurable behavior use `PrefectBaseSettings` subclasses in a `settings.py` file at the package root. The `build_settings_config(("integrations", "<name>", ...))` call auto-generates the env var prefix — e.g., `build_settings_config(("integrations", "gcp", "cloud_run_v2", "worker"))` maps to `PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_*`.

Unlike core `prefect.settings`, integration settings are not wired into the root `Settings` hierarchy. Access them by instantiating the class directly: `settings = MyIntegrationSettings()`. Tests override values via `mock.patch.dict("os.environ", {...})`.

## Related

- `docs/integrations/` → Integration-specific documentation pages
