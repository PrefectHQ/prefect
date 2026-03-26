import contextvars
import sys
import threading
from contextlib import contextmanager
from typing import Generator
from uuid import UUID

from prefect._internal._logging import logger as internal_logger
from prefect._internal.concurrency.cancellation import (
    AsyncCancelScope,
    CancelledError,
    _send_exception_to_thread,
)
from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.retries import exponential_backoff_with_jitter
from prefect.client.orchestration import get_client
from prefect.logging.loggers import get_logger, get_run_logger


class _LeaseRenewalInterrupt(BaseException):
    """Injected into the caller thread when strict-mode lease renewal fails.

    Inherits from BaseException so user code with bare `except Exception`
    will not accidentally swallow it.
    """


@contextmanager
def maintain_concurrency_lease(
    lease_id: UUID,
    lease_duration: float,
    raise_on_lease_renewal_failure: bool = False,
    suppress_warnings: bool = False,
) -> Generator[None, None, None]:
    """
    Maintain a concurrency lease for the given lease ID.

    Spawns a daemon thread that renews the lease using a sync client,
    ensuring renewals fire even when the event loop is blocked by
    CPU-bound work.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        raise_on_lease_renewal_failure: A boolean specifying whether to raise
            an error if the lease renewal fails. When True, protected code is
            interrupted as soon as the lease is lost.
        suppress_warnings: A boolean specifying whether to suppress warnings
            when the lease renewal fails.
    """
    stop_event = threading.Event()
    caller_ready = threading.Event()
    failure_exc: list[BaseException] = []

    # Capture caller context for mid-execution interruption in strict mode
    caller_thread = threading.current_thread()
    caller_loop = get_running_loop()

    # For async callers, use an AsyncCancelScope so cancellation is persistent:
    # once cancelled, ALL subsequent awaits raise CancelledError, even if
    # user code catches the first one.
    cancel_scope: AsyncCancelScope | None = None
    if caller_loop is not None:
        cancel_scope = AsyncCancelScope()
        cancel_scope.__enter__()

    def _interrupt_caller() -> None:
        """Interrupt the protected code when strict-mode lease renewal fails."""
        if stop_event.is_set():
            # Context is exiting normally; don't inject an exception
            return

        if cancel_scope is not None:
            # Async caller: cancel the scope. AsyncCancelScope.cancel()
            # handles cross-thread dispatch internally via
            # loop.call_soon_threadsafe.
            cancel_scope.cancel()
        else:
            # Sync caller: inject exception into the caller's thread
            try:
                _send_exception_to_thread(caller_thread, _LeaseRenewalInterrupt)
            except ValueError:
                # Thread is gone
                pass

    def _log_non_strict_failure(exc: BaseException) -> None:
        """Log lease-renewal failure immediately from the renewal thread."""
        try:
            _logger = get_run_logger()
        except Exception:
            _logger = get_logger("concurrency")
        msg = (
            "Concurrency lease renewal failed - slots are no longer reserved. "
            "Execution will continue, but concurrency limits may be exceeded."
        )
        if suppress_warnings:
            _logger.debug(msg, exc_info=(type(exc), exc, exc.__traceback__))
        else:
            _logger.warning(msg, exc_info=(type(exc), exc, exc.__traceback__))

    def _renewal_loop() -> None:
        # Wait until the caller has entered the protected block (yield).
        # Without this gate, _send_exception_to_thread can fire during
        # thread.start() before the caller's try block is even entered.
        caller_ready.wait()

        try:
            with get_client(sync_client=True) as client:
                while not stop_event.is_set():
                    last_exc: BaseException | None = None
                    for attempt in range(3):
                        try:
                            client.renew_concurrency_lease(
                                lease_id=lease_id,
                                lease_duration=lease_duration,
                            )
                            last_exc = None
                            break
                        except Exception as exc:
                            last_exc = exc
                            if attempt < 2:
                                delay = exponential_backoff_with_jitter(
                                    attempt, base_delay=1, max_delay=10
                                )
                                internal_logger.warning(
                                    f"Attempt {attempt + 1} of 'concurrency lease renewal' "
                                    f"failed with {type(exc).__name__}: {exc}. "
                                    f"Retrying in {delay:.2f} seconds..."
                                )
                                # Use stop_event.wait so we can be interrupted during backoff
                                if stop_event.wait(delay):
                                    return
                            else:
                                internal_logger.exception(
                                    "Function 'concurrency lease renewal' failed after 3 attempts"
                                )

                    if last_exc is not None:
                        failure_exc.append(last_exc)
                        if raise_on_lease_renewal_failure:
                            _interrupt_caller()
                        else:
                            _log_non_strict_failure(last_exc)
                        return

                    # Sleep for 75% of the lease duration before next renewal
                    if stop_event.wait(lease_duration * 0.75):
                        return
        except Exception as exc:
            # Catch client startup failures or any other unexpected error
            # not already handled by the retry loop above.
            if exc not in failure_exc:
                failure_exc.append(exc)
                if raise_on_lease_renewal_failure:
                    _interrupt_caller()
                else:
                    _log_non_strict_failure(exc)

    # Snapshot the caller's contextvars so the daemon thread inherits
    # SettingsContext, SyncClientContext, etc.  Without this, get_client()
    # in the thread would fall back to default/environment settings.
    ctx = contextvars.copy_context()

    thread = threading.Thread(
        target=ctx.run,
        args=(_renewal_loop,),
        daemon=True,
        name=f"lease-renewal-{lease_id}",
    )
    thread.start()

    try:
        # Signal that the caller is now inside the protected block
        caller_ready.set()
        yield
    except _LeaseRenewalInterrupt:
        # Injected by _interrupt_caller via _send_exception_to_thread (sync path).
        # Fall through to finally for proper error handling.
        pass
    finally:
        stop_event.set()
        # Also signal caller_ready in case we exit before yield (e.g. exception
        # during setup) so the daemon thread doesn't block forever.
        caller_ready.set()
        if caller_loop is None:
            # Sync caller: safe to block on join
            try:
                thread.join(timeout=2)
            except _LeaseRenewalInterrupt:
                # The injected exception may fire during join if it was still
                # pending when we entered the finally block.
                pass
        # Async caller: skip join to avoid blocking the event loop.
        # stop_event signals the daemon thread to exit at its next
        # stop_event.wait() check; the daemon flag ensures process cleanup.

        if failure_exc:
            exc = failure_exc[0]

            # Exit the cancel scope before raising. Suppress its bare
            # CancelledError — we'll either raise a more informative one
            # (strict) or intentionally continue (non-strict).
            if cancel_scope is not None:
                try:
                    cancel_scope.__exit__(None, None, None)
                except CancelledError:
                    pass

            if raise_on_lease_renewal_failure:
                try:
                    logger = get_run_logger()
                except Exception:
                    logger = get_logger("concurrency")
                logger.error(
                    "Concurrency lease renewal failed - slots are no longer reserved. "
                    "Terminating execution to prevent over-allocation.",
                    exc_info=(type(exc), exc, exc.__traceback__),
                )
                # Raise CancelledError (a BaseException) so the flow engine's
                # crash path handles this, matching the old cancel-scope behavior.
                raise CancelledError("Concurrency lease renewal failed") from exc
            # else: already logged immediately in the renewal thread
        else:
            # No failure: exit scope normally. Propagates CancelledError
            # if scope was cancelled for some other reason.
            if cancel_scope is not None:
                cancel_scope.__exit__(*sys.exc_info())
