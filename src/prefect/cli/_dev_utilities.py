import asyncio
import os
import subprocess
from pathlib import Path
from typing import List

import anyio
from anyio import TASK_STATUS_IGNORED

import prefect
from prefect.agent import OrionAgent
from prefect.cli import deployment
from prefect.cli._types import PrefectTyper
from prefect.client import get_client
from prefect.deployments import Deployment
from prefect.exceptions import PrefectHTTPStatusError
from prefect.orion import schemas
from prefect.settings import PREFECT_AGENT_QUERY_INTERVAL
from prefect.utilities.filesystem import tmpchdir


async def create_qa_queue(app: PrefectTyper, task_status=TASK_STATUS_IGNORED):
    """Create a work queue for QA deployments"""
    async with prefect.get_client() as client:
        try:
            qa_q = await client.read_work_queue_by_name("PREFECT_DEV_QA_Q")
        except PrefectHTTPStatusError as exc:
            pass
        else:
            await client.delete_work_queue_by_id(qa_q.id)
        finally:
            q_id = await client.create_work_queue(name="PREFECT_DEV_QA_Q", tags=["qa"])
        app.console.print("'PREFECT_DEV_QA_Q' created...")
        await asyncio.sleep(1)
        task_status.started()
        return q_id


async def start_agent(app: PrefectTyper):
    """Start an agent that listens for work from PREFECT_DEV_QA_Q"""
    global loop_agent
    loop_agent = True
    async with OrionAgent(work_queue_name="PREFECT_DEV_QA_Q") as agent:
        app.console.print(
            f"Agent started! Looking for work from queue 'PREFECT_DEV_QA_Q'..."
        )
        while loop_agent:
            await agent.get_and_submit_flow_runs()
            await anyio.sleep(PREFECT_AGENT_QUERY_INTERVAL.value())

    print("Agent shutting down...")


async def register_deployments(task_status=TASK_STATUS_IGNORED):
    print("Registering deployments...")
    with tmpchdir(prefect.__root_path__ / "qa/deployments"):
        valid_deployments = []
        dirs = os.listdir()
        for dir in dirs:
            deployment_files = [f for f in os.listdir(dir) if f == "deployment.yaml"]
            for file in deployment_files:
                await deployment.apply(Path(f"{dir}/{file}"))
    print("Deployment registration complete")
    task_status.started()
    return valid_deployments


async def execute_flow_scripts(task_status=TASK_STATUS_IGNORED):
    """Run all of the <flow>.py files"""
    with tmpchdir(prefect.__root_path__ / "qa/pure_scripts"):
        scripts = os.listdir()
        for script in scripts:
            subprocess.run(["python3", script])
    task_status.started()


async def submit_deployments_for_execution(
    app: PrefectTyper, deployments: List[Deployment], task_status=TASK_STATUS_IGNORED
):
    async with get_client() as client:
        for deployment in deployments:
            try:
                await client.create_flow_run_from_deployment(
                    deployment_id=deployment.id
                )
                app.console.print(f"Created deployment {deployment.name}")
            except Exception as exc:
                app.console.print(exc)
                app.console.print(
                    f"Failed to create deployment {deployment.name}", style="red"
                )

        task_status.started()


async def get_qa_deployments() -> List[schemas.core.Deployment]:
    """
    Get a list of all deployments have 'qa_' in their name
    """
    async with get_client() as client:
        deployments = await client.read_deployments()

    qa_deployments = []
    for deployment in deployments:
        if "qa_" in deployment.name:
            qa_deployments.append(deployment)

    return qa_deployments
