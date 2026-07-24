import asyncio
import threading
import uuid
from concurrent.futures import Future
from unittest import mock

import pytest
from httpx import Response

from prefect.client.orchestration import SyncPrefectClient
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
    """A lease delivered to a caller that is already gone must not leak its slots."""
    lease_id = uuid.uuid4()
    response = Response(
        200,
        json={
            "lease_id": str(lease_id),
            "limits": [
                MinimalConcurrencyLimitResponse(
                    id=uuid.uuid4(), name="test", limit=1
                ).model_dump(mode="json")
            ],
        },
    )

    future: Future[Response] = Future()
    released = threading.Event()
    releases: list[uuid.UUID] = []

    client = mock.MagicMock(spec=SyncPrefectClient)

    def release(lease_id: uuid.UUID) -> None:
        releases.append(lease_id)
        released.set()

    client.release_concurrency_slots_with_lease.side_effect = release
    client.__enter__.return_value = client

    sent = asyncio.Event()

    def send(item: tuple[object, ...]) -> Future[Response]:
        sent.set()
        return future

    with mock.patch.object(
        ConcurrencySlotAcquisitionWithLeaseService, "instance"
    ) as instance:
        instance.return_value.send = send

        acquire = asyncio.create_task(
            aacquire_concurrency_slots_with_lease(names=["test"], slots=1)
        )
        # Once the request has been sent the task is suspended on the future, so
        # the acquisition below completes after the caller is already gone.
        await sent.wait()
        with mock.patch("prefect.concurrency._asyncio.get_client", return_value=client):
            future.set_result(response)
            acquire.cancel()

            with pytest.raises(asyncio.CancelledError):
                await acquire

            await asyncio.get_running_loop().run_in_executor(None, released.wait)

    assert releases == [lease_id]
