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
from prefect.concurrency.services import (
    ConcurrencySlotAcquisitionWithLeaseService,
    _create_empty_limits_response,
    _no_limits_cache,
    _should_use_cache,
)


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


class TestShouldUseCache:
    """Tests for the _should_use_cache helper function."""

    def test_returns_false_when_holder_is_none(self) -> None:
        """Cache should not be used when holder is None."""
        assert _should_use_cache(["tag:test"], None) is False

    def test_returns_false_when_holder_type_is_not_task_run(self) -> None:
        """Cache should not be used when holder type is not 'task_run'."""
        holder = ConcurrencyLeaseHolder(type="flow_run", id=uuid4())
        assert _should_use_cache(["tag:test"], holder) is False

    def test_returns_false_when_names_is_empty(self) -> None:
        """Cache should not be used when names list is empty."""
        holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        assert _should_use_cache([], holder) is False

    def test_returns_false_when_names_do_not_start_with_tag(self) -> None:
        """Cache should not be used when names don't start with 'tag:' prefix."""
        holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        assert _should_use_cache(["test-limit"], holder) is False
        assert _should_use_cache(["concurrency-limit"], holder) is False

    def test_returns_false_when_some_names_do_not_start_with_tag(self) -> None:
        """Cache should not be used when any name doesn't start with 'tag:' prefix."""
        holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        assert _should_use_cache(["tag:test", "other-limit"], holder) is False

    def test_returns_true_for_task_run_with_tag_names(self) -> None:
        """Cache should be used for task_run holder with tag-prefixed names."""
        holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        assert _should_use_cache(["tag:test"], holder) is True
        assert _should_use_cache(["tag:a", "tag:b", "tag:c"], holder) is True


class TestCreateEmptyLimitsResponse:
    """Tests for the _create_empty_limits_response helper function."""

    def test_returns_200_response(self) -> None:
        """Response should have 200 status code."""
        response = _create_empty_limits_response()
        assert response.status_code == 200

    def test_returns_empty_limits_list(self) -> None:
        """Response should contain empty limits list."""
        response = _create_empty_limits_response()
        data = response.json()
        assert data["limits"] == []

    def test_returns_valid_lease_id(self) -> None:
        """Response should contain a valid UUID lease_id."""
        response = _create_empty_limits_response()
        data = response.json()
        assert "lease_id" in data
        from uuid import UUID

        UUID(data["lease_id"])

    def test_returns_json_content_type(self) -> None:
        """Response should have JSON content type header."""
        response = _create_empty_limits_response()
        assert response.headers["content-type"] == "application/json"


class TestCachingBehavior:
    """Tests for the caching behavior in ConcurrencySlotAcquisitionWithLeaseService."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear the cache before each test."""
        _no_limits_cache.clear()

    async def test_caches_empty_limits_response_for_task_run_tags(
        self, mocked_client: Any
    ) -> None:
        """Test that empty limits responses are cached for task_run with tag names."""
        response = Response(200, json={"lease_id": str(uuid4()), "limits": []})
        mocked_client.client.increment_concurrency_slots_with_lease.return_value = (
            response
        )

        limit_names = frozenset(["tag:test-cache"])
        holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        service = ConcurrencySlotAcquisitionWithLeaseService.instance(limit_names)

        future1: Future[Response] = service.send(
            (1, "concurrency", None, None, 60.0, False, holder)
        )
        future2: Future[Response] = service.send(
            (1, "concurrency", None, None, 60.0, False, holder)
        )

        await service.drain()
        resp1 = await asyncio.wrap_future(future1)
        resp2 = await asyncio.wrap_future(future2)

        assert (
            mocked_client.client.increment_concurrency_slots_with_lease.call_count == 1
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["limits"] == []
        assert resp2.json()["limits"] == []

    async def test_does_not_cache_when_limits_exist(self, mocked_client: Any) -> None:
        """Test that responses with limits are not cached."""
        response = Response(
            200,
            json={
                "lease_id": str(uuid4()),
                "limits": [{"id": str(uuid4()), "name": "tag:test", "limit": 10}],
            },
        )
        mocked_client.client.increment_concurrency_slots_with_lease.return_value = (
            response
        )

        limit_names = frozenset(["tag:test-with-limits"])
        holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        service = ConcurrencySlotAcquisitionWithLeaseService.instance(limit_names)

        future1: Future[Response] = service.send(
            (1, "concurrency", None, None, 60.0, False, holder)
        )
        future2: Future[Response] = service.send(
            (1, "concurrency", None, None, 60.0, False, holder)
        )

        await service.drain()
        await asyncio.wrap_future(future1)
        await asyncio.wrap_future(future2)

        assert (
            mocked_client.client.increment_concurrency_slots_with_lease.call_count == 2
        )

    async def test_does_not_cache_when_holder_is_none(self, mocked_client: Any) -> None:
        """Test that caching is disabled when holder is None."""
        response = Response(200, json={"lease_id": str(uuid4()), "limits": []})
        mocked_client.client.increment_concurrency_slots_with_lease.return_value = (
            response
        )

        limit_names = frozenset(["tag:test-no-holder"])
        service = ConcurrencySlotAcquisitionWithLeaseService.instance(limit_names)

        future1: Future[Response] = service.send(
            (1, "concurrency", None, None, 60.0, False, None)
        )
        future2: Future[Response] = service.send(
            (1, "concurrency", None, None, 60.0, False, None)
        )

        await service.drain()
        await asyncio.wrap_future(future1)
        await asyncio.wrap_future(future2)

        assert (
            mocked_client.client.increment_concurrency_slots_with_lease.call_count == 2
        )

    async def test_does_not_cache_for_non_tag_names(self, mocked_client: Any) -> None:
        """Test that caching is disabled for non-tag limit names."""
        response = Response(200, json={"lease_id": str(uuid4()), "limits": []})
        mocked_client.client.increment_concurrency_slots_with_lease.return_value = (
            response
        )

        limit_names = frozenset(["regular-limit"])
        holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        service = ConcurrencySlotAcquisitionWithLeaseService.instance(limit_names)

        future1: Future[Response] = service.send(
            (1, "concurrency", None, None, 60.0, False, holder)
        )
        future2: Future[Response] = service.send(
            (1, "concurrency", None, None, 60.0, False, holder)
        )

        await service.drain()
        await asyncio.wrap_future(future1)
        await asyncio.wrap_future(future2)

        assert (
            mocked_client.client.increment_concurrency_slots_with_lease.call_count == 2
        )
