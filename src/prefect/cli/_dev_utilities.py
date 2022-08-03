import os
import pathlib
import subprocess
from pathlib import Path
from typing import List

import anyio
import yaml
from anyio import TASK_STATUS_IGNORED

import prefect
from prefect import infrastructure
from prefect.agent import OrionAgent
from prefect.cli._types import PrefectTyper
from prefect.cli.deployment import _create_deployment_from_deployment_yaml
from prefect.client import get_client
from prefect.deployments import Deployment, DeploymentYAML
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
        await storage_block.save(name)

    return storage_block


async def register_deployment_from_yaml(
    directory_path, deployment_name, yaml_name="main-deployment.yaml"
):
    flow_file = [f for f in os.listdir(directory_path) if ".py" in f][0]
    subprocess.run(
        [
            "prefect",
            "deployment",
            "build",
            f"{flow_file}:main",
            "-n",
            deployment_name,
            "-t",
            PREFECT_DEV_QA_TAG.value(),
        ]
    )
    with open(f"{directory_path}/{yaml_name}") as f:
        deployment = DeploymentYAML(**yaml.safe_load(f))

    deployment_id = await _create_deployment_from_deployment_yaml(deployment=deployment)

    return deployment_id


async def register_deployments(task_status=TASK_STATUS_IGNORED):
    # Create storage
    with tmpchdir(prefect.__root_path__ / "qa/deployments"):
        await get_qa_storage_block(path=Path.cwd().parent)
        deployment_ids = []
        dirs = [d for d in os.listdir() if os.path.isdir(d)]
        for directory in dirs:
            with tmpchdir(prefect.__root_path__ / f"qa/deployments/{directory}"):
                deployment_id = await register_deployment_from_yaml(
                    directory_path=Path.cwd(), deployment_name=directory
                )
                deployment_ids.append(deployment_id)

    print("Deployment registration complete")
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
    app: PrefectTyper, deployment_ids: List[Deployment], task_status=TASK_STATUS_IGNORED
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


async def create_deployment(path):
    # load the file
    with open(str(path), "r") as f:
        data = yaml.safe_load(f)
    # create deployment object
    try:
        deployment = DeploymentYAML(**data)
        print(f"Successfully loaded {deployment.name!r}")
    except Exception as exc:
        raise Exception("Issue loading deployment")
        # exit_with_error(f"Provided file did not conform to deployment spec: {exc!r}")
    async with get_client() as client:
        # prep IDs
        flow_id = await client.create_flow_from_name(deployment.flow_name)

        deployment.infrastructure = deployment.infrastructure.copy()
        try:
            infrastructure_document_id = await deployment.infrastructure._save(
                is_anonymous=True,
            )
        except ValueError as exc:
            deployment_infrastructure = infrastructure.Process()
            deployment.infrastructure = deployment_infrastructure
            infrastructure_document_id = await deployment.infrastructure._save(
                is_anonymous=True,
            )

        # we assume storage was already saved
        storage_document_id = deployment.storage._block_document_id
        try:
            await client.read_block_document(deployment.storage._block_document_id)
        except ObjectNotFound as exc:
            storage = LocalFileSystem(basepath=Path(".").absolute())
            await storage._save(is_anonymous=True)
            deployment.storage = storage
            storage_document_id = storage._block_document_id

        deployment.manifest_path = str(
            pathlib.Path(path).absolute().parent / "manifest.json"
        )

        with open(path, "w") as f:
            f.write(deployment.header)
            yaml.dump(deployment.editable_fields_dict(), f, sort_keys=False)
            f.write("###\n### DO NOT EDIT BELOW THIS LINE\n###\n")
            yaml.dump(deployment.immutable_fields_dict(), f, sort_keys=False)

        deployment_id = await client.create_deployment(
            flow_id=flow_id,
            name=deployment.name,
            schedule=deployment.schedule,
            parameters=deployment.parameters,
            description=deployment.description,
            tags=deployment.tags,
            manifest_path=deployment.manifest_path,
            storage_document_id=storage_document_id,
            infrastructure_document_id=infrastructure_document_id,
            parameter_openapi_schema=deployment.parameter_openapi_schema.dict(),
        )

    print(
        f"Deployment '{deployment.flow_name}/{deployment.name}' successfully created with id '{deployment_id}'."
    )
    return deployment_id
