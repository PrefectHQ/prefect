from __future__ import annotations

import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from prefect import get_client
from prefect.client.schemas.objects import FlowRun
from prefect.events.schemas.events import Event
from prefect.exceptions import ObjectNotFound
from prefect.states import StateType

# Where the flows baked into the test image live, relative to its WORKDIR.
FLOW_NAME = "sleepy"
FLOW_ENTRYPOINT = "flows.py:sleepy"


async def create_flow_run(
    name: str,
    work_pool_name: str,
    job_variables: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> FlowRun:
    """Create a flow run of the flow baked into the test image.

    Args:
        name: The name of the deployment to create the flow run from.
        work_pool_name: The work pool to deploy to.
        job_variables: Job variables for the deployment, including the image.
        parameters: Parameters for the flow run.
    """
    async with get_client() as client:
        flow_id = await client.create_flow_from_name(FLOW_NAME)
        deployment_id = await client.create_deployment(
            flow_id=flow_id,
            name=name,
            entrypoint=FLOW_ENTRYPOINT,
            work_pool_name=work_pool_name,
            job_variables=job_variables,
        )
        return await client.create_flow_run_from_deployment(
            deployment_id, parameters=parameters
        )


def work_pool_exists(work_pool_name: str) -> bool:
    """Whether a work pool with the given name exists on the Prefect API."""
    with get_client(sync_client=True) as client:
        try:
            client.read_work_pool(work_pool_name)
        except ObjectNotFound:
            return False
        return True


@contextmanager
def running_worker(
    work_pool_name: str, env: dict[str, str] | None = None
) -> Generator[subprocess.Popen[bytes], None, None]:
    """Run a Prefect worker for the given work pool for the duration of the block."""
    with subprocess.Popen(
        ["prefect", "worker", "start", "--pool", work_pool_name], env=env
    ) as worker_process:
        try:
            yield worker_process
        finally:
            worker_process.terminate()
            try:
                worker_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                worker_process.kill()


def get_flow_run_state(flow_run_id: UUID) -> tuple[StateType | None, str | None]:
    """Get the current state of a flow run."""
    with get_client(sync_client=True) as client:
        flow_run = client.read_flow_run(flow_run_id)
        if not flow_run.state:
            return None, "No state found"
        return flow_run.state.type, flow_run.state.message


def wait_for_flow_run_state(
    flow_run_id: UUID, target_state: StateType, timeout: int = 10
) -> None:
    """Wait for a flow run to reach a specific state."""
    start_time = time.time()
    previous_state = None

    print(f"Waiting for flow run {flow_run_id} to reach state {target_state}")
    while True:
        state, message = get_flow_run_state(flow_run_id)

        # Log state transitions to help with debugging
        if state != previous_state:
            print(f"Flow run {flow_run_id} state: {state} - {message}")
            previous_state = state

        if state == target_state:
            print(f"Flow run {flow_run_id} reached target state {target_state}")
            return

        time.sleep(1)

        # Log timeout with clear message
        if time.time() - start_time > timeout:
            elapsed = int(time.time() - start_time)
            raise TimeoutError(
                f"Flow run {flow_run_id} did not reach state {target_state!r} within {timeout} seconds. "
                f"Final state: {state!r} after {elapsed}s. Message: {message}"
            )


def wait_for_infrastructure_pid(flow_run_id: UUID, timeout: int = 60) -> str:
    """Wait for the worker to record the Armada job it submitted for a flow run."""
    start_time = time.time()

    print(f"Waiting for flow run {flow_run_id} to be submitted to Armada")
    while True:
        with get_client(sync_client=True) as client:
            flow_run = client.read_flow_run(flow_run_id)
        if flow_run.infrastructure_pid:
            print(f"Flow run {flow_run_id} submitted: {flow_run.infrastructure_pid}")
            return flow_run.infrastructure_pid

        if time.time() - start_time > timeout:
            raise TimeoutError(
                f"Flow run {flow_run_id} was not submitted to Armada within "
                f"{timeout} seconds. State: {flow_run.state!r}"
            )

        time.sleep(1)


async def read_job_events_for_flow_run(flow_run_id: UUID) -> list[Event]:
    """Read the replicated Armada job events for a flow run."""
    async with get_client() as client:
        response = await client.request(
            "POST",
            "/events/filter",
            json={
                "filter": {
                    "event": {"prefix": ["prefect.armada.job"]},
                    "related": {
                        "id": [f"prefect.flow-run.{flow_run_id}"],
                    },
                    "order": "ASC",
                },
            },
        )
        return [Event.model_validate(event) for event in response.json()["events"]]
