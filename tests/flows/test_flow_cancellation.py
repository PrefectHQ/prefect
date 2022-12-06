import anyio
import pytest

from prefect import OrionClient, flow
from prefect.context import get_run_context
from prefect.exceptions import CancelledRun
from prefect.settings import PREFECT_CANCEL_CHECK_QUERY_INTERVAL, temporary_settings
from prefect.states import Cancelled


@pytest.fixture(autouse=True)
def check_for_cancellation_fast():
    with temporary_settings({PREFECT_CANCEL_CHECK_QUERY_INTERVAL: 0.1}):
        yield


async def test_flow_run_cancelled_while_running(orion_client: OrionClient):
    event = anyio.Event()
    flow_run_context = None

    @flow
    async def foo():
        nonlocal flow_run_context
        flow_run_context = get_run_context()
        event.set()
        await anyio.sleep_forever()

    with pytest.raises(CancelledRun, match="test"):
        async with anyio.create_task_group() as tg:
            tg.start_soon(foo)

            # Once the flow run is running, set a cancelled state
            await event.wait()
            await orion_client.set_flow_run_state(
                flow_run_context.flow_run.id, Cancelled(message="test")
            )


async def test_child_flow_run_cancelled_while_running(orion_client: OrionClient):
    event = anyio.Event()
    parent_flow_run_context = None
    child_flow_run_context = None

    @flow
    async def parent():
        nonlocal parent_flow_run_context
        parent_flow_run_context = get_run_context()
        await child()

    @flow
    async def child():
        nonlocal child_flow_run_context
        child_flow_run_context = get_run_context()
        event.set()
        await anyio.sleep_forever()

    with pytest.raises(CancelledRun, match="test"):
        async with anyio.create_task_group() as tg:
            tg.start_soon(parent)

            # Once the flow run is running, set a cancelled state
            await event.wait()
            await orion_client.set_flow_run_state(
                child_flow_run_context.flow_run.id, Cancelled(message="test")
            )

    parent_flow_run_context = await orion_client.read_flow_run(
        parent_flow_run_context.flow_run.id
    )
    assert parent_flow_run_context.state.is_cancelled()


async def test_parent_flow_run_cancelled_while_child_running(orion_client: OrionClient):
    event = anyio.Event()
    parent_flow_run_context = None
    child_flow_run_context = None

    @flow
    async def parent():
        nonlocal parent_flow_run_context
        parent_flow_run_context = get_run_context()
        await child()

    @flow
    async def child():
        nonlocal child_flow_run_context
        child_flow_run_context = get_run_context()
        event.set()
        await anyio.sleep_forever()

    with pytest.raises(CancelledRun, match="test"):
        async with anyio.create_task_group() as tg:
            tg.start_soon(parent)

            # Once the flow run is running, set a cancelled state
            await event.wait()
            await orion_client.set_flow_run_state(
                parent_flow_run_context.flow_run.id, Cancelled(message="test")
            )

    child_flow_run = await orion_client.read_flow_run(
        child_flow_run_context.flow_run.id
    )
    assert child_flow_run.state.is_cancelled()
