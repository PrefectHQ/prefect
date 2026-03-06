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

Use `get_logger()` from `prefect.logging` instead of raw `logging.getLogger()` — it adds API key obfuscation and places loggers under the `"prefect."` namespace.

- General library code → `get_logger(__name__)`
- SDK core modules (flows, tasks, engine) → `get_logger("flows")`, `get_logger("engine")`, etc.
- Worker implementations → `get_worker_logger(self)`
- Infrastructure orchestrating a run (engines) → `flow_run_logger(flow_run)` / `task_run_logger(task_run)`
- Workers/runners needing child loggers → `.getChild("worker"|"runner", extra={...})` on a run logger
- Code that may run inside or outside a run (concurrency, transactions, blocks) → try `get_run_logger()`, fall back to `get_logger(...)`
- Raw `logging.getLogger()` only inside `src/prefect/logging/` (circular imports) or configuring third-party loggers
