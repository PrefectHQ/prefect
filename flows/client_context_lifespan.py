from packaging.version import Version

import prefect

# Only run these tests if the version is at least 2.13.0
if Version(prefect.__version__) < Version("2.13.0"):
    raise NotImplementedError()

import asyncio
import random
import threading
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import anyio
from prefect._vendor.fastapi import FastAPI

import prefect.context
import prefect.exceptions
from prefect.client.orchestration import PrefectClient


def make_lifespan(startup, shutdown) -> callable:
    async def lifespan(app):
        try:
            startup()
            yield
        finally:
            shutdown()

    return asynccontextmanager(lifespan)


def client_context_lifespan_is_robust_to_threaded_concurrency():
    startup, shutdown = MagicMock(), MagicMock()
    app = FastAPI(lifespan=make_lifespan(startup, shutdown))

    async def enter_client(context):
        # We must re-enter the profile context in the new thread
        with context:
            # Use random sleeps to interleave clients
            await anyio.sleep(random.random())
            async with PrefectClient(app):
                await anyio.sleep(random.random())

    threads = [
        threading.Thread(
            target=anyio.run,
            args=(enter_client, prefect.context.SettingsContext.get().copy()),
        )
        for _ in range(100)
    ]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(3)

    assert startup.call_count == shutdown.call_count
    assert startup.call_count > 0


async def client_context_lifespan_is_robust_to_high_async_concurrency():
    startup, shutdown = MagicMock(), MagicMock()
    app = FastAPI(lifespan=make_lifespan(startup, shutdown))

    async def enter_client():
        # Use random sleeps to interleave clients
        await anyio.sleep(random.random())
        async with PrefectClient(app):
            await anyio.sleep(random.random())

    with anyio.fail_after(15):
        async with anyio.create_task_group() as tg:
            for _ in range(1000):
                tg.start_soon(enter_client)

    assert startup.call_count == shutdown.call_count
    assert startup.call_count > 0


async def client_context_lifespan_is_robust_to_mixed_concurrency():
    startup, shutdown = MagicMock(), MagicMock()
    app = FastAPI(lifespan=make_lifespan(startup, shutdown))

    async def enter_client():
        # Use random sleeps to interleave clients
        await anyio.sleep(random.random())
        async with PrefectClient(app):
            await anyio.sleep(random.random())

    async def enter_client_many_times(context):
        # We must re-enter the profile context in the new thread
        with context:
            async with anyio.create_task_group() as tg:
                for _ in range(100):
                    tg.start_soon(enter_client)

    threads = [
        threading.Thread(
            target=anyio.run,
            args=(
                enter_client_many_times,
                prefect.context.SettingsContext.get().copy(),
            ),
        )
        for _ in range(100)
    ]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(3)

    assert startup.call_count == shutdown.call_count
    assert startup.call_count > 0


async def concurrency_tests():
    client_context_lifespan_is_robust_to_threaded_concurrency()
    await client_context_lifespan_is_robust_to_high_async_concurrency()
    await client_context_lifespan_is_robust_to_mixed_concurrency()


if __name__ == "__main__":
    asyncio.run(concurrency_tests())
