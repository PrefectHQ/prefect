from __future__ import annotations

import time

import grpc
from armada_client.typings import JobState
from prefect_armada.credentials import ArmadaCredentials
from prefect_armada.utilities import job_state_from_value
from rich.console import Console

console = Console()


def ensure_queue(name: str) -> None:
    """Ensure an Armada queue exists, creating it if it does not.

    Connection details are read from the environment, as they are by a worker
    whose work pool does not reference a credentials block.
    """
    with ArmadaCredentials().get_sync_client() as client:
        try:
            client.get_queue(name=name)
            console.log(f"Using existing Armada queue: {name}")
            return
        except grpc.RpcError as exc:
            if exc.code() is not grpc.StatusCode.NOT_FOUND:
                raise

        console.log(f"Creating Armada queue: {name}")
        try:
            client.create_queue(
                client.create_queue_request(name=name, priority_factor=1)
            )
        except grpc.RpcError as exc:
            # Another test session may have created it in the meantime.
            if exc.code() is not grpc.StatusCode.ALREADY_EXISTS:
                raise

        # Queue creation is asynchronous; submissions are rejected until the
        # queue is visible.
        deadline = time.time() + 30
        while True:
            try:
                client.get_queue(name=name)
                return
            except grpc.RpcError as exc:
                if (
                    exc.code() is not grpc.StatusCode.NOT_FOUND
                    or time.time() > deadline
                ):
                    raise
            time.sleep(1)


def get_job_state(job_id: str) -> JobState:
    """Get the current state of an Armada job."""
    with ArmadaCredentials().get_sync_client() as client:
        response = client.get_job_status(job_ids=[job_id])
    if job_id not in response.job_states:
        return JobState.UNKNOWN
    return job_state_from_value(response.job_states[job_id])


def wait_for_job_state(job_id: str, target_state: JobState, timeout: int = 60) -> None:
    """Wait for an Armada job to reach a specific state."""
    start_time = time.time()
    previous_state = None

    print(f"Waiting for Armada job {job_id} to reach state {target_state.name}")
    while True:
        state = get_job_state(job_id)

        if state != previous_state:
            print(f"Armada job {job_id} state: {state.name}")
            previous_state = state

        if state == target_state:
            return

        if time.time() - start_time > timeout:
            raise TimeoutError(
                f"Armada job {job_id} did not reach state {target_state.name} "
                f"within {timeout} seconds. Final state: {state.name}"
            )

        time.sleep(1)


def cancel_job(queue: str, job_set_id: str, job_id: str) -> None:
    """Cancel an Armada job, as an operator outside of Prefect would."""
    with ArmadaCredentials().get_sync_client() as client:
        client.cancel_jobs(queue=queue, job_set_id=job_set_id, job_id=job_id)
    console.log(f"Requested cancellation of Armada job: {job_id}")
