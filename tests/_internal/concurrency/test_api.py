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


def test_from_sync_wait_for_call_in_loop_thread():
    result = from_sync.wait_for_call_in_loop_thread(create_call(aidentity, 1))
    assert result == 1


@pytest.mark.parametrize("from_module", [from_async, from_sync])
async def test_call_soon_in_waiter_thread_no_call(from_module):
    with pytest.raises(RuntimeError, match="No call found in context"):
        getattr(from_module, "call_soon_in_waiter_thread")(create_call(identity, 1))


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_soon_in_waiter_thread_from_worker_thread(work):
    async def worker():
        call = from_async.call_soon_in_waiter_thread(create_call(work, 1))
        assert await call.aresult() == 1
        return 2

    result = await from_async.wait_for_call_in_new_thread(create_call(worker))
    assert result == 2


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_soon_in_waiter_thread_from_worker_thread(work):
    def worker():
        call = from_sync.call_soon_in_waiter_thread(create_call(work, 1))
        assert call.result() == 1
        return 2

    result = from_sync.wait_for_call_in_new_thread(create_call(worker))
    assert result


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_soon_in_waiter_thread_from_loop_thread(work):
    async def from_loop_thread():
        call = from_async.call_soon_in_waiter_thread(create_call(work, 1))
        assert await call.aresult() == 1
        return 2

    result = await from_async.wait_for_call_in_loop_thread(
        create_call(from_loop_thread)
    )
    assert result


async def test_from_async_call_soon_in_waiter_thread_allows_concurrency():
    last_task_run = None

    async def sleep_then_set(n):
        # Sleep for an inverse amount so later tasks sleep less
        print(f"Starting task {n}")
        await asyncio.sleep(1 / (n * 10))
        nonlocal last_task_run
        last_task_run = n
        print(f"Finished task {n}")

    async def from_worker():
        calls = []
        calls.append(
            from_async.call_soon_in_waiter_thread(create_call(sleep_then_set, 1))
        )
        calls.append(
            from_async.call_soon_in_waiter_thread(create_call(sleep_then_set, 2))
        )
        calls.append(
            from_async.call_soon_in_waiter_thread(create_call(sleep_then_set, 3))
        )
        await asyncio.gather(*[call.aresult() for call in calls])
        return last_task_run

    result = await from_async.wait_for_call_in_loop_thread(create_call(from_worker))
    assert result == 1


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_soon_in_waiter_thread_from_loop_thread(work):
    async def from_loop_thread():
        call = from_async.call_soon_in_waiter_thread(create_call(work, 1))
        assert await call.aresult() == 1
        return 2

    result = from_sync.wait_for_call_in_loop_thread(create_call(from_loop_thread))
    assert result


async def test_from_async_wait_for_call_in_loop_thread_captures_context_variables():
    with set_contextvar("test"):
        result = await from_async.wait_for_call_in_loop_thread(
            create_call(aget_contextvar)
        )
        assert result == "test"


def test_from_sync_wait_for_call_in_loop_thread_captures_context_variables():
    with set_contextvar("test"):
        result = from_sync.wait_for_call_in_loop_thread(create_call(aget_contextvar))
        assert result == "test"


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


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
async def test_from_async_call_soon_in_waiter_thread_captures_context_varaibles(
    get,
):
    async def from_loop_thread():
        with set_contextvar("test"):
            call = from_async.call_soon_in_waiter_thread(get)
        assert await call.aresult() == "test"

    await from_async.wait_for_call_in_loop_thread(from_loop_thread)


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
def test_from_sync_call_soon_in_waiter_thread_captures_context_varaibles(get):
    async def from_loop_thread():
        with set_contextvar("test"):
            call = from_async.call_soon_in_waiter_thread(get)
        assert await call.aresult() == "test"

    from_sync.wait_for_call_in_loop_thread(from_loop_thread)


async def test_from_async_wait_for_call_in_loop_thread_timeout():
    with pytest.raises(TimeoutError):
        await from_async.wait_for_call_in_loop_thread(
            create_call(asyncio.sleep, 1),
            timeout=0.1,
        )


def test_from_sync_wait_for_call_in_loop_thread_timeout():
    with pytest.raises(TimeoutError):
        # In this test, there is a slight race condition where the waiter can reach
        # the timeout before the call does resulting in an error during `wait_for...`
        # or the call can encounter the timeout and return before the waiter times out
        # in which the error is raised when the result is retrieved

        from_sync.wait_for_call_in_loop_thread(
            create_call(asyncio.sleep, 1),
            timeout=0.1,
        )


async def test_from_async_wait_for_call_in_new_thread_timeout():
    with pytest.raises(TimeoutError):
        await from_async.wait_for_call_in_new_thread(
            create_call(sleep_repeatedly, 1),
            timeout=0.1,
        )


def test_from_sync_wait_for_call_in_new_thread_timeout():
    with pytest.raises(TimeoutError):
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


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_in_loop_thread(work):
    result = from_sync.call_in_loop_thread(create_call(work, 1))
    assert result == 1


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_in_waiter_thread_from_worker_thread(work):
    async def worker():
        result = await from_async.call_in_waiter_thread(create_call(work, 1))
        assert result == 1
        return 2

    result = await from_async.wait_for_call_in_new_thread(create_call(worker))
    assert result == 2


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_in_waiter_thread_from_worker_thread(work):
    def worker():
        result = from_sync.call_in_waiter_thread(create_call(work, 1))
        assert result == 1
        return 2

    result = from_sync.wait_for_call_in_new_thread(create_call(worker))
    assert result


def test_from_sync_call_in_loop_thread_from_loop_thread():
    def worker():
        # Here, a call is submitted to the loop thread from the loop thread which would
        # deadlock if `call_in_loop_thread` did not detect this case
        result = from_sync.call_in_loop_thread(create_call(identity, 1))
        assert result == 1
        return 2

    result = from_sync.call_in_loop_thread(worker)
    assert result == 2


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
