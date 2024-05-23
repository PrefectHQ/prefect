import asyncio
import contextlib
import contextvars
import time

import pytest

from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect._internal.concurrency.cancellation import CancelledError
from prefect._internal.concurrency.threads import wait_for_global_loop_exit


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
async def test_from_async_wait_for_call_in_new_thread(work):
    result = await from_async.wait_for_call_in_new_thread(create_call(work, 1))
    assert result == 1


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_wait_for_call_in_new_thread(work):
    result = from_sync.wait_for_call_in_new_thread(create_call(work, 1))
    assert result == 1


async def test_from_async_wait_for_call_in_loop_thread():
    result = await from_async.wait_for_call_in_loop_thread(create_call(aidentity, 1))
    assert result == 1
    wait_for_global_loop_exit()


def test_from_sync_wait_for_call_in_loop_thread():
    result = from_sync.wait_for_call_in_loop_thread(create_call(aidentity, 1))
    assert result == 1
    wait_for_global_loop_exit()


async def test_from_async_wait_for_call_in_loop_thread_captures_context_variables():
    with set_contextvar("test"):
        result = await from_async.wait_for_call_in_loop_thread(
            create_call(aget_contextvar)
        )
        assert result == "test"

    wait_for_global_loop_exit()


def test_from_sync_wait_for_call_in_loop_thread_captures_context_variables():
    with set_contextvar("test"):
        result = from_sync.wait_for_call_in_loop_thread(create_call(aget_contextvar))
        assert result == "test"

    wait_for_global_loop_exit()


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
async def test_from_async_wait_for_call_in_new_thread_captures_context_variables(get):
    with set_contextvar("test"):
        result = await from_async.wait_for_call_in_new_thread(get)
        assert result == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
def test_from_sync_wait_for_call_in_new_thread_captures_context_variables(get):
    with set_contextvar("test"):
        result = from_sync.wait_for_call_in_new_thread(get)
        assert result == "test"


async def test_from_async_wait_for_call_in_loop_thread_timeout():
    with pytest.raises(CancelledError):
        await from_async.wait_for_call_in_loop_thread(
            create_call(asyncio.sleep, 1),
            timeout=0.1,
        )

    wait_for_global_loop_exit()


def test_from_sync_wait_for_call_in_loop_thread_timeout():
    with pytest.raises(CancelledError):
        # In this test, there is a slight race condition where the waiting can reach
        # the timeout before the call does resulting in an error during `wait_for...`
        # or the call can encounter the timeout and return before the waiting times out
        # in which the error is raised when the result is retrieved

        from_sync.wait_for_call_in_loop_thread(
            create_call(asyncio.sleep, 1),
            timeout=0.1,
        )

    wait_for_global_loop_exit()


async def test_from_async_wait_for_call_in_new_thread_timeout():
    with pytest.raises(CancelledError):
        await from_async.wait_for_call_in_new_thread(
            create_call(sleep_repeatedly, 1),
            timeout=0.1,
        )


def test_from_sync_wait_for_call_in_new_thread_timeout():
    with pytest.raises(CancelledError):
        from_sync.wait_for_call_in_new_thread(
            create_call(sleep_repeatedly, 1),
            timeout=0.1,
        )


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_in_new_thread(work):
    result = await from_async.call_in_new_thread(create_call(work, 1))
    assert result == 1


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_in_new_thread(work):
    result = from_sync.call_in_new_thread(create_call(work, 1))
    assert result == 1


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_in_loop_thread(work):
    result = await from_async.call_in_loop_thread(create_call(work, 1))
    assert result == 1

    wait_for_global_loop_exit()


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_in_loop_thread(work):
    result = from_sync.call_in_loop_thread(create_call(work, 1))
    assert result == 1

    wait_for_global_loop_exit()


def test_from_sync_call_in_loop_thread_from_loop_thread():
    def worker():
        # Here, a call is submitted to the loop thread from the loop thread which would
        # deadlock if `call_in_loop_thread` did not detect this case
        result = from_sync.call_in_loop_thread(create_call(identity, 1))
        assert result == 1
        return 2

    result = from_sync.call_in_loop_thread(worker)
    assert result == 2

    wait_for_global_loop_exit()


async def test_from_async_call_in_loop_thread_from_loop_thread():
    async def worker():
        # Unlike `test_from_sync_call_in_loop_thread_from_loop_thread` this does not
        # have special handling; it should just work since the `await` unblocks the
        # event loop
        result = await from_async.call_in_loop_thread(create_call(identity, 1))
        assert result == 1
        return 2

    result = await from_async.call_in_loop_thread(worker)
    assert result == 2

    wait_for_global_loop_exit()
