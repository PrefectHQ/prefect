import asyncio
import concurrent.futures
import contextlib
import contextvars
import time

import pytest

from prefect._internal.concurrency.supervisors import (
    AsyncSupervisor,
    SyncSupervisor,
    call_soon_in_supervising_thread,
    new_supervisor,
)

TEST_CONTEXTVAR = contextvars.ContextVar("TEST_CONTEXTVAR")


def get_contextvar():
    return TEST_CONTEXTVAR.get()


async def aget_contextvar():
    return TEST_CONTEXTVAR.get()


@contextlib.contextmanager
def set_contextvar(value):
    try:
        token = TEST_CONTEXTVAR.set(value)
        yield
    finally:
        TEST_CONTEXTVAR.reset(token)


def fake_submit_fn(__fn, *args, **kwargs):
    future = concurrent.futures.Future()
    return future


def fake_fn(*args, **kwargs):
    pass


def sleep_repeatedly(seconds: int):
    for i in range(seconds * 10):
        time.sleep(float(i) / 10)


def identity(x):
    return x


async def aidentity(x):
    return x


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_soon_in_worker_thread(work):
    supervisor = new_supervisor().call_soon_in_worker_thread(work, 1)
    assert await supervisor.result() == 1


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_soon_in_worker_thread(work):
    supervisor = new_supervisor().call_soon_in_worker_thread(work, 1)
    assert supervisor.result() == 1


async def test_from_async_call_soon_in_runtime_thread():
    supervisor = new_supervisor().call_soon_in_runtime_thread(aidentity, 1)
    assert await supervisor.result() == 1


def test_from_sync_call_soon_in_runtime_thread():
    supervisor = new_supervisor().call_soon_in_runtime_thread(aidentity, 1)
    assert supervisor.result() == 1


async def test_from_async_call_soon_in_runtime_thread_must_be_coroutine_fn():
    with pytest.raises(TypeError, match="coroutine"):
        new_supervisor().call_soon_in_runtime_thread(identity, 1)


def test_from_sync_call_soon_in_runtime_thread_must_be_coroutine_fn():
    with pytest.raises(TypeError, match="coroutine"):
        new_supervisor().call_soon_in_runtime_thread(identity, 1)


async def test_call_soon_in_supervising_thread_no_supervisor():
    with pytest.raises(RuntimeError, match="No supervisor"):
        call_soon_in_supervising_thread(identity, 1)


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_soon_in_supervising_thread_from_worker(work):
    async def worker():
        future = asyncio.wrap_future(call_soon_in_supervising_thread(work, 1))
        assert await future == 1
        return 2

    supervisor = new_supervisor().call_soon_in_worker_thread(worker)
    assert await supervisor.result() == 2


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_soon_in_supervising_thread_from_worker(work):
    def worker():
        future = call_soon_in_supervising_thread(work, 1)
        assert future.result() == 1
        return 2

    supervisor = new_supervisor().call_soon_in_worker_thread(worker)
    assert supervisor.result() == 2


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_soon_in_supervising_thread_from_runtime(work):
    async def from_runtime():
        future = asyncio.wrap_future(call_soon_in_supervising_thread(work, 1))
        assert await future == 1
        return 2

    supervisor = new_supervisor().call_soon_in_runtime_thread(from_runtime)
    assert await supervisor.result() == 2


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_soon_in_supervising_thread_from_runtime(work):
    async def from_runtime():
        future = asyncio.wrap_future(call_soon_in_supervising_thread(work, 1))
        assert await future == 1
        return 2

    supervisor = new_supervisor().call_soon_in_runtime_thread(from_runtime)
    assert supervisor.result() == 2


async def test_from_async_call_soon_in_runtime_thread_captures_context_variables():
    with set_contextvar("test"):
        supervisor = new_supervisor().call_soon_in_runtime_thread(aget_contextvar)
        assert await supervisor.result() == "test"


def test_from_sync_call_soon_in_runtime_thread_captures_context_variables():
    with set_contextvar("test"):
        supervisor = new_supervisor().call_soon_in_runtime_thread(aget_contextvar)
        assert supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
async def test_from_async_call_soon_in_worker_thread_captures_context_variables(get):
    with set_contextvar("test"):
        supervisor = new_supervisor().call_soon_in_worker_thread(get)
        assert await supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
def test_from_sync_call_soon_in_worker_thread_captures_context_variables(get):
    with set_contextvar("test"):
        supervisor = new_supervisor().call_soon_in_worker_thread(get)
        assert supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
async def test_from_async_call_soon_in_supervising_thread_captures_context_varaibles(
    get,
):
    async def from_runtime():
        with set_contextvar("test"):
            future = asyncio.wrap_future(call_soon_in_supervising_thread(get))
        assert await future == "test"

    supervisor = new_supervisor().call_soon_in_runtime_thread(from_runtime)
    await supervisor.result()


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
def test_from_sync_call_soon_in_supervising_thread_captures_context_varaibles(get):
    async def from_runtime():
        with set_contextvar("test"):
            future = asyncio.wrap_future(call_soon_in_supervising_thread(get))
        assert await future == "test"

    supervisor = new_supervisor().call_soon_in_runtime_thread(from_runtime)
    supervisor.result()


@pytest.mark.parametrize("cls", [AsyncSupervisor, SyncSupervisor])
async def test_supervisor_repr(cls):
    supervisor = cls()
    assert (
        repr(supervisor)
        == f"<{cls.__name__} future=<not submitted>, owner='MainThread'>"
    )
    future = supervisor.submit_with(fake_submit_fn, fake_fn, 1, 2)
    assert repr(supervisor) == f"<{cls.__name__} future={future!r}, owner='MainThread'>"


def test_sync_supervisor_timeout_in_worker_thread():
    """
    In this test, a timeout is raised due to a slow call that is occuring on the worker
    thread.
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        supervisor = new_supervisor(timeout=0.1)
        future = supervisor.submit_with(executor.submit, sleep_repeatedly, 1)

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
        supervisor = new_supervisor(timeout=0.1)

        def on_worker_thread():
            # Send sleep to the main thread
            future = supervisor.call_soon_in_supervisor_thread(time.sleep, 2)
            return future

        supervisor.submit_with(executor.submit, on_worker_thread)

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
        supervisor = new_supervisor(timeout=0.1)
        future = supervisor.submit_with(executor.submit, sleep_repeatedly, 1)

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
        supervisor = new_supervisor(timeout=0.1)

        def on_worker_thread():
            # Send sleep to the main thread
            future = supervisor.call_soon_in_supervisor_thread(asyncio.sleep, 1)
            return future

        supervisor.submit_with(executor.submit, on_worker_thread)

        t0 = time.time()
        future = await supervisor.result()
        t1 = time.time()

        assert t1 - t0 < 1

        # The timeout error is not raised by `supervisor.result()` because the worker
        # does not check the result of the future; however, the work that was sent
        # to the main thread should have a timeout error
        with pytest.raises(asyncio.CancelledError):
            future.result()
