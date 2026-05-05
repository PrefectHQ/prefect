# Testing Utilities

Test helpers and fixtures shipped with the Prefect SDK for testing flows against a real local server.

## Purpose & Scope

Provides the `prefect_test_harness` context manager and assertion helpers consumed by both the Prefect test suite and downstream user code. Does **not** own pytest fixtures (those live in `tests/`) or integration-test infrastructure.

## Entry Points & Contracts

- **`prefect_test_harness()`** (`utilities.py`) — Context manager that spins up a temporary SQLite-backed `SubprocessASGIServer` and overrides `PREFECT_API_URL` for the duration of the block. Safe to nest; restores prior state on exit.
- **`assert_does_not_warn()`** — Converts warnings to errors inside the block. Accepts an `ignore_warnings` list for expected categories.
- **`assert_blocks_equal()`** / **`assert_uses_result_serializer()`** / **`assert_uses_result_storage()`** — Deep-equality helpers for blocks and result metadata.
- **`fixtures.py`** — Pytest fixtures for WebSocket servers, events clients (`AssertingEventsClient`, `AssertingPassthroughEventsClient`), and CSRF/ephemeral-mode overrides. Imported in `tests/conftest.py`.
- **`standard_test_suites/`** — Reusable test suite classes (e.g., `BlockStandardTestSuite`) for testing block implementations.

## Invariants

- **`prefect_test_harness` registers the test server under `SubprocessASGIServer._instances[None]`.** `SubprocessASGIServer` is a port-keyed singleton. The harness creates a server with an explicit port (keyed by that port), then also registers it under the `None` key. This ensures that internal `SubprocessASGIServer()` calls during flow execution return the *same* managed instance rather than spawning a second unmanaged subprocess. On exit the prior `None`-keyed entry is restored (or removed if there was none). Violating this invariant causes a leaked server process that keeps pytest hanging after test completion — see issue #21544.
- **`prefect_test_harness` drains `APILogWorker` and `EventsWorker` before stopping the server.** Skipping this causes connection errors on shutdown and stale events leaking into subsequent test harnesses.
