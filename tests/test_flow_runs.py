import asyncio
import time
import uuid

import pytest

import prefect.client.schemas as client_schemas
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.events.utilities import emit_event
from prefect.exceptions import FlowRunWaitTimeout
from prefect.flow_engine import run_flow_async
from prefect.flow_runs import wait_for_flow_run
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
