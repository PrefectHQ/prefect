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

**Lease renewal:** `_leases.py` runs a background loop that renews immediately on entry, then sleeps for 75% of `lease_duration` between renewals. Each renewal call uses `@retry_async_fn(max_attempts=3)` for transient failures. If all 3 attempts fail, the background task raises and a done-callback either cancels execution (`raise_on_lease_renewal_failure=True`) or logs a warning.

**Sync/async lockstep invariant:** `asyncio.py`/`sync.py` and `_asyncio.py`/`_sync.py` are parallel implementations. Any behavior change to one must be mirrored in the other.

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
- **Lease renewal runs on the global event loop** (sync path). If the global loop is blocked or torn down, renewal silently fails — you'll see the renewal failure callback fire after `max_attempts` retries are exhausted.
- **Cancellation during acquire or release** — if a `CancelledError` is raised either during slot acquisition or during `release_concurrency_slots_with_lease` in the `finally` block, the lease ID is appended to `ConcurrencyContext.cleanup_lease_ids`. `ConcurrencyContext.__exit__` releases them via a sync client. If `ConcurrencyContext` is not active, those leases are abandoned until server-side expiry.
- **`v1/` subdirectory** contains the legacy slot API (no lease model). New code should use the top-level `concurrency()` / `rate_limit()` APIs.
