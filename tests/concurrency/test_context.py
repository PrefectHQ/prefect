import asyncio
import time
from unittest import mock
from uuid import UUID, uuid4

import pytest

from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
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


async def test_concurrency_context_cleanup_continues_after_release_failure(
    concurrency_limit: ConcurrencyLimitV2, prefect_client: PrefectClient
):
    with get_client(sync_client=True) as client:
        response = client.increment_concurrency_slots_with_lease(
            names=[concurrency_limit.name],
            slots=1,
            mode="concurrency",
            lease_duration=300,
        )
    lease_id = UUID(response.json()["lease_id"])

    real_release = SyncPrefectClient.release_concurrency_slots_with_lease
    failing_lease_id = uuid4()

    def release(self: SyncPrefectClient, lease_id: UUID):
        if lease_id == failing_lease_id:
            raise RuntimeError("transient API failure")
        return real_release(self, lease_id=lease_id)

    # The first release fails; the real lease must still be released.
    with mock.patch.object(
        SyncPrefectClient, "release_concurrency_slots_with_lease", release
    ):
        with ConcurrencyContext(cleanup_lease_ids=[failing_lease_id, lease_id]):
            pass

    limit = await prefect_client.read_global_concurrency_limit_by_name(
        concurrency_limit.name
    )
    assert limit.active_slots == 0
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
