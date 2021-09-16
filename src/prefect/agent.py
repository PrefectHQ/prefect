from typing import Callable, List

import anyio
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
    client: OrionClient,
    flow_run: FlowRun,
    task_group,
) -> None:
    if not flow_run.deployment_id:
        raise ValueError(
            "Flow run does not have an associated deployment so the flow cannot be "
            "loaded."
        )

    deployment = await client.read_deployment(flow_run.deployment_id)
    flow = await load_flow_from_deployment(deployment, client=client)

    task_group.start_soon(
        anyio.to_process.run_sync,
        cloudpickle_wrapped_call(
            prefect.engine.enter_flow_run_engine_from_deployed_run,
            flow=flow,
            parameters={},  # TODO: Send parameters from deployment
            flow_run_id=flow_run.id,
        ),
    )
    print(f"Submitted {flow_run.id}")


@inject_client
async def run_agent(
    client: OrionClient,
    prefetch_seconds: int = 10,
    query_interval_seconds: int = 2,
    submit_fn: Callable[[OrionClient, FlowRun], None] = submit_local_flow_run,
) -> None:
    submitted_ids = set()

    async with anyio.create_task_group() as submission_tg:
        while True:
            ready_runs = await query_for_ready_flow_runs(client, prefetch_seconds)

            # Filter out runs that are already being submitted but maintain ordering
            submittable_runs = [
                run
                for run in ready_runs
                # TODO: Add these to the `query_for_ready_flow_runs` filter
                if run.id not in submitted_ids and run.deployment_id is not None
            ]

            for flow_run in submittable_runs:
                print(f"Submitting {flow_run.id}")
                submission_tg.start_soon(submit_fn, client, flow_run, submission_tg)
                submitted_ids.add(flow_run.id)

            # Wait until the next query
            await anyio.sleep(query_interval_seconds)


async def query_for_ready_flow_runs(
    client: OrionClient, prefetch_seconds: int
) -> List[FlowRun]:
    return await client.read_flow_runs(
        flow_runs=FlowRunFilter(
            states=[StateType.SCHEDULED],
            start_time_before=pendulum.now("utc").add(seconds=prefetch_seconds),
        )
    )
