from typing import Callable, List, Set
from uuid import UUID

import anyio
import anyio.abc
import anyio.to_process
import pendulum

import prefect.engine
from prefect.client import OrionClient, inject_client
from prefect.deployments import load_flow_from_deployment
from prefect.orion.schemas.core import FlowRun
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.states import StateType
from prefect.utilities.callables import cloudpickle_wrapped_call


async def submit_local_flow_run(
    flow_run: FlowRun,
    task_group: anyio.abc.TaskGroup,
) -> None:
    task_group.start_soon(
        anyio.to_process.run_sync,
        cloudpickle_wrapped_call(
            prefect.engine.enter_flow_run_engine_from_deployed_run,
            flow_run_id=flow_run.id,
        ),
    )
    print(f"Submitted {flow_run.id}")


@inject_client
async def run_agent(
    client: OrionClient,
    prefetch_seconds: int = 10,
    query_interval_seconds: int = 2,
    submit_fn: Callable[[FlowRun, anyio.abc.TaskGroup], None] = submit_local_flow_run,
) -> None:
    submitted_ids = set()

    async with anyio.create_task_group() as submission_tg:
        while True:
            ready_runs = await query_for_ready_flow_runs(
                client, prefetch_seconds, submitted_ids
            )

            for flow_run in ready_runs:
                print(f"Submitting {flow_run.id}")
                submission_tg.start_soon(submit_fn, flow_run, submission_tg)
                submitted_ids.add(flow_run.id)

            # Wait until the next query
            await anyio.sleep(query_interval_seconds)


async def query_for_ready_flow_runs(
    client: OrionClient, prefetch_seconds: int, submitted_ids: Set[UUID] = None
) -> List[FlowRun]:
    submitted_ids = submitted_ids or set()

    scheduled_runs = await client.read_flow_runs(
        flow_runs=FlowRunFilter(
            state_types=dict(any_=[StateType.SCHEDULED]),
            next_scheduled_start_time=dict(
                before_=pendulum.now("utc").add(seconds=prefetch_seconds)
            ),
        )
    )

    # Filter out runs that should not be submitted again but maintain ordering
    # TODO: Move this into the `FlowRunFilter` once it supports this
    ready_runs = [
        run
        for run in scheduled_runs
        if run.id not in submitted_ids and run.deployment_id is not None
    ]

    return ready_runs
