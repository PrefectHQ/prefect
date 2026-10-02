"""Module to define tasks for reading logs from Armada jobs."""

from __future__ import annotations

from collections.abc import Callable

from anyio.to_thread import run_sync
from armada_client.log_client import LogLine

from prefect import task
from prefect_armada.credentials import ArmadaCredentials


def _read_log_lines(
    armada_credentials: ArmadaCredentials,
    job_id: str,
    namespace: str,
    pod_number: int,
    since_time: str,
) -> list[LogLine]:
    """Reads log lines for an Armada job using a synchronous client."""
    with armada_credentials.get_binoculars_client() as binoculars_client:
        response = binoculars_client.logs(
            job_id=job_id,
            since_time=since_time,
            pod_namespace=namespace,
            pod_number=pod_number,
        )
    return [LogLine(line.line, line.timestamp) for line in response.log]


@task
async def read_job_log_lines(
    armada_credentials: ArmadaCredentials,
    job_id: str,
    namespace: str | None = "default",
    pod_number: int = 0,
    since_time: str = "",
) -> list[LogLine]:
    """Task for reading the log lines of an Armada job.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        job_id: The ID of the job to read logs from.
        namespace: The Kubernetes namespace the job's pod runs in.
        pod_number: The zero-indexed pod number to read logs from.
        since_time: If provided, only logs emitted since this RFC 3339 timestamp
            are returned.

    Returns:
        A list of `LogLine` objects, each with a `line` and a `timestamp`.

    Example:
        Read the log lines of a job:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.logs import read_job_log_lines

        @flow
        def armada_orchestrator():
            log_lines = read_job_log_lines(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                job_id="01hqk8m0z6z9jz3q0k9pz9x5nb",
            )
        ```
    """
    # Armada only ships a synchronous log client, so the blocking gRPC call is
    # moved off the event loop.
    return await run_sync(
        _read_log_lines,
        armada_credentials,
        job_id,
        namespace or "default",
        pod_number,
        since_time,
    )


@task
async def read_job_log(
    armada_credentials: ArmadaCredentials,
    job_id: str,
    namespace: str | None = "default",
    pod_number: int = 0,
    since_time: str = "",
    print_func: Callable | None = None,
) -> str:
    """Task for reading the logs of an Armada job.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        job_id: The ID of the job to read logs from.
        namespace: The Kubernetes namespace the job's pod runs in.
        pod_number: The zero-indexed pod number to read logs from.
        since_time: If provided, only logs emitted since this RFC 3339 timestamp
            are returned.
        print_func: If provided, it will be called once for every log line in
            addition to the logs being returned.

    Returns:
        A string containing the job's logs.

    Example:
        Read the logs of a job and send them to the flow run logger:
        ```python
        from prefect import flow
        from prefect.logging import get_run_logger
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.logs import read_job_log

        @flow
        def armada_orchestrator():
            logger = get_run_logger()

            job_logs = read_job_log(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                job_id="01hqk8m0z6z9jz3q0k9pz9x5nb",
                print_func=logger.info,
            )
        ```
    """
    log_lines = await read_job_log_lines.fn(
        armada_credentials=armada_credentials,
        job_id=job_id,
        namespace=namespace,
        pod_number=pod_number,
        since_time=since_time,
    )

    if print_func is not None:
        for log_line in log_lines:
            print_func(log_line.line)

    return "\n".join(log_line.line for log_line in log_lines)
