import asyncio
import contextvars

import anyio
import pytest

from prefect._internal.concurrency.runtime import Runtime


def identity(x):
    return x


async def aidentity(x):
    await asyncio.sleep(0)
    return x


TEST_CONTEXTVAR = contextvars.ContextVar("TEST_CONTEXTVAR")


def test_runtime_context_manager():
    with Runtime():
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
        return await asyncio.wrap_future(future)

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
            match="The runtime is sync but 'aidentity' is async",
        ):
            runtime.submit_from_thread(aidentity, 1)

    with Runtime() as runtime:
        runtime.run_in_loop(work)


async def test_async_runtime_submit_from_thread_requires_async_function():
    async def work():
        with pytest.raises(
            RuntimeError,
            match="The runtime is async but 'identity' is sync",
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


@pytest.mark.parametrize("sync", [True, False], ids=["sync", "async"])
async def test_runtime_run_in_thread_captures_context_variables(sync):
    def _get_value():
        return TEST_CONTEXTVAR.get()

    if sync:

        def get_value():
            return _get_value()

    else:

        async def get_value():
            return _get_value()

    with Runtime() as runtime:
        try:
            token = TEST_CONTEXTVAR.set("test")
            assert await runtime.run_in_thread(get_value) == "test"
        finally:
            TEST_CONTEXTVAR.reset(token)


@pytest.mark.parametrize("sync", [True, False], ids=["sync", "async"])
async def test_runtime_run_in_loop_captures_context_variables(sync):
    async def get_value():
        return TEST_CONTEXTVAR.get()

    with Runtime() as runtime:
        try:
            token = TEST_CONTEXTVAR.set("test")
            result = await runtime.run_in_loop(get_value)
            assert result == "test"
        finally:
            TEST_CONTEXTVAR.reset(token)


async def test_async_runtime_submit_from_thread_captures_context_variables():
    def _get_value():
        return TEST_CONTEXTVAR.get()

    async def get_value():
        return _get_value()

    async def work():
        token = TEST_CONTEXTVAR.set("test")
        try:
            future = runtime.submit_from_thread(get_value)
        finally:
            TEST_CONTEXTVAR.reset(token)
        return await asyncio.wrap_future(future)

    with Runtime() as runtime:
        result = await runtime.run_in_loop(work)
        assert result == "test"
