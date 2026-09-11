import asyncio
import time as _time
from unittest import mock
from uuid import UUID, uuid4

import pytest

from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
from prefect.concurrency.v1.asyncio import concurrency as aconcurrency
from prefect.concurrency.v1.context import ConcurrencyContext
from prefect.concurrency.v1.sync import concurrency
from prefect.server.schemas.core import ConcurrencyLimit
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.timeout import timeout, timeout_async

pytestmark = pytest.mark.clear_db


async def test_concurrency_context_releases_slots_async(
    v1_concurrency_limit: ConcurrencyLimit, prefect_client: PrefectClient
):
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    async def expensive_task():
        async with aconcurrency(v1_concurrency_limit.tag, task_run_id):
            response = await prefect_client.read_concurrency_limit_by_tag(
                v1_concurrency_limit.tag
            )
            assert response.active_slots == [task_run_id]

            # Occupy the slot for longer than the timeout
            await asyncio.sleep(10)

    with pytest.raises(TimeoutError):
        with timeout_async(seconds=1):
            with ConcurrencyContext():
                await expensive_task()

    response = await prefect_client.read_concurrency_limit_by_tag(
        v1_concurrency_limit.tag
    )
    assert response.active_slots == []


async def test_concurrency_context_cleanup_continues_after_release_failure(
    v1_concurrency_limit: ConcurrencyLimit, prefect_client: PrefectClient
):
    task_run_id = uuid4()
    with get_client(sync_client=True) as client:
        client.increment_v1_concurrency_slots(
            names=[v1_concurrency_limit.tag], task_run_id=task_run_id
        )

    real_decrement = SyncPrefectClient.decrement_v1_concurrency_slots

    def decrement(
        self: SyncPrefectClient,
        names: list[str],
        task_run_id: UUID,
        occupancy_seconds: float,
    ):
        if names == ["failing-tag"]:
            raise RuntimeError("transient API failure")
        return real_decrement(
            self,
            names=names,
            task_run_id=task_run_id,
            occupancy_seconds=occupancy_seconds,
        )

    # The first release fails; the real slot must still be released.
    with mock.patch.object(
        SyncPrefectClient, "decrement_v1_concurrency_slots", decrement
    ):
        with ConcurrencyContext(
            cleanup_slots=[
                (["failing-tag"], 1.0, task_run_id),
                ([v1_concurrency_limit.tag], 1.0, task_run_id),
            ]
        ):
            pass

    response = await prefect_client.read_concurrency_limit_by_tag(
        v1_concurrency_limit.tag
    )
    assert response.active_slots == []
    assert ConcurrencyContext.get() is None


async def test_concurrency_context_releases_slots_sync(
    v1_concurrency_limit: ConcurrencyLimit, prefect_client: PrefectClient
):
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    def expensive_task():
        with concurrency(v1_concurrency_limit.tag, task_run_id):
            client = get_client()
            response = run_coro_as_sync(
                client.read_concurrency_limit_by_tag(v1_concurrency_limit.tag)
            )
            assert response and response.active_slots == [task_run_id]

            # Use a time-bounded busy loop instead of time.sleep()
            # because sleep is a C-level call that cannot be interrupted
            # by WatcherThreadCancelScope.
            deadline = _time.monotonic() + 30
            while _time.monotonic() < deadline:
                pass

    with pytest.raises(TimeoutError):
        with timeout(seconds=1):
            with ConcurrencyContext():
                expensive_task()

    response = await prefect_client.read_concurrency_limit_by_tag(
        v1_concurrency_limit.tag
    )
    assert response.active_slots == []
