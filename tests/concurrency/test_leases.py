import asyncio
import logging
import time
from contextlib import contextmanager
from unittest import mock
from uuid import uuid4

import pytest

from prefect._internal.concurrency.cancellation import CancelledError
from prefect.concurrency._leases import (
    amaintain_concurrency_lease,
    maintain_concurrency_lease,
)


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

    with _patch_renewal_client(mock_client):
        with caplog.at_level(logging.WARNING):
            with maintain_concurrency_lease(
                lease_id=uuid4(),
                lease_duration=60,
                raise_on_lease_renewal_failure=False,
            ):
                assert _wait_for(
                    lambda: mock_client.renew_concurrency_lease.call_count == 3
                )
                continued_after_failure = True

    assert continued_after_failure is True
    assert mock_client.renew_concurrency_lease.call_count == 3
    assert (
        caplog.text.count(
            "Concurrency lease renewal failed - slots are no longer reserved."
        )
        == 1
    )


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
