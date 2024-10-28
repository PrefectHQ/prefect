import asyncio
import time
from uuid import UUID

import pytest

from prefect.client.orchestration import PrefectClient, get_client
from prefect.concurrency.v1.asyncio import concurrency as aconcurrency
from prefect.concurrency.v1.context import ConcurrencyContext
from prefect.concurrency.v1.sync import concurrency
from prefect.server.schemas.core import ConcurrencyLimit
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.timeout import timeout, timeout_async


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
            await asyncio.sleep(1)

    with pytest.raises(TimeoutError):
        with timeout_async(seconds=0.5):
            with ConcurrencyContext():
                await expensive_task()

    response = await prefect_client.read_concurrency_limit_by_tag(
        v1_concurrency_limit.tag
    )
    assert response.active_slots == []


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

            # Occupy the slot for longer than the timeout
            time.sleep(1)

    with pytest.raises(TimeoutError):
        with timeout(seconds=0.5):
            with ConcurrencyContext():
                expensive_task()

    response = await prefect_client.read_concurrency_limit_by_tag(
        v1_concurrency_limit.tag
    )
    assert response.active_slots == []
