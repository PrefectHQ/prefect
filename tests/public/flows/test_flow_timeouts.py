import time

import anyio
import pytest

import prefect

# The sleep time should be much longer than the declared flow timeouts in the tests
# below in order to give them all time for the mechanics to work.  If the timeouts do
# not work at all, the tests will be cancelled by the pytest-timeout timeout mechanism,
# telling us that we have failed to enforce the timeout
FLOW_TIMEOUT = 0.1
SLEEP_TIME = FLOW_TIMEOUT * 1000


async def test_sync_flow_timeout():
    flow_completed = False

    @prefect.flow(timeout_seconds=FLOW_TIMEOUT)
    def sleep_flow():
        # Sleep in 0.1 second intervals; the sync flow runs in a worker
        # thread which does not interrupt long-running sleep calls
        for _ in range(int(SLEEP_TIME)):
            time.sleep(0.1)

        nonlocal flow_completed
        flow_completed = True

    state = sleep_flow(return_state=True)

    assert not flow_completed
    assert state.is_failed()
    with pytest.raises(TimeoutError):
        await state.result()


async def test_async_flow_timeout():
    flow_completed = False

    @prefect.flow(timeout_seconds=FLOW_TIMEOUT)
    async def sleep_flow():
        await anyio.sleep(SLEEP_TIME)
        nonlocal flow_completed
        flow_completed = True

    state = await sleep_flow(return_state=True)

    assert not flow_completed
    assert state.is_failed()
    with pytest.raises(TimeoutError):
        await state.result()


# In the subflow tests below, the odd return values of (None, state) prevent
# prefect from treating the return value as the state for the _parent_ flow


async def test_sync_subflow_timeout_in_sync_flow():
    subflow_completed = False

    @prefect.flow(timeout_seconds=FLOW_TIMEOUT)
    def sleep_flow():
        # Sleep in 0.1 second intervals; the sync flow runs in a worker
        # thread which does not interrupt long-running sleep calls
        for _ in range(int(SLEEP_TIME)):
            time.sleep(0.1)

        nonlocal subflow_completed
        subflow_completed = True

    @prefect.flow
    def parent_flow():
        subflow_state = sleep_flow(return_state=True)
        return (None, subflow_state)

    (_, subflow_state) = parent_flow()

    assert not subflow_completed
    assert subflow_state.is_failed()
    with pytest.raises(TimeoutError):
        await subflow_state.result()


async def test_sync_subflow_timeout_in_async_flow():
    subflow_completed = False

    @prefect.flow(timeout_seconds=FLOW_TIMEOUT)
    def sleep_flow():
        # Sleep in 0.1 second intervals; the sync flow runs in a worker
        # thread which does not interrupt long-running sleep calls
        for _ in range(int(SLEEP_TIME)):
            time.sleep(0.1)

        nonlocal subflow_completed
        subflow_completed = True

    @prefect.flow
    async def parent_flow():
        subflow_state = sleep_flow(return_state=True)
        return (None, subflow_state)

    (_, subflow_state) = await parent_flow()

    assert not subflow_completed
    assert subflow_state.is_failed()
    with pytest.raises(TimeoutError):
        await subflow_state.result()


@pytest.mark.skip(
    reason="Not supported by new engine",
)
def test_async_subflow_timeout_in_sync_flow():
    subflow_completed = False

    @prefect.flow(timeout_seconds=FLOW_TIMEOUT)
    async def sleep_flow():
        await anyio.sleep(SLEEP_TIME)

        nonlocal subflow_completed
        subflow_completed = True

    @prefect.flow
    def parent_flow():
        subflow_state = sleep_flow(return_state=True)
        return (None, subflow_state)

    (_, subflow_state) = parent_flow()

    assert not subflow_completed
    assert subflow_state.is_failed()
    with pytest.raises(TimeoutError):
        subflow_state.result()


async def test_async_subflow_timeout_in_async_flow():
    subflow_completed = False

    @prefect.flow(timeout_seconds=FLOW_TIMEOUT)
    async def sleep_flow():
        await anyio.sleep(SLEEP_TIME)

        nonlocal subflow_completed
        subflow_completed = True

    @prefect.flow
    async def parent_flow():
        subflow_state = await sleep_flow(return_state=True)
        return (None, subflow_state)

    (_, subflow_state) = await parent_flow()

    assert not subflow_completed
    assert subflow_state.is_failed()
    with pytest.raises(TimeoutError):
        await subflow_state.result()
