# Codebase Structure

**Analysis Date:** 2026-02-03

## Directory Layout

```
prefect.feat-bundles-include-files/
├── src/prefect/                    # Main Python package
│   ├── flows.py                    # Flow class and @flow decorator
│   ├── tasks.py                    # Task class and @task decorator
│   ├── main.py                     # Public API exports
│   ├── flow_engine.py              # Flow execution logic
│   ├── task_engine.py              # Task execution logic
│   ├── states.py                   # State objects and transitions
│   ├── context.py                  # Runtime context managers
│   ├── results.py                  # Result persistence and retrieval
│   ├── futures.py                  # Future objects for pending results
│   ├── cache_policies.py           # Task result caching policies
│   ├── transactions.py             # Transaction support
│   ├── artifacts.py                # Artifact logging
│   ├── client/                     # HTTP client for API communication
│   ├── server/                     # Backend server implementation
│   ├── cli/                        # Command-line interface
│   ├── blocks/                     # Infrastructure blocks
│   ├── deployments/                # Deployment configuration and runners
│   ├── runner/                     # Flow execution runners
│   ├── infrastructure/             # Infrastructure block types
│   ├── workers/                    # Worker implementations
│   ├── events/                     # Event emission and handling
│   ├── logging/                    # Logging configuration
│   ├── concurrency/                # Concurrency limits and leases
│   ├── assets/                     # Asset tracking
│   ├── filesystems.py              # File system abstractions
│   ├── telemetry/                  # Observability/metrics
│   ├── utilities/                  # Shared utilities
│   ├── _internal/                  # Internal implementation details
│   ├── _experimental/              # Experimental features
│   ├── settings/                   # Configuration and profiles
│   └── types/                      # Type definitions
├── src/integrations/               # Third-party integration packages
│   ├── prefect-aws/
│   ├── prefect-gcp/
│   ├── prefect-kubernetes/
│   └── (other integration packages)
├── client/                         # Standalone Python client package
├── ui/                             # Legacy Vue.js UI
├── ui-v2/                          # Modern React/TypeScript UI
├── tests/                          # Test suite (mirrors src structure)
├── docs/                           # Documentation (mkdocs)
├── scripts/                        # Build and utility scripts
├── integration-tests/              # Integration test suite
├── .github/                        # GitHub Actions workflows
├── pyproject.toml                  # Project metadata and dependencies
└── prefect.yaml                    # Deployment configuration template
```

## Directory Purposes

**`src/prefect/`**
- Purpose: Core Prefect framework including decorators, execution, client, and server
- Contains: All user-facing API and internal orchestration logic
- Key files: `flows.py`, `tasks.py`, `main.py` (user API exports)

**`src/prefect/client/`**
- Purpose: HTTP client for communicating with Prefect server and cloud
- Contains: PrefectClient (async), SyncPrefectClient, API schemas, authentication
- Key files: `base.py` (client base), `orchestration.py` (async client), `cloud.py` (cloud integration)

**`src/prefect/server/`**
- Purpose: REST API server, orchestration logic, database layer
- Contains: FastAPI routes, SQLAlchemy ORM models, orchestration policies
- Key subdirs: `api/` (endpoints), `models/` (ORM), `database/` (migrations, interface), `schemas/` (Pydantic)

**`src/prefect/cli/`**
- Purpose: Command-line interface using Typer
- Contains: All prefect CLI commands (flow, task, deploy, server, etc)
- Key files: `__init__.py` (command router), `deployment.py` (deploy commands), `flow_run.py` (run commands)

**`src/prefect/blocks/`**
- Purpose: Infrastructure and service blocks for external integrations
- Contains: Abstract block definition, core blocks (filesystem, webhook), notification blocks
- Key files: `abstract.py` (Block base class), `core.py` (block types)

**`src/prefect/deployments/`**
- Purpose: Deployment configuration, build/push/pull steps, runner logic
- Contains: Deployment YAML handling, deployment runners, build step orchestration
- Key files: `base.py` (deployment configuration), `runner.py` (run deployments), `steps/` (build steps)

**`src/prefect/infrastructure/`**
- Purpose: Infrastructure block types (Docker, Kubernetes, Process, etc)
- Contains: Block implementations for different execution environments
- Key files: One file per infrastructure type (docker.py, kubernetes.py, process.py)

**`src/prefect/runner/`**
- Purpose: Flow execution runners that actually execute flows
- Contains: ProcessWorker, ThreadWorker, async execution adapters
- Key files: `runner.py` (runner base), `worker.py` (worker implementations)

**`src/prefect/context.py`**
- Purpose: Runtime context (ContextVar-based) for flow/task execution state
- Contains: FlowRunContext, TaskRunContext, SettingsContext, AssetContext classes
- Key pattern: context managers that set/restore context variables

**`src/prefect/utilities/`**
- Purpose: Shared utilities across the codebase
- Contains: Async helpers, filesystem utilities, import/reflection tools, collections utilities
- Key subdirs: `asyncutils.py`, `callables.py`, `collections.py`, `filesystem.py`, `importtools.py`

**`src/prefect/_internal/`**
- Purpose: Internal implementation details not part of public API
- Contains: Concurrency implementation, analytics, compatibility layers, plugin system
- Key subdirs: `concurrency/` (sync/async concurrency), `compatibility/`, `analytics/`

**`src/prefect/settings/`**
- Purpose: Configuration management, profiles, environment variable mapping
- Contains: Settings dataclass, profile loading, environment variable handling
- Key files: `__init__.py` (settings definitions), `context.py` (settings context)

**`src/prefect/logging/`**
- Purpose: Logging configuration and custom loggers
- Contains: Logger setup, run-specific log handlers, formatters
- Key files: `configuration.py` (logging setup), `loggers.py` (custom logger factories)

**`tests/`**
- Purpose: Comprehensive test suite
- Contains: Unit tests, integration tests, fixtures, test utilities
- Key structure: Mirrors `src/prefect/` structure (e.g., `tests/engine/`, `tests/cli/`, `tests/server/`)

**`ui/`**
- Purpose: Legacy Vue.js single-page application
- Contains: Vue components, router, API service layer
- Key subdirs: `src/pages/` (route pages), `src/components/` (Vue components), `src/services/` (API calls)

**`ui-v2/`**
- Purpose: Modern React/TypeScript UI (current/maintained)
- Contains: React components, React Router, TanStack Query integration
- Key subdirs: `src/routes/` (file-based routing), `src/components/`, `src/api/` (API service layer)

**`docs/`**
- Purpose: MkDocs documentation source
- Contains: Markdown files organized by topic
- Key files: `mkdocs.yml` (configuration)

**`client/`**
- Purpose: Standalone Python client package (separate from main package)
- Contains: Lightweight client without server dependencies
- Used by: Headless Prefect server setups

**`src/integrations/`**
- Purpose: Pluggable integration packages for third-party services
- Contains: One directory per integration (aws, gcp, kubernetes, etc)
- Pattern: Each integration has own pyproject.toml and can be installed separately

## Key File Locations

**Entry Points:**
- `src/prefect/__init__.py`: Package initialization, lazy module imports, plugin system setup
- `src/prefect/main.py`: Public API exports (@flow, @task, get_client, etc)
- `src/prefect/__main__.py`: CLI entry point
- `src/prefect/server/api/__init__.py`: Server route registration

**Core User API:**
- `src/prefect/flows.py`: Flow class, @flow decorator
- `src/prefect/tasks.py`: Task class, @task decorator
- `src/prefect/context.py`: Runtime context access (FlowRunContext, TaskRunContext)

**Execution:**
- `src/prefect/flow_engine.py`: Flow execution with state management
- `src/prefect/task_engine.py`: Task execution with caching, retries, concurrency
- `src/prefect/states.py`: State objects and state conversion utilities
- `src/prefect/futures.py`: Future objects returned from flow/task calls

**Persistence:**
- `src/prefect/results.py`: Result storage and retrieval
- `src/prefect/filesystems.py`: Filesystem abstractions (local, S3, GCS, etc)

**Server/API:**
- `src/prefect/server/api/`: FastAPI route handlers for all endpoints
- `src/prefect/server/models/`: SQLAlchemy ORM models
- `src/prefect/server/database/`: Database interface and migrations
- `src/prefect/server/orchestration/`: State transition policies and rules

**Configuration:**
- `src/prefect/settings/__init__.py`: Settings dataclass
- `src/prefect/settings/context.py`: Settings context management
- `pyproject.toml`: Project dependencies and build configuration

**Testing:**
- `tests/conftest.py`: Pytest fixtures and configuration
- `tests/fixtures/`: Test data and helper fixtures
- `tests/server/conftest.py`: Server-specific test fixtures

## Naming Conventions

**Files:**
- Modules: lowercase with underscores (e.g., `flow_engine.py`, `task_runner.py`)
- Classes: CamelCase (e.g., `Flow`, `Task`, `FlowRun`)
- Test files: `test_<module>.py` (e.g., `test_flows.py`, `test_engine.py`)

**Directories:**
- Package dirs: lowercase with underscores (e.g., `src/prefect/server/api/`)
- Grouping: Related functionality grouped together (e.g., `src/prefect/infrastructure/`, `src/prefect/workers/`)

**Imports:**
- Relative imports within same package: `from . import module` or `from .submodule import Class`
- Absolute imports across packages: `from prefect.client import PrefectClient`
- Avoid circular imports by using TYPE_CHECKING guards

**API Exports:**
- Core API re-exported from `src/prefect/main.py` and `src/prefect/__init__.py`
- Internal APIs prefixed with `_` (e.g., `_internal/`, `_experimental/`)

## Where to Add New Code

**New Feature (Flow-Level):**
- Primary code: `src/prefect/flows.py` (if modifying Flow class) or new module in `src/prefect/`
- Tests: Mirror structure in `tests/` (e.g., `tests/test_new_feature.py`)
- CLI: New command file in `src/prefect/cli/` if user-facing command needed
- Server: New API endpoint in `src/prefect/server/api/` if server-side logic needed

**New Task-Level Feature:**
- Primary code: `src/prefect/tasks.py` (if modifying Task class) or new module in `src/prefect/`
- Tests: `tests/engine/test_task_engine.py` or new `tests/test_feature.py`

**New Execution/Engine Feature:**
- Primary code: `src/prefect/flow_engine.py` or `src/prefect/task_engine.py`
- Tests: `tests/engine/` directory

**New Storage Backend:**
- Primary code: `src/prefect/filesystems.py` (add new filesystem class)
- Alternative: As block in `src/prefect/blocks/core.py` if user-configurable

**New Infrastructure Type:**
- Primary code: `src/prefect/infrastructure/<type>.py` (new file)
- Tests: `tests/infrastructure/test_<type>.py`
- Ensure inherits from `Infrastructure` base class in `src/prefect/infrastructure/base.py`

**New CLI Command:**
- Primary code: New file `src/prefect/cli/<command>.py` following Typer patterns
- Registration: Import and register in `src/prefect/cli/__init__.py`
- Tests: `tests/cli/test_<command>.py`

**New Block Type:**
- Primary code: `src/prefect/blocks/core.py` or new integration package
- Inherit from `Block` in `src/prefect/blocks/abstract.py`
- Tests: `tests/blocks/test_<block_type>.py`

**New Integration Package:**
- Primary code: New directory `src/integrations/prefect-<service>/`
- Structure: Mirrors main package with own pyproject.toml
- Tests: Separate test directory within integration package

**Utilities/Helpers:**
- Shared helpers: `src/prefect/utilities/` (new module or existing relevant module)
- Internal helpers: `src/prefect/_internal/` for non-public utilities
- Tests: `tests/utilities/test_<module>.py`

## Special Directories

**`src/prefect/_vendor/`**
- Purpose: Bundled third-party code
- Generated: No (manually maintained)
- Committed: Yes

**`src/prefect/server/collection_blocks_data.json`**
- Purpose: Pre-generated collection block registry
- Generated: Yes (from integration packages)
- Committed: Yes

**`src/prefect/server/ui_build/` and `ui_v2_build/`**
- Purpose: Built/dist directories for UIs
- Generated: Yes (from ui/ and ui-v2/ npm builds)
- Committed: No (generated at install/build time)

**`src/prefect/server/_migrations/`**
- Purpose: Alembic database migrations
- Generated: No (manually created)
- Committed: Yes

**`.planning/codebase/`**
- Purpose: Architecture and structure documentation
- Generated: No (agent-generated or manual)
- Committed: Yes

**`tests/test-projects/`**
- Purpose: Sample projects for integration testing
- Generated: No
- Committed: Yes

## File Organization Principles

1. **Co-location:** Tests live near source (or mirror structure in tests/)
2. **Layering:** Clear separation between SDK (public API), engine (execution), client (communication), server (backend)
3. **Modularity:** Each module has single responsibility, avoids circular dependencies
4. **Discoverability:** Related code grouped in directories (e.g., all infrastructure blocks in infrastructure/)
5. **Naming clarity:** File and directory names reflect content (engine files contain execution, client files contain HTTP communication)
6. **Public vs Internal:** Public API in main namespace or main.py, internal details in _internal/ or prefixed with _
