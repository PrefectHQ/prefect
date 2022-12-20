import asyncio
from unittest.mock import MagicMock

import anyio
import pytest

from prefect._internal.concurrency.runtime import Runtime


def identity(x):
    return x


async def aidentity(x):
    await asyncio.sleep(0)
    return x


@pytest.mark.timeout(10)
def test_runtime_context_manager():
    with Runtime():
        pass


def test_runtime_with_failure_in_loop_thread_start():
    runtime = Runtime()

    # Simulate a failure during loop thread start
    runtime._loop_thread._ready_future.set_result = MagicMock(
        side_effect=ValueError("test")
    )

    # The error should propagate to the main thread
    with pytest.raises(ValueError, match="test"):
        with runtime:
            pass


@pytest.mark.parametrize("fn", [identity, aidentity], ids=["sync", "async"])
def test_runtime_run_in_thread(fn):
    with Runtime() as runtime:
        assert runtime.run_in_thread(fn, 1) == 1


@pytest.mark.parametrize("fn", [identity, aidentity], ids=["sync", "async"])
def test_runtime_run_in_process(fn):
    with Runtime() as runtime:
        assert runtime.run_in_process(fn, 1) == 1


def test_sync_runtime_run_in_loop():
    with Runtime() as runtime:
        assert runtime.run_in_loop(aidentity, 1) == 1


async def test_async_runtime_run_in_loop():
    with Runtime() as runtime:
        assert await runtime.run_in_loop(aidentity, 1) == 1


async def test_async_runtime_run_in_loop_many_concurrent():
    async def work():
        future = runtime.submit_from_thread(aidentity, 1)
        assert await asyncio.wrap_future(future) == 1

    with Runtime() as runtime:
        async with anyio.create_task_group() as tg:
            for _ in range(100):
                tg.start_soon(runtime.run_in_loop, work)


def test_runtime_run_in_loop_does_not_accept_sync_functions():
    with Runtime() as runtime:
        with pytest.raises(TypeError, match="coroutine object is required"):
            runtime.run_in_loop(identity, 1)


def test_sync_runtime_submit_from_runtime_loop_thread():
    async def work():
        future = runtime.submit_from_thread(identity, 1)
        result = await asyncio.wrap_future(future)
        return result

    with Runtime() as runtime:
        assert runtime.run_in_loop(work) == 1


async def test_async_runtime_submit_from_runtime_loop_thread():
    async def work():
        future = runtime.submit_from_thread(aidentity, 1)
        return await asyncio.wrap_future(future)

    with Runtime() as runtime:
        assert await runtime.run_in_loop(work) == 1


def test_sync_runtime_submit_thread_requires_sync_function():
    async def work():
        with pytest.raises(
            RuntimeError,
            match="The runtime is sync but .*aidentity.* is async",
        ):
            runtime.submit_from_thread(aidentity, 1)

    with Runtime() as runtime:
        runtime.run_in_loop(work)


async def test_async_runtime_submit_from_thread_requires_async_function():
    async def work():
        with pytest.raises(
            RuntimeError,
            match="The runtime is async but .*identity.* is sync",
        ):
            runtime.submit_from_thread(identity, 1)

    with Runtime() as runtime:
        await runtime.run_in_loop(work)


def test_async_runtime_submit_from_worker_thread():
    async def work():
        future = runtime.submit_from_thread(identity, 1)
        return await asyncio.wrap_future(future)

    with Runtime() as runtime:
        assert runtime.run_in_thread(work) == 1
