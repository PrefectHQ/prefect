"""
Command line interface for working with tasks.
"""
import typing as t
import uuid

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.deployment import get_deployment
from prefect.cli.root import app
from prefect.client.orchestration import PrefectClient, get_client
from prefect.exceptions import ObjectNotFound
from prefect.flows import load_flow_from_entrypoint
from prefect.task_engine import run_autonomous_task
from prefect.tasks import load_task_from_entrypoint

if t.TYPE_CHECKING:
    from prefect.client.schemas import FlowRun


task_app = PrefectTyper(name="task", help="Commands for interacting with tasks.")
app.add_typer(task_app, aliases=["tasks"])


async def get_flow_run(client: PrefectClient, flow_run_id: uuid.UUID) -> "FlowRun":
    try:
        return await client.read_flow_run(flow_run_id)
    except ObjectNotFound:
        exit_with_error(f"Flow run {str(flow_run_id)!r} not found!")


@task_app.command()
async def rerun(deployment_name: str, flow_run_id: uuid.UUID, task_name: str):
    """
    Rerun a flow run's task.
    """

    async with get_client() as client:
        deployment = await get_deployment(client, deployment_name, None)
        path, _ = deployment.entrypoint.rsplit(":", maxsplit=1)
        flow = load_flow_from_entrypoint(deployment.entrypoint)
        task = load_task_from_entrypoint(f"{path}:{task_name}")

        flow_run = await get_flow_run(client, flow_run_id)

        # resolve inputs
        await run_autonomous_task(task, flow, flow_run)
