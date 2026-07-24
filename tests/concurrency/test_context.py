import asyncio
import time
import uuid
from unittest import mock

import pytest

from prefect.client.orchestration import PrefectClient, get_client
from prefect.concurrency.asyncio import concurrency as aconcurrency
from prefect.concurrency.context import ConcurrencyContext
from prefect.concurrency.sync import concurrency
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.timeout import timeout, timeout_async

pytestmark = pytest.mark.clear_db


async def test_concurrency_context_releases_slots_async(
    concurrency_limit: ConcurrencyLimitV2, prefect_client: PrefectClient
):
    async def expensive_task():
        async with aconcurrency(concurrency_limit.name):
            response = await prefect_client.read_global_concurrency_limit_by_name(
                concurrency_limit.name
            )
            assert response.active_slots == 1

            # Occupy the slot for longer than the timeout
            await asyncio.sleep(1)

    with pytest.raises(TimeoutError):
        with timeout_async(seconds=0.5):
            with ConcurrencyContext():
                await expensive_task()

    response = await prefect_client.read_global_concurrency_limit_by_name(
        concurrency_limit.name
    )
    assert response.active_slots == 0


def test_concurrency_context_cleanup_continues_after_release_failure():
    lease_ids = [uuid.uuid4() for _ in range(3)]
    released: list[uuid.UUID] = []

    def release(lease_id: uuid.UUID) -> None:
        released.append(lease_id)
        if lease_id == lease_ids[0]:
            raise RuntimeError("transient API failure")

    client = mock.MagicMock()
    client.__enter__.return_value = client
    client.release_concurrency_slots_with_lease.side_effect = release

    with mock.patch(
        "prefect.concurrency.context.get_client", return_value=client
    ) as get_client_mock:
        context = ConcurrencyContext(cleanup_lease_ids=lease_ids)
        with context:
            pass

    get_client_mock.assert_called_once_with(sync_client=True)
    assert released == lease_ids
    assert ConcurrencyContext.get() is None


async def test_concurrency_context_releases_slots_sync(
    concurrency_limit: ConcurrencyLimitV2, prefect_client: PrefectClient
):
    def expensive_task():
        with concurrency(concurrency_limit.name):
            client = get_client()
            response = run_coro_as_sync(
                client.read_global_concurrency_limit_by_name(concurrency_limit.name)
            )
            assert response and response.active_slots == 1

            # Occupy the slot for longer than the timeout
            time.sleep(1)

    with pytest.raises(TimeoutError):
        with timeout(seconds=0.5):
            with ConcurrencyContext():
                expensive_task()

    response = await prefect_client.read_global_concurrency_limit_by_name(
        concurrency_limit.name
    )
    assert response.active_slots == 0
