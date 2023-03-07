import asyncio
import contextlib
import contextvars
import time

import pytest

from prefect._internal.concurrency.api import create_call, from_async, from_sync


def identity(x):
    return x


async def aidentity(x):
    return x


TEST_CONTEXTVAR = contextvars.ContextVar("TEST_CONTEXTVAR")


def get_contextvar():
    return TEST_CONTEXTVAR.get()


async def aget_contextvar():
    return TEST_CONTEXTVAR.get()


def sleep_repeatedly(seconds: int):
    # Synchronous sleeps cannot be interrupted unless a signal is used, so we check
    # for cancellation between sleep calls
    for i in range(seconds * 10):
        time.sleep(float(i) / 10)


@contextlib.contextmanager
def set_contextvar(value):
    try:
        token = TEST_CONTEXTVAR.set(value)
        yield
    finally:
        TEST_CONTEXTVAR.reset(token)


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_supervise_call_in_new_worker(work):
    supervisor = from_async.call_soon_in_new_thread(create_call(work, 1))
    assert await supervisor.result() == 1


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_supervise_call_in_new_worker(work):
    supervisor = from_sync.call_soon_in_new_thread(create_call(work, 1))
    assert supervisor.result() == 1


async def test_from_async_supervise_call_in_global_thread():
    supervisor = from_async.call_soon_in_global_thread(create_call(aidentity, 1))
    assert await supervisor.result() == 1


def test_from_sync_supervise_call_in_global_thread():
    supervisor = from_sync.call_soon_in_global_thread(create_call(aidentity, 1))
    assert supervisor.result() == 1


@pytest.mark.parametrize("from_module", [from_async, from_sync])
async def test_send_callback_no_call_context(from_module):
    with pytest.raises(RuntimeError, match="No call found in context"):
        getattr(from_module, "send_callback")(create_call(identity, 1))


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_send_callback_from_worker(work):
    async def worker():
        future = from_async.send_callback(create_call(work, 1))
        assert await future == 1
        return 2

    supervisor = from_async.call_soon_in_new_thread(create_call(worker))
    assert await supervisor.result() == 2


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_send_callback_from_worker(work):
    def worker():
        future = from_sync.send_callback(create_call(work, 1))
        assert future.result() == 1
        return 2

    supervisor = from_sync.call_soon_in_new_thread(create_call(worker))
    assert supervisor.result() == 2


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_send_callback_from_global(work):
    async def from_global():
        future = from_async.send_callback(create_call(work, 1))
        assert await future == 1
        return 2

    supervisor = from_async.call_soon_in_global_thread(create_call(from_global))
    assert await supervisor.result() == 2


async def test_from_async_send_callback_from_worker_allows_concurrency():
    last_task_run = None

    async def sleep_then_set(n):
        # Sleep for an inverse amount so later tasks sleep less
        print(f"Starting task {n}")
        await asyncio.sleep(1 / (n * 10))
        nonlocal last_task_run
        last_task_run = n
        print(f"Finished task {n}")

    async def from_worker():
        futures = []
        futures.append(from_async.send_callback(create_call(sleep_then_set, 1)))
        futures.append(from_async.send_callback(create_call(sleep_then_set, 2)))
        futures.append(from_async.send_callback(create_call(sleep_then_set, 3)))
        await asyncio.gather(*futures)
        return last_task_run

    supervisor = from_async.call_soon_in_global_thread(create_call(from_worker))
    assert await supervisor.result() == 1


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_send_callback_from_global(work):
    async def from_global():
        future = from_async.send_callback(create_call(work, 1))
        assert await future == 1
        return 2

    supervisor = from_sync.call_soon_in_global_thread(create_call(from_global))
    assert supervisor.result() == 2


async def test_from_async_supervise_call_in_global_thread_captures_context_variables():
    with set_contextvar("test"):
        supervisor = from_async.call_soon_in_global_thread(create_call(aget_contextvar))
        assert await supervisor.result() == "test"


def test_from_sync_supervise_call_in_global_thread_captures_context_variables():
    with set_contextvar("test"):
        supervisor = from_sync.call_soon_in_global_thread(create_call(aget_contextvar))
        assert supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
async def test_from_async_supervise_call_in_new_worker_captures_context_variables(get):
    with set_contextvar("test"):
        supervisor = from_async.call_soon_in_new_thread(create_call(get))
        assert await supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
def test_from_sync_supervise_call_in_new_worker_captures_context_variables(get):
    with set_contextvar("test"):
        supervisor = from_sync.call_soon_in_new_thread(create_call(get))
        assert supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
async def test_from_async_send_callback_captures_context_varaibles(
    get,
):
    async def from_global():
        with set_contextvar("test"):
            future = from_async.send_callback(create_call(get))
        assert await future == "test"

    supervisor = from_async.call_soon_in_global_thread(create_call(from_global))
    await supervisor.result()


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
def test_from_sync_send_callback_captures_context_varaibles(get):
    async def from_global():
        with set_contextvar("test"):
            future = from_async.send_callback(create_call(get))
        assert await future == "test"

    supervisor = from_sync.call_soon_in_global_thread(create_call(from_global))
    supervisor.result()


async def test_from_async_supervise_call_in_global_thread_timeout():
    supervisor = from_async.call_soon_in_global_thread(
        create_call(asyncio.sleep, 1),
        timeout=0.1,
    )
    with pytest.raises(TimeoutError):
        assert await supervisor.result() == 1


def test_from_sync_supervise_call_in_global_thread_timeout():
    supervisor = from_sync.call_soon_in_global_thread(
        create_call(asyncio.sleep, 1),
        timeout=0.1,
    )
    with pytest.raises(TimeoutError):
        assert supervisor.result() == 1


async def test_from_async_supervise_call_in_worker_thread_timeout():
    supervisor = from_async.call_soon_in_new_thread(
        create_call(sleep_repeatedly, 1),
        timeout=0.1,
    )
    with pytest.raises(TimeoutError):
        assert await supervisor.result() == 1


def test_from_sync_supervise_call_in_worker_thread_timeout():
    supervisor = from_sync.call_soon_in_new_thread(
        create_call(sleep_repeatedly, 1),
        timeout=0.1,
    )
    with pytest.raises(TimeoutError):
        assert supervisor.result() == 1
