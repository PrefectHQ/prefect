import asyncio
import concurrent.futures
import time

import pytest

from prefect._internal.concurrency.supervisors import (
    AsyncSupervisor,
    Call,
    SyncSupervisor,
)


def fake_submit_fn(__fn, *args, **kwargs):
    future = concurrent.futures.Future()
    return future


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


@pytest.mark.parametrize("cls", [AsyncSupervisor, SyncSupervisor])
async def test_supervisor_repr(cls):
    supervisor = cls(Call.new(fake_fn, 1, 2), submit_fn=fake_submit_fn)
    assert (
        repr(supervisor)
        == f"<{cls.__name__} call=fake_fn(1, 2), submit_fn='fake_submit_fn',"
        " owner='MainThread'>"
    )


def test_sync_supervisor_timeout_in_worker_thread():
    """
    In this test, a timeout is raised due to a slow call that is occuring on the worker
    thread.
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        supervisor = SyncSupervisor(
            Call.new(sleep_repeatedly, 1), submit_fn=executor.submit, timeout=0.1
        )
        future = supervisor.submit()

        t0 = time.time()
        with pytest.raises(TimeoutError):
            supervisor.result()
        t1 = time.time()

        with pytest.raises(TimeoutError):
            future.result()

        assert t1 - t0 < 1


def test_sync_supervisor_timeout_in_main_thread():
    """
    In this test, a timeout is raised due to a slow call that is sent back to the main
    thread by the worker thread.
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:

        def on_worker_thread():
            # Send sleep to the main thread
            future = supervisor.send_call_to_supervisor(Call.new(time.sleep, 2))
            return future

        supervisor = SyncSupervisor(
            Call.new(on_worker_thread), submit_fn=executor.submit, timeout=0.1
        )
        supervisor.submit()

        t0 = time.time()
        future = supervisor.result()
        t1 = time.time()

        # The timeout error is not raised by `supervisor.result()` because the worker
        # does not check the result of the future; however, the work that was sent
        # to the main thread should have a timeout error
        with pytest.raises(TimeoutError):
            future.result()

        # main thread timeouts round up to the nearest second
        assert t1 - t0 < 2


async def test_async_supervisor_timeout_in_worker_thread():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        supervisor = AsyncSupervisor(
            Call.new(sleep_repeatedly, 1), submit_fn=executor.submit, timeout=0.1
        )
        future = supervisor.submit()

        t0 = time.time()
        with pytest.raises(TimeoutError):
            await supervisor.result()
        t1 = time.time()

        assert t1 - t0 < 1

        # The future has a timeout error too
        with pytest.raises(TimeoutError):
            future.result()


async def test_async_supervisor_timeout_in_main_thread():
    with concurrent.futures.ThreadPoolExecutor() as executor:

        def on_worker_thread():
            # Send sleep to the main thread
            future = supervisor.send_call_to_supervisor(Call.new(asyncio.sleep, 1))
            return future

        supervisor = AsyncSupervisor(
            Call.new(on_worker_thread), submit_fn=executor.submit, timeout=0.1
        )
        supervisor.submit()

        t0 = time.time()
        future = await supervisor.result()
        t1 = time.time()

        assert t1 - t0 < 1

        # The timeout error is not raised by `supervisor.result()` because the worker
        # does not check the result of the future; however, the work that was sent
        # to the main thread should have a timeout error
        with pytest.raises(asyncio.CancelledError):
            future.result()


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
