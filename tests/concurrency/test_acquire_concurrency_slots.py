import asyncio
import uuid
from concurrent.futures import Future
from unittest import mock

import pytest
from httpx import Response

from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.concurrency._asyncio import (
    aacquire_concurrency_slots,
    aacquire_concurrency_slots_with_lease,
)
from prefect.concurrency.services import ConcurrencySlotAcquisitionWithLeaseService

pytestmark = pytest.mark.clear_db


async def test_calls_increment_client_method():
    limits = [
        MinimalConcurrencyLimitResponse(id=uuid.uuid4(), name=f"test-{i}", limit=i)
        for i in range(1, 3)
    ]

    with mock.patch(
        "prefect.client.orchestration.PrefectClient.increment_concurrency_slots"
    ) as increment_concurrency_slots:
        response = Response(
            200, json=[limit.model_dump(mode="json") for limit in limits]
        )
        increment_concurrency_slots.return_value = response

        await aacquire_concurrency_slots(
            names=["test-1", "test-2"], slots=1, mode="concurrency"
        )
        increment_concurrency_slots.assert_called_once_with(
            names=["test-1", "test-2"],
            slots=1,
            mode="concurrency",
        )


async def test_returns_minimal_concurrency_limit():
    limits = [
        MinimalConcurrencyLimitResponse(id=uuid.uuid4(), name=f"test-{i}", limit=i)
        for i in range(1, 3)
    ]

    with mock.patch(
        "prefect.client.orchestration.PrefectClient.increment_concurrency_slots"
    ) as increment_concurrency_slots:
        response = Response(
            200, json=[limit.model_dump(mode="json") for limit in limits]
        )
        increment_concurrency_slots.return_value = response

        result = await aacquire_concurrency_slots(["test-1", "test-2"], 1)
        assert result == limits


async def test_releases_lease_granted_after_caller_is_cancelled():
    """A lease delivered to a caller that is already gone must not leak its slots.

    The future is marked running before the caller is cancelled, mirroring the
    service: `asyncio.wrap_future` can no longer cancel it, so the granted lease
    reaches a caller that is already gone.
    """
    response = Response(
        200,
        json={
            "lease_id": str(uuid.uuid4()),
            "limits": [
                MinimalConcurrencyLimitResponse(
                    id=uuid.uuid4(), name="test", limit=1
                ).model_dump(mode="json")
            ],
        },
    )

    future: Future[Response] = Future()
    sent = asyncio.Event()

    def send(item: tuple[object, ...]) -> Future[Response]:
        sent.set()
        return future

    service = mock.MagicMock(spec=ConcurrencySlotAcquisitionWithLeaseService)
    service.send = send

    with mock.patch.object(
        ConcurrencySlotAcquisitionWithLeaseService, "instance", return_value=service
    ):
        acquire = asyncio.create_task(
            aacquire_concurrency_slots_with_lease(names=["test"], slots=1)
        )
        # Once the request has been sent, the caller is suspended on the future.
        await sent.wait()

        assert future.set_running_or_notify_cancel()
        acquire.cancel()
        with pytest.raises(asyncio.CancelledError):
            await acquire

        future.set_result(response)

    service.release_orphaned_lease.assert_called_once_with(response)


@pytest.mark.parametrize("outcome", ["cancelled", "failed"])
async def test_does_not_release_when_no_lease_was_granted(outcome: str):
    """Only a granted lease needs releasing; a dead acquisition has nothing to clean up."""
    future: Future[Response] = Future()
    sent = asyncio.Event()

    def send(item: tuple[object, ...]) -> Future[Response]:
        sent.set()
        return future

    service = mock.MagicMock(spec=ConcurrencySlotAcquisitionWithLeaseService)
    service.send = send

    with mock.patch.object(
        ConcurrencySlotAcquisitionWithLeaseService, "instance", return_value=service
    ):
        acquire = asyncio.create_task(
            aacquire_concurrency_slots_with_lease(names=["test"], slots=1)
        )
        await sent.wait()

        if outcome == "failed":
            assert future.set_running_or_notify_cancel()

        acquire.cancel()
        with pytest.raises(asyncio.CancelledError):
            await acquire

        if outcome == "failed":
            future.set_exception(ValueError("increment failed"))

    service.release_orphaned_lease.assert_not_called()
