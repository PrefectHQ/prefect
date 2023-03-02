import time

import anyio
import pytest

import prefect


def test_sync_flow_timeout():
    # note the timeout is rounded up to 1s because this flow is run on the main thread
    # and a signal is used to interrupt the sleep call and it does not support floats
    @prefect.flow(timeout_seconds=0.1)
    def sleep_flow():
        time.sleep(3)

    t0 = time.monotonic()
    state = sleep_flow(return_state=True)
    t1 = time.monotonic()
    runtime = t1 - t0

    assert runtime < 3, "Flow should exit early; ran for {runtime}s"
    assert state.is_failed()
    with pytest.raises(TimeoutError):
        state.result()


async def test_async_flow_timeout():
    @prefect.flow(timeout_seconds=0.1)
    async def sleep_flow():
        await anyio.sleep(3)

    t0 = time.monotonic()
    state = await sleep_flow(return_state=True)
    t1 = time.monotonic()
    runtime = t1 - t0

    assert runtime < 3, "Flow should exit early; ran for {runtime}s"
    assert state.is_failed()
    with pytest.raises(TimeoutError):
        await state.result()


def test_sync_flow_timeout_in_sync_flow():
    # note the timeout is rounded up to 1s because this flow is run on the main thread
    # and a signal is used to interrupt the sleep call and it does not support floats
    @prefect.flow(timeout_seconds=1)
    def sleep_flow():
        time.sleep(3)

    @prefect.flow
    def parent_flow():
        t0 = time.monotonic()
        state = sleep_flow(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, flow_state = parent_flow()

    assert runtime < 3, "Flow should exit early; ran for {runtime}s"
    assert flow_state.is_failed()
    with pytest.raises(TimeoutError):
        flow_state.result()


async def test_sync_flow_timeout_in_async_flow():
    # note the timeout is rounded up to 1s because this flow is run on the main thread
    # and a signal is used to interrupt the sleep call and it does not support floats
    @prefect.flow(timeout_seconds=0.1)
    def sleep_flow():
        time.sleep(3)

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = sleep_flow(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, flow_state = await parent_flow()

    assert runtime < 3, f"Flow should exit early; ran for {runtime}s"
    assert flow_state.is_failed()
    with pytest.raises(TimeoutError):
        await flow_state.result()


def test_async_flow_timeout_in_sync_flow():
    @prefect.flow(timeout_seconds=0.1)
    async def sleep_flow():
        await anyio.sleep(1)

    @prefect.flow
    def parent_flow():
        t0 = time.monotonic()
        state = sleep_flow(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, flow_state = parent_flow()

    assert runtime < 1, f"Flow should exit early; ran for {runtime}s"
    assert flow_state.is_failed()
    with pytest.raises(TimeoutError):
        flow_state.result()


async def test_async_flow_timeout_in_async_flow():
    @prefect.flow(timeout_seconds=0.1)
    async def sleep_flow():
        await anyio.sleep(1)

    @prefect.flow
    async def parent_flow():
        t0 = time.monotonic()
        state = await sleep_flow(return_state=True)
        t1 = time.monotonic()
        return t1 - t0, state

    runtime, flow_state = await parent_flow()

    assert runtime < 1, "Flow should exit early; ran for {runtime}s"
    assert flow_state.is_failed()
    with pytest.raises(TimeoutError):
        await flow_state.result()
