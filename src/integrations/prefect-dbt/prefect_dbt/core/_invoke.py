"""Supervised in-process dbt invocation.

`dbtRunner.invoke()` runs dbt on the calling thread and only cleans up its
worker pool and open database connections for `KeyboardInterrupt`,
`SystemExit` and `FailFastError`. Prefect signals timeouts and cancellation
with its own `CancelledError`, which dbt neither recognizes nor propagates: it
is swallowed into the returned `dbtRunnerResult` while worker threads and
in-flight queries keep running.

`invoke_dbt` runs dbt on a dedicated thread so that a cancellation delivered
to the caller can be translated into dbt's own shutdown path: a
`KeyboardInterrupt` is injected into the dbt thread and open connections are
cancelled on every registered adapter (repeatedly, since dbt's main thread
only observes the interrupt between blocking waits and may keep dispatching
queued nodes until then). The caller waits for the dbt thread to exit before
the cancellation propagates, so a task retry never overlaps a previous
attempt.
"""

from __future__ import annotations

import contextvars
import ctypes
import threading
import time
from typing import Any

from dbt.adapters.factory import FACTORY
from dbt.cli.main import dbtRunner, dbtRunnerResult

from prefect.logging import get_logger

logger = get_logger(__name__)

_WAIT_POLL_INTERVAL = 0.1
_CANCEL_RETRY_INTERVAL = 1.0
_SHUTDOWN_WARNING_INTERVAL = 30.0


def _inject_keyboard_interrupt(thread: threading.Thread) -> None:
    if thread.ident is None:
        return
    # Returns 0 (no-op) if the thread has already exited.
    ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread.ident), ctypes.py_object(KeyboardInterrupt)
    )


class _Invocation:
    """A dbt invocation running on its own thread.

    Liveness is tracked with an `Event` rather than `Thread.join()`: an
    asynchronous exception (which is how Prefect delivers timeouts and
    cancellation to a synchronous caller) raised inside `join()` makes CPython
    mark the thread as stopped even though it is still running.
    """

    def __init__(self, runner: dbtRunner, args: list[str]) -> None:
        self._runner = runner
        self._args = args
        self._context = contextvars.copy_context()
        self._outcome: dict[str, Any] = {}
        self.done = threading.Event()
        self.thread = threading.Thread(
            target=self._run, name="prefect-dbt-invoke", daemon=True
        )

    def _run(self) -> None:
        try:
            self._outcome["result"] = self._context.run(self._runner.invoke, self._args)
        except BaseException as exc:
            self._outcome["error"] = exc
        finally:
            self.done.set()

    def start(self) -> None:
        self.thread.start()

    def wait(self, timeout: float) -> bool:
        return self.done.wait(timeout)

    def result(self) -> dbtRunnerResult:
        if "error" in self._outcome:
            raise self._outcome["error"]
        return self._outcome["result"]


def cancel_open_adapter_connections() -> None:
    """Cancel in-flight queries on every registered dbt adapter.

    Mirrors dbt-core's `GraphRunnableTask._cancel_connections`, which is only
    reached by dbt for `KeyboardInterrupt`/`SystemExit`. Adapters that are not
    yet registered (cancellation during parsing) or not cancelable are skipped.
    """
    with FACTORY.lock:
        adapters: list[Any] = list(FACTORY.adapters.values())

    if not adapters:
        logger.debug("No dbt adapter registered; nothing to cancel")
        return

    for adapter in adapters:
        if not adapter.is_cancelable():
            logger.debug(
                "dbt adapter %r does not support cancelling open connections; "
                "in-flight queries continue until they finish",
                adapter.type(),
            )
            continue
        try:
            with adapter.connection_named("master"):
                adapter.cancel_open_connections()
        except Exception as exc:
            logger.warning(
                "Failed to cancel open connections for dbt adapter %r: %s",
                adapter.type(),
                exc,
            )


def invoke_dbt(runner: dbtRunner, args: list[str]) -> dbtRunnerResult:
    """Run `runner.invoke(args)` on a supervised thread.

    Returns dbt's result on normal completion. If the calling thread receives
    any `BaseException` while waiting (Prefect timeout/cancellation,
    `KeyboardInterrupt`, ...), dbt is shut down before it is re-raised.
    """
    invocation = _Invocation(runner, args)

    try:
        invocation.start()
        while not invocation.wait(_WAIT_POLL_INTERVAL):
            pass
    except BaseException:
        if invocation.thread.ident is not None:
            logger.info("dbt invocation cancelled; shutting down dbt worker threads")
            _inject_keyboard_interrupt(invocation.thread)
            cancel_open_adapter_connections()
            _wait_for_shutdown(invocation)
        raise

    result = invocation.result()
    # dbt encodes cancellation in its result; preserve it as control flow so
    # every caller performs exception cleanup rather than normal completion.
    if (
        not result.success
        and isinstance(result.exception, BaseException)
        and not isinstance(result.exception, Exception)
    ):
        raise result.exception
    return result


def _wait_for_shutdown(invocation: _Invocation) -> None:
    started = time.monotonic()
    last_cancel = last_warning = started
    while not invocation.wait(_WAIT_POLL_INTERVAL):
        now = time.monotonic()
        if now - last_cancel >= _CANCEL_RETRY_INTERVAL:
            last_cancel = now
            cancel_open_adapter_connections()
        if now - last_warning >= _SHUTDOWN_WARNING_INTERVAL:
            last_warning = now
            logger.warning(
                "Still waiting for dbt to shut down after cancellation (%.0fs)",
                now - started,
            )
