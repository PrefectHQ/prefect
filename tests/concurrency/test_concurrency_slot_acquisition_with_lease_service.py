"""Tests for ConcurrencySlotAcquisitionWithLeaseService."""

import asyncio
from concurrent.futures import Future
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
from httpx import HTTPStatusError, Request, Response

from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import ConcurrencyLeaseHolder
from prefect.concurrency.services import ConcurrencySlotAcquisitionWithLeaseService


class ClientWrapper:
    """Wrapper to make mocked client work with async context manager."""

    def __init__(self, client: PrefectClient):
        self.client = client

    async def __aenter__(self) -> PrefectClient:
        return self.client

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.fixture
async def mocked_client(test_database_connection_url: str) -> Any:
    """Fixture providing a mocked client with increment_concurrency_slots_with_lease patched."""
    async with get_client() as client:
        with mock.patch.object(
            client, "increment_concurrency_slots_with_lease", autospec=True
        ):
            wrapped_client = ClientWrapper(client)
            with mock.patch(
                "prefect.concurrency.services.get_client", lambda: wrapped_client
            ):
                yield wrapped_client


async def test_returns_successful_response(mocked_client: Any) -> None:
    """Test that the service returns a successful response with lease information."""
    lease_id = uuid4()
    response_data = {
        "lease_id": str(lease_id),
        "limits": [{"id": str(uuid4()), "name": "test-limit", "limit": 10}],
    }
    response = Response(200, json=response_data)

    mocked_method = mocked_client.client.increment_concurrency_slots_with_lease
    mocked_method.return_value = response

    expected_names = sorted(["tag:test"])
    expected_slots = 1
    expected_mode = "concurrency"
    expected_lease_duration = 60.0
    expected_holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())

    service = ConcurrencySlotAcquisitionWithLeaseService.instance(
        frozenset(expected_names)
    )
    future: Future[Response] = service.send(
        (
            expected_slots,
            expected_mode,
            None,  # timeout_seconds
            None,  # max_retries
            expected_lease_duration,
            False,  # strict
            expected_holder,
        )
    )
    await service.drain()
    returned_response = await asyncio.wrap_future(future)
    assert returned_response == response

    mocked_method.assert_called_once_with(
        names=expected_names,
        slots=expected_slots,
        mode=expected_mode,
        lease_duration=expected_lease_duration,
        holder=expected_holder,
    )


async def test_retries_failed_call_respects_retry_after_header(
    mocked_client: Any,
) -> None:
    """Test that the service respects Retry-After headers on 423 responses."""
    lease_id = uuid4()
    responses = [
        HTTPStatusError(
            "Limit is locked",
            request=Request("post", "/v2/concurrency_limits/increment-with-lease"),
            response=Response(423, headers={"Retry-After": "10"}),
        ),
        Response(
            200,
            json={
                "lease_id": str(lease_id),
                "limits": [{"id": str(uuid4()), "name": "tag:test", "limit": 10}],
            },
        ),
    ]

    mocked_client.client.increment_concurrency_slots_with_lease.side_effect = responses

    limit_names = sorted(["tag:test"])
    service = ConcurrencySlotAcquisitionWithLeaseService.instance(
        frozenset(limit_names)
    )

    with mock.patch("asyncio.sleep") as sleep:
        future: Future[Response] = service.send(
            (
                1,  # slots
                "concurrency",  # mode
                None,  # timeout_seconds
                None,  # max_retries
                60.0,  # lease_duration
                False,  # strict
                None,  # holder
            )
        )
        await service.drain()
        returned_response = await asyncio.wrap_future(future)

        assert returned_response == responses[1]

        # Verify sleep was called with the Retry-After value
        sleep.assert_called_once_with(
            float(responses[0].response.headers["Retry-After"])
        )
        assert (
            mocked_client.client.increment_concurrency_slots_with_lease.call_count == 2
        )


async def test_failed_call_status_code_not_retryable_returns_exception(
    mocked_client: Any,
) -> None:
    """Test that non-423 errors are not retried and are returned as exceptions."""
    response = HTTPStatusError(
        "Internal server error",
        request=Request("post", "/v2/concurrency_limits/increment-with-lease"),
        response=Response(500, headers={"Retry-After": "2"}),
    )

    mocked_client.client.increment_concurrency_slots_with_lease.side_effect = response

    limit_names = sorted(["tag:test"])
    service = ConcurrencySlotAcquisitionWithLeaseService.instance(
        frozenset(limit_names)
    )

    future: Future[Response] = service.send(
        (1, "concurrency", None, None, 60.0, False, None)
    )
    await service.drain()

    with pytest.raises(HTTPStatusError) as exc_info:
        await asyncio.wrap_future(future)

    assert exc_info.value == response


async def test_max_retries_honored(mocked_client: Any) -> None:
    """Test that max_retries limit is respected and acquisition stops after exhausting retries."""
    responses = [
        HTTPStatusError(
            "Limit is locked",
            request=Request("post", "/v2/concurrency_limits/increment-with-lease"),
            response=Response(423, headers={"Retry-After": "1"}),
        )
    ] * 5  # More 423s than max_retries

    mocked_client.client.increment_concurrency_slots_with_lease.side_effect = responses

    limit_names = sorted(["tag:test"])
    service = ConcurrencySlotAcquisitionWithLeaseService.instance(
        frozenset(limit_names)
    )

    with mock.patch("asyncio.sleep"):
        future: Future[Response] = service.send(
            (
                1,  # slots
                "concurrency",  # mode
                None,  # timeout_seconds
                2,  # max_retries - only allow 2 retries
                60.0,  # lease_duration
                False,  # strict
                None,  # holder
            )
        )
        await service.drain()

        # Should get an exception after max_retries is exhausted
        with pytest.raises(HTTPStatusError):
            await asyncio.wrap_future(future)

        # Should have called increment 3 times (initial + 2 retries)
        assert (
            mocked_client.client.increment_concurrency_slots_with_lease.call_count == 3
        )


async def test_basic_exception_returns_exception(mocked_client: Any) -> None:
    """Test that basic exceptions are propagated correctly."""
    exc = Exception("Something went wrong")
    mocked_client.client.increment_concurrency_slots_with_lease.side_effect = exc

    limit_names = sorted(["tag:test"])
    service = ConcurrencySlotAcquisitionWithLeaseService.instance(
        frozenset(limit_names)
    )

    future: Future[Response] = service.send(
        (1, "concurrency", None, None, 60.0, False, None)
    )
    await service.drain()

    with pytest.raises(Exception) as exc_info:
        await asyncio.wrap_future(future)

    assert exc_info.value == exc


async def test_singleton_per_limit_names(mocked_client: Any) -> None:
    """Test that the service is a singleton per unique set of limit names."""
    names_a = frozenset(["tag:test-a"])
    names_b = frozenset(["tag:test-b"])
    names_a_duplicate = frozenset(["tag:test-a"])

    service_a1 = ConcurrencySlotAcquisitionWithLeaseService.instance(names_a)
    service_a2 = ConcurrencySlotAcquisitionWithLeaseService.instance(names_a_duplicate)
    service_b = ConcurrencySlotAcquisitionWithLeaseService.instance(names_b)

    # Same limit names should return the same instance
    assert service_a1 is service_a2

    # Different limit names should return different instances
    assert service_a1 is not service_b
    assert service_a2 is not service_b


async def test_serialization_behavior(mocked_client: Any) -> None:
    """Test that multiple concurrent acquisitions are serialized through the service.

    This is the key test that validates the fix for the thundering herd issue.
    When multiple tasks try to acquire slots simultaneously, the service ensures
    they are processed one at a time rather than all hitting the server at once.
    """
    call_order: list[dict[str, int | None]] = []

    async def mock_increment(*args: Any, **kwargs: Any) -> Response:
        # Record when this call starts
        call_index = len(call_order)
        call_order.append({"start": call_index, "end": None})
        # Simulate some processing time
        await asyncio.sleep(0.01)
        # Record when this call ends
        call_order[-1]["end"] = len([c for c in call_order if c["end"] is not None])
        return Response(
            200,
            json={
                "lease_id": str(uuid4()),
                "limits": [{"id": str(uuid4()), "name": "tag:test", "limit": 10}],
            },
        )

    mocked_client.client.increment_concurrency_slots_with_lease.side_effect = (
        mock_increment
    )

    limit_names = frozenset(["tag:test"])
    service = ConcurrencySlotAcquisitionWithLeaseService.instance(limit_names)

    # Send 10 concurrent acquisition requests
    futures: list[Future[Response]] = []
    for i in range(10):
        future = service.send((1, "concurrency", None, None, 60.0, False, None))
        futures.append(future)

    # Wait for all acquisitions to complete
    await service.drain()
    responses = await asyncio.gather(*[asyncio.wrap_future(f) for f in futures])

    # Verify all succeeded
    assert len(responses) == 10
    assert all(r.status_code == 200 for r in responses)

    # Verify they were processed serially (no overlapping execution)
    # Each call should complete before the next one starts
    for i in range(len(call_order) - 1):
        # Current call's end index should be <= next call's start index
        # This proves serialization
        assert call_order[i]["end"] is not None
        assert call_order[i]["end"] <= len(
            [c for c in call_order[: i + 2] if c["end"] is not None]
        )
