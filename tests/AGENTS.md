# Test Suite

Comprehensive testing for all Prefect components.

## Test Structure

- Core SDK tests in root directory
- `server/` - Server API and orchestration tests
- `client/` - Client functionality tests
- `infrastructure/`, `workers/` - Execution environment tests

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

- Fixtures in `conftest.py` for shared setup
- Tests must be deterministic
- Performance regression tests for critical paths
- Temporary databases for isolation