# Testing Patterns

**Analysis Date:** 2026-02-03

## Test Framework

**Runner:**
- pytest 8.3.4+
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`

**Assertion Library:**
- pytest's built-in assertions
- pytest-asyncio for async test support (< 1.1)

**Run Commands:**
```bash
pytest tests/                          # Run all tests
pytest tests/blocks/test_abstract.py   # Run specific test file
pytest -k "test_credentials"           # Run tests matching pattern
pytest --asyncio-mode=auto             # Auto-detect async fixtures
pytest -n auto                         # Run tests in parallel (pytest-xdist)
pytest --cov=prefect                   # Generate coverage report
pytest -x                              # Stop on first failure
pytest --timeout=90                    # Enforce 90-second timeout per test
```

**Coverage:**
```bash
pytest --cov=prefect --cov-report=html  # Generate HTML coverage report
```

## Test File Organization

**Location:**
- Co-located structure: `tests/` mirrors `src/prefect/` structure
- Example: `src/prefect/blocks/abstract.py` → `tests/blocks/test_abstract.py`
- Example: `src/prefect/flows.py` → `tests/test_flows.py`

**Naming:**
- Test files: `test_*.py` prefix (e.g., `test_abstract.py`, `test_flows.py`)
- Benchmark files: `bench_*.py` prefix
- Test functions: `test_*` prefix (e.g., `test_credentials_block_is_abstract`)
- Test classes: `Test*` prefix (e.g., `TestCredentialsBlock`, `TestNotificationBlock`)

**Structure:**
```
tests/
├── blocks/
│   ├── test_abstract.py
│   ├── test_core.py
│   └── ...
├── fixtures/
│   ├── api.py
│   ├── client.py
│   ├── database.py
│   └── ...
├── conftest.py              # Root-level pytest configuration
└── test_flows.py
```

## Test Structure

**Suite Organization:**
```python
class TestCredentialsBlock:
    """Test class grouping related tests"""

    def test_credentials_block_is_abstract(self):
        """Single responsibility per test"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            CredentialsBlock()

    def test_credentials_block_implementation(self, caplog):
        """Test with fixture - caplog captures logs"""
        class ACredentialsBlock(CredentialsBlock):
            def get_client(self):
                self.logger.info("Got client.")
                return "client"

        a_credentials_block = ACredentialsBlock()
        assert a_credentials_block.get_client() == "client"
        assert len(caplog.records) == 1
```

**Patterns:**
- **Setup/Teardown:** Use pytest fixtures instead of setUp/tearDown
- **Async tests:** Mark with `async def test_*` - asyncio_mode="auto" handles scope
- **Fixtures:** Defined at module level with `@pytest.fixture` decorator
- **Scope control:** `@pytest.fixture(scope="session")` for expensive setup

**Global pytest Configuration** (`pyproject.toml`):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-rfEs"
python_files = ["test_*.py", "bench_*.py"]
python_functions = ["test_*", "bench_*"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
timeout = 90
```

## Mocking

**Framework:** unittest.mock (Python standard library)

**Patterns:**
```python
from unittest.mock import AsyncMock, patch, Mock

# Async mocking
async def test_with_async_mock():
    async_mock = AsyncMock(return_value="result")
    result = await async_mock()
    assert result == "result"

# Context manager patching
def test_with_patch():
    with patch('module.function') as mock_func:
        mock_func.return_value = "mocked"
        # test code
        mock_func.assert_called_once()

# Patch decorator
@patch('module.function')
def test_with_decorator(mock_func):
    mock_func.return_value = "mocked"
    # test code
```

**What to Mock:**
- External API calls and services
- Database calls (use fixtures instead when possible)
- File I/O operations for unit tests
- Time-dependent code (with special time fixtures)

**What NOT to Mock:**
- Internal business logic (test the real implementation)
- Pydantic models and validation
- Block implementations (create real test subclasses)
- Logging calls (use caplog fixture to assert logs)

## Fixtures and Factories

**Test Data:**
```python
# From tests/fixtures/client.py
@pytest.fixture(scope="session")
def flow_function():
    @flow(version="test", description="A test function")
    def client_test_flow(param: int = 1) -> int:
        return param
    return client_test_flow

# From tests/fixtures/client.py - Block fixture
@pytest.fixture(scope="session")
def test_block():
    class x(Block):
        _block_type_slug = "x-fixture"
        foo: str
    return x
```

**Location:**
- Fixtures: `tests/fixtures/` directory with topical files
- `tests/fixtures/client.py` - Client-related fixtures (prefect_client, sync_prefect_client)
- `tests/fixtures/database.py` - Database and session fixtures (db, session, clear_db)
- `tests/fixtures/api.py` - API server fixtures
- `tests/conftest.py` - Root-level fixtures and pytest configuration

**Key Fixtures:**
- `prefect_client` - Async PrefectClient with test database
- `sync_prefect_client` - Synchronous client variant
- `session` - SQLAlchemy AsyncSession for database tests
- `clear_db` - Auto-clears database before each marked test
- `caplog` - Captures log records for assertion
- `tmp_path` - Temporary directory for file operations
- `database_engine` - Test database engine (session-scoped)

## Coverage

**Requirements:** Not explicitly enforced (no minimum threshold)

**View Coverage:**
```bash
pytest --cov=prefect --cov-report=html
# Opens htmlcov/index.html in browser

pytest --cov=prefect --cov-report=term-missing
# Shows missing lines in terminal
```

**Coverage Configuration** (`pyproject.toml`):
```toml
[tool.coverage.run]
branch = true

[tool.coverage.report]
exclude_lines = ["@(abc.)?abstractmethod", "if TYPE_CHECKING:"]
omit = ["src/prefect/server/database/migrations/versions/*"]
ignore_errors = true
```

## Test Types

**Unit Tests:**
- Scope: Test individual functions/methods in isolation
- Approach: Fast, comprehensive coverage, heavy use of mocks
- Location: Same directory structure as source code
- Example: `tests/blocks/test_abstract.py` - Tests abstract block classes

**Integration Tests:**
- Scope: Test interactions between components
- Approach: Use real fixtures (database, clients), minimal mocks
- Location: `integration-tests/` directory
- Example: Database operations, API client interactions

**E2E Tests:**
- Framework: Not systematically used in main test suite
- Alternative: Integration tests cover end-to-end scenarios

## Common Patterns

**Async Testing:**
```python
# Auto-detected as async, runs in session event loop
async def test_database_block_implementation(self, caplog):
    class ADatabaseBlock(DatabaseBlock):
        async def fetch_one(self, operation, parameters=None, **kwargs):
            return ("result",)

    block = ADatabaseBlock()
    result = await block.fetch_one("SELECT *")
    assert result == ("result",)
```

**Error Testing:**
```python
# Exception matching
def test_job_run_error(self):
    class AJobRun(JobRun):
        def fetch_result(self):
            if self.status != "completed":
                raise JobRunIsRunning("Job run is still running.")
            return "results"

    job_run = AJobRun()
    with pytest.raises(JobRunIsRunning, match="Job run is still running."):
        job_run.fetch_result()
```

**Fixture Usage:**
```python
def test_block_with_fixtures(self, caplog, tmp_path):
    # caplog - capture log records
    # tmp_path - temporary directory

    block = MyBlock()
    block.logger.info("Operation complete")

    assert len(caplog.records) == 1
    assert caplog.records[0].msg == "Operation complete"
```

**Abstract Class Testing:**
```python
def test_abstract_class_cannot_instantiate(self):
    # Verify abstract class cannot be directly instantiated
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        CredentialsBlock()

def test_concrete_implementation_works(self):
    # Create concrete subclass and test
    class ConcreteBlock(CredentialsBlock):
        def get_client(self):
            return "client"

    block = ConcreteBlock()
    assert block.get_client() == "client"
```

## Markers and Special Cases

**Pytest Markers:**
```python
@pytest.mark.service(arg="docker")  # Service integration test
@pytest.mark.clear_db              # Clears database after test
@pytest.mark.windows               # Windows-specific test
@pytest.mark.unix                  # Unix-specific test
@pytest.mark.enable_api_log_handler # Enable log handler to API
```

**Auto-marked for clear_db:**
- Tests not in `EXCLUDE_FROM_CLEAR_DB_AUTO_MARK` list in `tests/conftest.py`
- Database cleared before each marked test to ensure isolation
- List includes: `tests/utilities/`, `tests/test_flows.py`, `tests/logging/`, etc.

**Test Environment Variables:**
```
PREFECT_TESTING_TEST_MODE=1
PREFECT_TESTING_UNIT_TEST_MODE=1
PREFECT_SERVER_LOGGING_LEVEL=DEBUG
```

## Warning Filters

**Configured Filters** (in `pyproject.toml`):
```toml
filterwarnings = [
    "error",  # Treat warnings as errors by default
    "ignore::DeprecationWarning:tornado.*",
    "ignore::ResourceWarning",
    "ignore::pytest.PytestUnraisableExceptionWarning",
]
```

## Testing Best Practices

**In codebase:**
1. **One assertion per test** when possible (clear failure messages)
2. **Descriptive test names** that explain the scenario
3. **Use fixtures** for common setup rather than duplicating in multiple tests
4. **Test behavior, not implementation** (avoid testing private methods)
5. **Group related tests in classes** for organization
6. **Keep tests fast** - mock I/O, use session-scoped fixtures for expensive setups
7. **Avoid test interdependence** - each test should be independent

**Example Test Structure:**
```python
class TestMyFeature:
    """Group of related tests"""

    def test_basic_functionality(self):
        """Test the happy path"""
        # Arrange
        obj = MyClass()
        # Act
        result = obj.do_something()
        # Assert
        assert result == expected

    def test_error_condition(self):
        """Test error handling"""
        obj = MyClass()
        with pytest.raises(ValueError, match="error message"):
            obj.do_something_invalid()

    async def test_async_operation(self):
        """Test async code"""
        obj = MyClass()
        result = await obj.async_do_something()
        assert result == expected
```

---

*Testing analysis: 2026-02-03*
