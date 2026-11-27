import asyncio
import uuid

import pytest

from prefect import flow
from prefect._internal.waiters import FlowRunWaiter
from prefect.client.orchestration import PrefectClient
from prefect.events import emit_event
from prefect.flow_engine import run_flow_async
from prefect.server.events.pipeline import EventsPipeline
from prefect.states import Completed, Pending, State


class TestFlowRunWaiter:
    @pytest.fixture(autouse=True)
    def teardown(self):
        yield

        FlowRunWaiter.instance().stop()

    def test_instance_returns_singleton(self):
        assert FlowRunWaiter.instance() is FlowRunWaiter.instance()

    def test_instance_returns_instance_after_stop(self):
        instance = FlowRunWaiter.instance()
        instance.stop()
        assert FlowRunWaiter.instance() is not instance

    @pytest.mark.timeout(20)
    async def test_wait_for_flow_run(
        self, prefect_client: PrefectClient, emitting_events_pipeline: EventsPipeline
    ):
        """This test will fail with a timeout error if waiting is not working correctly."""

        @flow
        async def test_flow():
            await asyncio.sleep(1)

        flow_run = await prefect_client.create_flow_run(test_flow, state=Pending())
        asyncio.create_task(run_flow_async(flow=test_flow, flow_run=flow_run))

        await FlowRunWaiter.wait_for_flow_run(flow_run.id)

        await emitting_events_pipeline.process_events()

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()

    async def test_wait_for_flow_run_with_timeout(self, prefect_client: PrefectClient):
        @flow
        async def test_flow():
            await asyncio.sleep(5)

        flow_run = await prefect_client.create_flow_run(test_flow, state=Pending())
        run = asyncio.create_task(run_flow_async(flow=test_flow, flow_run=flow_run))

        await FlowRunWaiter.wait_for_flow_run(flow_run.id, timeout=1)

        # FlowRunWaiter stopped waiting before the task finished
        assert not run.done()
        await run

    @pytest.mark.timeout(method="thread")  # alarm-based pytest-timeout will interfere
    async def test_wait_for_flow_run_in_timed_out_state(
        self, prefect_client: PrefectClient
    ):
        """
        A flow run that exceeds its timeout finishes in a `TimedOut` state, so its
        final event is `prefect.flow-run.TimedOut`.
        """

        @flow(timeout_seconds=2)
        async def test_flow() -> None:
            await asyncio.sleep(5)

        flow_run = await prefect_client.create_flow_run(test_flow, state=Pending())
        run = asyncio.create_task(
            run_flow_async(flow=test_flow, flow_run=flow_run, return_type="state")
        )

        await FlowRunWaiter.wait_for_flow_run(flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "TimedOut"
        await run

    @pytest.mark.timeout(20)
    async def test_wait_for_flow_run_keeps_waiting_through_retries(
        self, prefect_client: PrefectClient
    ):
        """
        A retried flow run passes through `AwaitingRetry` and `Retrying`, which are
        not final states.
        """
        attempts = 0

        @flow(retries=1, retry_delay_seconds=2)
        async def test_flow() -> int:
            nonlocal attempts
            attempts += 1
            await asyncio.sleep(1)
            if attempts == 1:
                raise ValueError("fail the first attempt")
            return 42

        flow_run = await prefect_client.create_flow_run(test_flow, state=Pending())
        run = asyncio.create_task(run_flow_async(flow=test_flow, flow_run=flow_run))

        await FlowRunWaiter.wait_for_flow_run(flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()
        assert await run == 42

    @pytest.mark.timeout(20)
    async def test_wait_for_flow_run_in_completed_state_named_pending(
        self, prefect_client: PrefectClient
    ):
        """
        A final state can have the name of a non-final state type, so its event is
        `prefect.flow-run.Pending`.
        """

        @flow
        async def test_flow() -> State:
            await asyncio.sleep(1)
            return Completed(name="Pending")

        flow_run = await prefect_client.create_flow_run(test_flow, state=Pending())
        run = asyncio.create_task(run_flow_async(flow=test_flow, flow_run=flow_run))

        await FlowRunWaiter.wait_for_flow_run(flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()
        assert flow_run.state.name == "Pending"
        await run

    @pytest.mark.timeout(20)
    async def test_wait_for_flow_run_with_state_type_only_in_payload(
        self, emitting_events_pipeline: EventsPipeline
    ):
        """
        A final state event without a `prefect.state-type` label still wakes the
        waiter through the state type in its payload. This test will fail with a
        timeout error if it doesn't.
        """
        flow_run_id = uuid.uuid4()
        emit_event(
            event="prefect.flow-run.Completed",
            resource={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"},
            payload={"validated_state": {"type": "COMPLETED", "name": "Completed"}},
            id=uuid.uuid4(),
        )
        # Store the event so the waiter receives it when it subscribes
        await emitting_events_pipeline.process_events()

        await FlowRunWaiter.wait_for_flow_run(flow_run_id)

    @pytest.mark.timeout(20)
    async def test_non_singleton_mode(
        self, prefect_client: PrefectClient, emitting_events_pipeline: EventsPipeline
    ):
        waiter = FlowRunWaiter()
        assert waiter is not FlowRunWaiter.instance()

        @flow
        async def test_flow():
            await asyncio.sleep(1)

        flow_run = await prefect_client.create_flow_run(test_flow, state=Pending())
        asyncio.create_task(run_flow_async(flow=test_flow, flow_run=flow_run))

        await waiter.wait_for_flow_run(flow_run.id)

        await emitting_events_pipeline.process_events()

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()

        waiter.stop()

    @pytest.mark.timeout(20)
    async def test_handles_concurrent_task_runs(
        self, prefect_client: PrefectClient, emitting_events_pipeline: EventsPipeline
    ):
        @flow
        async def fast_flow():
            await asyncio.sleep(1)

        @flow
        async def slow_flow():
            await asyncio.sleep(5)

        flow_run_1 = await prefect_client.create_flow_run(fast_flow, state=Pending())
        flow_run_2 = await prefect_client.create_flow_run(slow_flow, state=Pending())

        asyncio.create_task(run_flow_async(flow=fast_flow, flow_run=flow_run_1))
        asyncio.create_task(run_flow_async(flow=slow_flow, flow_run=flow_run_2))

        await FlowRunWaiter.wait_for_flow_run(flow_run_1.id)

        await emitting_events_pipeline.process_events()

        flow_run_1 = await prefect_client.read_flow_run(flow_run_1.id)
        flow_run_2 = await prefect_client.read_flow_run(flow_run_2.id)

        assert flow_run_1.state
        assert flow_run_1.state.is_completed()

        assert flow_run_2.state
        assert not flow_run_2.state.is_completed()

        await FlowRunWaiter.wait_for_flow_run(flow_run_2.id)

        await emitting_events_pipeline.process_events()

        flow_run_1 = await prefect_client.read_flow_run(flow_run_1.id)
        flow_run_2 = await prefect_client.read_flow_run(flow_run_2.id)

        assert flow_run_1.state
        assert flow_run_1.state.is_completed()

        assert flow_run_2.state
        assert flow_run_2.state.is_completed()
