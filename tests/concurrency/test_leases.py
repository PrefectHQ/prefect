import asyncio
from unittest import mock
from uuid import uuid4

import pytest

from prefect.concurrency._leases import _lease_renewal_loop


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
