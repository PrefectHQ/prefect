"""
Test concurrency leases with filesystem lease storage.

This test is designed to be run in a GitHub Actions workflow.

If you want to run these tests locally, be sure to set these environment variables in the test process and the server process:

PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE=prefect.server.concurrency.lease_storage.filesystem
PREFECT_SERVER_SERVICES_REPOSSESSOR_LOOP_SECONDS=1
"""

import asyncio
import uuid
from datetime import timedelta
from multiprocessing import Process

import pytest

import prefect
from prefect.client.schemas.actions import GlobalConcurrencyLimitCreate
from prefect.concurrency.asyncio import concurrency
from prefect.server.concurrency.lease_storage import get_concurrency_lease_storage
from prefect.server.concurrency.lease_storage.filesystem import (
    ConcurrencyLeaseStorage as FileSystemConcurrencyLeaseStorage,
)


@pytest.fixture(autouse=True)
async def clear_lease_storage():
    lease_storage = get_concurrency_lease_storage()
    active_lease_ids = await lease_storage.read_active_lease_ids()
    for lease_id in active_lease_ids:
        await lease_storage.revoke_lease(lease_id)


@pytest.fixture
async def concurrency_limit_name():
    async with prefect.get_client() as client:
        name = f"test-{uuid.uuid4()}"
        await client.create_global_concurrency_limit(
            concurrency_limit=GlobalConcurrencyLimitCreate(name=name, limit=1)
        )
        return name


async def function_that_uses_concurrency_and_goes_belly_up(concurrency_limit_name: str):
    async with concurrency(concurrency_limit_name, occupy=1):
        await asyncio.sleep(10)


def wrapper_func(concurrency_limit_name: str):
    asyncio.run(
        function_that_uses_concurrency_and_goes_belly_up(concurrency_limit_name)
    )


async def test_async_concurrency_with_leases(concurrency_limit_name: str):
    lease_storage = get_concurrency_lease_storage()
    assert isinstance(lease_storage, FileSystemConcurrencyLeaseStorage), (
        "Set PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE=prefect.server.concurrency.lease_storage.filesystem to run these tests"
    )

    # Start a process doomed to fail
    process = Process(
        target=wrapper_func,
        args=(concurrency_limit_name,),
    )
    process.start()

    # Wait for lease to be created
    while (active_lease_ids := await lease_storage.read_active_lease_ids()) == []:
        await asyncio.sleep(1)
    assert len(active_lease_ids) == 1

    # Nothing personal
    process.kill()

    # Check that the concurrency limit still has a slot taken
    async with prefect.get_client() as client:
        limit = await client.read_global_concurrency_limit_by_name(
            name=concurrency_limit_name
        )
        assert limit.limit == 1
        assert limit.active_slots == 1

    # Force lease to expire immediately
    await lease_storage.renew_lease(active_lease_ids[0], timedelta(seconds=0))

    # Wait for the lease to be revoked
    while (await lease_storage.read_expired_lease_ids()) != []:
        await asyncio.sleep(1)

    # Check that the concurrency limit has no slots taken after the lease is revoked
    async with prefect.get_client() as client:
        limit = await client.read_global_concurrency_limit_by_name(
            name=concurrency_limit_name
        )
        assert limit.limit == 1
        assert limit.active_slots == 0
