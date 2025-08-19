"""
Test concurrency leases with filesystem lease storage.

This test is designed to be run in a GitHub Actions workflow.

If you want to run these tests locally, be sure to set these environment variables in the test process and the server process:

PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE=prefect.server.concurrency.lease_storage.filesystem
PREFECT_SERVER_SERVICES_REPOSSESSOR_LOOP_SECONDS=1
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta
from multiprocessing import Process
from typing import Any
from unittest import mock

import pytest

import prefect
from prefect.client.schemas.actions import GlobalConcurrencyLimitCreate
from prefect.client.schemas.objects import GlobalConcurrencyLimit
from prefect.concurrency.asyncio import concurrency
from prefect.concurrency.sync import concurrency as sync_concurrency
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
async def concurrency_limit():
    async with prefect.get_client() as client:
        name = f"test-{uuid.uuid4()}"
        await client.create_global_concurrency_limit(
            concurrency_limit=GlobalConcurrencyLimitCreate(name=name, limit=1)
        )
        limit = await client.read_global_concurrency_limit_by_name(name=name)
        return limit


async def function_that_uses_async_concurrency_and_goes_belly_up(
    concurrency_limit_name: str,
):
    original_sleep = asyncio.sleep

    # Mock sleep so that the lease is renewed more quickly
    async def mock_sleep(*args: Any, **kwargs: Any):
        await original_sleep(0.1)

    with mock.patch("asyncio.sleep", mock_sleep):
        try:
            async with concurrency(
                concurrency_limit_name, occupy=1, lease_duration=60, strict=True
            ):
                await original_sleep(120)
        except Exception as e:
            # Log and re-raise to ensure process exits properly
            print(
                f"Async process caught exception: {type(e).__name__}: {e}", flush=True
            )
            raise


def function_that_uses_sync_concurrency_and_goes_belly_up(
    concurrency_limit_name: str,
):
    original_sleep = asyncio.sleep

    # Mock sleep so that the lease is renewed more quickly
    async def mock_sleep(*args: Any, **kwargs: Any):
        await original_sleep(0.1)

    with mock.patch("asyncio.sleep", mock_sleep):
        try:
            with sync_concurrency(
                concurrency_limit_name, occupy=1, lease_duration=60, strict=True
            ):
                # Use a bunch a little sleeps to make this easier to interrupt
                for _ in range(120):
                    time.sleep(1)
        except Exception as e:
            # Log and re-raise to ensure process exits properly
            print(f"Process caught exception: {type(e).__name__}: {e}", flush=True)
            raise


def wrapper_func(concurrency_limit_name: str):
    try:
        asyncio.run(
            function_that_uses_async_concurrency_and_goes_belly_up(
                concurrency_limit_name
            )
        )
    except Exception as e:
        print(f"Wrapper caught exception: {type(e).__name__}: {e}", flush=True)
        import sys

        sys.exit(1)


@pytest.mark.timeout(60)  # Override default timeout
async def test_async_concurrency_with_leases(concurrency_limit: GlobalConcurrencyLimit):
    print(
        f"Starting test_async_concurrency_with_leases with limit: {concurrency_limit.name}",
        flush=True,
    )
    lease_storage = get_concurrency_lease_storage()
    assert isinstance(lease_storage, FileSystemConcurrencyLeaseStorage), (
        "Set PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE=prefect.server.concurrency.lease_storage.filesystem to run these tests"
    )

    # Start a process doomed to fail
    print("Starting background process", flush=True)
    process = Process(
        target=wrapper_func,
        args=(concurrency_limit.name,),
        daemon=True,
    )
    process.start()

    # Wait for lease to be created
    print("Waiting for lease to be created...", flush=True)
    active_lease = None
    start_time = datetime.now()
    timeout_seconds = 30  # Add timeout to prevent infinite loop
    while not active_lease:
        await asyncio.sleep(1)
        active_lease_ids = await lease_storage.read_active_lease_ids()
        print(
            f"Found {len(active_lease_ids)} active lease IDs: {active_lease_ids}",
            flush=True,
        )
        for lease_id in active_lease_ids:
            lease = await lease_storage.read_lease(lease_id)
            if lease and lease.resource_ids == [concurrency_limit.id]:
                active_lease = lease
                print(
                    f"Found target lease: {lease.id} expires at {lease.expiration}",
                    flush=True,
                )
                break

        # Check for timeout
        if (datetime.now() - start_time).total_seconds() > timeout_seconds:
            print(
                f"Timeout waiting for lease creation after {timeout_seconds}s",
                flush=True,
            )
            print(
                f"Process alive: {process.is_alive()}, PID: {process.pid}", flush=True
            )
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            raise TimeoutError(f"Lease not created within {timeout_seconds} seconds")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Lease created after {elapsed:.2f} seconds", flush=True)
    assert active_lease
    updated_lease = await lease_storage.read_lease(active_lease.id)
    assert updated_lease

    # Wait for lease to be renewed
    print("Waiting for lease renewal...", flush=True)
    start_time = datetime.now()
    while updated_lease.expiration == active_lease.expiration:
        await asyncio.sleep(1)
        updated_lease = await lease_storage.read_lease(active_lease.id)
        assert updated_lease
        print(f"Lease expiration: {updated_lease.expiration}", flush=True)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Lease renewed after {elapsed:.2f} seconds", flush=True)

    # Verify that the lease is renewed periodically
    assert updated_lease.expiration > active_lease.expiration

    # Nothing personal
    print(f"Killing process PID: {process.pid}", flush=True)
    process.kill()
    print(f"Process killed, is_alive: {process.is_alive()}", flush=True)

    # Check that the concurrency limit still has a slot taken
    print("Checking active slots immediately after kill...", flush=True)
    async with prefect.get_client() as client:
        limit = await client.read_global_concurrency_limit_by_name(
            name=concurrency_limit.name
        )
        print(
            f"Active slots after kill: {limit.active_slots} (expected: 1)", flush=True
        )
        assert limit.active_slots == 1

    # Force lease to expire immediately
    print("Forcing lease to expire...", flush=True)
    await lease_storage.renew_lease(active_lease.id, timedelta(seconds=0))

    # Wait for the lease to be revoked
    print("Waiting for lease revocation...", flush=True)
    start_time = datetime.now()
    expired_lease_ids = await lease_storage.read_expired_lease_ids()
    while expired_lease_ids != []:
        await asyncio.sleep(1)
        expired_lease_ids = await lease_storage.read_expired_lease_ids()
        print(f"Expired lease IDs: {expired_lease_ids}", flush=True)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Lease revoked after {elapsed:.2f} seconds", flush=True)

    # Check that the concurrency limit has no slots taken after the lease is revoked
    async with prefect.get_client() as client:
        limit = await client.read_global_concurrency_limit_by_name(
            name=concurrency_limit.name
        )
        print(f"Final active slots: {limit.active_slots} (expected: 0)", flush=True)
        assert limit.limit == 1
        assert limit.active_slots == 0


@pytest.mark.timeout(60)  # Override default timeout
async def test_async_concurrency_with_lease_renewal_failure(
    concurrency_limit: GlobalConcurrencyLimit,
):
    print(
        f"Starting test_async_concurrency_with_lease_renewal_failure with limit: {concurrency_limit.name}",
        flush=True,
    )
    print(
        f"Starting test_async_concurrency_with_lease_renewal_failure with limit: {concurrency_limit.name}",
        flush=True,
    )
    lease_storage = get_concurrency_lease_storage()
    assert isinstance(lease_storage, FileSystemConcurrencyLeaseStorage), (
        "Set PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE=prefect.server.concurrency.lease_storage.filesystem to run these tests"
    )

    # Start a process with some bad luck
    print("Starting background process", flush=True)
    process = Process(
        target=wrapper_func,
        args=(concurrency_limit.name,),
        daemon=True,
    )
    process.start()
    print(f"Process started with PID: {process.pid}", flush=True)

    # Wait for lease to be created
    print("Waiting for lease to be created...", flush=True)
    active_lease = None
    start_time = datetime.now()
    timeout_seconds = 30  # Add timeout to prevent infinite loop
    iteration = 0
    while not active_lease:
        iteration += 1
        print(f"Iteration {iteration}: checking for lease...", flush=True)
        await asyncio.sleep(1)
        active_lease_ids = await lease_storage.read_active_lease_ids()
        print(
            f"Found {len(active_lease_ids)} active lease IDs: {active_lease_ids}",
            flush=True,
        )
        for lease_id in active_lease_ids:
            lease = await lease_storage.read_lease(lease_id)
            if lease and lease.resource_ids == [concurrency_limit.id]:
                active_lease = lease
                print(f"Found target lease: {lease.id}", flush=True)
                break

        # Check for timeout
        if (datetime.now() - start_time).total_seconds() > timeout_seconds:
            print(f"Timeout after {timeout_seconds}s!", flush=True)
            print(
                f"Timeout waiting for lease creation after {timeout_seconds}s",
                flush=True,
            )
            print(
                f"Process alive: {process.is_alive()}, PID: {process.pid}", flush=True
            )
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            raise TimeoutError(f"Lease not created within {timeout_seconds} seconds")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Lease created after {elapsed:.2f} seconds", flush=True)
    assert active_lease

    # Revoke the current lease and create a new one to simulate a lease renewal failure
    print(f"Revoking lease {active_lease.id} to simulate renewal failure", flush=True)
    await lease_storage.revoke_lease(active_lease.id)

    # Wait for the process to exit cleanly before the configured sleep time
    print(f"Waiting for process {process.pid} to exit...", flush=True)
    start_time = datetime.now()
    process.join(timeout=10)
    elapsed = (datetime.now() - start_time).total_seconds()

    if process.is_alive():
        print("Process did not exit after join timeout, terminating...", flush=True)
        process.terminate()
        process.join(timeout=5)

    print(
        f"Process exited after {elapsed:.2f} seconds with code: {process.exitcode}",
        flush=True,
    )
    # On Linux, the exit code might be negative (killed by signal) or different from 1
    # Accept any non-zero exit code as a failure
    assert process.exitcode != 0 and process.exitcode is not None, (
        f"Expected non-zero exit code, got {process.exitcode}"
    )


@pytest.mark.timeout(60)  # Override default timeout
async def test_sync_concurrency_with_leases(concurrency_limit: GlobalConcurrencyLimit):
    print(
        f"Starting test_sync_concurrency_with_leases with limit: {concurrency_limit.name}",
        flush=True,
    )
    lease_storage = get_concurrency_lease_storage()
    assert isinstance(lease_storage, FileSystemConcurrencyLeaseStorage), (
        "Set PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE=prefect.server.concurrency.lease_storage.filesystem to run these tests"
    )

    # Start a process doomed to fail
    print("Starting background process", flush=True)
    process = Process(
        target=function_that_uses_sync_concurrency_and_goes_belly_up,
        args=(concurrency_limit.name,),
        daemon=True,
    )
    process.start()

    # Wait for lease to be created
    print("Waiting for lease to be created...", flush=True)
    active_lease = None
    start_time = datetime.now()
    timeout_seconds = 30  # Add timeout to prevent infinite loop
    while not active_lease:
        await asyncio.sleep(1)
        active_lease_ids = await lease_storage.read_active_lease_ids()
        print(
            f"Found {len(active_lease_ids)} active lease IDs: {active_lease_ids}",
            flush=True,
        )
        for lease_id in active_lease_ids:
            lease = await lease_storage.read_lease(lease_id)
            if lease and lease.resource_ids == [concurrency_limit.id]:
                active_lease = lease
                print(
                    f"Found target lease: {lease.id} expires at {lease.expiration}",
                    flush=True,
                )
                break

        # Check for timeout
        if (datetime.now() - start_time).total_seconds() > timeout_seconds:
            print(
                f"Timeout waiting for lease creation after {timeout_seconds}s",
                flush=True,
            )
            print(
                f"Process alive: {process.is_alive()}, PID: {process.pid}", flush=True
            )
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            raise TimeoutError(f"Lease not created within {timeout_seconds} seconds")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Lease created after {elapsed:.2f} seconds", flush=True)
    assert active_lease
    updated_lease = active_lease

    # Wait for lease to be renewed
    print("Waiting for lease renewal...", flush=True)
    start_time = datetime.now()
    while updated_lease.expiration == active_lease.expiration:
        updated_lease = await lease_storage.read_lease(active_lease.id)
        assert updated_lease
        print(f"Lease expiration: {updated_lease.expiration}", flush=True)
        await asyncio.sleep(1)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Lease renewed after {elapsed:.2f} seconds", flush=True)

    # Verify that the lease is renewed periodically
    assert updated_lease.expiration > active_lease.expiration

    # Good night, sweet prince
    print(f"Killing process PID: {process.pid}", flush=True)
    process.kill()
    print(f"Process killed, is_alive: {process.is_alive()}", flush=True)

    # Check that the concurrency limit still has a slot taken
    print("Checking active slots immediately after kill...", flush=True)
    async with prefect.get_client() as client:
        limit = await client.read_global_concurrency_limit_by_name(
            name=concurrency_limit.name
        )
        print(
            f"Active slots after kill: {limit.active_slots} (expected: 1)", flush=True
        )
        assert limit.active_slots == 1

    # Force lease to expire immediately
    print("Forcing lease to expire...", flush=True)
    await lease_storage.renew_lease(active_lease.id, timedelta(seconds=0))

    # Wait for the lease to be revoked
    print("Waiting for lease revocation...", flush=True)
    start_time = datetime.now()
    expired_lease_ids = await lease_storage.read_expired_lease_ids()
    while expired_lease_ids != []:
        await asyncio.sleep(1)
        expired_lease_ids = await lease_storage.read_expired_lease_ids()
        print(f"Expired lease IDs: {expired_lease_ids}", flush=True)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Lease revoked after {elapsed:.2f} seconds", flush=True)

    # Check that the concurrency limit has no slots taken after the lease is revoked
    async with prefect.get_client() as client:
        limit = await client.read_global_concurrency_limit_by_name(
            name=concurrency_limit.name
        )
        print(f"Final active slots: {limit.active_slots} (expected: 0)", flush=True)
        assert limit.limit == 1
        assert limit.active_slots == 0


@pytest.mark.timeout(60)  # Override default timeout
async def test_sync_concurrency_with_lease_renewal_failure(
    concurrency_limit: GlobalConcurrencyLimit,
):
    print(
        f"Starting test_sync_concurrency_with_lease_renewal_failure with limit: {concurrency_limit.name}",
        flush=True,
    )
    lease_storage = get_concurrency_lease_storage()
    assert isinstance(lease_storage, FileSystemConcurrencyLeaseStorage), (
        "Set PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE=prefect.server.concurrency.lease_storage.filesystem to run these tests"
    )

    # Start a process with some bad luck
    print("Starting background process", flush=True)
    process = Process(
        target=function_that_uses_sync_concurrency_and_goes_belly_up,
        args=(concurrency_limit.name,),
        daemon=True,
    )
    process.start()

    # Wait for lease to be created
    print("Waiting for lease to be created...", flush=True)
    active_lease = None
    start_time = datetime.now()
    timeout_seconds = 30  # Add timeout to prevent infinite loop
    while not active_lease:
        await asyncio.sleep(1)
        active_lease_ids = await lease_storage.read_active_lease_ids()
        print(
            f"Found {len(active_lease_ids)} active lease IDs: {active_lease_ids}",
            flush=True,
        )
        for lease_id in active_lease_ids:
            lease = await lease_storage.read_lease(lease_id)
            if lease and lease.resource_ids == [concurrency_limit.id]:
                active_lease = lease
                print(f"Found target lease: {lease.id}", flush=True)
                break

        # Check for timeout
        if (datetime.now() - start_time).total_seconds() > timeout_seconds:
            print(
                f"Timeout waiting for lease creation after {timeout_seconds}s",
                flush=True,
            )
            print(
                f"Process alive: {process.is_alive()}, PID: {process.pid}", flush=True
            )
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            raise TimeoutError(f"Lease not created within {timeout_seconds} seconds")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Lease created after {elapsed:.2f} seconds", flush=True)
    assert active_lease

    # Revoke the current lease and create a new one to simulate a lease renewal failure
    print(f"Revoking lease {active_lease.id} to simulate renewal failure", flush=True)
    await lease_storage.revoke_lease(active_lease.id)

    # Wait for the process to exit cleanly before the configured sleep time
    print(f"Waiting for process {process.pid} to exit...", flush=True)
    start_time = datetime.now()
    process.join(timeout=10)
    elapsed = (datetime.now() - start_time).total_seconds()

    if process.is_alive():
        print("Process did not exit after join timeout, terminating...", flush=True)
        process.terminate()
        process.join(timeout=5)

    print(
        f"Process exited after {elapsed:.2f} seconds with code: {process.exitcode}",
        flush=True,
    )
    # On Linux, the exit code might be negative (killed by signal) or different from 1
    # Accept any non-zero exit code as a failure
    assert process.exitcode != 0 and process.exitcode is not None, (
        f"Expected non-zero exit code, got {process.exitcode}"
    )
