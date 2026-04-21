# asyncutils

Async/sync bridging, thread coordination, and concurrency primitives used throughout the SDK.

## Purpose & Scope

Bridges Prefect's async engine with user-written sync code (and vice versa) without deadlocking the event loop or losing context. Also provides a handful of async-aware primitives (`LazySemaphore`, timed task creation) used by higher layers.

## Entry Points

- `run_coro_as_sync(coro)` — run an async coroutine from sync code, reusing the global loop when available.
- `run_sync_in_worker_thread(fn, *args, **kwargs)` — execute a blocking sync callable off the event loop.
- `sync_compatible(fn)` — decorator letting a single `async def` be called from both sync and async callers.
- `LazySemaphore` — a semaphore whose capacity is resolved on first acquisition (used for managing open-file limits at import time without evaluating `resource` limits eagerly).
- `gather(*calls)` / `create_gather_task_group()` — run a collection of coroutine-returning callables concurrently and collect their results positionally.
- `create_task(coro)` — create an `asyncio.Task` with Prefect's logging-and-cancellation-friendly wiring.

## Pitfalls

_No pitfalls documented yet. Add here when non-obvious behaviors surface during debugging — especially around context propagation, thread-to-loop hand-off, and cancellation semantics, which tend to bite in subtle ways._
