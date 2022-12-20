import asyncio

import pytest

from prefect._internal.concurrency.executor import Executor


def identity(x):
    return x


async def aidentity(x):
    await asyncio.sleep(0)
    return x


@pytest.mark.parametrize("worker_type", ["thread", "process"])
@pytest.mark.parametrize("fn", [identity, aidentity], ids=["sync", "async"])
def test_submit(fn, worker_type):
    with Executor(worker_type=worker_type) as executor:
        future = executor.submit(fn, 1)
        assert future.result() == 1


@pytest.mark.parametrize("worker_type", ["thread", "process"])
@pytest.mark.parametrize("fn", [identity, aidentity], ids=["sync", "async"])
def test_map(fn, worker_type):
    with Executor(worker_type=worker_type) as executor:
        results = executor.map(fn, range(100))
        assert list(results) == list(range(100))


@pytest.mark.parametrize("worker_type", ["thread", "process"])
@pytest.mark.parametrize("fn", [identity, aidentity], ids=["sync", "async"])
def test_submit_many_single_worker(fn, worker_type):
    with Executor(max_workers=1, worker_type=worker_type) as executor:
        futures = [executor.submit(fn, i) for i in range(100)]
        results = [future.result() for future in futures]
        assert results == list(range(100))


def test_submit_after_shutdown():
    with Executor() as executor:
        pass

    with pytest.raises(
        RuntimeError, match="cannot schedule new futures after shutdown"
    ):
        executor.submit(identity, 1)


async def test_async_context_manager_with_no_futures():
    async with Executor():
        pass


async def test_async_context_manager_with_completed_future():
    async with Executor() as executor:
        future = executor.submit(identity, 1)
        await asyncio.wrap_future(future)


async def test_async_context_manager_with_outstanding_future():
    async with Executor() as executor:
        future = executor.submit(identity, 1)

    assert future.result() == 1
