import os
import time

import anyio
import pytest

import prefect

# GitHub Actions sets the CI environment variable — the runners are much slower there
# so the sleep time needs to be larger to account for overhead
SLEEP_TIME = 3 if os.environ.get("CI") else 1


def test_sync_task_timeout_in_sync_flow():
    @prefect.task(timeout_seconds=0.1)
    def sleep_task():
        time.sleep(SLEEP_TIME)

    @prefect.flow
    def parent_flow():
        t0 = time.monotonic()
        state = sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = parent_flow()
    assert runtime < SLEEP_TIME, f"Task should exit early; ran for {runtime}s"
    assert task_state.is_failed()
    with pytest.raises(TimeoutError):
        task_state.result()


async def test_sync_task_timeout_in_async_flow():
    @prefect.task(timeout_seconds=0.1)
    def sleep_task():
        time.sleep(SLEEP_TIME)

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = await parent_flow()
    assert runtime < SLEEP_TIME, f"Task should exit early; ran for {runtime}s"
    assert task_state.is_failed()
    with pytest.raises(TimeoutError):
        await task_state.result()


def test_async_task_timeout_in_sync_flow():
    @prefect.task(timeout_seconds=0.1)
    async def sleep_task():
        await anyio.sleep(SLEEP_TIME)

    @prefect.flow
    def parent_flow():
        t0 = time.monotonic()
        state = sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = parent_flow()
    assert runtime < SLEEP_TIME, f"Task should exit early; ran for {runtime}s"
    assert task_state.is_failed()
    with pytest.raises(TimeoutError):
        task_state.result()


async def test_async_task_timeout_in_async_flow():
    @prefect.task(timeout_seconds=0.1)
    async def sleep_task():
        await anyio.sleep(SLEEP_TIME)

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = await sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = await parent_flow()
    assert runtime < SLEEP_TIME, f"Task should exit early; ran for {runtime}s"
    assert task_state.is_failed()
    with pytest.raises(TimeoutError):
        await task_state.result()


async def test_task_timeout_deadline_is_reset_on_retry():
    run_count: int = 0

    @prefect.task(timeout_seconds=0.1, retries=2)
    async def sleep_task():
        nonlocal run_count
        run_count += 1

        # Task should timeout 2 times then succeed on the third run
        if run_count < 3:
            await anyio.sleep(SLEEP_TIME)

        return run_count

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = await sleep_task(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, task_state = await parent_flow()
    assert runtime < SLEEP_TIME, f"Task should exit early; ran for {runtime}s"
    assert await task_state.result() == 3  # Task should run 3 times
