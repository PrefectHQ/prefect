import asyncio
import time

import pytest

from prefect._internal.concurrency.supervisors import (
    AsyncSupervisor,
    Call,
    SyncSupervisor,
)
from prefect._internal.concurrency.workers import WorkerThread


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
    worker = WorkerThread(run_once=True)
    supervisor = cls(Call.new(fake_fn, 1, 2), worker=worker)
    assert (
        repr(supervisor)
        == f"<{cls.__name__} call=fake_fn(1, 2), worker='WorkerThread',"
        " owner='MainThread'>"
    )


def test_sync_supervisor_timeout_in_worker_thread():
    """
    In this test, a timeout is raised due to a slow call that is occuring on the worker
    thread.
    """
    worker = WorkerThread(run_once=True)
    supervisor = SyncSupervisor(
        Call.new(sleep_repeatedly, 1), worker=worker, timeout=0.1
    )
    supervisor.start()

    t0 = time.time()
    with pytest.raises(TimeoutError):
        supervisor.result()
    t1 = time.time()

    # The call has a timeout error too
    with pytest.raises(TimeoutError):
        supervisor._call.result()

    assert t1 - t0 < 1


def test_sync_supervisor_timeout_in_main_thread():
    """
    In this test, a timeout is raised due to a slow call that is sent back to the main
    thread by the worker thread.
    """
    worker = WorkerThread(run_once=True)

    def on_worker_thread():
        # Send sleep to the main thread
        call = supervisor.submit(Call.new(time.sleep, 2))
        return call

    supervisor = SyncSupervisor(Call.new(on_worker_thread), worker=worker, timeout=0.1)
    supervisor.start()

    t0 = time.time()
    call = supervisor.result()
    t1 = time.time()

    # The timeout error is not raised by `supervisor.result()` because the worker
    # does not check the result of the call; however, the work that was sent
    # to the main thread should have a timeout error
    with pytest.raises(TimeoutError):
        call.result()

    # main thread timeouts round up to the nearest second
    assert t1 - t0 < 2


async def test_async_supervisor_timeout_in_worker_thread():
    worker = WorkerThread(run_once=True)
    supervisor = AsyncSupervisor(
        Call.new(sleep_repeatedly, 1), worker=worker, timeout=0.1
    )
    supervisor.start()

    t0 = time.time()
    with pytest.raises(TimeoutError):
        await supervisor.result()
    t1 = time.time()

    assert t1 - t0 < 1

    # The call has a timeout error too
    with pytest.raises(TimeoutError):
        supervisor._call.result()


async def test_async_supervisor_timeout_in_main_thread():
    worker = WorkerThread(run_once=True)

    def on_worker_thread():
        # Send sleep to the main thread
        future = supervisor.submit(Call.new(asyncio.sleep, 1))
        return future

    supervisor = AsyncSupervisor(Call.new(on_worker_thread), worker=worker, timeout=0.1)
    supervisor.start()

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
