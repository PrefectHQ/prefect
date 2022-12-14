import asyncio
import time

import anyio
import pytest

from prefect._internal.concurrency.workers import WorkerThreadPool


def identity(x):
    return x


async def test_submit():
    async with WorkerThreadPool() as pool:
        future = await pool.submit(identity, 1)
        assert await future.aresult() == 1


async def test_submit_many():
    async with WorkerThreadPool() as pool:
        futures = [await pool.submit(identity, i) for i in range(100)]
        results = await asyncio.gather(*[future.aresult() for future in futures])
        assert results == list(range(100))
        assert len(pool._workers) == pool._max_workers


async def test_submit_reuses_idle_thread():
    async with WorkerThreadPool() as pool:
        future = await pool.submit(identity, 1)
        await future.aresult()

        # Spin until the worker is marked as idle
        with anyio.fail_after(1):
            while pool._idle._value == 0:
                await anyio.sleep(0)

        future = await pool.submit(identity, 1)
        await future.aresult()
        assert len(pool._workers) == 1


async def test_submit_after_shutdown():
    pool = WorkerThreadPool()
    await pool.shutdown()

    with pytest.raises(
        RuntimeError, match="Work cannot be submitted to pool after shutdown"
    ):
        await pool.submit(identity, 1)


async def test_submit_during_shutdown():
    async with WorkerThreadPool() as pool:

        async with anyio.create_task_group() as tg:
            await tg.start(pool.shutdown)

            with pytest.raises(
                RuntimeError, match="Work cannot be submitted to pool after shutdown"
            ):
                await pool.submit(identity, 1)


async def test_shutdown_no_workers():
    pool = WorkerThreadPool()
    await pool.shutdown()


async def test_shutdown_multiple_times():
    pool = WorkerThreadPool()
    await pool.submit(identity, 1)
    await pool.shutdown()
    await pool.shutdown()


async def test_shutdown_with_idle_workers():
    pool = WorkerThreadPool()
    futures = [await pool.submit(identity, 1) for _ in range(5)]
    await asyncio.gather(*[future.aresult() for future in futures])
    await pool.shutdown()


async def test_shutdown_with_active_worker():
    pool = WorkerThreadPool()
    future = await pool.submit(time.sleep, 1)
    await pool.shutdown()
    assert await future.aresult() is None


async def test_shutdown_exception_during_join():
    pool = WorkerThreadPool()
    future = await pool.submit(identity, 1)
    await future.aresult()

    try:
        async with anyio.create_task_group() as tg:
            await tg.start(pool.shutdown)
            raise ValueError()
    except ValueError:
        pass

    assert pool._shutdown is True


async def test_context_manager_with_outstanding_future():
    async with WorkerThreadPool() as pool:
        future = await pool.submit(identity, 1)

    assert pool._shutdown is True
    assert await future.aresult() == 1
