from typing import Callable, List

import pendulum
import anyio
import anyio.to_process

import prefect.engine
from prefect.client import OrionClient, inject_client
from prefect.deployments import load_flow_from_text
from prefect.orion.schemas.core import FlowRun
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.states import StateType
from prefect.orion.utilities.database import UUID
from prefect.utilities.asyncio import sync_compatible


async def submit_local_flow_run(flow_run: FlowRun, task_group) -> None:
    task_group.start_soon(anyio.to_process.run_sync, execute_flow_run, flow_run.id)
    print(f"Submitted {flow_run.id}")


@inject_client
async def run_agent(
    client: OrionClient,
    prefetch_seconds: int = 10,
    query_interval_seconds: int = 2,
    submit_fn: Callable[[FlowRun], None] = submit_local_flow_run,
) -> None:
    submitted_ids = set()

    async with anyio.create_task_group() as submission_tg:
        while True:
            ready_runs = await query_for_ready_flow_runs(client, prefetch_seconds)

            # Filter out runs that are already being submitted but maintain ordering
            submittable_runs = [
                run for run in ready_runs if run.id not in submitted_ids
            ]

            for flow_run in submittable_runs:
                print(f"Submitting {flow_run.id}")
                submission_tg.start_soon(submit_fn, flow_run, submission_tg)
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


@sync_compatible
@inject_client
async def execute_flow_run(flow_run_id: UUID, client: OrionClient):
    print(f"Preparing to execute {flow_run_id}")
    flow_run = await client.read_flow_run(flow_run_id)
    if not flow_run.deployment_id:
        raise ValueError(
            "Flow run does not have a deployment id. Cannot execute flows without deployments."
        )
    deployment = await client.read_deployment(flow_run.deployment_id)
    flow_model = await client.read_flow(flow_run.flow_id)

    if deployment.flow_data.encoding == "file":
        flow_script_contents = deployment.flow_data.decode()
        flow = load_flow_from_text(flow_script_contents, flow_model.name)
    elif deployment.flow_data.encoding == "cloudpickle":
        flow = deployment.flow_data.decode()
    else:
        raise ValueError(
            f"Unknown flow data encoding {deployment.flow_data.encoding!r}"
        )

    await prefect.engine.begin_flow_run(
        flow,
        parameters={},  # TODO: Include parameters from deployment
        client=client,
        flow_run_id=flow_run_id,
    )
