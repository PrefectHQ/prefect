import asyncio
import time as _time
from unittest import mock
from uuid import UUID, uuid4

import pytest

from prefect.client.orchestration import PrefectClient, get_client
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


def test_concurrency_context_cleanup_continues_after_release_failure():
    cleanup_slots = [([f"tag-{i}"], 1.0, uuid4()) for i in range(3)]
    released: list[UUID] = []

    def decrement(names: list[str], occupancy_seconds: float, task_run_id: UUID):
        released.append(task_run_id)
        if task_run_id == cleanup_slots[0][2]:
            raise RuntimeError("transient API failure")

    client = mock.MagicMock()
    client.__enter__.return_value = client
    client.decrement_v1_concurrency_slots.side_effect = decrement

    with mock.patch(
        "prefect.concurrency.v1.context.get_client", return_value=client
    ) as get_client_mock:
        with ConcurrencyContext(cleanup_slots=cleanup_slots):
            pass

    get_client_mock.assert_called_once_with(sync_client=True)
    assert released == [task_run_id for _, _, task_run_id in cleanup_slots]
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
