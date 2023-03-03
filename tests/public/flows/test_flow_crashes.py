"""
Tests flow run crash handling.

Assertions need to be made with the flow run state from the API rather than locally
since crashes are always reraised and no state is returned by the run. Crashes must
be reraised to prevent Prefect from swallowing important signals like keyboard
interrupts.
"""
import asyncio

import anyio
import pytest

import prefect
import prefect.context
import prefect.exceptions
from prefect.client.schemas import FlowRun


async def assert_flow_run_crashed(flow_run: FlowRun, expected_message: str):
    """
    Utility for asserting that flow runs are crashed.
    """
    assert flow_run.state.is_crashed()
    assert expected_message in flow_run.state.message
    with pytest.raises(prefect.exceptions.CrashedRun, match=expected_message):
        await flow_run.state.result()


async def test_anyio_cancellation_crashes_flow(orion_client):
    started = asyncio.Future()
    flow_run_id = None

    @prefect.flow
    async def my_flow():
        started.set_result(prefect.context.get_run_context().flow_run.id)
        await anyio.sleep_forever()

    async with anyio.create_task_group() as tg:
        tg.start_soon(my_flow)

        # Wait for the flow run to start, retrieve the flow run id
        flow_run_id = await started
        tg.cancel_scope.cancel()

    flow_run = await orion_client.read_flow_run(flow_run_id)
    await assert_flow_run_crashed(
        flow_run, expected_message="Execution was cancelled by the runtime environment"
    )


async def test_anyio_cancellation_crashes_flow_with_timeout_configured(orion_client):
    """
    Our timeout cancellation mechanisms for async flows can overlap with AnyIO
    cancellation. This test defends against regressions where reporting a timed out
    flow obscures a crash from cancellation.
    """
    started = asyncio.Future()
    flow_run_id = None

    @prefect.flow(timeout_seconds=10)
    async def my_flow():
        started.set_result(prefect.context.get_run_context().flow_run.id)
        await anyio.sleep_forever()

    async with anyio.create_task_group() as tg:
        tg.start_soon(my_flow)

        # Wait for the flow run to start, retrieve the flow run id
        flow_run_id = await started
        tg.cancel_scope.cancel()

    flow_run = await orion_client.read_flow_run(flow_run_id)
    await assert_flow_run_crashed(
        flow_run, expected_message="Execution was cancelled by the runtime environment"
    )


async def test_anyio_cancellation_crashes_parent_and_child_flow(orion_client):
    child_started = asyncio.Future()
    parent_started = asyncio.Future()
    child_flow_run_id = parent_flow_run_id = None

    @prefect.flow
    async def child_flow():
        child_started.set_result(prefect.context.get_run_context().flow_run.id)
        await anyio.sleep_forever()

    @prefect.flow
    async def parent_flow():
        parent_started.set_result(prefect.context.get_run_context().flow_run.id)
        await child_flow()

    async with anyio.create_task_group() as tg:
        tg.start_soon(parent_flow)

        # Wait for the flow runs to start, retrieve the flow run ids
        parent_flow_run_id = await parent_started
        child_flow_run_id = await child_started
        tg.cancel_scope.cancel()

    child_flow_run = await orion_client.read_flow_run(child_flow_run_id)
    await assert_flow_run_crashed(
        child_flow_run,
        expected_message="Execution was cancelled by the runtime environment",
    )

    parent_flow_run = await orion_client.read_flow_run(parent_flow_run_id)
    await assert_flow_run_crashed(
        parent_flow_run,
        expected_message="Execution was cancelled by the runtime environment",
    )


@pytest.mark.filterwarnings(
    "ignore::pytest.PytestUnhandledThreadExceptionWarning"
)  # Pytest complains about unhandled exception in runtime thread
@pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
async def test_interrupt_crashes_flow(orion_client, interrupt_type):
    flow_run_id = None

    @prefect.flow
    async def my_flow():
        nonlocal flow_run_id
        flow_run_id = prefect.context.get_run_context().flow_run.id
        raise interrupt_type()

    with pytest.raises(interrupt_type):
        await my_flow()

    flow_run = await orion_client.read_flow_run(flow_run_id)
    await assert_flow_run_crashed(
        flow_run,
        expected_message="Execution was aborted",
    )


@pytest.mark.filterwarnings(
    "ignore::pytest.PytestUnhandledThreadExceptionWarning"
)  # Pytest complains about unhandled exception in runtime thread
@pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
async def test_interrupt_in_child_crashes_parent_and_child_flow(
    orion_client, interrupt_type
):
    child_flow_run_id = parent_flow_run_id = None

    @prefect.flow
    async def child_flow():
        nonlocal child_flow_run_id
        child_flow_run_id = prefect.context.get_run_context().flow_run.id
        raise interrupt_type()

    @prefect.flow
    async def parent_flow():
        nonlocal parent_flow_run_id
        parent_flow_run_id = prefect.context.get_run_context().flow_run.id
        await child_flow()

    with pytest.raises(interrupt_type):
        await parent_flow()

    parent_flow_run = await orion_client.read_flow_run(parent_flow_run_id)
    await assert_flow_run_crashed(
        parent_flow_run,
        expected_message="Execution was aborted",
    )

    child_flow_run = await orion_client.read_flow_run(child_flow_run_id)
    await assert_flow_run_crashed(
        child_flow_run,
        expected_message="Execution was aborted",
    )
