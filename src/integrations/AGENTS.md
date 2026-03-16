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
just unreleased-integrations          # List integrations with commits since their last release tag
```

## Related

- `docs/integrations/` → Integration-specific documentation pages
- `docs/integrations/catalog/` → YAML metadata for each integration
