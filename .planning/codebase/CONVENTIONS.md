# Coding Conventions

**Analysis Date:** 2026-02-03

## Naming Patterns

**Files:**
- Python: `snake_case` (e.g., `src/prefect/flows.py`, `src/prefect/blocks/abstract.py`, `tests/blocks/test_abstract.py`)
- TypeScript/Vue: `camelCase` or `PascalCase` (e.g., `ui/src/maps/featureFlag.ts`, `ui/src/App.vue`)
- Test files: `test_*.py` prefix for Python, following module being tested (e.g., `test_flows.py`, `test_abstract.py`)

**Functions and Methods:**
- Python: `snake_case` (e.g., `get_client()`, `fetch_result()`, `wait_for_completion()`)
- TypeScript/Vue: `camelCase` for functions (e.g., `mapFlagResponseToFeatureFlag()`)
- Abstract methods: annotated with `@abstractmethod` decorator
- Async functions: prefixed with `async def` (e.g., `async def test_database_block_implementation()`)

**Variables:**
- Python: `snake_case` (e.g., `test_database_connection_url`, `retry_delay_seconds`)
- TypeScript/Vue: `camelCase` (e.g., `source`, `exhaustiveCheck`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `PREFECT_TESTING_UNIT_TEST_MODE`, `PREFECT_TESTING_TEST_MODE`)
- Type variables: `PascalCase` single letters (e.g., `T = TypeVar("T")`, `R = TypeVar("R")`, `P = ParamSpec("P")`)

**Types:**
- Classes: `PascalCase` (e.g., `CredentialsBlock`, `NotificationBlock`, `DatabaseBlock`)
- Exceptions: `PascalCase` ending with `Error` or `Exception` (e.g., `NotificationError`, `PrefectException`, `CrashedRun`)
- Type aliases: `PascalCase` or snake_case with TypeAlias annotation (e.g., `LoggerOrAdapter: TypeAlias = Union[Logger, LoggingAdapter]`)

## Code Style

**Formatting:**
- Python: Ruff 0.14.14 for linting
- TypeScript/Vue: ESLint via `@prefecthq/eslint-config` (v1.0.32)
- Vue components: Single-file components with `<template>`, `<script>`, and optional `<style>` blocks

**Linting:**
- Python: Ruff enables isort integration with `extend-select = ["I"]` in `tool.ruff.lint`
- Python: Mypy (1.15.0) for type checking with `ignore_missing_imports = true`
- TypeScript: ESLint with type validation via `vue-tsc` for Vue components
- Python: Codespell (2.4.1) for spell-checking

**Per-file Lint Exceptions:**
- `__init__.py` files: Ignore E402 (module level import not at top), F401 (unused imports), I (import sorting)
- `main.py` files: Same as `__init__.py`
- `src/prefect/utilities/compat.py`: Ignore F401 and I (imports compatibility module)
- `tests/conftest.py`: Ignore F405, E402, F403 (wildcard imports)
- `src/prefect/runtime/*`: Ignore F822 (undefined names in type checking)
- `src/prefect/server/database/migrations/**/*`: Ignore E501 (long lines)

## Import Organization

**Order:**
1. `from __future__ import annotations` (at top of file if needed)
2. Standard library imports (e.g., `import logging`, `from typing import Any`)
3. Third-party imports (e.g., `import pydantic`, `from pydantic import BaseModel`)
4. Internal prefect imports (e.g., `from prefect.blocks.core import Block`)
5. Relative imports from same module

**Path Aliases:**
- None explicitly configured. Use absolute imports from `prefect` or `src/prefect` root

**Import Grouping:**
- Imports separated by blank lines between groups
- `TYPE_CHECKING` guard used for imports only needed during type checking (e.g., `if TYPE_CHECKING: from prefect.workers.base import BaseWorker`)
- Type imports grouped with `from typing import` or `from typing_extensions import`

**Example from `src/prefect/flows.py`:**
```python
from __future__ import annotations

import asyncio
import datetime
# ... more stdlib

import pydantic
from exceptiongroup import BaseExceptionGroup
# ... more third-party

from prefect._experimental.sla.objects import SlaTypes
from prefect._internal.concurrency.api import create_call
# ... more internal

if TYPE_CHECKING:
    from prefect.docker.docker_image import DockerImage
```

## Error Handling

**Patterns:**
- Custom exceptions inherit from `PrefectException` base class: `class CustomError(PrefectException):`
- Raise with descriptive messages using f-strings: `raise ValueError(f"Expected {type}, got {actual}")`
- Use specific exception types: `FileNotFoundError`, `TypeError`, `ValueError` as appropriate
- Context managers for resource cleanup: Use `try/except` with `contextmanager` decorator
- Exception handling in tests: `with pytest.raises(ExceptionType, match="pattern"):`

**Examples:**
```python
# From src/prefect/blocks/abstract.py
class NotificationError(Exception):
    """Raised if a notification block fails to send a notification."""
    def __init__(self, log: str) -> None:
        self.log = log

# From src/prefect/flows.py
try:
    # operation
except FileNotFoundError:
    raise ValueError("File not found")
except (FileNotFoundError, TypeError, OSError):
    # handle multiple exception types
    pass

# In tests
with pytest.raises(JobRunIsRunning, match="Job run is still running."):
    a_job_run.fetch_result()
```

## Logging

**Framework:** Python's built-in `logging` module

**Getting loggers:**
- At module level: `logger = get_logger("module.name")`
- At class level via property:
  ```python
  @property
  def logger(self) -> LoggerOrAdapter:
      try:
          return get_run_logger()
      except MissingContextError:
          return get_logger(self.__class__.__name__)
  ```

**Log levels and patterns:**
- `logger.debug()` - Verbose diagnostic info
- `logger.info()` - General informational messages
- `logger.warning()` - Warning conditions
- `logger.error()` - Error conditions
- Use f-strings for message formatting: `logger.info(f"Got client: {client}")`
- Avoid logging mutable objects; log specific values instead

**Examples from `src/prefect/flows.py`:**
```python
logger.error("Error message here")
logger.debug(f"Downloading flow code from storage at {from_path!r}")
logger.info(f"Received {type(exc).__name__}, shutting down...")
run_logger.warning(f"Some condition occurred")
```

## Comments

**When to Comment:**
- Explain WHY not WHAT (code should be self-documenting)
- Complex algorithms or non-obvious logic
- Important notes about maintenance or gotchas
- Disabled code with rationale (rare, prefer removal)

**JSDoc/TSDoc/Docstrings:**
- Python: Use triple-quoted docstrings for modules, classes, and functions
- Format: Description, then optional Args/Returns/Raises sections
- Classes: Describe purpose, usage, and composition
- Methods/functions: Brief description, optional detailed explanation, Args/Returns section
- Type hints required in signatures (especially for public API)

**Docstring Examples:**
```python
class CredentialsBlock(Block, ABC):
    """
    Stores credentials for an external system and exposes a client for interacting
    with that system. Can also hold config that is tightly coupled to credentials
    (domain, endpoint, account ID, etc.) Will often be composed with other blocks.
    Parent block should rely on the client provided by a credentials block for
    interacting with the corresponding external system.
    """

def logger(self) -> LoggerOrAdapter:
    """
    Returns a logger based on whether the CredentialsBlock
    is called from within a flow or task run context.
    If a run context is present, the logger property returns a run logger.
    Else, it returns a default logger labeled with the class's name.

    Returns:
        The run logger or a default logger with the class's name.
    """

def get_client(self, *args: Any, **kwargs: Any) -> Any:
    """
    Returns a client for interacting with the external system.

    If a service offers various clients, this method can accept
    a `client_type` keyword argument to get the desired client
    within the service.
    """
```

## Function Design

**Size:**
- Prefer functions < 50 lines
- Extract complex logic into helper functions
- One responsibility per function

**Parameters:**
- Use type hints for all parameters (especially public APIs)
- Use positional-only parameters where appropriate (e.g., `def func(arg1, /, arg2, *, kwarg1)`)
- Optional parameters have `None` defaults with `Optional[Type]` annotation
- Use `*args: Any, **kwargs: Any` for flexible APIs like `get_client(*args, **kwargs)`

**Return Values:**
- Always annotate return type (even `None`)
- Use Union types for multiple possible returns: `Optional[Type]` or `Type | None`
- Use tuple unpacking for multiple values: `Tuple[Type1, Type2]`

**Examples:**
```python
def get_client(self, *args: Any, **kwargs: Any) -> Any:
    # flexible parameters

async def notify(self, body: str, subject: str | None = None) -> None:
    # optional parameter with None default

def fetch_result(self) -> str | None:
    # union return type

def logger(self) -> LoggerOrAdapter:
    # property return type
```

## Module Design

**Exports:**
- Use `__all__` in public modules to define public API: `__all__ = ["ClassName", "function_name"]`
- Keep public API minimal and explicit
- Prefix internal names with `_`: `_internal_helper()`

**Barrel Files:**
- `__init__.py` files import and re-export commonly used items
- Respect `__all__` definitions from sub-modules
- Ignore import ordering for re-exports (F401 flag disabled in `__init__.py`)

**Module Structure:**
- Constants and type definitions at top
- Utility functions before main classes
- Classes in logical order (base classes before subclasses)
- Entry points and main decorators at end

---

*Convention analysis: 2026-02-03*
