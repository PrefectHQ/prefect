import time

import anyio
import pytest

import prefect


def test_sync_task_timeout_in_sync_flow():
    # note the timeout is rounded up to 1s because this task is run on the main thread
    # and a signal is used to interrupt the sleep call and it does not support floats
    @prefect.task(timeout_seconds=0.1)
    def sleep_task():
        time.sleep(3)

    @prefect.flow
    def parent_flow():
        t0 = time.monotonic()
        state = sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = parent_flow()
    assert runtime < 3, "Task should exit early; ran for {runtime}s"
    assert task_state.is_failed()
    with pytest.raises(TimeoutError):
        task_state.result()


async def test_sync_task_timeout_in_async_flow():
    # note the timeout is rounded up to 1s because this task is run on the main thread
    # and a signal is used to interrupt the sleep call and it does not support floats
    @prefect.task(timeout_seconds=0.1)
    def sleep_task():
        time.sleep(3)

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = await parent_flow()
    assert runtime < 3, f"Task should exit early; ran for {runtime}s"
    assert task_state.is_failed()
    with pytest.raises(TimeoutError):
        await task_state.result()


def test_async_task_timeout_in_sync_flow():
    @prefect.task(timeout_seconds=0.1)
    async def sleep_task():
        await anyio.sleep(1)

    @prefect.flow
    def parent_flow():
        t0 = time.monotonic()
        state = sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = parent_flow()
    assert runtime < 1, f"Task should exit early; ran for {runtime}s"
    assert task_state.is_failed()
    with pytest.raises(TimeoutError):
        task_state.result()


async def test_async_task_timeout_in_async_flow():
    @prefect.task(timeout_seconds=0.1)
    async def sleep_task():
        await anyio.sleep(1)

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = await sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = await parent_flow()
    assert runtime < 1, "Task should exit early; ran for {runtime}s"
    assert task_state.is_failed()
    with pytest.raises(TimeoutError):
        await task_state.result()
