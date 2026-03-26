import contextvars
import threading
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

_RENEWAL_FRACTION = 0.75


class _LeaseRenewalInterrupt(BaseException):
    """Injected into the caller thread when strict-mode lease renewal fails.

    Inherits from BaseException so user code with bare `except Exception`
    will not accidentally swallow it.
    """


class maintain_concurrency_lease:
    """Maintain a concurrency lease for the given lease ID.

    Spawns a daemon thread that renews the lease using a sync client,
    ensuring renewals fire even when the event loop is blocked by
    CPU-bound work.

    Implemented as a class-based context manager (not @contextmanager)
    so that _LeaseRenewalInterrupt is caught directly in __exit__
    rather than relying on gen.throw(), which does not reliably deliver
    the exception to the generator's except handler on CPython 3.13.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        raise_on_lease_renewal_failure: A boolean specifying whether to raise
            an error if the lease renewal fails. When True, protected code is
            interrupted as soon as the lease is lost.
        suppress_warnings: A boolean specifying whether to suppress warnings
            when the lease renewal fails.
    """

    def __init__(
        self,
        lease_id: UUID,
        lease_duration: float,
        raise_on_lease_renewal_failure: bool = False,
        suppress_warnings: bool = False,
    ) -> None:
        self._lease_id = lease_id
        self._lease_duration = lease_duration
        self._raise_on_failure = raise_on_lease_renewal_failure
        self._suppress_warnings = suppress_warnings

    def __enter__(self) -> None:
        self._stop_event = threading.Event()
        self._caller_ready = threading.Event()
        self._failure_exc: list[BaseException] = []

        # Capture caller context for mid-execution interruption in strict mode
        self._caller_thread = threading.current_thread()
        self._caller_loop = get_running_loop()

        # For async callers, use an AsyncCancelScope so cancellation is persistent:
        # once cancelled, ALL subsequent awaits raise CancelledError, even if
        # user code catches the first one.
        self._cancel_scope: AsyncCancelScope | None = None
        if self._caller_loop is not None:
            self._cancel_scope = AsyncCancelScope()
            self._cancel_scope.__enter__()

        # Snapshot the caller's contextvars so the daemon thread inherits
        # SettingsContext, SyncClientContext, etc.  Without this, get_client()
        # in the thread would fall back to default/environment settings.
        ctx = contextvars.copy_context()

        self._thread = threading.Thread(
            target=ctx.run,
            args=(self._renewal_loop,),
            daemon=True,
            name=f"lease-renewal-{self._lease_id}",
        )
        self._thread.start()

        # Signal that the caller is now inside the protected block
        self._caller_ready.set()
        return None

    def __exit__(
        self,
        typ: type[BaseException] | None,
        value: BaseException | None,
        traceback: object,
    ) -> bool:
        is_interrupt = typ is not None and issubclass(typ, _LeaseRenewalInterrupt)

        try:
            self._stop_event.set()
            # Also signal caller_ready in case we exit before the protected
            # block (e.g. exception during setup) so the daemon thread
            # doesn't block forever.
            self._caller_ready.set()

            if self._caller_loop is None:
                # Sync caller: safe to block on join
                self._thread.join(timeout=2)
            # Async caller: skip join to avoid blocking the event loop.
            # stop_event signals the daemon thread to exit at its next
            # stop_event.wait() check; the daemon flag ensures process cleanup.

            if self._failure_exc:
                exc = self._failure_exc[0]

                # Exit the cancel scope before raising. Suppress its bare
                # CancelledError — we'll either raise a more informative one
                # (strict) or intentionally continue (non-strict).
                if self._cancel_scope is not None:
                    try:
                        self._cancel_scope.__exit__(None, None, None)
                    except CancelledError:
                        pass

                if self._raise_on_failure:
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
                if self._cancel_scope is not None:
                    if is_interrupt:
                        self._cancel_scope.__exit__(None, None, None)
                    else:
                        self._cancel_scope.__exit__(typ, value, traceback)
        except _LeaseRenewalInterrupt:
            # The daemon thread's async exception can fire at any bytecode
            # boundary in this __exit__ (observed on CPython 3.13).
            # Ensure cleanup and convert to the expected CancelledError.
            self._stop_event.set()
            self._caller_ready.set()
            if self._failure_exc and self._raise_on_failure:
                raise CancelledError(
                    "Concurrency lease renewal failed"
                ) from self._failure_exc[0]

        # Suppress _LeaseRenewalInterrupt — it's an internal mechanism
        return is_interrupt

    def _interrupt_caller(self) -> None:
        """Interrupt the protected code when strict-mode lease renewal fails."""
        if self._stop_event.is_set():
            # Context is exiting normally; don't inject an exception
            return

        if self._cancel_scope is not None:
            # Async caller: cancel the scope. AsyncCancelScope.cancel()
            # handles cross-thread dispatch internally via
            # loop.call_soon_threadsafe.
            self._cancel_scope.cancel()
        else:
            # Sync caller: inject exception into the caller's thread
            try:
                _send_exception_to_thread(self._caller_thread, _LeaseRenewalInterrupt)
            except ValueError:
                # Thread is gone
                pass

    def _log_non_strict_failure(self, exc: BaseException) -> None:
        """Log lease-renewal failure immediately from the renewal thread."""
        try:
            _logger = get_run_logger()
        except Exception:
            _logger = get_logger("concurrency")
        msg = (
            "Concurrency lease renewal failed - slots are no longer reserved. "
            "Execution will continue, but concurrency limits may be exceeded."
        )
        if self._suppress_warnings:
            _logger.debug(msg, exc_info=(type(exc), exc, exc.__traceback__))
        else:
            _logger.warning(msg, exc_info=(type(exc), exc, exc.__traceback__))

    def _renewal_loop(self) -> None:
        # Wait until the caller has entered the protected block.
        # Without this gate, _send_exception_to_thread can fire during
        # thread.start() before the caller's with block is even entered.
        self._caller_ready.wait()

        try:
            with get_client(sync_client=True) as client:
                while not self._stop_event.is_set():
                    last_exc: BaseException | None = None
                    for attempt in range(3):
                        try:
                            client.renew_concurrency_lease(
                                lease_id=self._lease_id,
                                lease_duration=self._lease_duration,
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
                                if self._stop_event.wait(delay):
                                    return
                            else:
                                internal_logger.exception(
                                    "Function 'concurrency lease renewal' failed after 3 attempts"
                                )

                    if last_exc is not None:
                        self._failure_exc.append(last_exc)
                        if self._raise_on_failure:
                            self._interrupt_caller()
                        else:
                            self._log_non_strict_failure(last_exc)
                        return

                    # Sleep for 75% of the lease duration before next renewal
                    if self._stop_event.wait(self._lease_duration * _RENEWAL_FRACTION):
                        return
        except Exception as exc:
            # Catch client startup failures or any other unexpected error
            # not already handled by the retry loop above.
            if exc not in self._failure_exc:
                self._failure_exc.append(exc)
                if self._raise_on_failure:
                    self._interrupt_caller()
                else:
                    self._log_non_strict_failure(exc)
