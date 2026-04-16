import asyncio
import concurrent.futures
from unittest import mock
from uuid import uuid4

import httpx
import pytest

from prefect.concurrency._leases import (
    _AsyncLeaseRenewer,
    _lease_renewal_loop,
    _SyncLeaseRenewer,
)


def _make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://test/leases/renew")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"{status_code}", request=request, response=response)


async def test_lease_renewal_loop_renews_lease():
    mock_client = mock.AsyncMock()
    mock_client.renew_concurrency_lease.side_effect = [
        None,
        None,
        asyncio.CancelledError(),
    ]

    with (
        mock.patch("prefect.concurrency._leases.get_client") as mock_get_client,
        mock.patch("asyncio.sleep", new_callable=mock.AsyncMock),
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        with pytest.raises(asyncio.CancelledError):
            await _lease_renewal_loop(lease_id=uuid4(), lease_duration=10.0)

    assert mock_client.renew_concurrency_lease.call_count == 3


async def test_lease_renewal_loop_retries_on_transient_failure():
    mock_client = mock.AsyncMock()
    mock_client.renew_concurrency_lease.side_effect = [
        RuntimeError("transient"),
        None,  # retry succeeds within first renew() call
        asyncio.CancelledError(),
    ]

    with (
        mock.patch("prefect.concurrency._leases.get_client") as mock_get_client,
        mock.patch("asyncio.sleep", new_callable=mock.AsyncMock),
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        with pytest.raises(asyncio.CancelledError):
            await _lease_renewal_loop(lease_id=uuid4(), lease_duration=10.0)

    assert mock_client.renew_concurrency_lease.call_count == 3


async def test_lease_renewal_loop_raises_after_max_retry_attempts():
    mock_client = mock.AsyncMock()
    mock_client.renew_concurrency_lease.side_effect = RuntimeError("server down")

    with (
        mock.patch("prefect.concurrency._leases.get_client") as mock_get_client,
        mock.patch("asyncio.sleep", new_callable=mock.AsyncMock),
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        with pytest.raises(RuntimeError, match="server down"):
            await _lease_renewal_loop(lease_id=uuid4(), lease_duration=10.0)

    # retry_async_fn with max_attempts=3 tries exactly 3 times
    assert mock_client.renew_concurrency_lease.call_count == 3


async def test_lease_renewal_loop_does_not_retry_on_410():
    """A 410 response raises httpx.HTTPStatusError immediately without any retries."""
    mock_client = mock.AsyncMock()
    mock_client.renew_concurrency_lease.side_effect = _make_http_status_error(410)

    with (
        mock.patch("prefect.concurrency._leases.get_client") as mock_get_client,
        mock.patch("asyncio.sleep", new_callable=mock.AsyncMock),
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await _lease_renewal_loop(lease_id=uuid4(), lease_duration=10.0)

    assert exc_info.value.response.status_code == 410
    # No retries — called exactly once
    assert mock_client.renew_concurrency_lease.call_count == 1


async def test_lease_renewal_loop_retries_on_non_410_http_error():
    """Non-410 HTTP errors (e.g. 500) are retried up to 3 times like any other Exception."""
    mock_client = mock.AsyncMock()
    mock_client.renew_concurrency_lease.side_effect = _make_http_status_error(500)

    with (
        mock.patch("prefect.concurrency._leases.get_client") as mock_get_client,
        mock.patch("asyncio.sleep", new_callable=mock.AsyncMock),
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        with pytest.raises(httpx.HTTPStatusError):
            await _lease_renewal_loop(lease_id=uuid4(), lease_duration=10.0)

    # Retried up to max_attempts=3
    assert mock_client.renew_concurrency_lease.call_count == 3


def test_sync_lease_renewer_stop_swallows_completed_failure():
    future: concurrent.futures.Future[None] = concurrent.futures.Future()
    future.set_exception(RuntimeError("server down"))
    lease_renewal_call = mock.Mock()
    lease_renewal_call.future = future

    renewer = _SyncLeaseRenewer(lease_renewal_call=lease_renewal_call)

    renewer.stop()

    lease_renewal_call.cancel.assert_called_once_with()
    assert renewer.stopped is True


async def test_async_lease_renewer_stop_swallows_completed_failure():
    async def fail() -> None:
        raise RuntimeError("server down")

    task = asyncio.create_task(fail())
    await asyncio.sleep(0)

    renewer = _AsyncLeaseRenewer(lease_renewal_task=task)

    await renewer.stop()

    assert renewer.stopped is True
