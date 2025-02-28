import asyncio

import pytest

from prefect import flow
from prefect._waiters import FlowRunWaiter
from prefect.client.orchestration import PrefectClient
from prefect.flow_engine import run_flow_async
from prefect.server.events.pipeline import EventsPipeline
from prefect.states import Pending


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
