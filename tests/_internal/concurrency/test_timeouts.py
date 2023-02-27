import asyncio
import concurrent.futures
import time

import pytest

from prefect._internal.concurrency.timeouts import (
    cancel_async_after,
    cancel_async_at,
    cancel_sync_after,
    cancel_sync_at,
    get_deadline,
)


async def test_cancel_async_after():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_async_after(0.1) as ctx:
            await asyncio.sleep(1)
    t1 = time.perf_counter()

    assert ctx.cancelled
    assert t1 - t0 < 1


def test_cancel_sync_after_in_main_thread():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_sync_after(0.1) as ctx:
            # floats are not suppported by alarm timeouts so this will actually timeout
            # after 1s
            time.sleep(2)
    t1 = time.perf_counter()

    assert ctx.cancelled
    assert t1 - t0 < 2


def test_cancel_sync_after_in_worker_thread():
    def on_worker_thread():
        t0 = time.perf_counter()
        with pytest.raises(TimeoutError):
            with cancel_sync_after(0.1) as ctx:
                # this timeout method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
        t1 = time.perf_counter()
        return t1 - t0, ctx

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(on_worker_thread)
        elapsed_time, ctx = future.result()

    assert elapsed_time < 1
    assert ctx.cancelled


async def test_cancel_async_at():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_async_at(get_deadline(timeout=0.1)) as ctx:
            await asyncio.sleep(1)
    t1 = time.perf_counter()

    assert ctx.cancelled
    assert t1 - t0 < 1


def test_cancel_sync_at():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_sync_at(get_deadline(timeout=0.1)) as ctx:
            # floats are not suppported by alarm timeouts so this will actually timeout
            # after 1s
            time.sleep(2)
    t1 = time.perf_counter()

    assert ctx.cancelled
    assert t1 - t0 < 2
