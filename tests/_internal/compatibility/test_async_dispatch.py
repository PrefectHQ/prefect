import asyncio

import pytest

from prefect._internal.compatibility.async_dispatch import (
    async_dispatch,
    is_in_async_context,
)
from prefect.utilities.asyncutils import run_sync_in_worker_thread


class TestAsyncDispatchBasicUsage:
    def test_async_compatible_fn_in_sync_context(self):
        data = []

        async def my_function_async():
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function():
            data.append("sync")

        my_function()
        assert data == ["sync"]

    async def test_async_compatible_fn_in_async_context(self):
        data = []

        async def my_function_async():
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function():
            data.append("sync")

        await my_function()
        assert data == ["async"]


class TestAsyncDispatchExplicitUsage:
    async def test_async_compatible_fn_explicit_async_usage(self):
        """Verify .aio property works as expected"""
        data = []

        async def my_function_async():
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function():
            data.append("sync")

        await my_function.aio()
        assert data == ["async"]

    def test_async_compatible_fn_explicit_async_usage_with_asyncio_run(self):
        """Verify .aio property works as expected with asyncio.run"""
        data = []

        async def my_function_async():
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function():
            data.append("sync")

        asyncio.run(my_function.aio())
        assert data == ["async"]

    async def test_async_compatible_fn_explicit_sync_usage(self):
        """Verify .sync property works as expected in async context"""
        data = []

        async def my_function_async():
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function():
            data.append("sync")

        # Even though we're in async context, .sync should force sync execution
        my_function.sync()
        assert data == ["sync"]

    def test_async_compatible_fn_explicit_sync_usage_in_sync_context(self):
        """Verify .sync property works as expected in sync context"""
        data = []

        async def my_function_async():
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function():
            data.append("sync")

        my_function.sync()
        assert data == ["sync"]


class TestAsyncDispatchValidation:
    def test_async_compatible_requires_async_implementation(self):
        """Verify we properly reject non-async implementations"""

        def not_async():
            pass

        with pytest.raises(TypeError, match="async_impl must be an async function"):

            @async_dispatch(not_async)
            def my_function():
                pass

    async def test_async_compatible_fn_attributes_exist(self):
        """Verify both .sync and .aio attributes are present"""

        async def my_function_async():
            pass

        @async_dispatch(my_function_async)
        def my_function():
            pass

        assert hasattr(my_function, "sync"), "Should have .sync attribute"
        assert hasattr(my_function, "aio"), "Should have .aio attribute"
        assert (
            my_function.sync is my_function.__wrapped__
        ), "Should reference original sync function"
        assert (
            my_function.aio is my_function_async
        ), "Should reference original async function"


class TestAsyncCompatibleFnCannotBeUsedWithAsyncioRun:
    def test_async_compatible_fn_in_sync_context_errors_with_asyncio_run(self):
        """this is here to illustrate the expected behavior"""
        data = []

        async def my_function_async():
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function():
            data.append("sync")

        with pytest.raises(ValueError, match="coroutine was expected, got None"):
            asyncio.run(my_function())

    async def test_async_compatible_fn_in_async_context_fails_with_asyncio_run(self):
        """this is here to illustrate the expected behavior"""
        data = []

        async def my_function_async():
            data.append("async")

        @async_dispatch(my_function_async)
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
