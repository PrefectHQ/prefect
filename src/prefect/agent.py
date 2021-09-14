import pendulum
from anyio import create_task_group, sleep

import prefect.engine
from prefect.client import OrionClient, inject_client
from prefect.deployments import load_flow_from_text
from prefect.orion.schemas.core import FlowRun
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.states import StateType
from prefect.orion.utilities.database import UUID


async def submit_local_flow_run(flow_run: FlowRun):
    print(f"Submitting flow run '{flow_run.id}' for local execution")
    await execute_flow_run(flow_run.id)


@inject_client
async def run_agent(
    client: OrionClient,
    prefetch_seconds=10,
    query_interval_seconds=2,
    submit_fn=submit_local_flow_run,
):
    submitted_flow_runs = set()
    while True:
        flow_runs = await client.read_flow_runs(
            flow_runs=FlowRunFilter(
                states=[StateType.SCHEDULED],
                start_time_before=pendulum.now("utc").add(seconds=prefetch_seconds),
            )
        )
        async with create_task_group() as submit_tasks:
            for flow_run in flow_runs:
                if flow_run.id in submitted_flow_runs:
                    continue
                submitted_flow_runs.add(flow_run.id)
                submit_tasks.start_soon(submit_fn, flow_run)

        await sleep(query_interval_seconds)


@inject_client
async def execute_flow_run(flow_run_id: UUID, client: OrionClient):
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
        parameters={},
        client=client,
        flow_run_id=flow_run_id,
    )
