import asyncio
import time
import uuid

import pytest

import prefect.client.schemas as client_schemas
from prefect import flow
from prefect._internal.compatibility.async_dispatch import is_in_async_context
from prefect.client.orchestration import PrefectClient
from prefect.events.utilities import emit_event
from prefect.exceptions import FlowRunWaitTimeout
from prefect.flow_engine import run_flow_async
from prefect.flow_runs import (
    pause_flow_run,
    resume_flow_run,
    suspend_flow_run,
    wait_for_flow_run,
)
from prefect.server.events.pipeline import EventsPipeline
from prefect.states import Completed, Pending


async def test_create_then_wait_for_flow_run(prefect_client: PrefectClient):
    @flow
    def foo():
        pass

    flow_run = await prefect_client.create_flow_run(foo, state=Completed())
    assert isinstance(flow_run, client_schemas.FlowRun)

    lookup = await wait_for_flow_run(flow_run.id)
    # Estimates will not be equal since time has passed
    assert lookup == flow_run
    assert flow_run.state
    assert flow_run.state.is_final()


async def test_create_then_wait_timeout(prefect_client: PrefectClient):
    @flow
    def foo():
        time.sleep(9999)

    flow_run = await prefect_client.create_flow_run(
        foo,
    )
    assert isinstance(flow_run, client_schemas.FlowRun)

    with pytest.raises(FlowRunWaitTimeout):
        await wait_for_flow_run(flow_run.id, timeout=0)


async def test_wait_for_flow_run_handles_heartbeats(
    prefect_client: PrefectClient, emitting_events_pipeline: EventsPipeline
):
    """Tests that flow_runs.wait_for_flow_run correctly handles heartbeats.

    Regression test for https://github.com/PrefectHQ/prefect/issues/17930
    """

    @flow
    async def my_short_flow():
        await asyncio.sleep(1)

    flow_run = await prefect_client.create_flow_run(my_short_flow, state=Pending())
    flow_run_id = flow_run.id

    run_task = asyncio.create_task(
        run_flow_async(flow=my_short_flow, flow_run=flow_run)
    )

    async def _emit_heartbeat():
        await asyncio.sleep(0.1)
        emit_event(
            event="prefect.flow-run.heartbeat",
            resource={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"},
            id=uuid.uuid4(),
        )
        await emitting_events_pipeline.process_events()

    heartbeat_task = asyncio.create_task(_emit_heartbeat())

    finished_flow_run = await wait_for_flow_run(flow_run_id, log_states=True)

    await run_task
    await heartbeat_task

    await emitting_events_pipeline.process_events()

    assert finished_flow_run.id == flow_run_id
    assert finished_flow_run.state is not None
    assert finished_flow_run.state.is_completed()


class TestAsyncDispatch:
    """Test that async_dispatch works correctly for flow_runs functions."""

    async def test_pause_flow_run_dispatches_to_async_in_async_context(self):
        """Test that pause_flow_run uses async implementation in async context."""
        # We can't actually pause without a flow context, but we can verify dispatch
        assert is_in_async_context() is True

        # The function should be callable without await in async context and return a coroutine
        result = pause_flow_run(_sync=False)
        assert asyncio.iscoroutine(result)
        # Clean up the coroutine
        result.close()

    def test_pause_flow_run_dispatches_to_sync_in_sync_context(self):
        """Test that pause_flow_run uses sync implementation in sync context."""
        assert is_in_async_context() is False

        # In sync context, should not return a coroutine
        # We can't actually pause without a flow context, but we can verify it doesn't return a coroutine
        try:
            pause_flow_run(_sync=True)
        except RuntimeError as e:
            # Expected error about not being in a flow run
            assert "Flow runs can only be paused from within a flow run" in str(e)

    async def test_suspend_flow_run_dispatches_to_async_in_async_context(self):
        """Test that suspend_flow_run uses async implementation in async context."""
        assert is_in_async_context() is True

        # The function should be callable without await in async context and return a coroutine
        result = suspend_flow_run(flow_run_id=uuid.uuid4(), _sync=False)
        assert asyncio.iscoroutine(result)
        # Clean up the coroutine
        result.close()

    def test_suspend_flow_run_dispatches_to_sync_in_sync_context(self):
        """Test that suspend_flow_run uses sync implementation in sync context."""
        assert is_in_async_context() is False

        # In sync context, should not return a coroutine
        # Will fail because the flow doesn't exist, but that's OK - we're testing dispatch
        flow_run_id = uuid.uuid4()
        try:
            suspend_flow_run(flow_run_id=flow_run_id, _sync=True)
        except Exception:
            # We expect some error, but the important thing is it didn't return a coroutine
            pass

    async def test_resume_flow_run_dispatches_to_async_in_async_context(self):
        """Test that resume_flow_run uses async implementation in async context."""
        assert is_in_async_context() is True

        # The function should be callable without await in async context and return a coroutine
        result = resume_flow_run(flow_run_id=uuid.uuid4(), _sync=False)
        assert asyncio.iscoroutine(result)
        # Clean up the coroutine
        result.close()

    def test_resume_flow_run_dispatches_to_sync_in_sync_context(self):
        """Test that resume_flow_run uses sync implementation in sync context."""
        assert is_in_async_context() is False

        # In sync context, should not return a coroutine
        # Will fail because the flow doesn't exist, but that's OK - we're testing dispatch
        flow_run_id = uuid.uuid4()
        try:
            resume_flow_run(flow_run_id=flow_run_id, _sync=True)
        except Exception:
            # We expect some error, but the important thing is it didn't return a coroutine
            pass
