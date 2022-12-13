import concurrent.futures

import anyio
import pytest

from prefect._internal.concurrency.primitives import Event, Future
from prefect.testing.utilities import exceptions_equal


def test_event_set_in_sync_context_before_wait():

    event = Event()
    event.set()

    async def main():
        with anyio.fail_after(1):
            await event.wait()

    anyio.run(main)


async def test_event_set_in_async_context_before_wait():
    event = Event()
    event.set()
    await event.wait()


async def test_event_set_from_async_task():
    event = Event()

    async def set_event():
        event.set()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            tg.start_soon(event.wait)
            tg.start_soon(set_event)


async def test_event_set_from_sync_thread():
    event = Event()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            tg.start_soon(event.wait)
            tg.start_soon(anyio.to_thread.run_sync, event.set)


async def test_event_set_from_sync_thread_before_wait():
    event = Event()

    async def set_event(task_status):
        await anyio.to_thread.run_sync(event.set)
        task_status.started()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            await tg.start(set_event)
            tg.start_soon(event.wait)


async def test_event_created_and_set_from_sync_thread():
    def create_event():
        return Event()

    async def create_and_set_event(task_status):
        event = await anyio.to_thread.run_sync(create_event)
        task_status.started(event)
        await anyio.to_thread.run_sync(event.set)

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            event = await tg.start(create_and_set_event)
            tg.start_soon(event.wait)


async def test_event_set_from_async_thread():
    event = Event()

    async def set_event():
        event.set()

    def set_event_in_new_loop():
        anyio.run(set_event)

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            tg.start_soon(event.wait)
            tg.start_soon(anyio.to_thread.run_sync, set_event_in_new_loop)


async def test_event_set_from_async_thread_before_wait():
    event = Event()

    async def set_event():
        event.set()

    def set_event_in_new_loop():
        anyio.run(set_event)

    await anyio.to_thread.run_sync(set_event_in_new_loop)
    with anyio.fail_after(1):
        await event.wait()


def test_event_is_set():
    event = Event()
    assert not event.is_set()
    event.set()
    assert event.is_set()


async def test_future_result_set_in_same_async_context():
    future = Future()
    future.set_result("test")
    assert await future.aresult() == "test"


async def test_future_result_from_async_context():
    future = Future()
    future.set_result("test")
    with pytest.raises(RuntimeError, match="cannot be called from an async thread"):
        future.result()


async def test_future_result_from_sync_context():
    future = Future()
    future.set_result("test")
    assert await anyio.to_thread.run_sync(future.result) == "test"


async def test_future_result_set_from_async_task():
    future = Future()
    result = None

    async def set_result():
        future.set_result("test")

    async def get_result():
        nonlocal result
        result = await future.aresult()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            tg.start_soon(get_result)
            tg.start_soon(set_result)

    assert result == "test"
    assert await future.aresult() == "test"


async def test_future_result_set_from_sync_thread():
    future = Future()
    result = None

    async def get_result():
        nonlocal result
        result = await future.aresult()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            tg.start_soon(get_result)
            tg.start_soon(anyio.to_thread.run_sync, future.set_result, "test")

    assert result == "test"
    assert await future.aresult() == "test"


async def test_future_result_set_to_exception():
    future = Future()
    future.set_exception(ValueError("test"))
    with pytest.raises(ValueError, match="test"):
        await future.aresult()


async def test_future_result_set_to_exception_instance():
    future = Future()
    future.set_result(ValueError("test"))
    result = await future.aresult()
    assert exceptions_equal(result, ValueError("test"))


async def test_future_cancel():
    future = Future()
    assert future.cancel() is True
    with pytest.raises(concurrent.futures.CancelledError):
        await future.aresult()


async def test_future_cancel_after_running():
    future = Future()
    assert future.set_running_or_notify_cancel() is True
    assert future.cancel() is False


async def test_future_set_running_or_notify_cancel():
    future = Future()
    assert future.set_running_or_notify_cancel() is True
    future.set_result("test")
    await future.aresult() == "test"

    future = Future()
    future.cancel()
    assert future.set_running_or_notify_cancel() is False


async def test_future_from_existing_sync_future():
    sync_future = concurrent.futures.Future()
    future = Future.from_existing(sync_future)
    sync_future.set_result("test")
    assert await future.aresult() == "test"
