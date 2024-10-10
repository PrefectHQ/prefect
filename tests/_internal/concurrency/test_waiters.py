import asyncio
import threading
import time

import pytest

from prefect._internal.concurrency.calls import Call
from prefect._internal.concurrency.cancellation import CancelledError
from prefect._internal.concurrency.threads import WorkerThread
from prefect._internal.concurrency.waiters import (
    AsyncWaiter,
    SyncWaiter,
)


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
    current_thread_name = threading.current_thread().name
    waiter = cls(Call.new(fake_fn, 1, 2))
    assert (
        repr(waiter)
        == f"<{cls.__name__} call=fake_fn(1, 2), owner='{current_thread_name}'>"
    )


def test_async_waiter_created_outside_of_loop():
    call = Call.new(identity, 1)
    call.run()
    asyncio.run(AsyncWaiter(call).wait())
    assert call.result() == 1


def test_async_waiter_early_submission():
    call = Call.new(identity, 1)
    waiter = AsyncWaiter(call)

    # Calls can be submitted before the waiter has a bound event loop
    callback = waiter.submit(Call.new(identity, 2))
    call.run()

    asyncio.run(waiter.wait())
    assert call.result() == 1

    # The call should be executed
    assert callback.result() == 2


def test_async_waiter_done_callback():
    call = Call.new(identity, 1)
    waiter = AsyncWaiter(call)

    callback = Call.new(identity, 2)
    assert not callback.future.done()

    waiter.add_done_callback(callback)
    call.run()
    asyncio.run(waiter.wait())
    assert call.result() == 1

    # The call should be executed
    assert callback.result() == 2


def test_async_waiter_done_callbacks():
    call = Call.new(identity, 1)
    waiter = AsyncWaiter(call)

    callbacks = [Call.new(identity, i) for i in range(10)]
    for callback in callbacks:
        waiter.add_done_callback(callback)

    call.run()
    asyncio.run(waiter.wait())
    assert call.result() == 1

    # The call should be executed
    for i, callback in enumerate(callbacks):
        assert callback.result() == i


def test_sync_waiter_timeout_in_worker_thread():
    """
    In this test, a timeout is raised due to a slow call that is occurring on the worker
    thread.
    """
    done_callback = Call.new(identity, 1)

    with WorkerThread(run_once=True) as runner:
        call = Call.new(sleep_repeatedly, 1)
        waiter = SyncWaiter(call)
        waiter.add_done_callback(done_callback)
        call.set_timeout(0.1)
        runner.submit(call)

    t0 = time.time()
    waiter.wait()
    t1 = time.time()

    with pytest.raises(CancelledError):
        call.result()

    assert t1 - t0 < 2

    assert call.cancelled()
    assert (
        done_callback.result(timeout=0) == 1
    ), "The done callback should still be called on cancel"


@pytest.mark.skip(reason="This test is flaky and should be rewritten")
@pytest.mark.timeout(method="thread")  # pytest-timeout alarm interefres with this test
def test_sync_waiter_timeout_in_main_thread():
    """
    In this test, a timeout is raised due to a slow call that is sent back to the main
    thread by the worker thread.
    """
    done_callback = Call.new(identity, 1)
    waiting_callback = Call.new(sleep_repeatedly, 2)

    with WorkerThread(run_once=True) as runner:

        def on_worker_thread():
            waiter.submit(waiting_callback)
            waiting_callback.result()

        call = Call.new(on_worker_thread)
        waiter = SyncWaiter(call)
        waiter.add_done_callback(done_callback)
        call.set_timeout(0.1)
        runner.submit(call)

        t0 = time.time()
        waiter.wait()
        t1 = time.time()

    with pytest.raises(CancelledError):
        call.result()

    with pytest.raises(CancelledError):
        # This call had no timeout attached so it just gets cancelled
        waiting_callback.result()

    assert t1 - t0 < 2
    assert waiting_callback.cancelled()
    assert call.cancelled()
    assert (
        done_callback.result(timeout=0) == 1
    ), "The done callback should still be called on cancel"


async def test_async_waiter_timeout_in_worker_thread():
    done_callback = Call.new(identity, 1)

    with WorkerThread(run_once=True) as runner:
        call = Call.new(sleep_repeatedly, 1)
        waiter = AsyncWaiter(call)
        waiter.add_done_callback(done_callback)
        call.set_timeout(0.1)
        runner.submit(call)

        t0 = time.time()
        await waiter.wait()
        t1 = time.time()

    assert t1 - t0 < 1

    # The call has a cancelled error
    with pytest.raises(CancelledError):
        call.result()

    assert call.cancelled()
    assert (
        done_callback.result(timeout=0) == 1
    ), "The done callback should still be called on cancel"


async def test_async_waiter_timeout_in_main_thread():
    done_callback = Call.new(identity, 1)
    waiting_callback = Call.new(asyncio.sleep, 2)

    with WorkerThread(run_once=True) as runner:

        def on_worker_thread():
            waiter.submit(waiting_callback)
            waiting_callback.result()

        call = Call.new(on_worker_thread)

        waiter = AsyncWaiter(call)
        waiter.add_done_callback(done_callback)
        call.set_timeout(1)
        runner.submit(call)

        t0 = time.time()
        await waiter.wait()
        t1 = time.time()

    with pytest.raises(CancelledError):
        call.result()

    with pytest.raises(CancelledError):
        waiting_callback.result()

    assert t1 - t0 < 2
    assert call.cancelled()
    assert waiting_callback.cancelled()
    assert (
        done_callback.result(timeout=0) == 1
    ), "The done callback should still be called on cancel"


async def test_async_waiter_timeout_in_worker_thread_mixed_sleeps():
    def sync_then_async_sleep():
        # With a timeout of 0.3 and a total sleep of 0.35 but partial sleeps less than
        # that, we ensure that we are enforcing a consistent deadline rather than
        # starting the timeout once for the sync part and again for the async part
        time.sleep(0.1)
        return asyncio.sleep(0.25)

    with WorkerThread(run_once=True) as runner:
        call = Call.new(sync_then_async_sleep)
        waiter = AsyncWaiter(call)
        call.set_timeout(0.3)
        runner.submit(call)

        t0 = time.time()
        await waiter.wait()
        t1 = time.time()

        assert t1 - t0 < 1

    with pytest.raises(CancelledError):
        call.result()

    assert call.cancelled()


@pytest.mark.parametrize("raise_fn", [raises, araises], ids=["sync", "async"])
@pytest.mark.parametrize(
    "exception_cls", [BaseException, KeyboardInterrupt, SystemExit]
)
async def test_async_waiter_base_exception_in_worker_thread(exception_cls, raise_fn):
    done_callback = Call.new(identity, 1)

    with WorkerThread(run_once=True) as runner:
        call = Call.new(raise_fn, exception_cls("test"))
        waiter = AsyncWaiter(call)
        waiter.add_done_callback(done_callback)
        runner.submit(call)

        # Waiting does not throw an exception
        await waiter.wait()

    # The call has the error attached
    with pytest.raises(exception_cls, match="test"):
        call.result()

    assert (
        done_callback.result(timeout=0) == 1
    ), "The done callback should still be called on exception"


@pytest.mark.parametrize("raise_fn", [raises, araises], ids=["sync", "async"])
@pytest.mark.parametrize(
    "exception_cls", [BaseException, KeyboardInterrupt, SystemExit]
)
async def test_async_waiter_base_exception_in_main_thread(exception_cls, raise_fn):
    done_callback = Call.new(identity, 1)

    with WorkerThread(run_once=True) as runner:

        def on_worker_thread():
            # Send exception to the main thread
            callback = Call.new(raise_fn, exception_cls("test"))
            waiter.submit(callback)
            return callback

        call = Call.new(on_worker_thread)

        waiter = AsyncWaiter(call)
        waiter.add_done_callback(done_callback)
        runner.submit(call)

        await waiter.wait()
        callback = call.result()

    # The base exception error is not raised by `call.result()` because the worker
    # does not check the result of the future; however, the work that was sent
    # to the main thread should have the error
    with pytest.raises(exception_cls, match="test"):
        callback.result()

    assert (
        done_callback.result(timeout=0) == 1
    ), "The done callback should still be called on exception"


@pytest.mark.parametrize("raise_fn", [raises, araises], ids=["sync", "async"])
@pytest.mark.parametrize(
    "exception_cls", [BaseException, KeyboardInterrupt, SystemExit]
)
def test_sync_waiter_base_exception_in_worker_thread(exception_cls, raise_fn):
    done_callback = Call.new(identity, 1)

    with WorkerThread(run_once=True) as runner:
        call = Call.new(raise_fn, exception_cls("test"))
        waiter = SyncWaiter(call)
        waiter.add_done_callback(done_callback)
        runner.submit(call)

        # Waiting does not throw an exception
        waiter.wait()

    # The call has the error too
    with pytest.raises(exception_cls, match="test"):
        call.result()

    assert (
        done_callback.result(timeout=0) == 1
    ), "The done callback should still be called on exception"


@pytest.mark.parametrize("raise_fn", [raises, araises], ids=["sync", "async"])
@pytest.mark.parametrize(
    "exception_cls", [BaseException, KeyboardInterrupt, SystemExit]
)
def test_sync_waiter_base_exception_in_main_thread(exception_cls, raise_fn):
    done_callback = Call.new(identity, 1)

    with WorkerThread(run_once=True) as runner:

        def on_worker_thread():
            # Send exception to the main thread
            callback = Call.new(raise_fn, exception_cls("test"))
            waiter.submit(callback)
            return callback

        call = Call.new(on_worker_thread)

        waiter = SyncWaiter(call)
        waiter.add_done_callback(done_callback)
        runner.submit(call)

        callback = waiter.wait().result()

    # The base exception error is not raised by `call.result()` because the worker
    # does not check the result of the future; however, the work that was sent
    # to the main thread should have the error
    with pytest.raises(exception_cls, match="test"):
        callback.result()
    assert (
        done_callback.result(timeout=0) == 1
    ), "The done callback should still be called on exception"
