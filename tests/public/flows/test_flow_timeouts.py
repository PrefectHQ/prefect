import os
import time

import anyio
import pytest

import prefect

# GitHub Actions sets the CI environment variable — the runners are much slower there
# so the sleep time needs to be larger to account for overhead
SLEEP_TIME = 4 if os.environ.get("CI") else 2


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_sync_flow_timeout():
    @prefect.flow(timeout_seconds=0.1)
    def sleep_flow():
        time.sleep(SLEEP_TIME)

    t0 = time.monotonic()
    state = sleep_flow(return_state=True)
    t1 = time.monotonic()
    runtime = t1 - t0

    assert runtime < SLEEP_TIME, f"Flow should exit early; ran for {runtime}s"
    assert state.is_failed()
    with pytest.raises(TimeoutError):
        state.result()


async def test_async_flow_timeout():
    @prefect.flow(timeout_seconds=0.1)
    async def sleep_flow():
        await anyio.sleep(SLEEP_TIME)

    t0 = time.monotonic()
    state = await sleep_flow(return_state=True)
    t1 = time.monotonic()
    runtime = t1 - t0

    assert runtime < SLEEP_TIME, f"Flow should exit early; ran for {runtime}s"
    assert state.is_failed()
    with pytest.raises(TimeoutError):
        await state.result()


@pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
def test_sync_flow_timeout_in_sync_flow():
    @prefect.flow(timeout_seconds=0.1)
    def sleep_flow():
        time.sleep(SLEEP_TIME)

    @prefect.flow
    def parent_flow():
        t0 = time.monotonic()
        state = sleep_flow(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, flow_state = parent_flow()

    assert runtime < SLEEP_TIME, f"Flow should exit early; ran for {runtime}s"
    assert flow_state.is_failed()
    with pytest.raises(TimeoutError):
        flow_state.result()


async def test_sync_flow_timeout_in_async_flow():
    @prefect.flow(timeout_seconds=0.1)
    def sleep_flow():
        # Sleep in 0.1 second intervals; the sync flow runs in a worker
        # thread which does not interrupt long-running sleep calls
        for _ in range(SLEEP_TIME * 10):
            time.sleep(0.1)

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = sleep_flow(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, flow_state = await parent_flow()

    assert runtime < SLEEP_TIME, f"Flow should exit early; ran for {runtime}s"
    assert flow_state.is_failed()
    with pytest.raises(TimeoutError):
        await flow_state.result()


def test_async_flow_timeout_in_sync_flow():
    @prefect.flow(timeout_seconds=0.1)
    async def sleep_flow():
        await anyio.sleep(SLEEP_TIME)

    @prefect.flow
    def parent_flow():
        t0 = time.monotonic()
        state = sleep_flow(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, flow_state = parent_flow()

    assert runtime < SLEEP_TIME, f"Flow should exit early; ran for {runtime}s"
    assert flow_state.is_failed()
    with pytest.raises(TimeoutError):
        flow_state.result()


async def test_async_flow_timeout_in_async_flow():
    @prefect.flow(timeout_seconds=0.1)
    async def sleep_flow():
        await anyio.sleep(SLEEP_TIME)

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = await sleep_flow(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, flow_state = await parent_flow()

    assert runtime < SLEEP_TIME, f"Flow should exit early; ran for {runtime}s"
    assert flow_state.is_failed()
    with pytest.raises(TimeoutError):
        await flow_state.result()
