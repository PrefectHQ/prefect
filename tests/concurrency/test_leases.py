import asyncio
import logging
import threading
import time
from contextlib import contextmanager
from unittest import mock
from uuid import UUID, uuid4

import httpx
import pytest

from prefect import flow
from prefect._internal.concurrency.cancellation import CancelledError
from prefect.concurrency._leases import (
    amaintain_concurrency_lease,
    maintain_concurrency_lease,
)
from prefect.states import Completed, Running, State

pytestmark = pytest.mark.clear_db


@contextmanager
def _mock_client_context(mock_client: mock.MagicMock):
    yield mock_client


@contextmanager
def _patch_renewal_client(mock_client: mock.MagicMock):
    with mock.patch(
        "prefect.concurrency._leases.get_client",
        side_effect=lambda *, sync_client: _mock_client_context(mock_client),
    ) as patched:
        yield patched


def _zero_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    return 0.0


def _wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def _lease_gone() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://prefect.test/api/leases/renew")
    return httpx.HTTPStatusError(
        "410 Gone", request=request, response=httpx.Response(410, request=request)
    )


def _renewal_thread_finished(lease_id: UUID) -> bool:
    return not any(
        thread.name == f"concurrency-lease-renewal-{lease_id}"
        for thread in threading.enumerate()
    )


def test_maintain_concurrency_lease_renews_lease():
    mock_client = mock.MagicMock()
    lease_id = uuid4()

    with _patch_renewal_client(mock_client) as patched_get_client:
        with maintain_concurrency_lease(lease_id=lease_id, lease_duration=0.05):
            assert _wait_for(
                lambda: mock_client.renew_concurrency_lease.call_count >= 2
            )

    patched_get_client.assert_called_once_with(sync_client=True)
    mock_client.renew_concurrency_lease.assert_called_with(
        lease_id=lease_id, lease_duration=0.05
    )


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_lease_renewal_retries_on_transient_failure():
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = [RuntimeError("transient"), None]

    with _patch_renewal_client(mock_client):
        with maintain_concurrency_lease(lease_id=uuid4(), lease_duration=60):
            assert _wait_for(
                lambda: mock_client.renew_concurrency_lease.call_count >= 2
            )

    assert mock_client.renew_concurrency_lease.call_count == 2


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_lease_renewal_logs_once_after_max_retries_non_strict(
    caplog: pytest.LogCaptureFixture,
):
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")
    continued_after_failure = False
    failure_message = "Concurrency lease renewal failed - slots are no longer reserved."

    with _patch_renewal_client(mock_client):
        with caplog.at_level(logging.WARNING):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=60,
                raise_on_lease_renewal_failure=False,
            ):
                assert _wait_for(lambda: caplog.text.count(failure_message) == 1)
                continued_after_failure = True

    assert continued_after_failure is True
    assert mock_client.renew_concurrency_lease.call_count == 3
    assert caplog.text.count(failure_message) == 1


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_maintain_concurrency_lease_handles_failure_strict():
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")

    with _patch_renewal_client(mock_client):
        with pytest.raises(CancelledError):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=60,
                raise_on_lease_renewal_failure=True,
            ):
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    time.sleep(0.01)
                raise AssertionError("Strict lease renewal failure did not cancel")


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
async def test_amaintain_concurrency_lease_handles_failure_strict():
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")

    with _patch_renewal_client(mock_client):
        with pytest.raises(asyncio.CancelledError):
            async with amaintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=60,
                raise_on_lease_renewal_failure=True,
            ):
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    await asyncio.sleep(0.01)
                raise AssertionError("Strict lease renewal failure did not cancel")


async def test_lease_renewal_fires_when_event_loop_blocked():
    mock_client = mock.MagicMock()

    with _patch_renewal_client(mock_client):
        async with amaintain_concurrency_lease(
            lease_id=uuid4(),
            lease_duration=0.05,
        ):
            deadline = time.monotonic() + 0.25
            while time.monotonic() < deadline:
                pass

    assert mock_client.renew_concurrency_lease.call_count >= 2


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_lease_renewal_failure_logs_via_run_logger_in_flow_context(
    caplog: pytest.LogCaptureFixture,
):
    """The failure message should reach the run logger (and thus the run logs API)
    when the lease is maintained from within a flow context, not fall back to the
    plain "prefect.concurrency" logger.

    Regression test for the contextvar copy in _start_lease_renewal_thread: the
    failure handler must run inside renewal_ctx so get_run_logger() resolves to
    the parent flow's FlowRunContext.
    """
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")
    failure_message = "Concurrency lease renewal failed - slots are no longer reserved."

    @flow
    def host_flow() -> None:
        with _patch_renewal_client(mock_client):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=60,
                raise_on_lease_renewal_failure=False,
            ):
                assert _wait_for(lambda: caplog.text.count(failure_message) == 1)

    with caplog.at_level(logging.WARNING):
        host_flow()

    failure_records = [
        record for record in caplog.records if failure_message in record.getMessage()
    ]
    assert failure_records, "expected a lease renewal failure log record"
    # If the handler runs outside the copied context, get_run_logger() raises
    # MissingContextError and the fallback emits via "prefect.concurrency".
    assert any(record.name == "prefect.flow_runs" for record in failure_records), (
        f"failure log did not reach the run logger; got loggers="
        f"{[r.name for r in failure_records]}"
    )


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
def test_lease_gone_does_not_cancel_when_flow_run_is_final():
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = _lease_gone()
    mock_client.read_flow_run.return_value.state = Completed()
    lease_id = uuid4()
    flow_run_id = uuid4()

    with _patch_renewal_client(mock_client):
        with maintain_concurrency_lease(
            lease_id=lease_id,
            lease_duration=60,
            raise_on_lease_renewal_failure=True,
            flow_run_id=flow_run_id,
        ):
            assert _wait_for(lambda: _renewal_thread_finished(lease_id))

    assert mock_client.renew_concurrency_lease.call_count == 3
    mock_client.read_flow_run.assert_called_once_with(flow_run_id)


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
async def test_alease_gone_does_not_cancel_when_flow_run_is_final():
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = _lease_gone()
    mock_client.read_flow_run.return_value.state = Completed()
    lease_id = uuid4()
    flow_run_id = uuid4()

    with _patch_renewal_client(mock_client):
        async with amaintain_concurrency_lease(
            lease_id=lease_id,
            lease_duration=60,
            raise_on_lease_renewal_failure=True,
            flow_run_id=flow_run_id,
        ):
            await asyncio.to_thread(
                _wait_for, lambda: _renewal_thread_finished(lease_id)
            )
            # A cancellation requested by the renewal thread would be delivered here
            await asyncio.sleep(0.1)

    assert mock_client.renew_concurrency_lease.call_count == 3
    mock_client.read_flow_run.assert_called_once_with(flow_run_id)


@pytest.mark.parametrize(
    "flow_run_state, renewal_error",
    [
        pytest.param(Running(), _lease_gone(), id="lease-gone-flow-run-running"),
        pytest.param(Completed(), RuntimeError("server down"), id="other-failure"),
    ],
)
@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
async def test_lease_renewal_failure_cancels_unless_flow_run_released_lease(
    flow_run_state: State, renewal_error: Exception
):
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = renewal_error
    mock_client.read_flow_run.return_value.state = flow_run_state

    with _patch_renewal_client(mock_client):
        with pytest.raises(asyncio.CancelledError):
            async with amaintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=60,
                raise_on_lease_renewal_failure=True,
                flow_run_id=uuid4(),
            ):
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    await asyncio.sleep(0.01)
                raise AssertionError("Lease renewal failure did not cancel")


@mock.patch(
    "prefect.concurrency._leases.exponential_backoff_with_jitter", _zero_backoff
)
async def test_lease_gone_cancels_when_flow_run_cannot_be_read():
    mock_client = mock.MagicMock()
    mock_client.renew_concurrency_lease.side_effect = _lease_gone()
    mock_client.read_flow_run.side_effect = RuntimeError("server down")

    with _patch_renewal_client(mock_client):
        with pytest.raises(asyncio.CancelledError):
            async with amaintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=60,
                raise_on_lease_renewal_failure=True,
                flow_run_id=uuid4(),
            ):
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    await asyncio.sleep(0.01)
                raise AssertionError("Lease renewal failure did not cancel")
