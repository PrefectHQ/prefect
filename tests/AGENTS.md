# Test Suite

Comprehensive testing for all Prefect components.

## Test Structure

Tests mirror the source tree under `src/prefect/`:

- `blocks/` - Block tests
- `cli/` - CLI command tests (includes `deploy/`, `cloud/`, `transfer/`)
- `client/` - Client SDK tests (`api/`, `schemas/`)
- `server/` - Server tests (`api/`, `models/`, `orchestration/`, `services/`, `database/`)
- `engine/` - Engine tests including `reliability/`
- `events/` - Event system tests (`client/`, `server/`)
- `deployment/` - Deployment tests
- `concurrency/` - Concurrency primitive tests (includes `v1/`)
- `runner/` - Runner tests
- `workers/` - Worker tests
- `infrastructure/` - Infrastructure and provisioner tests
- `logging/` - Logging framework tests
- `runtime/` - Runtime context tests
- `results/` - Result persistence tests
- `public/` - Public API contract tests (`flows/`, `tasks/`, `results/`)
- `_experimental/` - Experimental feature tests
- `_internal/` - Internal implementation tests
- `fixtures/` - Shared test fixtures
- `test-projects/` - Sample projects for CLI/deploy tests

## Essential Commands

```bash
uv run pytest tests/                          # Run all tests
uv run pytest tests/path.py -k test_name      # Run specific test
uv run pytest tests/module/ -n4               # Run in parallel
uv run pytest tests/path.py -x                # Stop on first failure
uv run pytest tests/path.py -x --tb=short     # Compact tracebacks
```

## Testing Approach

- **Unit Tests**: Isolated with mocked dependencies
- **Integration Tests**: Cross-component functionality
- **Async Tests**: For async code paths
- **Database Tests**: Real connections required

## Testing Guidelines

### Type Hints
- Full type hints on all test functions and fixtures (Python >=3.12 style: `dict[str, str]`)
- Include `from __future__ import annotations` for Python 3.9 compatibility
- Return type hints on fixtures, omit `-> None` on test functions

### Mocking Strategy
- Prefer real operations (flows, deployments, flow runs) over mocks
- Use `unittest.mock` only when necessary (external services, time-sensitive operations)
- Use `respx` for HTTP response mocking

## Test-Specific Notes

- Fixtures in `conftest.py` for shared setup (root and per-directory)
- Tests must be deterministic
- Performance regression tests for critical paths
- Temporary databases for isolation
