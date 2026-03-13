import asyncio
from unittest import mock
from uuid import uuid4

import httpx
import pytest

from prefect.concurrency._leases import _lease_renewal_loop, _LeaseGoneError


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


async def test_lease_renewal_loop_raises_lease_gone_on_410():
    """A 410 response raises _LeaseGoneError immediately without any retries."""
    mock_client = mock.AsyncMock()
    mock_client.renew_concurrency_lease.side_effect = _make_http_status_error(410)

    with (
        mock.patch("prefect.concurrency._leases.get_client") as mock_get_client,
        mock.patch("asyncio.sleep", new_callable=mock.AsyncMock),
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        with pytest.raises(_LeaseGoneError):
            await _lease_renewal_loop(lease_id=uuid4(), lease_duration=10.0)

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


async def test_lease_renewal_loop_exits_cleanly_when_should_stop():
    """If should_stop() is True from the start, the loop exits without making any requests."""
    mock_client = mock.AsyncMock()
    mock_client.renew_concurrency_lease.side_effect = _make_http_status_error(410)

    with (
        mock.patch("prefect.concurrency._leases.get_client") as mock_get_client,
        mock.patch("asyncio.sleep", new_callable=mock.AsyncMock),
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        await _lease_renewal_loop(
            lease_id=uuid4(), lease_duration=10.0, should_stop=lambda: True
        )

    assert mock_client.renew_concurrency_lease.call_count == 0
