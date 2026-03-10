# Concurrency

Client-side concurrency limit enforcement: acquires and releases slots against server-defined limits, maintains leases during execution, and tracks events for traceability.

## Purpose & Scope

Manages concurrency slot acquisition/release for flows and tasks enforcing named concurrency limits. Handles the full lifecycle: acquire → maintain lease → release, with both sync and async paths.

Does NOT define concurrency limits (server-side in `server/`). Does NOT handle task runner parallelism (separate concern).

## Entry Points & Contracts

**Public API** (`asyncio.py`, `sync.py`):
- `concurrency(names, occupy=1, timeout_seconds=None, max_retries=None, lease_duration=300, strict=False)` — context manager that acquires slots on entry and releases on exit
- `rate_limit(names, occupy=1, timeout_seconds=None, strict=False)` — one-shot acquire for decay-based limits (no release needed)

**`strict=False` (default):** logs a warning if the named limit doesn't exist, but proceeds. `strict=True` raises `ConcurrencySlotAcquisitionError`.

**Lease renewal:** `_leases.py` runs a background loop that renews the lease at 75% of `lease_duration`. Uses `@retry_async_fn(max_attempts=3)` for transient failures. After 3 failures the renewal raises, and the caller can either cancel execution (`raise_on_lease_renewal_failure=True`) or continue with a warning.

## Architecture

Layered — each layer has a single job:

1. **Public** (`asyncio.py`, `sync.py`) — user-facing context managers, emits acquisition/release events
2. **Internal** (`_asyncio.py`, `_sync.py`) — orchestrates acquire → lease → release, handles cancellation cleanup via `ConcurrencyContext`
3. **Services** (`services.py`) — serializes API requests per `frozenset(names)` to prevent thundering herd; retries on HTTP 423 with `Retry-After` backoff
4. **Leases** (`_leases.py`) — background renewal loop, sync and async variants
5. **Events** (`_events.py`) — acquisition/release event emission; release events link back to acquisition events
6. **Context** (`context.py`) — `ConcurrencyContext` accumulates lease IDs that need cleanup if execution is cancelled

## Usage Patterns

```python
# Async
from prefect.concurrency.asyncio import concurrency
async with concurrency("my-limit", occupy=1):
    ...  # slots held here; lease renewed in background

# Sync
from prefect.concurrency.sync import concurrency
with concurrency("my-limit", occupy=1):
    ...
```

## Anti-Patterns

- **Don't call internal `_asyncio`/`_sync` functions directly** — use the public `asyncio.py`/`sync.py` APIs. The internal modules skip event emission setup.
- **Don't mix sync `concurrency()` in async code** — use `asyncio.concurrency()` to avoid blocking the event loop.
- **Don't rely on strict=False for correctness** — in tests or scripts where the limit must exist, use `strict=True` so you catch misconfigurations early.

## Pitfalls

- **Service singleton is keyed on `frozenset(names)`.** Passing the same names in different order reuses the same singleton; passing a strict subset creates a different singleton. Each unique name-set gets its own queue.
- **Lease renewal runs on the global event loop** (sync path). If the global loop is blocked or torn down, renewal silently fails — you'll see the renewal failure callback fire after `max_attempts` retries are exhausted.
- **Cancellation during acquire** — lease IDs for mid-acquisition slots land in `ConcurrencyContext.cleanup_lease_ids`. `ConcurrencyContext.__exit__` releases them via a sync client. If `ConcurrencyContext` is not active, those leases are abandoned until server-side expiry.
- **`v1/` subdirectory** contains the legacy slot API (no lease model). New code should use the top-level `concurrency()` / `rate_limit()` APIs.
