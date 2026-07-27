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
from prefect.settings import (
    PREFECT_API_URL,
    get_current_settings,
    temporary_settings,
)

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


async def _cancel_acquisition_after_lease_is_granted(
    lease_id: uuid.UUID, get_client: mock.MagicMock
) -> None:
    """Cancel a caller once its acquisition is under way, then grant the lease.

    Reproduces the ordering the service uses: the future is marked running before
    the caller is cancelled, so `asyncio.wrap_future` cannot cancel it and the
    granted lease is delivered to a caller that is already gone.
    """
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
        # Once the request has been sent, the caller is suspended on the future.
        await sent.wait()

        assert future.set_running_or_notify_cancel()
        acquire.cancel()
        with pytest.raises(asyncio.CancelledError):
            await acquire

        with mock.patch("prefect.concurrency._asyncio.get_client", get_client):
            future.set_result(response)


async def test_releases_lease_granted_after_caller_is_cancelled():
    """A lease delivered to a caller that is already gone must not leak its slots."""
    lease_id = uuid.uuid4()
    released = threading.Event()
    releases: list[uuid.UUID] = []

    def release(lease_id: uuid.UUID) -> None:
        releases.append(lease_id)
        released.set()

    client = mock.MagicMock(spec=SyncPrefectClient)
    client.__enter__.return_value = client
    client.release_concurrency_slots_with_lease.side_effect = release

    await _cancel_acquisition_after_lease_is_granted(
        lease_id, mock.MagicMock(return_value=client)
    )

    assert released.wait(10)
    assert releases == [lease_id]


async def test_releases_orphaned_lease_against_the_callers_api():
    """The release runs off-caller, but must still target the caller's API."""
    lease_id = uuid.uuid4()
    released = threading.Event()
    api_urls: list[str | None] = []

    def release(lease_id: uuid.UUID) -> None:
        released.set()

    client = mock.MagicMock(spec=SyncPrefectClient)
    client.__enter__.return_value = client
    client.release_concurrency_slots_with_lease.side_effect = release

    def get_client(sync_client: bool = False) -> mock.MagicMock:
        api_urls.append(get_current_settings().api.url)
        return client

    with temporary_settings({PREFECT_API_URL: "https://scoped.example.com/api"}):
        await _cancel_acquisition_after_lease_is_granted(
            lease_id, mock.MagicMock(side_effect=get_client)
        )

    assert released.wait(10)
    assert api_urls == ["https://scoped.example.com/api"]
