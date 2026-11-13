import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

import prefect.client.schemas as client_schemas
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.events import Event, Resource
from prefect.events.utilities import emit_event
from prefect.exceptions import FlowRunWaitTimeout, NotPausedError
from prefect.flow_engine import run_flow_async
from prefect.flow_runs import (
    apause_flow_run,
    aresume_flow_run,
    asuspend_flow_run,
    pause_flow_run,
    resume_flow_run,
    suspend_flow_run,
    wait_for_flow_run,
)
from prefect.server.events.pipeline import EventsPipeline
from prefect.states import Completed, Pending, Running


async def test_create_then_wait_for_flow_run(prefect_client: PrefectClient):
    @flow(name=f"foo_{uuid.uuid4()}")
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
    @flow(name=f"foo_{uuid.uuid4()}")
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

    @flow(name=f"my_short_flow_{uuid.uuid4()}")
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


class TestWaitForFlowRunAfterFinalEvent:
    """
    Regression tests for https://github.com/PrefectHQ/prefect/issues/23668
    """

    @pytest.fixture
    async def flow_run(self, prefect_client: PrefectClient) -> client_schemas.FlowRun:
        @flow(name=f"foo_{uuid.uuid4()}")
        def foo():
            pass

        return await prefect_client.create_flow_run(foo, state=Running())

    @pytest.fixture
    def stale_reads(
        self,
        monkeypatch: pytest.MonkeyPatch,
        prefect_client: PrefectClient,
        flow_run: client_schemas.FlowRun,
    ) -> list[client_schemas.FlowRun]:
        """
        Delivers a `Completed` event after moving the flow run to `Completed`,
        while API reads return the pre-transition flow run until the returned
        list is cleared.
        """
        stale = [flow_run]
        read_flow_run = prefect_client.read_flow_run

        async def _read_flow_run(flow_run_id: uuid.UUID) -> client_schemas.FlowRun:
            fresh = await read_flow_run(flow_run_id)
            return stale[0] if stale else fresh

        @asynccontextmanager
        async def _subscriber(**kwargs: Any) -> AsyncIterator[AsyncIterator[Event]]:
            async def _events() -> AsyncIterator[Event]:
                await prefect_client.set_flow_run_state(
                    flow_run.id, Completed(), force=True
                )
                yield Event(
                    event="prefect.flow-run.Completed",
                    resource=Resource(
                        {
                            "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                            "prefect.state-type": "COMPLETED",
                        }
                    ),
                )
                await asyncio.Event().wait()

            yield _events()

        monkeypatch.setattr(prefect_client, "read_flow_run", _read_flow_run)
        monkeypatch.setattr("prefect.flow_runs.get_events_subscriber", _subscriber)
        return stale

    async def test_reads_until_final_state_after_final_event(
        self,
        prefect_client: PrefectClient,
        flow_run: client_schemas.FlowRun,
        stale_reads: list[client_schemas.FlowRun],
    ):
        async def _become_visible() -> None:
            await asyncio.sleep(0.5)
            stale_reads.clear()

        visibility_task = asyncio.create_task(_become_visible())

        finished_flow_run = await wait_for_flow_run(
            flow_run.id, timeout=10, client=prefect_client
        )
        await visibility_task

        assert finished_flow_run.id == flow_run.id
        assert finished_flow_run.state is not None
        assert finished_flow_run.state.is_completed()

    async def test_raises_timeout_if_final_state_never_visible(
        self,
        prefect_client: PrefectClient,
        flow_run: client_schemas.FlowRun,
        stale_reads: list[client_schemas.FlowRun],
    ):
        with pytest.raises(FlowRunWaitTimeout):
            await wait_for_flow_run(flow_run.id, timeout=1, client=prefect_client)


class TestResumeFlowRunAsyncDispatch:
    """Tests for the async_dispatch migration of resume_flow_run."""

    async def test_aresume_flow_run_raises_not_paused_error(
        self, prefect_client: PrefectClient
    ):
        """Test that aresume_flow_run raises NotPausedError for non-paused flow runs."""

        @flow(name=f"foo_{uuid.uuid4()}")
        def foo():
            pass

        flow_run = await prefect_client.create_flow_run(foo, state=Pending())

        with pytest.raises(
            NotPausedError, match="Cannot resume a run that isn't paused"
        ):
            await aresume_flow_run(flow_run.id)

    async def test_resume_flow_run_dispatches_to_async_in_async_context(
        self, prefect_client: PrefectClient
    ):
        """Test that resume_flow_run dispatches to async when awaited."""

        @flow(name=f"foo_{uuid.uuid4()}")
        def foo():
            pass

        flow_run = await prefect_client.create_flow_run(foo, state=Pending())

        # Should dispatch to async version and raise NotPausedError
        with pytest.raises(
            NotPausedError, match="Cannot resume a run that isn't paused"
        ):
            await resume_flow_run(flow_run.id)

    def test_resume_flow_run_works_in_sync_context(self, sync_prefect_client):
        """Test that resume_flow_run works in pure sync context."""

        @flow(name=f"foo_{uuid.uuid4()}")
        def foo():
            pass

        flow_run = sync_prefect_client.create_flow_run(foo, state=Pending())

        # In a sync context (no event loop), should use sync implementation
        # and raise NotPausedError for non-paused flow run
        with pytest.raises(
            NotPausedError, match="Cannot resume a run that isn't paused"
        ):
            resume_flow_run(flow_run.id)

    def test_resume_flow_run_in_sync_flow(self, sync_prefect_client):
        """Test sync usage within a sync flow."""

        @flow(name=f"foo_{uuid.uuid4()}")
        def foo():
            pass

        target_flow_run = sync_prefect_client.create_flow_run(foo, state=Pending())

        @flow(name=f"sync_test_flow_{uuid.uuid4()}")
        def sync_test_flow():
            with pytest.raises(
                NotPausedError, match="Cannot resume a run that isn't paused"
            ):
                resume_flow_run(target_flow_run.id)
            return "completed"

        result = sync_test_flow()
        assert result == "completed"

    async def test_resume_flow_run_in_async_flow(self, prefect_client: PrefectClient):
        """Test async usage within an async flow."""

        @flow(name=f"foo_{uuid.uuid4()}")
        def foo():
            pass

        flow_run = await prefect_client.create_flow_run(foo, state=Pending())

        @flow(name=f"async_test_flow_{uuid.uuid4()}")
        async def async_test_flow():
            with pytest.raises(
                NotPausedError, match="Cannot resume a run that isn't paused"
            ):
                await resume_flow_run(flow_run.id)
            return "completed"

        result = await async_test_flow()
        assert result == "completed"


class TestPauseFlowRunAsyncDispatch:
    """Tests for the async_dispatch migration of pause_flow_run."""

    async def test_apause_flow_run_raises_outside_flow_run(self):
        """Test that apause_flow_run raises RuntimeError when called outside a flow run."""
        with pytest.raises(
            RuntimeError, match="Flow runs can only be paused from within a flow run"
        ):
            await apause_flow_run()

    async def test_pause_flow_run_dispatches_to_async_in_async_context(self):
        """Test that pause_flow_run dispatches to async when awaited."""
        # Should dispatch to async version and raise RuntimeError
        with pytest.raises(
            RuntimeError, match="Flow runs can only be paused from within a flow run"
        ):
            await pause_flow_run()

    def test_pause_flow_run_works_in_sync_context(self):
        """Test that pause_flow_run works in pure sync context."""
        # In a sync context (no event loop), should use sync implementation
        # and raise RuntimeError when called outside a flow run
        with pytest.raises(
            RuntimeError, match="Flow runs can only be paused from within a flow run"
        ):
            pause_flow_run()

    def test_pause_flow_run_raises_value_error_for_negative_timeout(self):
        """Test that pause_flow_run raises ValueError for negative timeout values."""
        with pytest.raises(ValueError, match="'timeout' must be a non-negative number"):
            pause_flow_run(timeout=-1)

    @pytest.mark.asyncio
    async def test_apause_flow_run_raises_value_error_for_negative_timeout(self):
        """Test that apause_flow_run raises ValueError for negative timeout values."""
        with pytest.raises(ValueError, match="'timeout' must be a non-negative number"):
            await apause_flow_run(timeout=-1)

    def test_suspend_flow_run_raises_value_error_for_negative_timeout(self):
        """Test that suspend_flow_run raises ValueError for negative timeout values."""
        with pytest.raises(ValueError, match="'timeout' must be a non-negative number"):
            suspend_flow_run(timeout=-1)

    async def test_asuspend_flow_run_raises_value_error_for_negative_timeout(self):
        """Test that asuspend_flow_run raises ValueError for negative timeout values."""
        with pytest.raises(ValueError, match="'timeout' must be a non-negative number"):
            await asuspend_flow_run(timeout=-1)


class TestSuspendFlowRunAsyncDispatch:
    """Tests for the async_dispatch migration of suspend_flow_run."""

    async def test_asuspend_flow_run_raises_outside_flow_run(self):
        """Test that asuspend_flow_run raises RuntimeError when called outside a flow run."""
        with pytest.raises(
            RuntimeError, match="Flow runs can only be suspended from within a flow run"
        ):
            await asuspend_flow_run()

    async def test_suspend_flow_run_dispatches_to_async_in_async_context(self):
        """Test that suspend_flow_run dispatches to async when awaited."""
        # Should dispatch to async version and raise RuntimeError
        with pytest.raises(
            RuntimeError, match="Flow runs can only be suspended from within a flow run"
        ):
            await suspend_flow_run()

    def test_suspend_flow_run_works_in_sync_context(self):
        """Test that suspend_flow_run works in pure sync context."""
        # In a sync context (no event loop), should use sync implementation
        # and raise RuntimeError when called outside a flow run
        with pytest.raises(
            RuntimeError, match="Flow runs can only be suspended from within a flow run"
        ):
            suspend_flow_run()
