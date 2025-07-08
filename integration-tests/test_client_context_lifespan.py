import random
import threading
from contextlib import asynccontextmanager
from typing import Callable
from unittest.mock import MagicMock

import anyio
from fastapi import FastAPI

import prefect
import prefect.context
import prefect.exceptions
from prefect.client.orchestration import PrefectClient


def make_lifespan(startup, shutdown) -> Callable:
    async def lifespan(app):
        try:
            startup()
            yield
        finally:
            shutdown()

    return asynccontextmanager(lifespan)


def test_client_context_lifespan_is_robust_to_threaded_concurrency():
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
            args=(enter_client, prefect.context.SettingsContext.get().model_copy()),
        )
        for _ in range(100)
    ]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(15)

    assert startup.call_count == shutdown.call_count
    assert startup.call_count > 0


async def test_client_context_lifespan_is_robust_to_high_async_concurrency():
    startup, shutdown = MagicMock(), MagicMock()
    app = FastAPI(lifespan=make_lifespan(startup, shutdown))

    async def enter_client():
        # Use random sleeps to interleave clients
        await anyio.sleep(random.random())
        async with PrefectClient(app):
            await anyio.sleep(random.random())

    with anyio.fail_after(30):
        async with anyio.create_task_group() as tg:
            for _ in range(1000):
                tg.start_soon(enter_client)

    assert startup.call_count == shutdown.call_count
    assert startup.call_count > 0


async def test_client_context_lifespan_is_robust_to_mixed_concurrency():
    startup, shutdown = MagicMock(), MagicMock()
    app = FastAPI(lifespan=make_lifespan(startup, shutdown))

    async def enter_client():
        # Use random sleeps to interleave clients
        await anyio.sleep(random.random() * 0.1)
        async with PrefectClient(app):
            await anyio.sleep(random.random() * 0.1)

    async def enter_client_many_times(context):
        # We must re-enter the profile context in the new thread
        try:
            with context:
                async with anyio.create_task_group() as tg:
                    for _ in range(50):
                        tg.start_soon(enter_client)
        except Exception as e:
            print(f"Error entering client many times {e}")
            raise e

    threads = [
        threading.Thread(
            target=anyio.run,
            args=(
                enter_client_many_times,
                prefect.context.SettingsContext.get().model_copy(),
            ),
        )
        for _ in range(10)
    ]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(60)
        if thread.is_alive():
            raise TimeoutError(f"Thread {thread.name} did not complete within timeout")

    assert startup.call_count == shutdown.call_count
    assert startup.call_count > 0
