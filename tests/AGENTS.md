# Prefect Test Suite

This directory contains the comprehensive test suite for Prefect, covering all components from core functionality to integrations.

## Test Structure

- **Core Tests**: `test_*.py` files for flows, tasks, states, engines, etc.
- **Server Tests**: `server/` - API endpoints, database models, orchestration logic
- **Client Tests**: `client/` - Client functionality and API communication  
- **Integration Tests**: Component integration and end-to-end scenarios
- **Infrastructure Tests**: `infrastructure/`, `workers/` - Deployment and execution environments

## Test Categories

- **Unit Tests**: Isolated component testing with mocked dependencies
- **Integration Tests**: Cross-component functionality testing
- **Database Tests**: Persistence layer and migration testing
- **Concurrency Tests**: Async execution and race condition testing
- **CLI Tests**: Command-line interface testing

## Testing Conventions

- Use `pytest` as the test framework
- Async tests for async code paths
- Fixtures in `conftest.py` for shared test setup
- Mock external dependencies (databases, APIs, file systems)
- Test both success and failure scenarios
- Include performance regression tests for critical paths

## Running Tests

- `uv run pytest tests/some_file.py -k some_test_substr` - Run specific tests
- `uv run pytest -n4` - Run all tests in parallel  
- Use temporary databases and isolated environments
- Tests should be deterministic and not depend on external state 