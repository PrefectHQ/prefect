import asyncio
from typing import List, Optional

import pytest

from prefect._internal.compatibility.async_dispatch import (
    async_dispatch,
    is_in_async_context,
)
from prefect.flows import flow
from prefect.tasks import task
from prefect.utilities.asyncutils import run_coro_as_sync, run_sync_in_worker_thread


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

    async def test_works_with_classmethods(self):
        """Verify that async_impl can be a classmethod"""

        class MyClass:
            @classmethod
            async def my_amethod(cls) -> str:
                return "async"

            @classmethod
            @async_dispatch(my_amethod)
            def my_method(cls) -> str:
                return "sync"

        assert await MyClass.my_amethod() == "async"
        assert MyClass.my_method(_sync=True) == "sync"
        assert await MyClass.my_method() == "async"

    def test_works_with_classmethods_in_sync_context(self):
        """Verify that classmethods work in sync context"""

        class MyClass:
            @classmethod
            async def my_amethod(cls) -> str:
                return "async"

            @classmethod
            @async_dispatch(my_amethod)
            def my_method(cls) -> str:
                return "sync"

        assert MyClass.my_method() == "sync"


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
            assert result is True, (
                "the result we captured while loop was running should be True"
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)
            assert is_in_async_context() is False, (
                "the loop should be closed and not considered an async context"
            )


class TestIsInARunContext:
    def test_dispatches_to_async_in_async_flow(self):
        """
        Verify that async_dispatch dispatches to async in async flow

        The test function is sync, but the flow is async, so we should dispatch to
        the async implementation.
        """

        async def my_afunction() -> str:
            return "async"

        @async_dispatch(my_afunction)
        def my_function() -> str:
            return "sync"

        @flow
        async def my_flow() -> str:
            return await my_function()

        assert run_coro_as_sync(my_flow()) == "async"

    async def test_dispatches_to_sync_in_sync_flow(self):
        """
        Verify that async_dispatch dispatches to sync in sync flow

        The test function is async, but the flow is sync, so we should dispatch to
        the sync implementation.
        """

        async def my_afunction() -> str:
            return "async"

        @async_dispatch(my_afunction)
        def my_function() -> str:
            return "sync"

        @flow
        def my_flow() -> str:
            return my_function()

        assert my_flow() == "sync"

    def test_dispatches_to_async_in_an_async_task(self):
        """
        Verify that async_dispatch dispatches to async in an async task

        The test function is sync, but the task is async, so we should dispatch to
        the async implementation.
        """

        async def my_afunction() -> str:
            return "async"

        @async_dispatch(my_afunction)
        def my_function() -> str:
            return "sync"

        @task
        async def my_task() -> str:
            return await my_function()

        assert run_coro_as_sync(my_task()) == "async"

    async def test_dispatches_to_sync_in_a_sync_task(self):
        """
        Verify that async_dispatch dispatches to sync in a sync task

        The test function is async, but the task is sync, so we should dispatch to
        the sync implementation.
        """

        async def my_afunction() -> str:
            return "async"

        @async_dispatch(my_afunction)
        def my_function() -> str:
            return "sync"

        @task
        def my_task() -> str:
            return my_function()

        assert my_task() == "sync"


class TestAioAttribute:
    """Test that async_dispatch adds the .aio attribute for compatibility."""

    def test_async_dispatch_adds_aio_attribute(self):
        """Test that the decorator adds an .aio attribute pointing to async implementation."""

        async def async_impl(x: int) -> str:
            return f"async {x}"

        @async_dispatch(async_impl)
        def sync_impl(x: int) -> str:
            return f"sync {x}"

        # Check that .aio attribute exists and points to async implementation
        assert hasattr(sync_impl, "aio")
        assert sync_impl.aio is async_impl

    async def test_aio_attribute_can_be_called_directly(self):
        """Test that the .aio attribute can be called directly."""

        async def async_impl(x: int) -> str:
            return f"async {x}"

        @async_dispatch(async_impl)
        def sync_impl(x: int) -> str:
            return f"sync {x}"

        # Call .aio directly
        result = await sync_impl.aio(42)
        assert result == "async 42"

    async def test_aio_attribute_with_instance_methods(self):
        """Test that .aio works correctly with instance methods."""

        class Counter:
            def __init__(self) -> None:
                self.count = 0

            async def increment_async(self) -> int:
                self.count += 1
                return self.count

            @async_dispatch(increment_async)
            def increment(self) -> int:
                self.count += 10
                return self.count

        counter = Counter()

        # Call via .aio directly - should increment by 1
        result = await counter.increment.aio(counter)
        assert result == 1
        assert counter.count == 1
