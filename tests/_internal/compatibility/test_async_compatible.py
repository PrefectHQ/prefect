import asyncio

import pytest

from prefect._internal.compatibility.async_compatible import (
    async_compatible,
    is_in_async_context,
)
from prefect.utilities.asyncutils import run_sync_in_worker_thread


def test_async_compatible_fn_in_sync_context():
    data = []

    async def my_function_async():
        data.append("async")

    @async_compatible(my_function_async)
    def my_function():
        data.append("sync")

    my_function()
    assert data == ["sync"]


async def test_async_compatible_fn_in_async_context():
    data = []

    async def my_function_async():
        data.append("async")

    @async_compatible(my_function_async)
    def my_function():
        data.append("sync")

    await my_function()
    assert data == ["async"]


async def test_async_compatible_fn_explicit_async_usage():
    """Verify .aio property works as expected"""
    data = []

    async def my_function_async():
        data.append("async")

    @async_compatible(my_function_async)
    def my_function():
        data.append("sync")

    await my_function.aio()
    assert data == ["async"]


def test_async_compatible_fn_explicit_async_usage_with_asyncio_run():
    """Verify .aio property works as expected with asyncio.run"""
    data = []

    async def my_function_async():
        data.append("async")

    @async_compatible(my_function_async)
    def my_function():
        data.append("sync")

    asyncio.run(my_function.aio())
    assert data == ["async"]


def test_async_compatible_requires_async_implementation():
    """Verify we properly reject non-async implementations"""

    def not_async():
        pass

    with pytest.raises(TypeError, match="async_impl must be an async function"):

        @async_compatible(not_async)
        def my_function():
            pass


class TestAsyncCompatibleFnCannotBeUsedWithAsyncioRun:
    def test_async_compatible_fn_in_sync_context_errors_with_asyncio_run(self):
        """this is here to illustrate the expected behavior"""
        data = []

        async def my_function_async():
            data.append("async")

        @async_compatible(my_function_async)
        def my_function():
            data.append("sync")

        with pytest.raises(ValueError, match="coroutine was expected, got None"):
            asyncio.run(my_function())

    async def test_async_compatible_fn_in_async_context_fails_with_asyncio_run(self):
        """this is here to illustrate the expected behavior"""
        data = []

        async def my_function_async():
            data.append("async")

        @async_compatible(my_function_async)
        def my_function():
            data.append("sync")

        with pytest.raises(
            RuntimeError, match="cannot be called from a running event loop"
        ):
            asyncio.run(my_function())


class TestIsInAsyncContext:
    async def test_is_in_async_context_from_coroutine(self):
        """Verify detection inside a coroutine"""
        assert is_in_async_context() is True

    def test_is_in_async_context_from_sync(self):
        """Verify detection in pure sync context"""
        assert is_in_async_context() is False

    async def test_is_in_async_context_with_nested_sync_in_worker_thread(self):
        def sync_func():
            return is_in_async_context()

        assert await run_sync_in_worker_thread(sync_func) is False

    def test_is_in_async_context_with_running_loop(self):
        """Verify detection with just a running event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = None

        def check_context():
            nonlocal result
            result = is_in_async_context()
            loop.stop()

        try:
            loop.call_soon(check_context)
            loop.run_forever()
            assert (
                result is True
            ), "the result we captured while loop was running should be True"
        finally:
            loop.close()
            asyncio.set_event_loop(None)
            assert (
                is_in_async_context() is False
            ), "the loop should be closed and not considered an async context"
