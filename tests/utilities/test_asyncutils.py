import asyncio
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from functools import partial, wraps

import anyio
import pytest

from prefect.utilities.asyncutils import (
    GatherIncomplete,
    add_event_loop_shutdown_callback,
    create_gather_task_group,
    gather,
    in_async_main_thread,
    in_async_worker_thread,
    is_async_fn,
    is_async_gen_fn,
    run_async_from_worker_thread,
    run_async_in_new_loop,
    run_sync_in_interruptible_worker_thread,
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


async def test_run_sync_in_interruptible_worker_thread():
    def foo(x, y, z=3):
        return x + y + z

    assert await run_sync_in_interruptible_worker_thread(foo, 1, y=2) == 6


async def test_run_sync_in_interruptible_worker_thread_does_not_hide_exceptions():
    def foo():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        await run_sync_in_interruptible_worker_thread(foo)


async def test_run_sync_in_interruptible_worker_thread_does_not_hide_base_exceptions():
    class LikeKeyboardInterrupt(BaseException):
        """Like a keyboard interrupt but not for real"""

    def foo():
        raise LikeKeyboardInterrupt("test")

    with pytest.raises(LikeKeyboardInterrupt, match="test"):
        await run_sync_in_interruptible_worker_thread(foo)


async def test_run_sync_in_interruptible_worker_thread_function_can_return_exception():
    def foo():
        return ValueError("test")

    result = await run_sync_in_interruptible_worker_thread(foo)

    assert isinstance(result, ValueError)
    assert result.args == ("test",)


async def test_run_sync_in_interruptible_worker_thread_can_be_interrupted():
    i = 0

    def just_sleep():
        nonlocal i
        for i in range(100):  # Sleep for 10 seconds
            time.sleep(0.1)

    with pytest.raises(TimeoutError):
        with anyio.fail_after(1):
            t0 = time.perf_counter()
            await run_sync_in_interruptible_worker_thread(just_sleep)

    t1 = time.perf_counter()
    runtime = t1 - t0
    assert runtime < 2, "The call should be return quickly after timeout"

    # Sleep for an extra second to check if the thread is still running. We cannot
    # check `thread.is_alive()` because it is still alive — presumably this is because
    # AnyIO is using long-lived worker threads instead of creating a new thread per
    # task. Without a check like this, the thread can be running after timeout in the
    # background and we will not know — the next test will start.
    await anyio.sleep(1)

    assert i <= 10, "`just_sleep` should not be running after timeout"


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


@pytest.mark.parametrize("fn", SYNC_COMPAT_TEST_CASES)
async def test_sync_compatible_call_from_worker(fn):
    def run_fn():
        return fn(1, y=2)

    assert await run_sync_in_worker_thread(run_fn) == 6


def test_sync_compatible_allows_direct_access_to_async_fn():
    async def foo():
        pass

    assert sync_compatible(foo).aio is foo


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
    thread = threading.Thread(target=loop.run_until_complete(run_test()))
    thread.start()
    assert not callback_called.wait(timeout=1)
    thread.join(timeout=1)


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
