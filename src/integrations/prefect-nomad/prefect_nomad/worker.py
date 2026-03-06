"""
Module containing the Nomad worker used for executing flow runs as Nomad jobs.

The Nomad worker submits flow runs as batch jobs to a HashiCorp Nomad cluster
using the Docker task driver. Each flow run becomes a Nomad job with a single
task group and task that runs the Prefect flow in a Docker container.

Job Lifecycle (Two-Phase Monitoring)
-------------------------------------

    ┌─────────────────────────────────────────────────────────────────┐
    │  Phase 1: Evaluation (Scheduling Decision)                      │
    │  ┌──────────┐   pending    ┌──────────┐   complete   ┌────────┐ │
    │  │ Register │─────────────>│Evaluation│────────────> │Success │ │
    │  │   Job    │              │  (Nomad  │              └────────┘ │
    │  └──────────┘              │Scheduler)│                         │
    │       │                    └──────────┘                         │
    │       │                         │ blocked → NextEval (chain)    │
    │       │                         │ failed / canceled             │
    │       │                         v                               │
    │       │                    ┌─────────────────────┐              │
    │       │                    │ FailedTGAllocs Set? │              │
    │       │                    │ (No matching nodes, │              │
    │       │                    │  resource shortage) │              │
    │       │                    └─────────────────────┘              │
    │       │                             │                           │
    │       v                             v                           │
    │  RuntimeError <──────────────── FAILURE                         │
    └─────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Evaluation succeeded
                                      v
    ┌─────────────────────────────────────────────────────────────────┐
    │  Phase 2: Allocation (Job Execution)                            │
    │  ┌──────────┐   running   ┌──────────┐  complete  ┌──────────┐  │
    │  │  Client  │────────────>│   Task   │───────────>│Exit Code │  │
    │  │ Schedules│             │  Running │            │   = 0    │  │
    │  │   Task   │             │ (stream  │            └──────────┘  │
    │  └──────────┘             │  logs)   │                          │
    │       │                   └──────────┘                          │
    │       │ (no allocations yet)   │ failed / lost                  │
    │       │                        v                                │
    │       │                   ┌──────────┐                          │
    │       │                   │Exit Code │                          │
    │       │                   │   ≠ 0    │                          │
    │       v                   └──────────┘                          │
    │  job_timeout ───────────> FAILURE                               │
    └─────────────────────────────────────────────────────────────────┘

To start a Nomad worker, run the following command:

```bash
prefect worker start --pool 'my-work-pool' --type nomad
```

Replace `my-work-pool` with the name of the work pool you want the worker
to poll for flow runs.

For more information about work pools and workers,
checkout out the [Prefect docs](https://docs.prefect.io/latest/deploy/infrastructure-concepts).
"""

from __future__ import annotations

import re
import time
from typing import (
    TYPE_CHECKING,
    Any,
)

import anyio.abc
import nomad
import nomad.api.exceptions
from pydantic import BaseModel, Field, PrivateAttr

import prefect
from prefect.events import Event, RelatedResource, emit_event
from prefect.exceptions import InfrastructureNotFound
from prefect.logging import get_logger
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.workers.base import BaseJobConfiguration, BaseWorker, BaseWorkerResult

from .credentials import NomadCredentials
from .exceptions import (
    NomadEvaluationError,
    NomadJobRegistrationError,
    NomadJobSchedulingError,
    NomadJobStopError,
    NomadJobTimeoutError,
)

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.objects import (
        Flow as APIFlow,
    )
    from prefect.client.schemas.objects import (
        FlowRun,
        WorkPool,
    )
    from prefect.client.schemas.responses import DeploymentResponse

logger = get_logger(__name__)

# Default interval for polling Nomad evaluation/allocation status (seconds)
DEFAULT_POLL_INTERVAL_SECONDS = 1

# Labels applied to Nomad job metadata
JOB_META = {
    "prefect.version": prefect.__version__,
}


class NomadTaskResources(BaseModel):
    """Resource requirements for a Nomad task.

    Attributes:
        cpu: CPU resources to reserve in MHz.
        memory_mb: Memory to reserve in MiB.
    """

    cpu: int = Field(
        default=500,
        description="CPU resources to reserve in MHz.",
        ge=1,
    )
    memory_mb: int = Field(
        default=256,
        description="Memory to reserve in MiB.",
        ge=1,
    )


class NomadWorkerJobConfiguration(BaseJobConfiguration):
    """Configuration class used by the Nomad worker.

    An instance of this class is passed to the Nomad worker's `run` method
    for each flow run. It contains all the information necessary to execute the
    flow run as a Nomad job using the Docker task driver.

    Attributes:
        image: The Docker image to use for the Nomad task.
        nomad_credentials: Optional credentials block for authenticating with Nomad.
        datacenters: List of Nomad datacenters to target for job placement.
        namespace: The Nomad namespace to submit the job to.
        region: The Nomad region to submit the job to.
        task_resources: CPU and memory resource requirements for the task.
        docker_auth: Docker registry authentication credentials.
        network_mode: Docker network mode (e.g. bridge, host).
        privileged: Whether to run the Docker container in privileged mode.
        force_pull: Whether to always pull the Docker image, even if present locally.
        extra_docker_config: Additional Docker driver configuration options.
        extra_task_config: Additional Nomad task-level configuration options.
        stream_output: Whether to stream task logs to local stdout.
        priority: Nomad job priority (0-100, higher is more important).
        meta: Additional metadata key-value pairs for the Nomad job.
        poll_interval: Interval in seconds between allocation status polls.
    """

    image: str = Field(
        default_factory=get_prefect_image_name,
        description=(
            "The Docker image reference to use for the Nomad task. "
            "If not set, the latest Prefect image will be used."
        ),
        examples=["docker.io/prefecthq/prefect:3-latest"],
    )
    nomad_credentials: NomadCredentials | None = Field(
        default=None,
        description=(
            "Nomad credentials block for authenticating with the Nomad cluster. "
            "If not provided, the worker will use standard Nomad environment "
            "variables (NOMAD_ADDR, NOMAD_TOKEN, etc.)."
        ),
    )
    datacenters: list[str] = Field(
        default_factory=lambda: ["dc1"],
        description="List of Nomad datacenters to target for job placement.",
    )
    namespace: str | None = Field(
        default=None,
        description="The Nomad namespace to submit the job to.",
    )
    region: str | None = Field(
        default=None,
        description="The Nomad region to submit the job to.",
    )
    task_resources: NomadTaskResources = Field(
        default_factory=NomadTaskResources,
        description="CPU and memory resource requirements for the task.",
    )
    docker_auth: dict[str, str] | None = Field(
        default=None,
        description=(
            "Docker registry authentication credentials. "
            "Expected keys: `username`, `password`, and optionally `server_address`."
        ),
    )
    network_mode: str | None = Field(
        default=None,
        description="Docker network mode (e.g. bridge, host, none).",
    )
    privileged: bool = Field(
        default=False,
        description="Whether to run the Docker container in privileged mode.",
    )
    force_pull: bool = Field(
        default=False,
        description=(
            "Whether to always pull the Docker image, even if present locally on "
            "the Nomad client node."
        ),
    )
    extra_docker_config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Additional Docker driver configuration options to merge into the "
            "task config. These are passed directly to Nomad's Docker driver. "
            "See https://developer.hashicorp.com/nomad/docs/job-declare/task-driver/docker "
            "for available options."
        ),
    )
    extra_task_config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Additional Nomad task-level configuration to merge into the task. "
            "Useful for setting kill_timeout, templates, artifacts, etc."
        ),
    )
    stream_output: bool = Field(
        default=True,
        description="Whether to stream task logs to local standard output.",
    )
    priority: int | None = Field(
        default=None,
        description="Nomad job priority (0-100, higher is more important).",
        ge=0,
        le=100,
    )
    meta: dict[str, str] | None = Field(
        default=None,
        description="Additional metadata key-value pairs for the Nomad job.",
    )
    poll_interval: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        description="Interval in seconds between evaluation/allocation status polls.",
        ge=1,
    )
    job_timeout: int | None = Field(
        default=None,
        description=(
            "Maximum time in seconds to wait for the job to complete "
            "(including evaluation and allocation phases). If None, waits indefinitely."
        ),
        ge=1,
    )

    _flow_run_name: str | None = PrivateAttr(default=None)
    _deployment_name: str | None = PrivateAttr(default=None)

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: "DeploymentResponse | None" = None,
        flow: "APIFlow | None" = None,
        work_pool: "WorkPool | None" = None,
        worker_name: "str | None" = None,
        worker_id: "UUID | None" = None,
    ):
        """Prepares the job configuration for a specific flow run.

        Naming convention:
        - Nomad **Job ID/Name**: deployment name + 8-char flow run ID suffix
          (falls back to flow run name when no deployment exists).
        - Nomad **TaskGroup Name**: flow run name.
        - Nomad **Task Name**: flow run name.

        All names are slugified for Nomad compatibility (RFC 1123: lowercase
        alphanumeric + hyphens, max 63 chars).
        """
        super().prepare_for_flow_run(
            flow_run, deployment, flow, work_pool, worker_name, worker_id=worker_id
        )

        self.image = self.image or get_prefect_image_name()

        # Store the slugified flow run name for TaskGroup/Task naming
        self._flow_run_name = self._slugify(flow_run.name)

        # Use the full flow run ID as the Nomad job name
        self.name = str(flow_run.id)

    @staticmethod
    def _slugify(value: str | None) -> str | None:
        """Converts a string into a Nomad-compatible identifier.

        Nomad job IDs, task group names, and task names must match RFC 1123:
        lowercase alphanumeric characters or hyphens, must start with an
        alphanumeric character, and max 63 chars.

        Args:
            value: The string to slugify.

        Returns:
            A slugified string, or ``None`` if the input is empty or
            contains no valid characters.
        """
        if not value:
            return None

        # Convert to lowercase and replace non-alphanumeric chars with hyphens
        name = value.lower()
        name = re.sub(r"[^a-z0-9-]+", "-", name)
        # Remove leading/trailing hyphens
        name = name.strip("-")
        # Collapse multiple consecutive hyphens
        name = re.sub(r"-{2,}", "-", name)
        # Truncate to 63 characters
        name = name[:63].rstrip("-")

        return name or None

    def build_nomad_job_spec(self) -> dict[str, Any]:
        """Builds a complete Nomad job specification for the Docker task driver.

        Returns:
            A dictionary containing the Nomad job specification in the format
            expected by the Nomad HTTP API (wrapped in a `Job` key).
        """
        job_id = self.name or "prefect-flow-run"

        # Derive task group and task names from the flow run name
        task_group_name = self._flow_run_name or "prefect"
        task_name = self._flow_run_name or "prefect-job"

        # Build Docker driver config
        docker_config: dict[str, Any] = {
            "image": self.image,
            "force_pull": self.force_pull,
        }

        # Set command - Nomad Docker driver uses `command` + `args` format
        if self.command:
            parts = self.command.split()
            docker_config["command"] = parts[0]
            if len(parts) > 1:
                docker_config["args"] = parts[1:]

        if self.docker_auth:
            docker_config["auth"] = {
                k: v
                for k, v in {
                    "username": self.docker_auth.get("username"),
                    "password": self.docker_auth.get("password"),
                    "server_address": self.docker_auth.get("server_address"),
                }.items()
                if v is not None
            }

        if self.network_mode:
            docker_config["network_mode"] = self.network_mode

        if self.privileged:
            docker_config["privileged"] = True

        # Merge any extra Docker driver configuration
        if self.extra_docker_config:
            docker_config.update(self.extra_docker_config)

        # Build the task definition
        task: dict[str, Any] = {
            "Name": task_name,
            "Driver": "docker",
            "Config": docker_config,
            "Env": {k: str(v) for k, v in self.env.items() if v is not None},
            "Resources": {
                "CPU": self.task_resources.cpu,
                "MemoryMB": self.task_resources.memory_mb,
            },
        }

        # Merge extra task-level config
        if self.extra_task_config:
            task.update(self.extra_task_config)

        # Build the task group
        task_group: dict[str, Any] = {
            "Name": task_group_name,
            "Count": 1,
            "RestartPolicy": {
                "Attempts": 0,  # Prefect handles retries, not Nomad
                "Mode": "fail",
            },
            "Tasks": [task],
        }

        # Build job-level metadata by merging defaults with user meta
        job_meta = dict(JOB_META)
        if self.meta:
            job_meta.update(self.meta)

        # Convert labels to Nomad meta format (Nomad meta keys can't have
        # dots or slashes so we convert them)
        for key, value in self.labels.items():
            meta_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
            job_meta[meta_key] = value

        # Build the job specification
        job_spec: dict[str, Any] = {
            "ID": job_id,
            "Name": job_id,
            "Type": "batch",
            "Datacenters": self.datacenters,
            "Meta": job_meta,
            "TaskGroups": [task_group],
        }

        if self.namespace:
            job_spec["Namespace"] = self.namespace

        if self.region:
            job_spec["Region"] = self.region

        if self.priority is not None:
            job_spec["Priority"] = self.priority

        return {"Job": job_spec}


class NomadWorkerResult(BaseWorkerResult):
    """Contains information about a completed Nomad job."""


class NomadWorker(BaseWorker):
    """Prefect worker that executes flow runs as Nomad jobs using the Docker
    task driver.

    This worker submits each flow run as a Nomad batch job. The job uses the
    Docker task driver to run the Prefect flow in a container. The worker polls
    the job's allocation status until the task reaches a terminal state, and
    optionally streams logs from the allocation.

    Attributes:
        type: The worker type identifier (`nomad`).
    """

    type = "nomad"
    job_configuration = NomadWorkerJobConfiguration
    _description = (
        "Execute flow runs as Nomad jobs using the Docker task driver. "
        "Requires access to a running Nomad cluster."
    )
    _display_name = "Nomad"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-nomad"
    _logo_url = "https://www.datocms-assets.com/2885/1620155117-brandhcnomadprimaryattributedcolor.svg"  # noqa: E501

    def _get_nomad_client(
        self, configuration: NomadWorkerJobConfiguration
    ) -> nomad.Nomad:
        """Creates a Nomad client from the job configuration.

        If a `NomadCredentials` block is provided in the configuration, it is
        used. Otherwise, falls back to `python-nomad` default behavior which
        reads from NOMAD_ADDR, NOMAD_TOKEN, and other standard environment
        variables.

        Args:
            configuration: The job configuration that may contain credentials.

        Returns:
            A configured `nomad.Nomad` client.
        """
        if configuration.nomad_credentials:
            return configuration.nomad_credentials.get_client()

        # Fall back to env-var-based client (python-nomad reads NOMAD_ADDR,
        # NOMAD_TOKEN, NOMAD_NAMESPACE, NOMAD_REGION, NOMAD_CLIENT_CERT,
        # NOMAD_CLIENT_KEY automatically)
        return nomad.Nomad()

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: NomadWorkerJobConfiguration,
        task_status: anyio.abc.TaskStatus[str] | None = None,
    ) -> NomadWorkerResult:
        """Executes a flow run by submitting it as a Nomad batch job.

        This method registers a Nomad job with the Docker task driver,
        polls the allocation status until completion, optionally streams
        logs, and returns the result.

        Args:
            flow_run: The flow run to execute.
            configuration: The job configuration.
            task_status: Optional task status to report the infrastructure PID.

        Returns:
            A `NomadWorkerResult` with the job's exit code.
        """
        nomad_client = self._get_nomad_client(configuration)
        job_spec = configuration.build_nomad_job_spec()
        job_id = job_spec["Job"]["ID"]
        task_name = job_spec["Job"]["TaskGroups"][0]["Tasks"][0]["Name"]

        # Register the job (submit to Nomad)
        self._logger.info(f"Submitting Nomad job {job_id!r}...")
        register_response = await run_sync_in_worker_thread(
            self._register_job, nomad_client, job_id, job_spec
        )
        eval_id = register_response["EvalID"]

        infrastructure_pid = self._get_infrastructure_pid(
            nomad_client, job_id, configuration
        )
        created_event = self._emit_job_status_change_event(
            job_id, "submitted", configuration
        )

        # Report the infrastructure PID
        if task_status:
            task_status.started(infrastructure_pid)

        self._logger.info(f"Nomad job {job_id!r} submitted successfully.")

        # Start timing for job_timeout (covers both eval and allocation phases)
        start_time = time.monotonic()

        # Phase 1: Wait for the evaluation to complete (scheduling decision)
        await run_sync_in_worker_thread(
            self._wait_for_evaluation,
            nomad_client,
            eval_id,
            job_id,
            configuration,
            start_time,
        )

        # Phase 2: Wait for the allocation to complete (job execution)
        exit_code = await run_sync_in_worker_thread(
            self._wait_for_job_completion,
            nomad_client,
            job_id,
            task_name,
            configuration,
            created_event,
            start_time,
        )

        return NomadWorkerResult(
            status_code=exit_code,
            identifier=infrastructure_pid,
        )

    def _register_job(
        self,
        nomad_client: nomad.Nomad,
        job_id: str,
        job_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Registers a job with the Nomad cluster.

        Args:
            nomad_client: The Nomad API client.
            job_id: The job ID.
            job_spec: The job specification dictionary.

        Returns:
            The API response from Nomad.
        """
        try:
            return nomad_client.job.register_job(job_id, job_spec)
        except nomad.api.exceptions.BaseNomadException as exc:
            raise NomadJobRegistrationError(
                f"Failed to register Nomad job {job_id!r}: {exc}"
            ) from exc

    def _wait_for_evaluation(
        self,
        nomad_client: nomad.Nomad,
        eval_id: str,
        job_id: str,
        configuration: NomadWorkerJobConfiguration,
        start_time: float,
    ) -> None:
        """Waits for a Nomad evaluation to reach a terminal state.

        Polls the evaluation status until it reaches a terminal state
        (complete, failed, or canceled). Follows evaluation chains
        (NextEval) iteratively. Raises RuntimeError if the evaluation
        fails or has scheduling failures (FailedTGAllocs).

        Args:
            nomad_client: The Nomad API client.
            eval_id: The initial evaluation ID to monitor.
            job_id: The Nomad job ID (for logging).
            configuration: The job configuration.
            start_time: The start time (from time.monotonic()) for timeout tracking.

        Raises:
            NomadJobTimeoutError: If the job times out during evaluation.
            NomadJobSchedulingError: If the job fails to schedule.
            NomadEvaluationError: If the evaluation fails or is canceled.
        """
        current_eval_id = eval_id

        while True:
            # Check timeout
            if configuration.job_timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed > configuration.job_timeout:
                    raise NomadJobTimeoutError(
                        f"Nomad job {job_id!r} timed out after "
                        f"{configuration.job_timeout} seconds during evaluation phase"
                    )

            try:
                eval_data = nomad_client.evaluation.get_evaluation(current_eval_id)
            except nomad.api.exceptions.BaseNomadException as exc:
                self._logger.warning(
                    f"Failed to get evaluation {current_eval_id!r}: {exc}"
                )
                time.sleep(configuration.poll_interval)
                continue

            status = eval_data.get("Status", "pending")
            self._logger.debug(f"Evaluation {current_eval_id[:8]} status: {status}")

            # Check for terminal states
            if status == "complete":
                # Check for scheduling failures
                failed_tg_allocs = eval_data.get("FailedTGAllocs")
                if failed_tg_allocs:
                    # Build detailed error message
                    failure_details = []
                    for tg_name, metrics in failed_tg_allocs.items():
                        nodes_available = metrics.get("NodesAvailable", {})
                        nodes_evaluated = metrics.get("NodesEvaluated", 0)
                        constraint_filtered = metrics.get("ConstraintFiltered")
                        resources_exhausted = metrics.get("ResourcesExhausted")

                        detail = f"Task group {tg_name!r}: "
                        reasons = []
                        if nodes_evaluated == 0:
                            reasons.append("no nodes evaluated")
                        if not any(nodes_available.values()):
                            reasons.append("no nodes available")
                        if constraint_filtered:
                            reasons.append(
                                f"constraint filtered {sum(constraint_filtered.values())} nodes"
                            )
                        if resources_exhausted:
                            reasons.append(
                                f"resources exhausted on {sum(resources_exhausted.values())} nodes"
                            )
                        detail += ", ".join(reasons) if reasons else "unknown failure"
                        failure_details.append(detail)

                    raise NomadJobSchedulingError(
                        f"Nomad job {job_id!r} failed to schedule. "
                        f"Evaluation {current_eval_id[:8]} completed with scheduling failures: "
                        + "; ".join(failure_details)
                    )

                # Evaluation succeeded, scheduling complete
                self._logger.info(
                    f"Evaluation {current_eval_id[:8]} completed successfully"
                )
                return

            elif status == "failed":
                status_desc = eval_data.get("StatusDescription", "")
                raise NomadEvaluationError(
                    f"Nomad evaluation {current_eval_id[:8]} failed"
                    + (f": {status_desc}" if status_desc else "")
                )

            elif status == "canceled":
                raise NomadEvaluationError(
                    f"Nomad evaluation {current_eval_id[:8]} was canceled"
                )

            # Non-terminal states: blocked, pending
            # Check for evaluation chaining
            next_eval = eval_data.get("NextEval", "")
            if next_eval:
                self._logger.info(
                    f"Evaluation {current_eval_id[:8]} spawned next evaluation "
                    f"{next_eval[:8]}, following chain..."
                )
                current_eval_id = next_eval
                # Don't sleep before polling the new eval
                continue

            # Still pending/blocked, wait and retry
            time.sleep(configuration.poll_interval)

    def _wait_for_job_completion(
        self,
        nomad_client: nomad.Nomad,
        job_id: str,
        task_name: str,
        configuration: NomadWorkerJobConfiguration,
        created_event: Event | None = None,
        start_time: float | None = None,
    ) -> int:
        """Polls a Nomad job's allocations until the task reaches a terminal state.

        Terminal allocation client statuses: `complete`, `failed`, `lost`.

        Args:
            nomad_client: The Nomad API client.
            job_id: The Nomad job ID to monitor.
            task_name: The Nomad task name to look up in allocation state.
            configuration: The job configuration.
            created_event: The event from job creation, for event chaining.
            start_time: The start time (from time.monotonic()) for timeout tracking.
                If None, no timeout is enforced.

        Returns:
            The exit code of the task (0 for success, non-zero for failure).

        Raises:
            NomadJobTimeoutError: If the job times out.
        """
        last_event = created_event
        log_offset = 0
        alloc_id = None
        seen_statuses: set[str] = set()

        while True:
            # Check timeout
            if configuration.job_timeout is not None and start_time is not None:
                elapsed = time.monotonic() - start_time
                if elapsed > configuration.job_timeout:
                    raise NomadJobTimeoutError(
                        f"Nomad job {job_id!r} timed out after "
                        f"{configuration.job_timeout} seconds"
                    )

            try:
                allocations = nomad_client.job.get_allocations(job_id)
            except nomad.api.exceptions.BaseNomadException as exc:
                self._logger.warning(
                    f"Failed to get allocations for job {job_id!r}: {exc}"
                )
                time.sleep(configuration.poll_interval)
                continue

            if not allocations:
                self._logger.debug(f"No allocations yet for job {job_id!r}, waiting...")
                time.sleep(configuration.poll_interval)
                continue

            # Use the most recent allocation
            alloc = allocations[0]
            alloc_id = alloc["ID"]
            client_status = alloc.get("ClientStatus", "pending")

            if client_status not in seen_statuses:
                seen_statuses.add(client_status)
                self._logger.info(
                    f"Nomad job {job_id!r} allocation {alloc_id[:8]} "
                    f"status: {client_status}"
                )
                last_event = self._emit_job_status_change_event(
                    job_id,
                    client_status,
                    configuration,
                    last_event=last_event,
                )

            # Stream logs if the allocation is running
            if configuration.stream_output and client_status == "running":
                log_offset = self._stream_allocation_logs(
                    nomad_client, alloc_id, task_name, log_offset
                )

            # Check for terminal states
            if client_status in ("complete", "failed", "lost"):
                # Stream any remaining logs
                if configuration.stream_output and alloc_id:
                    self._stream_allocation_logs(
                        nomad_client, alloc_id, task_name, log_offset
                    )

                exit_code = self._get_exit_code_from_allocation(alloc, task_name)
                self._logger.info(
                    f"Nomad job {job_id!r} finished with status "
                    f"{client_status!r} (exit code: {exit_code})"
                )
                return exit_code

            time.sleep(configuration.poll_interval)

    def _stream_allocation_logs(
        self,
        nomad_client: nomad.Nomad,
        alloc_id: str,
        task_name: str,
        offset: int = 0,
    ) -> int:
        """Streams stdout logs from a Nomad allocation.

        Args:
            nomad_client: The Nomad API client.
            alloc_id: The allocation ID.
            task_name: The task name within the allocation.
            offset: The byte offset to start reading from.

        Returns:
            The new offset after reading logs.
        """
        try:
            stdout = nomad_client.client.stream_logs.stream(
                id_=alloc_id,
                task=task_name,
                type_="stdout",
                plain=True,
                offset=offset,
                origin="start",
            )
            if stdout:
                for line in stdout.splitlines():
                    if line:
                        print(line)
                return offset + len(stdout.encode("utf-8"))
        except Exception:
            # Log streaming is best-effort; don't fail the job
            self._logger.debug(
                f"Could not stream logs for allocation {alloc_id[:8]}",
                exc_info=True,
            )

        return offset

    def _get_exit_code_from_allocation(
        self,
        allocation: dict[str, Any],
        task_name: str,
    ) -> int:
        """Extracts the exit code from a Nomad allocation's task states.

        Args:
            allocation: The allocation dictionary from the Nomad API.
            task_name: The task name to look up.

        Returns:
            The exit code (0 for success, 1 as fallback for failures).
        """
        task_states = allocation.get("TaskStates", {})
        task_state = task_states.get(task_name, {})
        events = task_state.get("Events", [])

        # Look for a Terminated event which contains the exit code
        for event in reversed(events):
            if event.get("Type") == "Terminated":
                exit_code = event.get("ExitCode")
                if exit_code is not None:
                    return exit_code

        # If the allocation completed, assume success
        client_status = allocation.get("ClientStatus", "")
        if client_status == "complete":
            return 0

        # For failed/lost allocations without explicit exit code, return 1
        return 1

    def _get_infrastructure_pid(
        self,
        nomad_client: nomad.Nomad,
        job_id: str,
        configuration: NomadWorkerJobConfiguration,
    ) -> str:
        """Generates an infrastructure PID string for a Nomad job.

        The format is `<nomad_address>:<job_id>` which allows the worker to
        reconstruct a client and stop the job during cancellation.

        Args:
            nomad_client: The Nomad client (used to determine the address).
            job_id: The Nomad job ID.
            configuration: The job configuration.

        Returns:
            An infrastructure PID string.
        """
        if configuration.nomad_credentials:
            address = configuration.nomad_credentials.address
        else:
            # Reconstruct from the nomad client's connection info
            protocol = "https" if nomad_client.secure else "http"
            address = f"{protocol}://{nomad_client.host}:{nomad_client.port}"

        return f"{address}:{job_id}"

    @staticmethod
    def _parse_infrastructure_pid(
        infrastructure_pid: str,
    ) -> tuple[str, str]:
        """Splits a Nomad infrastructure PID into its component parts.

        Args:
            infrastructure_pid: The PID string in format `<address>:<job_id>`.

        Returns:
            A tuple of (nomad_address, job_id).
        """
        # The address contains `://` and potentially a port with `:`, so we
        # split on the last `:` to get the job_id
        last_colon = infrastructure_pid.rfind(":")
        if last_colon == -1:
            raise ValueError(
                f"Invalid infrastructure PID format: {infrastructure_pid!r}. "
                "Expected format: '<nomad_address>:<job_id>'"
            )

        # But we need to be careful: the address is like http://host:port
        # and job_id follows. Find the job_id after the address portion.
        # Pattern: scheme://host:port:job_id or scheme://host:job_id
        parts = infrastructure_pid.split(":")
        # parts = ['http', '//host', 'port', 'job_id'] or
        # parts = ['http', '//host', 'job_id']
        if len(parts) < 3:
            raise ValueError(
                f"Invalid infrastructure PID format: {infrastructure_pid!r}. "
                "Expected format: '<nomad_address>:<job_id>'"
            )

        job_id = parts[-1]
        address = ":".join(parts[:-1])
        return address, job_id

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: NomadWorkerJobConfiguration,
        grace_seconds: int = 30,
    ) -> None:
        """Stops a running Nomad job.

        Args:
            infrastructure_pid: The infrastructure PID in format
                `<nomad_address>:<job_id>`.
            configuration: The job configuration.
            grace_seconds: Not directly used for Nomad (Nomad handles
                graceful shutdown via kill_timeout on the task), but kept
                for API compatibility.

        Raises:
            InfrastructureNotFound: If the job doesn't exist in Nomad.
        """
        _, job_id = self._parse_infrastructure_pid(infrastructure_pid)
        nomad_client = self._get_nomad_client(configuration)

        await run_sync_in_worker_thread(self._stop_job, nomad_client, job_id)

    def _stop_job(self, nomad_client: nomad.Nomad, job_id: str) -> None:
        """Deregisters (stops) a Nomad job.

        Args:
            nomad_client: The Nomad API client.
            job_id: The job ID to stop.

        Raises:
            InfrastructureNotFound: If the job doesn't exist.
            NomadJobStopError: If the job fails to stop.
        """
        try:
            nomad_client.job.deregister_job(job_id, purge=True)
            self._logger.info(f"Stopped Nomad job {job_id!r}")
        except nomad.api.exceptions.URLNotFoundNomadException:
            raise InfrastructureNotFound(f"Nomad job {job_id!r} not found")
        except nomad.api.exceptions.BaseNomadException as exc:
            raise NomadJobStopError(
                f"Failed to stop Nomad job {job_id!r}: {exc}"
            ) from exc

    def _job_as_resource(self, job_id: str) -> dict[str, str]:
        """Convert a Nomad job to a Prefect event resource dictionary."""
        return {
            "prefect.resource.id": f"prefect.nomad.job.{job_id}",
            "prefect.resource.name": job_id,
        }

    def _emit_job_status_change_event(
        self,
        job_id: str,
        status: str,
        configuration: NomadWorkerJobConfiguration,
        last_event: Event | None = None,
    ) -> Event | None:
        """Emits a Prefect event for a Nomad job status change.

        Args:
            job_id: The Nomad job ID.
            status: The current status string.
            configuration: The job configuration.
            last_event: The previous event for chaining.

        Returns:
            The emitted event, or None if emission failed.
        """
        related = self._event_related_resources(configuration=configuration)

        worker_resource = self._event_resource()
        worker_resource["prefect.resource.role"] = "worker"
        worker_related_resource = RelatedResource(worker_resource)

        return emit_event(
            event=f"prefect.nomad.job.{status.lower()}",
            resource=self._job_as_resource(job_id),
            related=related + [worker_related_resource],
            follows=last_event,
        )
