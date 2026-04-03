# Test Suite

Tests for all Prefect components. Directory structure mirrors `src/prefect/`.

## Key Contracts

- **Server and client test fixtures should not mix.** Server-side tests use a stripped-down client. Do not use `prefect_client` (the full client fixture) in server tests.
- **Prefer real operations over mocks.** Use real flows, deployments, and flow runs where possible. Reserve `unittest.mock` for external services and time-sensitive operations.
- **Tests must be deterministic.** No reliance on timing, ordering, or external state.
- **Both SQLite and PostgreSQL are tested in CI.** Database-related tests run against both.

## Essential Commands

```bash
uv run pytest tests/                          # Run all tests
uv run pytest tests/path.py -k test_name      # Run specific test
uv run pytest tests/module/ -n4               # Run in parallel
uv run pytest tests/path.py -x                # Stop on first failure
uv run pytest tests/path.py -x --tb=short     # Compact tracebacks
```

## Important Fixtures

Shared fixtures live in `fixtures/` (see fixtures/AGENTS.md) and root `conftest.py`. The key distinction:

- **Client-side tests** use `prefect_client` (full SDK client). Do not use in server tests.
- **Server API tests** use `client` / `test_client` (raw httpx/FastAPI against an ephemeral server)
- **Server model/orchestration tests** use `session` (async SQLAlchemy) and pre-built ORM fixtures (`flow`, `flow_run`, `task_run`, `deployment`, etc.)
- `test-projects/` — Sample projects used by CLI/deploy tests

## Testing Guidelines

### Type Hints
- Full type hints on all test functions and fixtures (Python >=3.12 style: `dict[str, str]`)
- Return type hints on fixtures, omit `-> None` on test functions

### Mocking Strategy
- Use `unittest.mock` only when necessary (external services, time-sensitive operations)
- Use `respx` for HTTP response mocking

### Flaky Tests
We have a workflow that identifies and fixes tests that flake after merging to main. Check CI test output to see which tests are currently slow or flaky.

For tests using `hosted_api_client` (which spins up a real subprocess server), SQLite "database is locked" 503 errors can occur due to concurrent access between the test session and the server subprocess. Use `retry_asserts` from `prefect._internal.testing` to retry the HTTP request portion only — keep the result assertions outside the retry loop so a wrong result is never masked.

## Related

- `src/prefect/testing/` → Test utilities shipped with the SDK
- `integration-tests/` → End-to-end tests requiring a running server
- `ui-v2/e2e/` → Playwright UI tests (see ui-v2/e2e/AGENTS.md)
