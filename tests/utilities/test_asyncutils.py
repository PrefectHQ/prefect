import asyncio
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from functools import partial, wraps

import anyio
import pytest

from prefect._internal.concurrency.threads import get_run_sync_loop
from prefect.context import ContextModel
from prefect.utilities.asyncutils import (
    GatherIncomplete,
    LazySemaphore,
    add_event_loop_shutdown_callback,
    create_gather_task_group,
    gather,
    in_async_main_thread,
    in_async_worker_thread,
    is_async_fn,
    is_async_gen_fn,
    run_async_from_worker_thread,
    run_async_in_new_loop,
    run_coro_as_sync,
    run_sync_in_worker_thread,
    sync_compatible,
)


def test_is_async_fn_sync():
    def foo():
        pass

    assert not is_async_fn(foo)


def test_is_async_fn_lambda():
    assert not is_async_fn(lambda: True)


def test_is_async_fn_sync_context_manager():
    @contextmanager
    def foo():
        pass

    assert not is_async_fn(foo)


def test_is_async_fn_async():
    async def foo():
        pass

    assert is_async_fn(foo)


def test_is_async_fn_async_decorated_with_sync():
    def wrapper(fn):
        @wraps(fn)
        def inner():
            return fn()

        return inner

    @wrapper
    async def foo():
        pass

    assert is_async_fn(foo)


def test_is_async_fn_async_decorated_with_asyncontextmanager():
    @asynccontextmanager
    async def foo():
        yield False

    assert not is_async_fn(foo)


def test_is_async_gen_fn_async_decorated_with_asyncontextmanager():
    @asynccontextmanager
    async def foo():
        yield True

    assert is_async_gen_fn(foo)


def test_is_async_gen_fn_sync_decorated_with_contextmanager():
    @contextmanager
    def foo():
        yield True

    assert not is_async_gen_fn(foo)


def test_is_async_gen_fn_async_that_returns():
    async def foo():
        return False

    assert not is_async_gen_fn(foo)


def test_is_async_gen_fn_async_that_yields():
    async def foo():
        yield True

    assert is_async_gen_fn(foo)


def test_in_async_main_thread_sync():
    assert not in_async_main_thread()


async def test_in_async_main_thread_async():
    assert in_async_main_thread()


async def test_in_async_main_thread_worker():
    assert not await run_sync_in_worker_thread(in_async_main_thread)


def test_in_async_worker_thread_sync():
    assert not in_async_worker_thread()


async def test_in_async_worker_thread_async():
    assert not in_async_worker_thread()


async def test_in_async_worker_thread_worker():
    assert await run_sync_in_worker_thread(in_async_worker_thread)


def test_run_async_in_new_loop():
    async def foo(x, y, z=3):
        return x + y + z

    assert run_async_in_new_loop(foo, 1, y=2) == 6


async def test_run_async_in_new_loop_does_not_work_from_async():
    async def foo(x, y, z=3):
        return x + y + z

    with pytest.raises(RuntimeError, match="Already running"):
        run_async_in_new_loop(foo, 1, y=2)


async def test_run_sync_in_worker_thread():
    def foo(x, y, z=3):
        return x + y + z

    assert await run_sync_in_worker_thread(foo, 1, y=2) == 6


async def test_run_sync_in_worker_thread_does_not_hide_exceptions():
    def foo():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        await run_sync_in_worker_thread(foo)


async def test_run_async_from_worker_thread():
    async def foo(x, y, z=3):
        return x + y + z

    def outer():
        return run_async_from_worker_thread(foo, 1, y=2)

    assert await run_sync_in_worker_thread(outer) == 6


@sync_compatible
async def sync_compatible_fn(x, y, z=3):
    return x + y + z


class SyncCompatibleClass:
    attr = 4

    @staticmethod
    @sync_compatible
    async def static_method(x, y, z=3):
        assert SyncCompatibleClass.attr == 4, "Can access class attributes"
        return x + y + z

    @classmethod
    @sync_compatible
    async def class_method(cls, x, y, z=3):
        assert cls.attr == 4, "`cls` is sent correctly`"
        return x + y + z

    @sync_compatible
    async def instance_method(self, x, y, z=3):
        assert self.attr == 4, "`self` is sent correctly"
        return x + y + z


SYNC_COMPAT_TEST_CASES = [
    sync_compatible_fn,
    SyncCompatibleClass.static_method,
    SyncCompatibleClass.class_method,
    SyncCompatibleClass().instance_method,
]


@pytest.mark.skip(
    reason="Not supported with new engine",
)
@pytest.mark.parametrize("fn", SYNC_COMPAT_TEST_CASES)
def test_sync_compatible_call_from_sync(fn):
    assert fn(1, y=2) == 6


@pytest.mark.parametrize("fn", SYNC_COMPAT_TEST_CASES)
async def test_sync_compatible_call_from_async(fn):
    assert await fn(1, y=2) == 6


async def test_sync_compatible_call_from_sync_in_async_thread():
    # Here we are in the async main thread

    def run_fn():
        # Here we are back in a sync context but still in the async main thread
        return sync_compatible_fn(1, y=2)

    # Returns a coroutine
    coro = run_fn()

    assert await coro == 6


async def test_sync_compatible_call_with_taskgroup():
    # Checks for an async caller by inspecting the caller's frame can fail when using
    # task groups due to internal mechanisms in anyio
    results = []

    @sync_compatible
    async def sync_compatible_fn(*args, task_status=None):
        if task_status is not None:
            task_status.started()
        result = sum(args)
        results.append(result)

    async with anyio.create_task_group() as tg:
        await tg.start(sync_compatible_fn, 1, 2)
        tg.start_soon(sync_compatible_fn, 1, 2)

    assert results == [3, 3]


@pytest.mark.skip(
    reason="Not supported with new engine",
)
@pytest.mark.parametrize("fn", SYNC_COMPAT_TEST_CASES)
async def test_sync_compatible_call_from_worker(fn):
    def run_fn():
        return fn(1, y=2)

    assert await run_sync_in_worker_thread(run_fn) == 6


def test_sync_compatible_allows_direct_access_to_async_fn():
    async def foo():
        pass

    assert sync_compatible(foo).aio is foo


def test_sync_compatible_allows_forced_behavior_sync():
    async def foo():
        return 42

    assert sync_compatible(foo)(_sync=True) == 42


async def test_sync_compatible_allows_forced_behavior_sync_and_async():
    async def foo():
        return 42

    assert sync_compatible(foo)(_sync=True) == 42
    assert await sync_compatible(foo)(_sync=False) == 42
    assert await sync_compatible(foo)() == 42


def test_sync_compatible_requires_async_function():
    with pytest.raises(TypeError, match="must be async"):

        @sync_compatible
        def foo():
            pass


def test_sync_compatible_with_async_context_manager():
    with pytest.raises(ValueError, match="Async generators cannot yet be marked"):

        @sync_compatible
        @asynccontextmanager
        async def foo():
            yield "bar"


def test_add_event_loop_shutdown_callback_is_called_with_asyncio_run():
    callback_called = threading.Event()

    async def set_event():
        callback_called.set()

    async def run_test():
        await add_event_loop_shutdown_callback(set_event)

    thread = threading.Thread(target=asyncio.run(run_test()))
    thread.start()
    assert callback_called.wait(timeout=1)
    thread.join(timeout=1)


def test_add_event_loop_shutdown_callback_is_called_with_anyio_run():
    callback_called = threading.Event()

    async def set_event():
        callback_called.set()

    async def run_test():
        await add_event_loop_shutdown_callback(set_event)

    thread = threading.Thread(target=anyio.run(run_test))
    thread.start()
    assert callback_called.wait(timeout=1)
    thread.join(timeout=1)


def test_add_event_loop_shutdown_callback_is_not_called_with_loop_run_until_complete():
    callback_called = threading.Event()

    async def set_event():
        # Should not occur in this test
        callback_called.set()

    async def run_test():
        await add_event_loop_shutdown_callback(set_event)

    loop = asyncio.new_event_loop()
    try:
        thread = threading.Thread(target=loop.run_until_complete(run_test()))
        thread.start()
        assert not callback_called.wait(timeout=1)
        thread.join(timeout=1)
    finally:
        loop.close()


async def test_gather():
    async def foo(i):
        return i + 1

    results = await gather(*[partial(foo, i) for i in range(10)])
    assert results == [await foo(i) for i in range(10)]


async def test_gather_is_robust_with_return_types_that_break_equality_checks():
    """
    Some libraries like pandas override the equality operator and can fail if gather
    performs an __eq__ check with the GatherIncomplete type
    """

    class Foo:
        def __eq__(self, __o: object) -> bool:
            raise ValueError()

    async def foo():
        return Foo()

    results = await gather(*[partial(foo) for _ in range(2)])
    assert len(results) == 2
    assert all(isinstance(x, Foo) for x in results)


async def test_gather_task_group_get_result():
    async def foo():
        await anyio.sleep(0.1)
        return 1

    async with create_gather_task_group() as tg:
        k = tg.start_soon(foo)
        with pytest.raises(GatherIncomplete):
            tg.get_result(k)

    assert tg.get_result(k) == 1


async def test_gather_task_group_get_result_bad_uuid():
    async with create_gather_task_group() as tg:
        pass

    with pytest.raises(KeyError):
        tg.get_result(uuid.uuid4())


async def test_lazy_semaphore_initialization():
    initial_value = 5
    lazy_semaphore = LazySemaphore(lambda: initial_value)

    assert lazy_semaphore._semaphore is None

    lazy_semaphore._initialize_semaphore()

    assert lazy_semaphore._semaphore._value == initial_value

    async with lazy_semaphore as semaphore:
        assert lazy_semaphore._semaphore is not None
        assert isinstance(semaphore, asyncio.Semaphore)
        assert lazy_semaphore._semaphore._value == initial_value - 1

    assert lazy_semaphore._semaphore._value == initial_value


class TestRunCoroAsSync:
    def test_run_coro_as_sync(self):
        async def foo():
            return 42

        assert run_coro_as_sync(foo()) == 42

    def test_run_coro_as_sync_error(self):
        async def foo():
            raise ValueError("test-42")

        with pytest.raises(ValueError, match="test-42"):
            run_coro_as_sync(foo())

    def test_nested_run_sync(self):
        async def foo():
            return 42

        async def bar():
            return run_coro_as_sync(foo())

        assert run_coro_as_sync(bar()) == 42

    def test_run_coro_as_sync_in_async(self):
        async def foo():
            return 42

        async def bar():
            return run_coro_as_sync(foo())

        assert asyncio.run(bar()) == 42

    async def test_run_coro_as_sync_in_async_with_await(self):
        async def foo():
            return 42

        async def bar():
            return run_coro_as_sync(foo())

        await bar() == 42

    def test_run_coro_as_sync_in_async_error(self):
        async def foo():
            raise ValueError("test-42")

        async def bar():
            return run_coro_as_sync(foo())

        with pytest.raises(ValueError, match="test-42"):
            asyncio.run(bar())

    def test_context_carries_to_async_frame(self):
        """
        Ensures that ContextVars set in a parent scope of `run_sync` are automatically
        carried over to the async frame.
        """

        class MyVar(ContextModel):
            __var__ = ContextVar("my_var")
            x: int = 1

        async def load_var():
            return MyVar.get().x

        async def parent():
            with MyVar(x=42):
                return run_coro_as_sync(load_var())

        # this has to be run via asyncio.run because
        # otherwise the context is maintained automatically
        assert asyncio.run(parent()) == 42

    def test_context_carries_to_nested_async_frame(self):
        """
        Ensures that ContextVars set in a parent scope of `run_sync` are automatically
        carried over to the async frame.
        """

        class MyVar(ContextModel):
            __var__ = ContextVar("my_var")
            x: int = 1

        async def load_var():
            return MyVar.get().x

        async def intermediate():
            val1 = run_coro_as_sync(load_var())
            with MyVar(x=99):
                val2 = run_coro_as_sync(load_var())
            return val1, val2

        async def parent():
            with MyVar(x=42):
                return run_coro_as_sync(intermediate())

        # this has to be run via asyncio.run because
        # otherwise the context is maintained automatically
        assert asyncio.run(parent()) == (42, 99)

    def test_run_coro_as_sync_runs_in_run_sync_thread(self):
        """
        run_coro_as_sync should always submit coros to the same run_sync loop thread
        """
        run_sync_loop = get_run_sync_loop()

        async def foo():
            return (threading.current_thread(), asyncio.get_running_loop())

        assert run_coro_as_sync(foo()) == (run_sync_loop.thread, run_sync_loop._loop)

    def test_nested_run_coro_as_sync_does_not_run_in_run_sync_thread(self):
        """
        nested run_coro_as_sync calls should not run in the run_sync loop thread because it would deadlock,
        so they make a new thread / loop
        """
        run_sync_loop = get_run_sync_loop()

        async def bar():
            return dict(bar=[threading.current_thread(), asyncio.get_running_loop()])

        async def foo():
            result = run_coro_as_sync(bar())
            result["foo"] = (threading.current_thread(), asyncio.get_running_loop())
            return result

        result = run_coro_as_sync(foo())
        assert result["bar"][0] != run_sync_loop.thread
        assert result["bar"][1] != run_sync_loop._loop
        assert result["foo"][0] == run_sync_loop.thread
        assert result["foo"][1] == run_sync_loop._loop

    def test_twice_nested_run_coro_as_sync_does_not_run_in_run_sync_thread(self):
        """
        Ensure that creating new threads/loops isn't based on the parent call, but is inherited by
        all nested calls
        """
        run_sync_loop = get_run_sync_loop()

        async def baz():
            return dict(baz=[threading.current_thread(), asyncio.get_running_loop()])

        async def bar():
            result = run_coro_as_sync(baz())
            result["bar"] = (threading.current_thread(), asyncio.get_running_loop())
            return result

        async def foo():
            result = run_coro_as_sync(bar())
            result["foo"] = (threading.current_thread(), asyncio.get_running_loop())
            return result

        result = run_coro_as_sync(foo())
        assert result["baz"][0] != run_sync_loop.thread
        assert result["baz"][1] != run_sync_loop._loop
        assert result["bar"][0] != run_sync_loop.thread
        assert result["bar"][1] != run_sync_loop._loop
        assert result["foo"][0] == run_sync_loop.thread
        assert result["foo"][1] == run_sync_loop._loop
