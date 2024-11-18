import asyncio
from typing import List, Optional

import pytest

from prefect._internal.compatibility.async_dispatch import (
    async_dispatch,
    is_in_async_context,
)
from prefect.utilities.asyncutils import run_sync_in_worker_thread


class TestAsyncDispatchBasicUsage:
    def test_async_compatible_fn_in_sync_context(self):
        data: List[str] = []

        async def my_function_async() -> None:
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function() -> None:
            data.append("sync")

        my_function()
        assert data == ["sync"]

    async def test_async_compatible_fn_in_async_context(self):
        data: List[str] = []

        async def my_function_async() -> None:
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function() -> None:
            data.append("sync")

        await my_function()
        assert data == ["async"]

    async def test_can_force_sync_or_async_dispatch(self):
        """Verify that we can force sync or async dispatch regardless of context"""
        data: List[str] = []

        async def my_function_async() -> None:
            data.append("async")

        @async_dispatch(my_function_async)
        def my_function() -> None:
            data.append("sync")

        # Force sync even in async context
        my_function(_sync=True)
        assert data == ["sync"]

        data.clear()

        # Force async
        await my_function(_sync=False)
        assert data == ["async"]


class TestAsyncDispatchValidation:
    def test_async_compatible_requires_async_implementation(self):
        """Verify we properly reject non-async implementations"""

        def not_async() -> None:
            pass

        with pytest.raises(TypeError, match="async_impl must be an async function"):

            @async_dispatch(not_async)
            def my_function() -> None:
                pass

    def test_async_compatible_requires_implementation(self):
        """Verify we properly reject missing implementations"""

        with pytest.raises(
            TypeError,
            match=r"async_dispatch\(\) missing 1 required positional argument: 'async_impl'",
        ):

            @async_dispatch()
            def my_function() -> None:
                pass


class TestMethodBinding:
    async def test_method_binding_works_correctly(self):
        """Verify that self is properly bound for instance methods"""

        class Counter:
            def __init__(self) -> None:
                self.count = 0

            async def increment_async(self) -> None:
                self.count += 1

            @async_dispatch(increment_async)
            def increment(self) -> None:
                self.count += 1

        counter = Counter()
        assert counter.count == 0

        # Test sync
        counter.increment(_sync=True)
        assert counter.count == 1

        # Test async
        await counter.increment(_sync=False)
        assert counter.count == 2

    async def test_method_binding_respects_context(self):
        """Verify that methods automatically dispatch based on context"""

        class Counter:
            def __init__(self) -> None:
                self.count = 0
                self.calls: List[str] = []

            async def increment_async(self) -> None:
                self.calls.append("async")
                self.count += 1

            @async_dispatch(increment_async)
            def increment(self) -> None:
                self.calls.append("sync")
                self.count += 1

        counter = Counter()

        # In sync context
        def sync_caller() -> None:
            counter.increment(_sync=True)

        sync_caller()
        assert counter.calls == ["sync"]
        assert counter.count == 1

        # In async context
        await counter.increment()
        assert counter.calls == ["sync", "async"]
        assert counter.count == 2


class TestIsInAsyncContext:
    async def test_is_in_async_context_from_coroutine(self):
        """Verify detection inside a coroutine"""
        assert is_in_async_context() is True

    def test_is_in_async_context_from_sync(self):
        """Verify detection in pure sync context"""
        assert is_in_async_context() is False

    async def test_is_in_async_context_with_nested_sync_in_worker_thread(self):
        def sync_func() -> bool:
            return is_in_async_context()

        assert await run_sync_in_worker_thread(sync_func) is False

    def test_is_in_async_context_with_running_loop(self):
        """Verify detection with just a running event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result: Optional[bool] = None

        def check_context() -> None:
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
