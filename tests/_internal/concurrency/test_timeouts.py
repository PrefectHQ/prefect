import asyncio
import concurrent.futures
import time

import pytest

from prefect._internal.concurrency.timeouts import cancel_async_after, cancel_sync_after


async def test_cancel_async_after():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_async_after(0.1):
            await asyncio.sleep(1)
    t1 = time.perf_counter()

    assert t1 - t0 < 1


def test_cancel_sync_after_in_main_thread():
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        with cancel_sync_after(0.1):
            # floats are not suppported by alarm timeouts so this will actually timeout
            # after 1s
            time.sleep(2)
    t1 = time.perf_counter()

    assert t1 - t0 < 2


def test_cancel_sync_after_in_worker_thread():
    def on_worker_thread():
        t0 = time.perf_counter()
        with pytest.raises(TimeoutError):
            with cancel_sync_after(0.1):
                # this timeout method does not interrupt sleep calls, the timeout is
                # raised on the next instruction
                for _ in range(10):
                    time.sleep(0.1)
        t1 = time.perf_counter()
        return t1 - t0

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(on_worker_thread)
        assert future.result() < 1
