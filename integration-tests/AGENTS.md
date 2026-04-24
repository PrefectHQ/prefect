# Integration Tests

End-to-end tests that require a live Prefect server and verify the full orchestration pipeline across process boundaries.

## Purpose & Scope

These tests cover scenarios that unit tests cannot: real server ↔ worker communication, subprocess flow execution, cancellation across process boundaries, event delivery, and scheduling statefulness.

They do NOT duplicate unit tests in `tests/`. If a behavior can be tested in isolation, it belongs there.

## Running

```bash
# Integration tests are excluded from the default testpaths in pyproject.toml — they will NOT run with uv run pytest tests/
uv run pytest integration-tests/
uv run pytest integration-tests/test_nested_cancellation.py
```

Requirements:
- `PREFECT_API_URL` must point to a running Prefect server (check with `prefect config view`)
- `uv` must be available in `PATH`

Some tests accept additional env vars: `SERVER_VERSION` (skip version-specific tests), `PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE`, `PREFECT_API_AUTH_STRING`.

## Structure

No shared `conftest.py`. Each test file is self-contained with its own helpers and fixtures inline. There are no pytest fixtures shared across files.

## Usage Patterns

**Poll, don't assert synchronously.** Hook execution, state transitions, and marker-file writes are independent side effects of the same cancel/complete sequence — the API state can become visible before the hook's file is written. Use `_wait_for()` instead of a bare `assert`:

```python
# Wrong — races on rare timing:
assert Path(marker_dir, HOOK_MARKER).exists()

# Right — polls until satisfied or timeout:
_wait_for(
    lambda: Path(marker_dir, HOOK_MARKER).exists(),
    timeout=30,
    message="Hook did not write its marker.\n" + _worker_output(log_path),
)
```

**Marker files for cross-process state.** Flows running in subprocesses write files to a shared `tmp_path` to signal that a state was reached. Name markers with constants (`PARENT_HOOK_MARKER`, `CHILD_STARTED_MARKER`, etc.) and document them at the top of the file.

**Subprocess invocations use `uv --isolated`.** All CLI calls go through `uv.find_uv_bin()` with `--isolated` to get a clean environment:

```python
subprocess.run([uv.find_uv_bin(), "run", "--isolated", "prefect", "worker", "start", ...])
```

`PREFECT_API_URL` is inherited from the calling process's env — it still needs to be set.

**Unique work pool names.** Always suffix with `uuid4()` to avoid conflicts across parallel test runs.

**Explicit cleanup in `finally`.** Deployments, work pools, and subprocesses must be cleaned up manually — there is no pytest fixture teardown:

```python
try:
    # set up pool, deployment, worker, run assertions
finally:
    client.delete_work_pool(pool_name)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
```

## Anti-Patterns

- Don't assert synchronously on hook markers or other side effects right after triggering a cancellation — always poll.
- Don't use fixed `asyncio.sleep()` delays as a substitute for `_wait_for()` — they either waste time or still race.
- Don't share state between test files via module-level globals — each file is standalone.

## Pitfalls

- `PREFECT_API_URL` not set produces cryptic errors, not a helpful configuration message. Check it first.
- These tests are slow (seconds to minutes per test) and intentionally excluded from the default `testpaths` in `pyproject.toml`.
- Process `terminate()` sends SIGTERM but the subprocess may not exit immediately — always `wait(timeout=...)` and fall back to `kill()`.
