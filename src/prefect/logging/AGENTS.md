# Prefect Logging

Structured logging infrastructure for Prefect: handler pipeline, API log shipping, run-context-aware loggers, and WebSocket log streaming.

## Purpose & Scope

This module owns the logging configuration, handlers, formatters, and context-aware logger factories. It ships structured logs to the Prefect API in batches and provides Rich-styled console output.

It does NOT enforce logging conventions in calling code — that's the responsibility of individual modules (documented in `src/prefect/AGENTS.md`).

## Entry Points & Contracts

Public API (exported from `__init__.py`):
- `get_logger(name)` — LRU-cached prefect-namespaced logger with API key obfuscation
- `get_run_logger(context=None, **kwargs)` — returns flow or task run logger from active context
- `LogEavesdropper` — context manager that captures log records into a list (for testing)
- `disable_run_logger()` — context manager that silences run loggers

Internal factories (not exported, but used by engines/workers):
- `flow_run_logger()` / `task_run_logger()` — direct logger factories with run metadata
- `get_worker_logger()` — adds `backend_id` if available (Cloud only)

**APILogHandler drops logs without a `flow_run_id`.** Logs emitted outside a run context raise `MissingContextError`, which is caught and converted to a warning or silently dropped depending on `PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW`.

## Handler Pipeline

```
prefect.flow_runs / prefect.task_runs  →  APILogHandler  →  APILogWorker (batched HTTP)
prefect._internal                      →  _SafeStreamHandler  →  stderr
prefect (root)                         →  PrefectConsoleHandler  →  stderr (Rich)
prefect.workers                        →  WorkerAPILogHandler  →  APILogWorker (Cloud only)
```

Key invariants:
- **`prefect._internal` uses `_SafeStreamHandler`**, not `logging.StreamHandler` — this suppresses `ValueError: I/O operation on closed file` that fires when background threads log after stream teardown. Do not revert to plain `StreamHandler` for this logger.
- Flow/task run logs go to `APILogHandler` only — they do NOT appear on the console by default.
- `WorkerAPILogHandler` requires a `worker_id` attribute on the record; logs without it are dropped silently.

## API Log Batching

`APILogWorker` is a **singleton per unique settings tuple** `(BATCH_SIZE, API_URL, MAX_LOG_SIZE)`. A new settings combination creates a new worker instance.

- `max_batch_size = max(BATCH_SIZE - MAX_LOG_SIZE, MAX_LOG_SIZE)` — defensive: ensures a single max-size log can always fit
- `APILogHandler.prepare()` truncates oversized logs with a buffer; `WorkerAPILogHandler.prepare()` raises `ValueError` instead (no truncation)

**Flush deadlock guard:** `APILogHandler.flush()` detects if called from within an event loop and avoids blocking via `from_sync.call_soon_in_new_thread()`. Do not call `flush()` synchronously from async code without this guard.

## Non-Obvious Behaviors

- **Subflow-in-task disambiguation:** `print_as_log()` compares `flow_run_id` between flow and task contexts when both are active — if they differ, the flow context wins (lines 340–352 in `loggers.py`).
- **`PrefectFormatter` changes format string by logger name** — only `"prefect.flow_runs"` and `"prefect.task_runs"` get the run-specific format; all others use the default. This name check is hardcoded in `formatters.py` and must match `logging.yml`.
- **Configuration is incremental after first load** — `setup_logging()` sets `PROCESS_LOGGING_CONFIG` on first call; subsequent calls default to `incremental=True` to avoid resetting user-added handlers.
- **WebSocket subscribers deduplicate** via a `TTLCache(maxsize=500_000, ttl=120)` — reconnects won't re-deliver logs seen in the last 2 minutes.

## Pitfalls

- `get_run_logger()` raises `MissingContextError` outside a run. Wrap with `try/except` or use `get_logger()` as fallback for code that runs both inside and outside runs.
- The logger name `"prefect._internal"` is load-bearing: `logging.yml` routes it to `_SafeStreamHandler` with `propagate: false`. Renaming it breaks teardown noise suppression.
- `APILogWorker.instance()` uses settings as a cache key — if you change `PREFECT_API_URL` mid-process (e.g., in tests), you'll get a stale worker pointing at the old URL unless you reset the singleton.
