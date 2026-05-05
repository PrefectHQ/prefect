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

**Flow timeout tests**: `pytest-timeout` defaults to SIGALRM on Unix, which interferes with Prefect's own SIGALRM-based flow timeout mechanism. Any test that exercises flow timeouts must opt into thread-based timeouts:
```python
@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
async def test_flows_fail_with_timeout(self): ...
```

When combining `timeout_seconds` flows with concurrency, use a generous timeout (≥ 2s): the heartbeat-thread setup runs inside the flow's timeout scope and can exhaust a tight timeout before the flow body starts, causing pre-`yield` cancellation on contended CI runners.

Use `retry_asserts` from `prefect._internal.testing` to handle timing-sensitive assertions. Two patterns:

- **Retrying assertions for async event propagation** (most common): wrap the assertion inside `with attempt:` so it retries until the event arrives.
  ```python
  async for attempt in retry_asserts(max_attempts=5, delay=0.5):
      with attempt:
          callback.assert_called_once_with(flow_run_id)
  ```
- **Retrying HTTP requests** (`hosted_api_client` tests): SQLite "database is locked" 503 errors can occur due to concurrent access. Retry the HTTP request inside the loop; keep the result assertions *outside* so a wrong result is never masked.

## Related

- `src/prefect/testing/` → Test utilities shipped with the SDK
- `integration-tests/` → End-to-end tests requiring a running server
- `ui-v2/e2e/` → Playwright UI tests (see ui-v2/e2e/AGENTS.md)
