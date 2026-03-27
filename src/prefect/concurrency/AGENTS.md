# Concurrency

Client-side concurrency limit enforcement: acquires and releases slots against server-defined limits, maintains leases during execution, and tracks events for traceability.

## Purpose & Scope

Manages concurrency slot acquisition/release for flows and tasks enforcing named concurrency limits. Handles the full lifecycle: acquire → maintain lease → release, with both sync and async paths.

Does NOT define concurrency limits (server-side in `server/`). Does NOT handle task runner parallelism (separate concern).

## Entry Points & Contracts

**Public API** (`asyncio.py`, `sync.py`):
- `concurrency()` — context manager that acquires slots on entry and releases on exit
- `rate_limit()` — one-shot acquire for decay-based limits (no release needed)

**`strict=False` (default):** logs a warning if the named limit doesn't exist, but proceeds. `strict=True` raises `ConcurrencySlotAcquisitionError`.

**Lease renewal:** `_leases.py` spawns a daemon thread that renews the lease using a sync HTTP client, sleeping for 75% of `lease_duration` between renewals. Each renewal is retried up to 3 times with exponential backoff. If all attempts fail and `raise_on_lease_renewal_failure=True`, the protected code is interrupted immediately (`_send_exception_to_thread` for sync callers, `task.cancel()` for async callers) and a `CancelledError` is raised to trigger the flow engine's crash path. Otherwise a warning is logged. The daemon thread approach ensures renewals fire even when the event loop is blocked by CPU-bound work.

**Unified lease maintenance:** Both sync and async paths use the same `maintain_concurrency_lease` context manager (a sync `@contextmanager`). The async `concurrency()` in `_asyncio.py` uses `with maintain_concurrency_lease(...)` (not `async with`).

## Architecture

Layered — public → internal → services, with leases and events as cross-cutting concerns:

- **Public** (`asyncio.py`, `sync.py`) — user-facing context managers; `rate_limit()` emits events directly
- **Internal** (`_asyncio.py`, `_sync.py`) — orchestrates acquire → lease → release, emits events for `concurrency()`, handles cancellation cleanup via `ConcurrencyContext`
- **Services** (`services.py`) — serializes API requests per `frozenset(names)` to prevent thundering herd; retries on HTTP 423 with `Retry-After` backoff

## Anti-Patterns

- **Don't call internal `_asyncio`/`_sync` functions directly** — use the public `asyncio.py`/`sync.py` APIs. The internal modules skip event emission setup.
- **Don't mix sync `concurrency()` in async code** — use `asyncio.concurrency()` to avoid blocking the event loop.
- **Don't rely on strict=False for correctness** — in tests or scripts where the limit must exist, use `strict=True` so you catch misconfigurations early.

## Pitfalls

- **Service singleton is keyed on `frozenset(names)`.** Passing the same names in different order reuses the same singleton; passing a strict subset creates a different singleton. Each unique name-set gets its own queue.
- **Lease renewal runs in a daemon thread** using a sync HTTP client. The thread is joined with a 2-second timeout on context exit; if it doesn't join in time, it continues as a daemon and is cleaned up on process exit. `_send_exception_to_thread` (used for strict-mode interruption) cannot interrupt C-level blocking calls like `time.sleep`.
- **Cancellation during acquire or release** — if a `CancelledError` is raised either during slot acquisition or during `release_concurrency_slots_with_lease` in the `finally` block, the lease ID is appended to `ConcurrencyContext.cleanup_lease_ids`. `ConcurrencyContext.__exit__` releases them via a sync client. If `ConcurrencyContext` is not active, those leases are abandoned until server-side expiry.
- **`v1/` subdirectory** contains the legacy slot API (no lease model). New code should use the top-level `concurrency()` / `rate_limit()` APIs.
