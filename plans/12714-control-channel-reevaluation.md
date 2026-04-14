# Control Channel Re-evaluation

## Current Contract

1. The runner registers a flow run and injects `PREFECT__CONTROL_PORT` / `PREFECT__CONTROL_TOKEN`.
2. The child connects early and authenticates with the token.
3. The child sends `b"r"` when Prefect's SIGTERM bridge is installed.
4. The child sends `b"n"` when that bridge is removed.
5. The runner sends `b"c"` to request cancellation.
6. The child records a process-global cancel intent as soon as it reads `b"c"`.
7. If the child is not ready yet, it defers final delivery until `capture_sigterm()` arms the bridge.
8. The child sends `b"a"` only when it believes cancellation can be consumed gracefully.
9. The engine reads the process-global intent in `except TerminationSignal` and dispatches to cancellation handling.
10. Same-process nested subflows inherit that process-global intent automatically.
11. Top-level runner-managed subprocesses still have terminal state finalized externally by the runner.
12. If the runner does not receive `b"a"`, it falls back to kill-only behavior and the engine treats the termination as a crash.

## Assessment

The control channel itself is still the right abstraction. The instability is concentrated in one place: child-side signal delivery.

The current implementation makes `b"a"` mean slightly different things depending on:

- startup vs steady-state
- POSIX vs Windows
- whether the child or the runner is expected to provide the actual termination trigger

That is why review comments keep clustering around:

- when `b"a"` is written
- whether readiness is still valid
- whether the queued signal reaches the main thread
- whether a late cancel can hit a restored handler

## Recommended Simplification

### Keep

- the runner-to-child control channel
- early child connection and token auth
- process-global child intent
- `b"r"` / `b"n"` readiness tracking
- runner-owned terminal state for top-level subprocesses
- child-owned cancellation/crash handling for same-process nested subflows

### Simplify

#### POSIX

Do not self-signal from the child at all.

- `b"a"` should mean only: "the child has durably recorded cancel intent and Prefect's SIGTERM bridge is currently armed."
- After `b"a"`, the runner should immediately use its normal OS kill path to send the real `SIGTERM`.
- That real runner-delivered `SIGTERM` is already the correct mechanism for interrupting blocking syscalls on POSIX.
- This removes the helper-thread / `pthread_kill` / late-restored-handler complexity entirely from the POSIX child path.

#### Windows

Keep the child-side `_thread.interrupt_main(SIGTERM)` path.

- The runner's external termination path on Windows is not a real SIGTERM bridge into Python.
- The child still needs to trigger `TerminationSignal` locally there.
- This leaves some platform-specific complexity, but it is isolated to Windows instead of shared across every platform.

#### Runner kill timing

Use one grace budget, not two.

- `b"a"` should not imply "cleanup already started".
- On POSIX, the runner's immediate `SIGTERM` after `b"a"` is the trigger that starts graceful cleanup.
- On Windows, `b"a"` means the child has accepted intent and has queued the local interrupt; the runner may wait within the same overall grace budget before forcing termination.

## Why This Is Better

- `b"a"` has one stable meaning on POSIX: intent recorded + bridge armed.
- Blocking syscalls are interrupted by the existing runner `SIGTERM`, not by a second in-process signal path.
- Startup-time cancel stays supported: the child can still defer `b"a"` until `capture_sigterm()` is ready.
- The late-cancel race against restored handlers disappears on POSIX because the child no longer sends a real signal.
- Most of the current review churn is eliminated without backing out the core control-channel design.

## Suggested Next Change

1. Remove POSIX self-signal delivery from `prefect._internal.control_listener`.
2. Make POSIX `b"a"` a pure "intent recorded and bridge armed" acknowledgement.
3. Have the runner use its normal `SIGTERM` path immediately after an acked POSIX cancel.
4. Keep the single-budget reconciliation and runner-side terminal-state verification already added.
5. Keep Windows on the child-interrupt path for now.

## Validation Plan

- Re-run the focused control-listener and control-channel tests.
- Re-run the nested in-process cancellation regression tests.
- Re-run the real Kubernetes work-pool repro.
- Add one explicit test that on POSIX the child does not self-signal anymore; the runner `SIGTERM` is what triggers `TerminationSignal`.
