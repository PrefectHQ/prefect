# Core Prefect SDK

The foundation for building and executing workflows with Python.

## Key Components

- **Flows & Tasks**: Workflow definition with `@flow` and `@task` decorators
- **States**: Execution status tracking (Pending, Running, Completed, Failed)
- **Context**: Runtime information and dependency injection
- **Results**: Task output persistence and retrieval
- **Deployments**: Packaging flows for scheduled/triggered execution
- **Blocks**: Reusable configuration for external systems

## Main Modules

- `flows.py` - Flow lifecycle and execution
- `tasks.py` - Task definition and dependency resolution
- `engine.py` - Core execution engine
- `flow_engine.py` / `task_engine.py` - Flow and task execution engines
- `states.py` - State objects and transitions
- `results.py` - Result persistence
- `futures.py` - PrefectFuture for async task results
- `transactions.py` - Transaction support
- `context.py` - Runtime context management
- `client/` - Server/Cloud API communication
- `deployments/` - Deployment management
- `blocks/` - Infrastructure and storage blocks

## SDK-Specific Notes

- Async-first execution model with sync support
- Immutable flow/task definitions after creation
- State transitions handle retries and caching
- Backward compatibility required for public APIs

## Logging

Always use Prefect's logging utilities from `prefect.logging` instead of raw `logging.getLogger()`. Prefect's `get_logger()` adds API key obfuscation and places loggers under the `"prefect."` namespace automatically.

**Which logger to use:**

| Context | Function | Import |
|---|---|---|
| Anywhere outside a flow/task run | `get_logger()` | `from prefect.logging import get_logger` |
| Inside a `@flow` or `@task` function | `get_run_logger()` | `from prefect.logging import get_run_logger` |
| Worker implementations | `get_worker_logger()` | `from prefect.logging import get_worker_logger` |

**Logger naming conventions:**
- SDK core modules use short area names: `get_logger("flows")`, `get_logger("engine")`, `get_logger("tasks")`
- Server, client, CLI, and integration code use `__name__`: `get_logger(__name__)`

**When raw `logging.getLogger()` is acceptable:**
- Inside `src/prefect/logging/` itself (avoiding circular imports)
- Configuring third-party library loggers (e.g., uvicorn, sqlalchemy)

**Run loggers and the API log pipeline:**

The `prefect.flow_runs` and `prefect.task_runs` loggers have an `APILogHandler` (configured in `logging.yml`) that batches log records and sends them to `POST /logs/`. `flow_run_logger()` and `task_run_logger()` return a `PrefectLogAdapter` wrapping these loggers, attaching run metadata (`flow_run_id`, `task_run_id`, names) to every record so the API can associate logs with specific runs.

- **Flow/task engines** (`flow_engine.py`, `task_engine.py`) run user code. During `setup_run_context()` they call `flow_run_logger()` / `task_run_logger()` to create the logger available via `get_run_logger()` inside `@flow` and `@task` functions. These logs are sent to the API.
- **Workers** (`workers/base.py`) use `get_worker_logger(self)` for general logging (not sent to API). For per-run logging they call `flow_run_logger(flow_run).getChild("worker", extra={...})`, which inherits the `APILogHandler` and attaches worker context (`worker_name`, `work_pool_name`, `worker_id`).
- **Runners** (`runner/runner.py`) use `get_logger("runner")` for general logging (not sent to API). For per-run logging they call `flow_run_logger(flow_run).getChild("runner", extra={"runner_name": ...})`.
