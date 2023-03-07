import asyncio
import time

import pytest

from prefect._internal.concurrency.portals import WorkerThreadPortal
from prefect._internal.concurrency.waiters import AsyncWaiter, Call, SyncWaiter


def fake_fn(*args, **kwargs):
    pass


def identity(x):
    return x


async def aidentity(x):
    return x


def raises(exc):
    raise exc


async def araises(exc):
    raise exc


def sleep_repeatedly(seconds: int):
    # Synchronous sleeps cannot be interrupted unless a signal is used, so we check
    # for cancellation between sleep calls
    for i in range(seconds * 10):
        time.sleep(float(i) / 10)


@pytest.mark.parametrize("cls", [AsyncWaiter, SyncWaiter])
async def test_waiter_repr(cls):
    waiter = cls(Call.new(fake_fn, 1, 2))
    assert repr(waiter) == f"<{cls.__name__} call=fake_fn(1, 2), owner='MainThread'>"


def test_sync_waiter_timeout_in_worker_thread():
    """
    In this test, a timeout is raised due to a slow call that is occuring on the worker
    thread.
    """
    with WorkerThreadPortal(run_once=True) as portal:
        call = Call.new(sleep_repeatedly, 1)
        waiter = SyncWaiter(call)
        call.set_timeout(0.1)
        portal.submit(call)

    t0 = time.time()
    with pytest.raises(TimeoutError):
        waiter.result()
    t1 = time.time()

    # The call has a timeout error too
    with pytest.raises(TimeoutError):
        call.result()

    assert t1 - t0 < 1


def test_sync_waiter_timeout_in_main_thread():
    """
    In this test, a timeout is raised due to a slow call that is sent back to the main
    thread by the worker thread.
    """
    with WorkerThreadPortal(run_once=True) as portal:

        def on_worker_thread():
            # Send sleep to the main thread
            callback = Call.new(time.sleep, 2)
            call.add_callback(callback)
            return callback

        call = Call.new(on_worker_thread)
        waiter = SyncWaiter(call)
        call.set_timeout(0.1)
        portal.submit(call)

        t0 = time.time()
        call = waiter.result()
        t1 = time.time()

    # The timeout error is not raised by `waiter.result()` because the worker
    # does not check the result of the call; however, the work that was sent
    # to the main thread should have a timeout error
    with pytest.raises(TimeoutError):
        call.result()

    # main thread timeouts round up to the nearest second
    assert t1 - t0 < 2


async def test_async_waiter_timeout_in_worker_thread():
    with WorkerThreadPortal(run_once=True) as portal:
        call = Call.new(sleep_repeatedly, 1)
        waiter = AsyncWaiter(call)
        call.set_timeout(0.1)
        portal.submit(call)

        t0 = time.time()
        with pytest.raises(TimeoutError):
            await waiter.result()
        t1 = time.time()

    assert t1 - t0 < 1

    # The call has a timeout error too
    with pytest.raises(TimeoutError):
        call.result()


async def test_async_waiter_timeout_in_main_thread():
    with WorkerThreadPortal(run_once=True) as portal:

        def on_worker_thread():
            # Send sleep to the main thread
            callback = Call.new(asyncio.sleep, 1)
            call.add_callback(callback)
            return callback

        call = Call.new(on_worker_thread)

        waiter = AsyncWaiter(call)
        call.set_timeout(0.1)
        portal.submit(call)

        t0 = time.time()
        callback = await waiter.result()
        t1 = time.time()

    assert t1 - t0 < 1

    # The timeout error is not raised by `waiter.result()` because the worker
    # does not check the result of the future; however, the work that was sent
    # to the main thread should have a timeout error
    with pytest.raises(asyncio.CancelledError):
        callback.result()


async def test_async_waiter_timeout_in_worker_thread_mixed_sleeps():
    def sync_then_async_sleep():
        # With a timeout of 0.3 and a total sleep of 0.35 but partial sleeps less than
        # that, we ensure that we are enforcing a consistent deadline rather than
        # starting the timeout once for the sync part and again for the async part
        time.sleep(0.1)
        return asyncio.sleep(0.25)

    with WorkerThreadPortal(run_once=True) as portal:
        call = Call.new(sync_then_async_sleep)
        waiter = AsyncWaiter(call)
        call.set_timeout(0.3)
        portal.submit(call)

        t0 = time.time()
        with pytest.raises(TimeoutError):
            await waiter.result()
        t1 = time.time()

        assert t1 - t0 < 1

    # The call has a timeout error too
    with pytest.raises(TimeoutError):
        call.result()


@pytest.mark.parametrize("fn", [identity, aidentity])
def test_sync_call(fn):
    call = Call.new(fn, 1)
    assert call() == 1


async def test_async_call_sync_function():
    call = Call.new(identity, 1)
    assert call() == 1


async def test_async_call_async_function():
    call = Call.new(aidentity, 1)
    assert await call() == 1


@pytest.mark.parametrize("fn", [raises, araises])
def test_sync_call_with_exception(fn):
    call = Call.new(fn, ValueError("test"))
    with pytest.raises(ValueError, match="test"):
        call()


async def test_async_call_sync_function():
    call = Call.new(raises, ValueError("test"))
    with pytest.raises(ValueError, match="test"):
        call()


async def test_async_call_async_function():
    call = Call.new(araises, ValueError("test"))
    coro = call()  # should not raise
    with pytest.raises(ValueError):
        await coro
