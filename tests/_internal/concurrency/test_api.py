import pytest

from prefect._internal.concurrency import from_async, from_sync


def sync_work(x, y):
    return x + y


async def async_work(x, y):
    return x + y


@pytest.mark.parametrize("work", [sync_work, async_work])
async def test_from_async_call_in_worker_thread(work):
    future = from_async.call_soon_in_worker_thread(work, 1, 2)
    assert await future.result() == 3


@pytest.mark.parametrize("work", [sync_work, async_work])
def test_from_sync_call_in_worker_thread(work):
    future = from_sync.call_soon_in_worker_thread(work, 1, 2)
    assert future.result() == 3
