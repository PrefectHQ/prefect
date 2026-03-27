from __future__ import annotations

import asyncio
import contextvars
import logging
import sys
import threading
import time
from contextlib import contextmanager
from unittest import mock
from uuid import uuid4

import pytest

from prefect._internal.concurrency.cancellation import CancelledError
from prefect.concurrency._leases import maintain_concurrency_lease


@contextmanager
def _mock_sync_client(mock_client: mock.MagicMock):
    """Patch get_client(sync_client=True) to return a mock sync client."""
    with mock.patch("prefect.concurrency._leases.get_client") as mock_get_client:
        mock_get_client.return_value.__enter__ = mock.MagicMock(
            return_value=mock_client
        )
        mock_get_client.return_value.__exit__ = mock.MagicMock(return_value=False)
        yield mock_get_client


def _zero_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    return 0.0


def test_maintain_concurrency_lease_renews_lease():
    mock_client = mock.MagicMock()

    with _mock_sync_client(mock_client):
        lease_id = uuid4()
        # Use a very short lease duration so the renewal fires quickly
        with maintain_concurrency_lease(
            lease_id=lease_id,
            lease_duration=0.1,
        ):
            # Wait long enough for at least 2 renewals (0.075s interval)
            time.sleep(0.3)

    assert mock_client.renew_concurrency_lease.call_count >= 2
    mock_client.renew_concurrency_lease.assert_called_with(
        lease_id=lease_id, lease_duration=0.1
    )


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_maintain_concurrency_lease_handles_failure_strict():
    """Strict mode raises CancelledError (a BaseException) so the flow engine
    routes it through the crash path, not normal exception handling."""
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")

    with _mock_sync_client(mock_client):
        with pytest.raises(CancelledError, match="Concurrency lease renewal failed"):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=0.1,
                raise_on_lease_renewal_failure=True,
            ):
                # On Python < 3.13, the async exception interrupts the busy-wait.
                # On Python >= 3.13, PyThreadState_SetAsyncExc is unreliable,
                # so the loop runs to completion and __exit__ raises CancelledError.
                end = time.monotonic() + 0.5
                while time.monotonic() < end:
                    pass


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_maintain_concurrency_lease_handles_failure_non_strict(
    caplog: pytest.LogCaptureFixture,
):
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")
    warning_seen = threading.Event()

    with _mock_sync_client(mock_client):
        # Should NOT raise
        with caplog.at_level(logging.WARNING):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=0.1,
                raise_on_lease_renewal_failure=False,
            ):
                # The warning should appear while the protected code is still running,
                # not after the context manager exits.
                end = time.monotonic() + 5.0
                while time.monotonic() < end:
                    if "Concurrency lease renewal failed" in caplog.text:
                        warning_seen.set()
                        break
                    time.sleep(0.05)

    assert warning_seen.is_set(), (
        "Warning should have been logged during the protected block, not after"
    )


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_maintain_concurrency_lease_retries_on_transient_failure():
    mock_client = mock.MagicMock()
    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient")
        return None

    mock_client.renew_concurrency_lease.side_effect = side_effect

    with _mock_sync_client(mock_client):
        with maintain_concurrency_lease(
            lease_id=uuid4(),
            lease_duration=0.1,
        ):
            # Wait for at least the retry + one more renewal
            time.sleep(0.5)

    # First attempt failed, second succeeded (retry), then more renewals
    assert mock_client.renew_concurrency_lease.call_count >= 3


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_maintain_concurrency_lease_raises_after_max_retries():
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")

    with _mock_sync_client(mock_client):
        with pytest.raises(CancelledError, match="Concurrency lease renewal failed"):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=0.1,
                raise_on_lease_renewal_failure=True,
            ):
                end = time.monotonic() + 0.5
                while time.monotonic() < end:
                    pass

    # 3 attempts (max retries)
    assert mock_client.renew_concurrency_lease.call_count == 3


@pytest.mark.skipif(
    sys.version_info >= (3, 13),
    reason="PyThreadState_SetAsyncExc cannot reliably interrupt threads on 3.13+",
)
@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_strict_mode_interrupts_protected_code():
    """When strict mode detects lease failure, protected code is interrupted
    before it completes naturally.

    Skipped on Python 3.13+ where PyThreadState_SetAsyncExc-injected exceptions
    bypass exception handlers. On those versions, __exit__ raises CancelledError
    when the with-block exits naturally (tested by the other strict-mode tests).
    """
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")
    completed = threading.Event()

    with _mock_sync_client(mock_client):
        with pytest.raises(CancelledError, match="Concurrency lease renewal failed"):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=0.1,
                raise_on_lease_renewal_failure=True,
            ):
                # Long-running work that should be interrupted
                end = time.monotonic() + 10.0
                while time.monotonic() < end:
                    pass
                completed.set()  # Should NOT be reached

    assert not completed.is_set(), "Protected code should have been interrupted"


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
async def test_strict_mode_interrupts_async_caller():
    """When strict mode detects lease failure, async protected code is
    interrupted with CancelledError (not RuntimeError) so the flow engine's
    crash path handles it correctly."""
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")
    completed = False

    with _mock_sync_client(mock_client):
        with pytest.raises(asyncio.CancelledError):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=0.1,
                raise_on_lease_renewal_failure=True,
            ):
                # Async work with checkpoints where CancelledError can fire
                for _ in range(100):
                    await asyncio.sleep(0.1)
                completed = True

    assert not completed, "Protected async code should have been interrupted"


async def test_lease_renewal_fires_when_event_loop_blocked():
    """Regression test: lease renewal must fire even when the event loop is blocked."""
    mock_client = mock.MagicMock()

    with _mock_sync_client(mock_client):
        with maintain_concurrency_lease(
            lease_id=uuid4(),
            lease_duration=0.2,
        ):
            # Block the event loop with CPU-bound work
            end = time.monotonic() + 1.0
            while time.monotonic() < end:
                pass  # busy-wait blocks the event loop

    # Daemon thread should have renewed multiple times despite the blocked loop
    assert mock_client.renew_concurrency_lease.call_count >= 3


def test_renewal_thread_inherits_caller_context():
    """The daemon thread must see the caller's contextvars (settings, client context)."""
    test_var: contextvars.ContextVar[str] = contextvars.ContextVar(
        "test_var", default="unset"
    )
    test_var.set("caller_value")
    observed_values: list[str] = []

    mock_client = mock.MagicMock()

    def capture_context(**kwargs):
        observed_values.append(test_var.get())

    mock_client.renew_concurrency_lease.side_effect = capture_context

    with _mock_sync_client(mock_client):
        with maintain_concurrency_lease(
            lease_id=uuid4(),
            lease_duration=0.1,
        ):
            time.sleep(0.2)

    assert observed_values, "Renewal should have fired at least once"
    assert all(v == "caller_value" for v in observed_values), (
        f"Thread should see caller's contextvar, got: {observed_values}"
    )


async def test_async_caller_does_not_block_on_join():
    """The finally block should not call thread.join() when the caller is async,
    avoiding a 2-second event loop block."""
    mock_client = mock.MagicMock()

    with _mock_sync_client(mock_client):
        start = time.monotonic()
        with maintain_concurrency_lease(
            lease_id=uuid4(),
            lease_duration=10.0,  # Long duration so thread is still sleeping
        ):
            pass  # Exit immediately
        elapsed = time.monotonic() - start

    # Should complete much faster than 2 seconds (the join timeout)
    assert elapsed < 0.5, f"Exit took {elapsed:.2f}s, expected < 0.5s"


def test_client_startup_failure_surfaces_in_strict_mode():
    """If get_client() raises during thread startup, strict mode should still
    cancel the protected code — the failure must not be silently swallowed."""
    with mock.patch(
        "prefect.concurrency._leases.get_client",
        side_effect=RuntimeError("connection refused"),
    ):
        with pytest.raises(CancelledError, match="Concurrency lease renewal failed"):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=0.1,
                raise_on_lease_renewal_failure=True,
            ):
                # On Python < 3.13, the async exception interrupts the loop.
                # On Python >= 3.13, the loop completes and __exit__ raises.
                end = time.monotonic() + 0.5
                while time.monotonic() < end:
                    pass


def test_client_startup_failure_logs_in_non_strict_mode(
    caplog: pytest.LogCaptureFixture,
):
    """If get_client() raises during thread startup, non-strict mode should
    log the failure immediately, while the protected code is still running."""
    warning_seen = threading.Event()

    with mock.patch(
        "prefect.concurrency._leases.get_client",
        side_effect=RuntimeError("connection refused"),
    ):
        with caplog.at_level(logging.WARNING):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=0.1,
                raise_on_lease_renewal_failure=False,
            ):
                end = time.monotonic() + 5.0
                while time.monotonic() < end:
                    if "Concurrency lease renewal failed" in caplog.text:
                        warning_seen.set()
                        break
                    time.sleep(0.05)

    assert warning_seen.is_set(), (
        "Warning should have been logged during the protected block, not after"
    )


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
async def test_async_strict_cancellation_is_persistent():
    """AsyncCancelScope keeps the scope cancelled — even if user code catches
    the first CancelledError, subsequent awaits must also raise.  The final
    error must be the informative CancelledError("Concurrency lease renewal
    failed"), not a bare CancelledError from the scope's __exit__."""
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")
    caught_first = False
    second_await_raised = False

    with _mock_sync_client(mock_client):
        with pytest.raises(CancelledError, match="Concurrency lease renewal failed"):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=0.1,
                raise_on_lease_renewal_failure=True,
            ):
                # Wait for the cancellation to fire
                try:
                    for _ in range(100):
                        await asyncio.sleep(0.1)
                except (asyncio.CancelledError, CancelledError):
                    caught_first = True

                # User code swallowed the error and tries to continue.
                # The cancel scope must re-raise on the next await.
                try:
                    await asyncio.sleep(0)
                except (asyncio.CancelledError, CancelledError):
                    second_await_raised = True

    assert caught_first, "First CancelledError should have been caught by user code"
    assert second_await_raised, (
        "Second await should also raise CancelledError (scope stays cancelled)"
    )


def test_renewal_uses_async_client_api_url():
    """When only an AsyncClientContext exists (no SyncClientContext), get_client
    with sync_client=True should create a SyncPrefectClient using the async
    client's API URL."""
    mock_async_client = mock.MagicMock()
    mock_async_client.api_url = "http://custom-server:4200/api"
    mock_async_client.server_type = None
    mock_async_client._ephemeral_app = None

    mock_async_ctx = mock.MagicMock()
    mock_async_ctx.client = mock_async_client
    mock_async_ctx._httpx_settings = None

    with (
        mock.patch("prefect.context.SyncClientContext.get", return_value=None),
        mock.patch(
            "prefect.context.AsyncClientContext.get", return_value=mock_async_ctx
        ),
        mock.patch("prefect.client.orchestration.SyncPrefectClient") as mock_sync_cls,
        mock.patch("prefect.client.orchestration.PREFECT_API_AUTH_STRING") as mock_auth,
        mock.patch("prefect.client.orchestration.PREFECT_API_KEY") as mock_key,
    ):
        mock_auth.value.return_value = None
        mock_key.value.return_value = None

        from prefect.client.orchestration import get_client

        result = get_client(sync_client=True)

        mock_sync_cls.assert_called_once_with(
            "http://custom-server:4200/api",
            auth_string=None,
            api_key=None,
            httpx_settings=None,
            server_type=None,
        )
        assert result is mock_sync_cls.return_value


def test_get_client_raises_for_ephemeral_async_client():
    """When the async client uses in-process ASGI transport (_ephemeral_app),
    get_client(sync_client=True) should raise RuntimeError instead of silently
    creating a client against a different backend."""
    mock_async_client = mock.MagicMock()
    mock_async_client.api_url = "http://ephemeral-prefect/api"
    mock_async_client._ephemeral_app = mock.MagicMock()  # has ASGI app

    mock_async_ctx = mock.MagicMock()
    mock_async_ctx.client = mock_async_client

    with (
        mock.patch("prefect.context.SyncClientContext.get", return_value=None),
        mock.patch(
            "prefect.context.AsyncClientContext.get", return_value=mock_async_ctx
        ),
    ):
        from prefect.client.orchestration import get_client

        with pytest.raises(RuntimeError, match="Cannot create a sync client"):
            get_client(sync_client=True)
