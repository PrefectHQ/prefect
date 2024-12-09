"""
Tests flow run crash handling.

Assertions need to be made with the flow run state from the API rather than locally
since crashes are always reraised and no state is returned by the run. Crashes must
be reraised to prevent Prefect from swallowing important signals like keyboard
interrupts.
"""

import asyncio
import os
import signal
import threading
from unittest.mock import ANY, MagicMock

import anyio
import pytest

import prefect
import prefect.context
import prefect.exceptions
import prefect.flow_engine
from prefect.client.schemas import FlowRun
from prefect.testing.utilities import AsyncMock


async def assert_flow_run_crashed(flow_run: FlowRun, expected_message: str):
    """
    Utility for asserting that flow runs are crashed.
    """
    assert flow_run.state.is_crashed(), flow_run.state
    assert expected_message in flow_run.state.message
    with pytest.raises(prefect.exceptions.CrashedRun, match=expected_message):
        await flow_run.state.result()


async def test_anyio_cancellation_crashes_flow(prefect_client):
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

    flow_run = await prefect_client.read_flow_run(flow_run_id)
    await assert_flow_run_crashed(
        flow_run, expected_message="Execution was cancelled by the runtime environment"
    )


@pytest.mark.skip(
    reason="Not able to support in the new engine. This was only possible with the internal concurrency utils.",
)
async def test_anyio_cancellation_crashes_flow_with_timeout_configured(prefect_client):
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

    flow_run = await prefect_client.read_flow_run(flow_run_id)
    await assert_flow_run_crashed(
        flow_run, expected_message="Execution was cancelled by the runtime environment"
    )


async def test_anyio_cancellation_crashes_parent_and_child_flow(prefect_client):
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

    child_flow_run = await prefect_client.read_flow_run(child_flow_run_id)
    await assert_flow_run_crashed(
        child_flow_run,
        expected_message="Execution was cancelled by the runtime environment",
    )

    parent_flow_run = await prefect_client.read_flow_run(parent_flow_run_id)
    await assert_flow_run_crashed(
        parent_flow_run,
        expected_message="Execution was cancelled by the runtime environment",
    )


@pytest.mark.xfail  # The child cannot be reported as crashed due to client closure
async def test_anyio_cancellation_crashes_child_flow(prefect_client):
    child_started = asyncio.Future()
    child_flow_run_id = parent_flow_run_id = None

    @prefect.flow
    async def child_flow():
        child_started.set_result(prefect.context.get_run_context().flow_run.id)
        await anyio.sleep_forever()

    @prefect.flow
    async def parent_flow():
        async with anyio.create_task_group() as tg:
            tg.start_soon(child_flow)

            # Wait for the flow run to start, retrieve the flow run ids
            child_flow_run_id = await child_started
            tg.cancel_scope.cancel()

        return prefect.context.get_run_context().flow_run.id, child_flow_run_id

    parent_flow_run_id, child_flow_run_id = await parent_flow()

    child_flow_run = await prefect_client.read_flow_run(child_flow_run_id)
    await assert_flow_run_crashed(
        child_flow_run,
        expected_message="Execution was cancelled by the runtime environment",
    )

    parent_flow_run = await prefect_client.read_flow_run(parent_flow_run_id)
    assert parent_flow_run.state.is_completed()


@pytest.mark.filterwarnings(
    "ignore::pytest.PytestUnhandledThreadExceptionWarning"
)  # Pytest complains about unhandled exception in runtime thread
@pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
async def test_interrupt_crashes_flow(prefect_client, interrupt_type):
    flow_run_id = None

    @prefect.flow
    async def my_flow():
        nonlocal flow_run_id
        flow_run_id = prefect.context.get_run_context().flow_run.id
        raise interrupt_type()

    with pytest.raises(interrupt_type):
        await my_flow()

    flow_run = await prefect_client.read_flow_run(flow_run_id)
    await assert_flow_run_crashed(
        flow_run,
        expected_message="Execution was aborted",
    )


@pytest.mark.filterwarnings(
    "ignore::pytest.PytestUnhandledThreadExceptionWarning"
)  # Pytest complains about unhandled exception in runtime thread
@pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
async def test_interrupt_in_child_crashes_parent_and_child_flow(
    prefect_client, interrupt_type
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

    parent_flow_run = await prefect_client.read_flow_run(parent_flow_run_id)
    await assert_flow_run_crashed(
        parent_flow_run,
        expected_message="Execution was aborted",
    )

    child_flow_run = await prefect_client.read_flow_run(child_flow_run_id)
    await assert_flow_run_crashed(
        child_flow_run,
        expected_message="Execution was aborted",
    )


@pytest.fixture
def mock_sigterm_handler():
    if threading.current_thread() != threading.main_thread():
        pytest.skip("Can't test signal handlers from a thread")
    mock = MagicMock()

    def handler(*args, **kwargs):
        mock(*args, **kwargs)

    prev_handler = signal.signal(signal.SIGTERM, handler)
    try:
        yield handler, mock
    finally:
        signal.signal(signal.SIGTERM, prev_handler)


async def test_sigterm_crashes_flow(prefect_client, mock_sigterm_handler):
    flow_run_id = None

    @prefect.flow
    async def my_flow():
        nonlocal flow_run_id
        flow_run_id = prefect.context.get_run_context().flow_run.id
        os.kill(os.getpid(), signal.SIGTERM)

    # The signal should be reraised as an exception
    with pytest.raises(prefect.exceptions.TerminationSignal):
        await my_flow()

    flow_run = await prefect_client.read_flow_run(flow_run_id)
    await assert_flow_run_crashed(
        flow_run,
        expected_message="Execution was aborted by a termination signal",
    )

    handler, mock = mock_sigterm_handler
    # The original signal handler should be restored
    assert signal.getsignal(signal.SIGTERM) == handler

    # The original signal handler should be called too
    mock.assert_called_once_with(signal.SIGTERM, ANY)


@pytest.mark.skip(
    reason="Relies explicitly on the old engine's subprocess handling. Consider rewriting for the new engine.",
)
def test_sigterm_crashes_deployed_flow(
    prefect_client, mock_sigterm_handler, monkeypatch, flow_run
):
    # This is not a part of our public API and generally we should not write tests like
    # this here, but we do not have robust testing utilities for deployed runs yet.
    from prefect.engine import enter_flow_run_engine_from_subprocess

    @prefect.flow
    async def my_flow():
        assert prefect.context.get_run_context().flow_run.id == flow_run.id
        os.kill(os.getpid(), signal.SIGTERM)

    # Patch `load_flow_from_flow_run` to bypass all deployment loading logic and use
    # our test flow
    monkeypatch.setattr(
        "prefect.engine.load_flow_from_flow_run", AsyncMock(return_value=my_flow)
    )
    # The signal should be reraised as an exception
    with pytest.raises(prefect.exceptions.TerminationSignal):
        enter_flow_run_engine_from_subprocess(flow_run.id)

    flow_run = asyncio.run(prefect_client.read_flow_run(flow_run.id))
    asyncio.run(
        assert_flow_run_crashed(
            flow_run,
            expected_message="Execution was aborted by a termination signal",
        )
    )

    handler, mock = mock_sigterm_handler
    # The original signal handler should be restored
    assert signal.getsignal(signal.SIGTERM) == handler

    # The original signal handler should be called too
    mock.assert_called_once_with(signal.SIGTERM, ANY)
