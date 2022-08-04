import os
import subprocess
from pathlib import Path
from typing import List
from uuid import UUID

import anyio
import yaml
from anyio import TASK_STATUS_IGNORED

import prefect
from prefect.agent import OrionAgent
from prefect.cli._types import PrefectTyper
from prefect.cli.deployment import _create_deployment_from_deployment_yaml
from prefect.client import get_client
from prefect.deployments import DeploymentYAML
from prefect.exceptions import ObjectNotFound, PrefectHTTPStatusError
from prefect.filesystems import LocalFileSystem
from prefect.settings import (
    PREFECT_AGENT_QUERY_INTERVAL,
    PREFECT_DEV_QA_TAG,
    PREFECT_DEV_QA_WORK_QUEUE,
)
from prefect.utilities.filesystem import tmpchdir


async def create_qa_queue(app: PrefectTyper, task_status=TASK_STATUS_IGNORED):
    """Create a new work queue for QA deployments"""
    async with prefect.get_client() as client:
        queue_name = PREFECT_DEV_QA_WORK_QUEUE.value()
        try:
            qa_q = await client.read_work_queue_by_name(queue_name)
        except PrefectHTTPStatusError as exc:
            pass  # if the work-queue doesn't exist, we will get a status error
        else:
            await client.delete_work_queue_by_id(qa_q.id)
        finally:
            q_id = await client.create_work_queue(
                name=queue_name, tags=[PREFECT_DEV_QA_TAG.value()]
            )
        app.console.print(f"'{queue_name}' created...")
        task_status.started()
        return q_id


async def start_agent(app: PrefectTyper):
    """Start an agent that listens for work from PREFECT_DEV_QA_Q"""
    global loop_agent  # eventually will be used to kill both orion and the agent
    loop_agent = True
    async with OrionAgent(work_queue_name=PREFECT_DEV_QA_WORK_QUEUE.value()) as agent:
        app.console.print(
            f"Agent started! Looking for work from queue '{PREFECT_DEV_QA_WORK_QUEUE.value()}'..."
        )
        while loop_agent:
            await agent.get_and_submit_flow_runs()
            await anyio.sleep(PREFECT_AGENT_QUERY_INTERVAL.value())

    print("Agent shutting down...")


async def get_qa_storage_block(path, name="qa-storage-block"):
    try:
        storage_block = await LocalFileSystem.load(name)
    except ValueError as exc:
        storage_block = LocalFileSystem(basepath=path)
        try:
            await storage_block.save(name, overwrite=True)
        except ObjectNotFound as exc:
            await storage_block.save(name)
    return storage_block


async def register_deployment_from_yaml(directory_path, block_slug):
    """
    Builds and applies the flow in a given directory to
    a deployment.

    Expects flows to have the same name as the directory that
    they are in.
    """
    deployment_name = directory_path.name
    yaml_name = f"{directory_path.name}-deployment.yaml"
    flow_file = [f for f in os.listdir(directory_path) if ".py" in f][0]
    subprocess.run(
        [
            "prefect",
            "deployment",
            "build",
            f"{flow_file}:{directory_path.name}",
            "-n",
            deployment_name,
            "-t",
            PREFECT_DEV_QA_TAG.value(),
            "-sb",
            block_slug,
        ]
    )
    with open(f"{directory_path}/{yaml_name}") as f:
        deployment = DeploymentYAML(**yaml.safe_load(f))

    deployment_id = await _create_deployment_from_deployment_yaml(deployment=deployment)

    return deployment_id


async def register_deployments(app: PrefectTyper, task_status=TASK_STATUS_IGNORED):
    # Create storage
    with tmpchdir(prefect.__root_path__ / "qa/deployments"):
        await get_qa_storage_block(path=Path.cwd().parent / "deployment_storage")
        deployment_ids = []
        dirs = [d for d in os.listdir() if os.path.isdir(d)]
        for directory in dirs:
            with tmpchdir(prefect.__root_path__ / f"qa/deployments/{directory}"):
                deployment_id = await register_deployment_from_yaml(
                    directory_path=Path.cwd(),
                    block_slug="local-file-system/qa-storage-block",
                )
                deployment_ids.append(deployment_id)

    app.console.print("Deployment registration complete")
    task_status.started()
    return deployment_ids


async def execute_flow_scripts(task_status=TASK_STATUS_IGNORED):
    """Run all of the <flow>.py files"""
    with tmpchdir(prefect.__root_path__ / "qa/pure_scripts"):
        scripts = os.listdir()
        for script in scripts:
            subprocess.run(["python3", script])
    task_status.started()


async def submit_deployments_for_execution(
    app: PrefectTyper, deployment_ids: List[UUID], task_status=TASK_STATUS_IGNORED
):
    """Submit all deployments for execution"""
    async with get_client() as client:
        for deployment_id in deployment_ids:
            deployment = await client.read_deployment(deployment_id)
            try:
                await client.create_flow_run_from_deployment(
                    deployment_id=deployment.id
                )
                print(f"Submitted deployment {deployment.name} for execution.")
            except Exception as exc:
                app.console.print(exc)
                app.console.print(
                    f"Failed to create deployment {deployment.name}", style="red"
                )

        task_status.started()
