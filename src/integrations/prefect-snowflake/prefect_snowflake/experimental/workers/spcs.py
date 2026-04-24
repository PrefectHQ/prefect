"""Classes and helper functions for creating a worker that can run job services in Snowpark Container Services."""

from __future__ import annotations

import datetime
import json
import os
import shlex
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

import anyio
import dateutil
import snowflake.connector
import yaml
from prefect_snowflake import SnowflakeCredentials
from pydantic import Field
from slugify import slugify
from snowflake.core import Root
from snowflake.core.exceptions import NotFoundError
from snowflake.core.service import (
    ServiceContainer,
    ServiceResource,
)
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_fixed,
    wait_random,
)

import prefect
from prefect.client.schemas.objects import FlowRun
from prefect.states import InfrastructurePending
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.utilities.engine import propose_state
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)

if TYPE_CHECKING:
    from prefect.server.schemas.core import Flow
    from prefect.server.schemas.responses import DeploymentResponse

SUSPENDED_POOL_STATES = frozenset({"SUSPENDED"})
TERMINAL_POOL_FAILURE_STATES = frozenset({"SUSPENDED"})

SPCS_DEFAULT_CPU_REQUEST = "1"
SPCS_DEFAULT_MEMORY_REQUEST = "1G"
SPCS_DEFAULT_CPU_LIMIT = None
SPCS_DEFAULT_MEMORY_LIMIT = None

DEFAULT_CONTAINER_ENTRYPOINT = "/opt/prefect/entrypoint.sh"

MAX_CREATE_SERVICE_ATTEMPTS = 3
CREATE_SERVICE_MIN_DELAY_SECONDS = 1
CREATE_SERVICE_MIN_DELAY_JITTER_SECONDS = 0
CREATE_SERVICE_MAX_DELAY_JITTER_SECONDS = 3


def _is_transient_error(exc: BaseException) -> bool:
    """Classify whether a Snowflake error is transient and worth retrying.

    Transient: connection resets, timeouts, network blips, operational errors.
    Permanent: auth failures, SQL syntax errors, object-not-found, privilege errors.
    """
    if isinstance(exc, snowflake.connector.errors.OperationalError):
        return True
    if isinstance(exc, snowflake.connector.errors.InterfaceError):
        return True
    if isinstance(exc, snowflake.connector.errors.DatabaseError):
        msg = str(exc).lower()
        if any(term in msg for term in ("connection", "timeout", "reset", "network")):
            return True
    return False


def _get_default_job_manifest_template() -> dict[str, Any]:
    """Returns the default job manifest template used by the SPCS job service."""
    # fmt: off
    return {
        "spec": {
            "containers": [
                {
                    "name": "{{ name }}",
                    "image": "{{ image }}",
                    "command": "{{ entrypoint }}",
                    "args": "{{ command }}",
                    "env": "{{ env }}",
                    "secrets": "{{ secrets }}",
                    "volumeMounts": "{{ volume_mounts }}",
                    "resources": {
                        "requests": {
                            "cpu": "{{ cpu_request }}",
                            "nvidia.com/gpu": "{{ gpu_count }}",
                            "memory": "{{ memory_request }}"
                        },
                        "limits": {
                            "cpu": "{{ cpu_limit }}",
                            "nvidia.com/gpu": "{{ gpu_count }}",
                            "memory": "{{ memory_limit }}"
                        },
                    },
                }
            ],
            "volumes": "{{ volumes }}",
            "logExporters": {
                "eventTableConfig": {
                    "logLevel": "{{ log_level }}"
                }
            },
            "platformMonitor":
            {
                "metricConfig": {
                    "groups": "{{ metrics_groups }}"
                }
            }
        }
    }
    # fmt: on


class SPCSWorkerConfiguration(BaseJobConfiguration):
    """Defines variables which can be overridden in the work pool.

    Also handles validation of the config, whether set in the work pool or in the deployment.
    """

    job_manifest: dict[str, Any] = Field(
        json_schema_extra={"template": _get_default_job_manifest_template()}
    )

    image: str = Field(
        default_factory=get_prefect_image_name,
        description="The image to use for the Prefect container in the task. This value defaults to a Prefect base image matching your local versions.",
        examples=["docker.io/prefecthq/prefect:3-latest"],
    )
    image_registry: str | None = Field(
        default=None,
        description="The fully qualified name of the Snowflake image registry.",
    )
    entrypoint: str | None = Field(
        default=DEFAULT_CONTAINER_ENTRYPOINT,
        description=(
            "The entrypoint of the container you wish to run."
            "This value defaults to the entrypoint used by Prefect images and should only be changed when using a custom image that is not based on an official Prefect image."
        ),
    )
    snowflake_credentials: SnowflakeCredentials = Field(
        default_factory=SnowflakeCredentials,
        description="Snowflake credentials to use when creating job services.",
    )
    secrets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Snowflake secrets to inject into the container as env variables or files.",
    )
    external_access_integrations: list[str] = Field(
        default_factory=list,
        description="The names of the external access integrations that the service should be created with.",
    )
    compute_pool: str | None = Field(
        default=None,
        description="The fully-qualified name of the compute pool to run services in.",
        examples=["common.compute.my_compute_pool"],
    )
    cpu_request: str = Field(
        default=SPCS_DEFAULT_CPU_REQUEST,
        description=f"CPU allocation request for the job service. If not provided, a default value of {SPCS_DEFAULT_CPU_REQUEST} will be used.",
    )
    cpu_limit: str | None = Field(
        default=SPCS_DEFAULT_CPU_LIMIT,
        description="CPU allocation limit for the job service. If not provided, there will be no limit.",
    )
    gpu_count: int | None = Field(
        default=None,
        description="The number of GPUs to use. If not provided, no GPUs will be used.",
    )
    memory_request: str = Field(
        default=SPCS_DEFAULT_MEMORY_REQUEST,
        description=(
            "Memory allocation request for the job service. "
            f"If not provided, a default value of {SPCS_DEFAULT_MEMORY_REQUEST} will be used unless present on the task definition."
        ),
    )
    memory_limit: str | None = Field(
        default=SPCS_DEFAULT_MEMORY_LIMIT,
        description="Memory allocation limit for the job service. If not provided, defaults to the same value as memory_request.",
    )
    volume_mounts: list[dict[str, str]] = Field(
        default_factory=list,
        description="Defines where volumes appears in the container.",
    )
    volumes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Shared file system that can be made available in your container.",
    )
    log_level: Literal["INFO", "ERROR", "NONE"] = Field(
        default="INFO",
        description="The level of application logs that Snowflake should collect and export to your event table.",
    )
    metrics_groups: list[str] = Field(
        default_factory=list,
        description="The list of predefined metrics groups that should be logged to the event table.",
    )
    query_warehouse: str | None = Field(
        default=None, description="The query warehouse of the job service."
    )
    service_comment: str | None = Field(
        default=None,
        description="Specify a comment for the job service. Visible in certain Snowflake logs.",
    )
    stream_output: bool = Field(
        default=False,
        description="Direct flow log output back to the worker's console.",
    )
    pool_start_timeout_seconds: int = Field(
        default=600,
        description="The number of seconds to wait for the compute pool to start before considering the run failed.",
    )
    service_start_timeout_seconds: int = Field(
        default=300,
        description="The number of seconds to wait for the job service to start before considering the run failed.",
    )
    service_watch_poll_interval: int = Field(
        default=5,
        description="The number of seconds to wait between Snowflake API calls while monitoring the state of the service.",
    )

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: "DeploymentResponse" | None = None,
        flow: "Flow" | None = None,
        worker_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Prepares the job configuration for a flow run."""
        super().prepare_for_flow_run(
            flow_run, deployment, flow, worker_id=worker_id, **kwargs
        )

        # Validate required fields
        if not self.compute_pool:
            raise ValueError(
                "compute_pool is required to run flows in Snowpark Container Services. "
                "Please set it in your work pool or deployment configuration."
            )

        # Validate compute_pool format
        parts = self.compute_pool.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"compute_pool must be in format 'database.schema.pool_name', got: {self.compute_pool}"
            )

        if not self.image_registry:
            raise ValueError(
                "image_registry is required to run flows in Snowpark Container Services. "
                "Please set it in your work pool or deployment configuration."
            )

        # Validate gpu_count if specified
        if self.gpu_count is not None and self.gpu_count < 0:
            raise ValueError("gpu_count must be a non-negative integer if specified.")

        # Validate image is not empty
        if not self.image or not self.image.strip():
            raise ValueError("image cannot be empty.")

        # Validate resource strings are not empty
        if not self.cpu_request or not self.cpu_request.strip():
            raise ValueError("cpu_request cannot be empty.")
        if not self.memory_request or not self.memory_request.strip():
            raise ValueError("memory_request cannot be empty.")
        if self.cpu_limit is not None and not self.cpu_limit.strip():
            raise ValueError("cpu_limit cannot be empty if specified.")
        if self.memory_limit is not None and not self.memory_limit.strip():
            raise ValueError("memory_limit cannot be empty if specified.")

        # There's only one container.
        container = self.job_manifest["spec"]["containers"][0]

        # Set the container name (may be None from template if no name was configured)
        container["name"] = self.name

        # Ensure an image is set.
        container["image"] = self.image

        # Set the container's environment variables by grabbing them from the worker.
        container["env"] = {**self._base_environment(), **self.env}

        # Remove PREFECT_API_KEY and PREFECT_API_AUTH_STRING from the environment variables, if they exist, and there is an equivalent secret.
        secret_env_vars = {
            secret.get("envVarName")
            for secret in self.secrets
            if "envVarName" in secret
        }
        if (
            "PREFECT_API_KEY" in secret_env_vars
            and "PREFECT_API_KEY" in container["env"]
        ):
            del container["env"]["PREFECT_API_KEY"]
        if (
            "PREFECT_API_AUTH_STRING" in secret_env_vars
            and "PREFECT_API_AUTH_STRING" in container["env"]
        ):
            del container["env"]["PREFECT_API_AUTH_STRING"]

        # Convert the entrypoint from a string to a list, because that's what SPCS expects
        if self.entrypoint:
            container["command"] = shlex.split(self.entrypoint)

        # Convert the command from a string to a list, because that's what SPCS expects
        if self.command:
            container["args"] = shlex.split(self.command)

        # Set memory_limit to the same value as memory_request, if not specified.
        if not self.memory_limit:
            container["resources"]["limits"]["memory"] = self.memory_request

        if not self.cpu_limit:
            container["resources"]["limits"].pop("cpu", None)

        if not self.gpu_count:
            container["resources"]["requests"].pop("nvidia.com/gpu", None)
            container["resources"]["limits"].pop("nvidia.com/gpu", None)

        # Remove the platformMonitor section if there are no metrics groups.
        if not self.metrics_groups:
            self.job_manifest["spec"].pop("platformMonitor")

        if self.pool_start_timeout_seconds < 0:
            raise ValueError(
                "pool_start_timeout_seconds must be a non-negative integer."
            )

        if self.service_start_timeout_seconds < 0:
            raise ValueError(
                "service_start_timeout_seconds must be a non-negative integer."
            )

        if self.service_watch_poll_interval <= 0:
            raise ValueError("service_watch_poll_interval must be a positive integer.")


class SPCSServiceTemplateVariables(BaseVariables):
    """Defines variables which can be overridden by deployments.

    Must include all variables in SPCSWorkerConfiguration. All validation should happen in SPCSWorkerConfiguration.
    """

    image: str = Field(
        default_factory=get_prefect_image_name,
        description="The image to use for the Prefect container in the task. This value defaults to a Prefect base image matching your local versions.",
        examples=["docker.io/prefecthq/prefect:3-latest"],
    )
    image_registry: str | None = Field(
        default=None,
        description="The fully qualified name of the Snowflake image registry.",
    )
    entrypoint: str | None = Field(
        default=DEFAULT_CONTAINER_ENTRYPOINT,
        description=(
            "The entrypoint of the container you wish to run. "
            "This value defaults to the entrypoint used by Prefect images and should only be changed when using a custom image that is not based on an official Prefect image."
        ),
    )
    snowflake_credentials: SnowflakeCredentials = Field(
        default_factory=SnowflakeCredentials,
        description="Snowflake credentials to use when creating job services.",
    )
    secrets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Snowflake secrets to inject into the container as env variables or files.",
    )
    external_access_integrations: list[str] = Field(
        default_factory=list,
        description="The names of the external access integrations that the service should be created with.",
    )
    compute_pool: str | None = Field(
        default=None,
        description="The fully-qualified name of the compute pool to run services in.",
        examples=["common.compute.my_compute_pool"],
    )
    cpu_request: str = Field(
        default=SPCS_DEFAULT_CPU_REQUEST,
        description=f"CPU allocation request for the job service. If not provided, a default value of {SPCS_DEFAULT_CPU_REQUEST} will be used.",
    )
    cpu_limit: str | None = Field(
        default=SPCS_DEFAULT_CPU_LIMIT,
        description="CPU allocation limit for the job service. If not provided, there will be no limit.",
    )
    gpu_count: int | None = Field(
        default=None,
        description="The number of GPUs to use. If not provided, no GPUs will be used.",
    )
    memory_request: str = Field(
        default=SPCS_DEFAULT_MEMORY_REQUEST,
        description=(
            "Memory allocation request for the job service. "
            f"If not provided, a default value of {SPCS_DEFAULT_MEMORY_REQUEST} will be used unless present on the task definition."
        ),
    )
    memory_limit: str | None = Field(
        default=SPCS_DEFAULT_MEMORY_LIMIT,
        description="Memory allocation limit for the job service. If not provided, defaults to the same value as memory_request.",
    )
    volume_mounts: list[dict[str, str]] = Field(
        default_factory=list,
        description="Defines where volumes appears in the container.",
    )
    volumes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Shared file system that can be made available in your container.",
    )
    log_level: Literal["INFO", "ERROR", "NONE"] = Field(
        default="INFO",
        description="The level of application logs that Snowflake should collect and export to your event table.",
    )
    metrics_groups: list[str] = Field(
        default_factory=list,
        description="The list of predefined metrics groups that should be logged to the event table.",
    )
    query_warehouse: str | None = Field(
        default=None, description="The query warehouse of the job service."
    )
    service_comment: str | None = Field(
        default=None,
        description="Specify a comment for the job service. Visible in certain Snowflake logs.",
    )
    stream_output: bool = Field(
        default=False,
        description="Direct flow log output back to the worker's console.",
    )
    pool_start_timeout_seconds: int = Field(
        default=600,
        description="The number of seconds to wait for the compute pool to start before considering the run failed.",
    )
    service_start_timeout_seconds: int = Field(
        default=300,
        description="The number of seconds to wait for the job service to start before considering the run failed.",
    )
    service_watch_poll_interval: int = Field(
        default=5,
        description="The number of seconds to wait between Snowflake API calls while monitoring the state of the service.",
    )


class SPCSWorkerResult(BaseWorkerResult):
    """Result returned by the SPCSWorker."""


class SPCSWorker(BaseWorker):
    """A Prefect worker that runs flows as service jobs in Snowpark Container Services."""

    type: str = "snowpark-container-service"
    job_configuration = SPCSWorkerConfiguration
    job_configuration_variables = SPCSServiceTemplateVariables
    _description = "Execute flow runs within containers on Snowflake's Snowpark Container Services. Requires a Snowflake account."

    async def _start_service_and_build_identifier(
        self,
        flow_run: FlowRun,
        configuration: SPCSWorkerConfiguration,
    ) -> tuple[str, str]:
        """Start a SPCS job service and build its infrastructure identifier.

        Returns:
            A tuple of (job_service_name, identifier).
        """
        [database, schema, _] = configuration.compute_pool.split(".")

        try:
            job_service_name = await run_sync_in_worker_thread(
                self._create_and_start_service,
                flow_run,
                configuration,
            )
        except Exception as exc:
            self._report_service_creation_failure(configuration, exc)
            raise

        identifier = f"{database}.{schema}::{job_service_name}"
        return job_service_name, identifier

    async def _initiate_run(
        self,
        flow_run: FlowRun,
        configuration: SPCSWorkerConfiguration,
    ) -> str:
        """Initiates a flow run as a service job in Snowpark Container Services.

        Returns the infrastructure identifier for cancellation support.
        """
        _, identifier = await self._start_service_and_build_identifier(
            flow_run, configuration
        )
        self._logger.info(f"Initiated SPCS job service: {identifier}")
        return identifier

    async def run(
        self,
        flow_run: FlowRun,
        configuration: SPCSWorkerConfiguration,
        task_status: anyio.abc.TaskStatus | None = None,
    ) -> BaseWorkerResult:
        """Run a flow as a service job in Snowpark Container Services.

        Args:
            flow_run: The flow run to run.
            configuration: The configuration for the flow run.
            task_status: The task status object for the current task. Used
            to provide an identifier that can be used to cancel the task.

        Returns:
            The result of the flow run.

        """
        job_service_name, identifier = await self._start_service_and_build_identifier(
            flow_run, configuration
        )
        self._logger.info(f"Created SPCS job service: {identifier}")

        try:
            async with prefect.get_client() as client:
                with anyio.move_on_after(5):
                    await propose_state(
                        client=client,
                        state=InfrastructurePending(
                            message="SPCS service is provisioning."
                        ),
                        flow_run_id=flow_run.id,
                    )
        except Exception:
            self._logger.debug(
                "Failed to propose InfrastructurePending for flow run %s",
                flow_run.id,
                exc_info=True,
            )

        if task_status:
            task_status.started(identifier)

        job_status = await run_sync_in_worker_thread(
            self._watch_service,
            job_service_name,
            configuration,
        )

        exit_code = job_status if job_status is not None else -1

        return SPCSWorkerResult(
            status_code=exit_code,
            identifier=identifier,
        )

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: SPCSWorkerConfiguration,
        grace_seconds: int = 30,
    ) -> None:
        database, schema, service_name = self._parse_infrastructure_pid(
            infrastructure_pid
        )

        if grace_seconds != 30:
            self._logger.info(
                f"grace_seconds={grace_seconds} ignored; SPCS enforces a "
                "built-in 30-second SIGTERM grace period."
            )
        self._logger.info(f"Dropping job service {service_name}...")

        connection_parameters = self._get_snowflake_connection_parameters(configuration)

        await run_sync_in_worker_thread(
            self._drop_service,
            database,
            schema,
            service_name,
            connection_parameters,
        )

    def _drop_service(
        self,
        database: str,
        schema: str,
        service_name: str,
        connection_parameters: dict[str, Any],
    ) -> None:
        from prefect.exceptions import InfrastructureNotFound

        with snowflake.connector.connect(**connection_parameters) as session:
            root = Root(session)
            try:
                service = (
                    root.databases[database].schemas[schema].services[service_name]
                )
                service.drop()
            except NotFoundError:
                raise InfrastructureNotFound(
                    f"Service {database}.{schema}.{service_name} not found. "
                    "It may have already completed or been deleted."
                )

    @staticmethod
    def _parse_infrastructure_pid(infrastructure_pid: str) -> tuple[str, str, str]:
        if "::" not in infrastructure_pid:
            raise ValueError(
                f"Invalid infrastructure PID format: {infrastructure_pid!r}. "
                "Expected 'database.schema::service_name'."
            )
        location, service_name = infrastructure_pid.split("::", 1)
        parts = location.split(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid location in infrastructure PID: {location!r}. "
                "Expected 'database.schema'."
            )
        return parts[0], parts[1], service_name

    def _report_service_creation_failure(
        self, configuration: SPCSWorkerConfiguration, exc: Exception
    ) -> None:
        """Wrap common Snowflake errors with actionable messages."""
        msg = str(exc)
        error_kind = "transient" if _is_transient_error(exc) else "permanent"
        self._logger.debug(
            f"Service creation failed ({error_kind}): {type(exc).__name__}: {msg}"
        )

        if isinstance(exc, snowflake.connector.errors.ProgrammingError):
            if "does not exist" in msg.lower():
                raise RuntimeError(
                    f"Failed to create SPCS job service: {msg}. "
                    "Verify that the compute pool, database, and schema exist "
                    "and that the configured role has access. "
                    f"Compute pool: {configuration.compute_pool}"
                ) from exc
            if "insufficient privileges" in msg.lower():
                raise RuntimeError(
                    "Failed to create SPCS job service: insufficient privileges. "
                    "Ensure the configured role has USAGE on the compute pool "
                    "and CREATE SERVICE on the schema. "
                    f"Compute pool: {configuration.compute_pool}"
                ) from exc
        elif isinstance(exc, snowflake.connector.errors.DatabaseError):
            if "connection" in msg.lower() or "timeout" in msg.lower():
                raise RuntimeError(
                    f"Failed to connect to Snowflake: {msg}. "
                    "Check your network connectivity and Snowflake account credentials."
                ) from exc
        raise

    @retry(
        stop=stop_after_attempt(MAX_CREATE_SERVICE_ATTEMPTS),
        wait=wait_fixed(CREATE_SERVICE_MIN_DELAY_SECONDS)
        + wait_random(
            CREATE_SERVICE_MIN_DELAY_JITTER_SECONDS,
            CREATE_SERVICE_MAX_DELAY_JITTER_SECONDS,
        ),
        retry=retry_if_exception(_is_transient_error),
        reraise=True,
    )
    def _create_and_start_service(
        self,
        flow_run: FlowRun,
        configuration: SPCSWorkerConfiguration,
    ) -> str:
        [database, schema, compute_pool] = configuration.compute_pool.split(".")

        job_manifest_yaml = yaml.dump(configuration.job_manifest)
        job_service_name = self._slugify_service_name(configuration.name, flow_run.id)

        self._logger.info(
            f"Starting job service {job_service_name} in compute pool {compute_pool}..."
        )
        self._logger.debug(
            f"Job manifest: {json.dumps(configuration.job_manifest, indent=2, default=str)}"
        )

        connection_parameters = self._get_snowflake_connection_parameters(configuration)
        auth_method = (
            "in-Snowflake OAuth"
            if os.getenv("SNOWFLAKE_HOST")
            else "external credentials"
        )
        self._logger.info(f"Connecting to Snowflake using {auth_method}")

        with snowflake.connector.connect(**connection_parameters) as session:
            # The Snowflake Python SDK currently doesn't support creating a service and
            # forgetting about it (the service will be deleted once the connection is closed).
            # We need to run SQL commands using snowflake-connector for now.
            cur = session.cursor()

            query_warehouse = (
                "\tQUERY_WAREHOUSE = IDENTIFIER(%s)\n"
                if configuration.query_warehouse is not None
                else ""
            )
            service_comment = (
                "\tCOMMENT = %s\n" if configuration.service_comment is not None else ""
            )

            eai_placeholders = ""
            if configuration.external_access_integrations:
                eai_placeholders = ", ".join(
                    ["IDENTIFIER(%s)"] * len(configuration.external_access_integrations)
                )
                external_access_integrations = (
                    f"\tEXTERNAL_ACCESS_INTEGRATIONS = ({eai_placeholders})\n"
                )
            else:
                external_access_integrations = ""

            sql_template = (
                "EXECUTE JOB SERVICE\n"
                "\tIN COMPUTE POOL IDENTIFIER(%s)\n"
                "\tNAME = IDENTIFIER(%s)\n"
                "\tASYNC = TRUE\n"
                f"{query_warehouse}"
                f"{service_comment}"
                f"{external_access_integrations}"
                "FROM SPECIFICATION %s;"
            )

            params = [compute_pool, f"{database}.{schema}.{job_service_name}"]

            if configuration.query_warehouse is not None:
                params.append(configuration.query_warehouse)

            if configuration.service_comment is not None:
                params.append(configuration.service_comment)

            if configuration.external_access_integrations:
                params.extend(configuration.external_access_integrations)

            params.append(job_manifest_yaml)

            cur.execute(sql_template, params)

        return job_service_name

    def _watch_service(
        self,
        job_service_name: str,
        configuration: SPCSWorkerConfiguration,
    ) -> int:
        pool_start_datetime = datetime.datetime.now(datetime.timezone.utc)
        pool_start_time_seconds = pool_start_datetime.timestamp()
        pool_timeout = configuration.pool_start_timeout_seconds

        [database, schema, compute_pool] = configuration.compute_pool.split(".")

        connection_parameters = self._get_snowflake_connection_parameters(configuration)

        with snowflake.connector.connect(**connection_parameters) as session:
            root = Root(session)
            pool = root.compute_pools[compute_pool]

            while True:
                pool_state = pool.fetch().state

                if pool_state in TERMINAL_POOL_FAILURE_STATES:
                    raise RuntimeError(
                        f"Compute pool {compute_pool} is in state {pool_state}. "
                        "Resume it with ALTER COMPUTE POOL ... RESUME before running flows."
                    )

                if pool_state in ("ACTIVE", "IDLE"):
                    break

                elapsed_time = time.time() - pool_start_time_seconds

                if pool_timeout and elapsed_time > pool_timeout:
                    raise RuntimeError(
                        f"Timed out after {elapsed_time} s while waiting for compute pool to become ready."
                    )

                self._logger.info(
                    f"Compute pool {compute_pool} is {pool_state}, waiting for ready state (polling in {configuration.service_watch_poll_interval}s)."
                )
                time.sleep(configuration.service_watch_poll_interval)

            service_start_datetime = datetime.datetime.now(datetime.timezone.utc)
            service_start_time_seconds = service_start_datetime.timestamp()
            service_timeout = configuration.service_start_timeout_seconds

            service = (
                root.databases[database].schemas[schema].services[job_service_name]
            )
            last_log_time = service_start_datetime
            service_status: str | None = None

            while True:
                # Sleep first, give the job service a chance to start.
                time.sleep(configuration.service_watch_poll_interval)

                try:
                    # There should only be one container in the service.
                    container = next(service.get_containers())
                    service_status = container.service_status

                    # Stream logs during execution if configured, and always
                    # forward final logs on failure (matches K8s/ECS behavior).
                    should_stream = configuration.stream_output and service_status in (
                        "RUNNING",
                        "DONE",
                        "FAILED",
                    )
                    should_forward_crash_logs = (
                        not configuration.stream_output
                        and service_status in ("FAILED", "INTERNAL_ERROR")
                    )
                    if should_stream or should_forward_crash_logs:
                        try:
                            last_log_time = self._get_and_stream_output(
                                service=service,
                                container=container,
                                last_log_time=last_log_time,
                            )
                        except Exception:
                            if should_forward_crash_logs:
                                self._logger.debug(
                                    f"Failed to retrieve crash logs for {job_service_name}",
                                    exc_info=True,
                                )
                            else:
                                raise

                    # If status in one of these, the container is no longer running.
                    if service_status in (
                        "DONE",
                        "FAILED",
                        "SUSPENDING",
                        "SUSPENDED",
                        "DELETING",
                        "DELETED",
                        "INTERNAL_ERROR",
                    ):
                        break
                except NotFoundError as not_found_error:
                    elapsed_time = time.time() - service_start_time_seconds

                    if service_timeout and elapsed_time > service_timeout:
                        raise RuntimeError(
                            f"Timed out after {elapsed_time} s while waiting for service start."
                        ) from not_found_error

                    self._logger.info(
                        f"Service {job_service_name} isn't running yet, polling for status again in {configuration.service_watch_poll_interval} seconds."
                    )

        if service_status is None:
            self._logger.warning(
                f"Service {job_service_name} loop exited without determining status"
            )
            return -1

        if service_status == "DONE":
            self._logger.info(f"Service {job_service_name} completed successfully.")
            return 0

        self._log_service_failure_diagnostic(job_service_name, service_status)
        return 1

    def _log_service_failure_diagnostic(
        self,
        job_service_name: str,
        service_status: str,
    ) -> None:
        _DIAGNOSTICS: dict[str, tuple[str, str]] = {
            "FAILED": (
                "error",
                "Container exited with an error. Check the Snowflake event "
                "table for detailed logs: "
                "SELECT * FROM <event_table> WHERE RESOURCE_ATTRIBUTES['snow.service.name'] = "
                f"'{job_service_name}' ORDER BY TIMESTAMP DESC LIMIT 50;",
            ),
            "INTERNAL_ERROR": (
                "error",
                "Snowflake encountered an internal platform error. This is "
                "typically transient — retry the flow run. Contact Snowflake "
                "support if it persists.",
            ),
            "SUSPENDING": (
                "warning",
                "Service is being suspended. The compute pool may have been "
                "suspended or auto-suspended due to inactivity. Resume with: "
                "ALTER COMPUTE POOL <pool> RESUME;",
            ),
            "SUSPENDED": (
                "warning",
                "Service was suspended. The compute pool may have been "
                "suspended or auto-suspended due to inactivity. Resume with: "
                "ALTER COMPUTE POOL <pool> RESUME;",
            ),
            "DELETING": (
                "warning",
                "Service is being deleted. This may indicate manual "
                "cancellation or automatic cleanup.",
            ),
            "DELETED": (
                "warning",
                "Service was deleted externally. This may indicate manual "
                "cancellation or automatic cleanup.",
            ),
        }

        level, message = _DIAGNOSTICS.get(
            service_status,
            ("warning", f"ended with unexpected status {service_status}"),
        )
        log_fn = self._logger.error if level == "error" else self._logger.warning
        log_fn(f"Service {job_service_name}: {message}")

    @staticmethod
    def _get_snowflake_connection_parameters(
        configuration: SPCSWorkerConfiguration,
    ) -> dict[str, Any]:
        """Get the Snowflake connection parameters for the worker.

        Args:
            configuration: The worker configuration.

        Returns:
            A dictionary containing the Snowflake connection parameters.

        """
        # If SNOWFLAKE_HOST is defined, we're probably running in Snowflake.
        # That means we can run as the service account.
        if os.getenv("SNOWFLAKE_HOST"):
            connection_parameters = {
                "host": os.getenv("SNOWFLAKE_HOST"),
                "account": os.getenv("SNOWFLAKE_ACCOUNT"),
                "token": Path("/snowflake/session/token").read_text(),
                "authenticator": "oauth",
                "application": "Prefect_Snowflake_Collection",
            }
        else:
            creds = configuration.snowflake_credentials
            connection_parameters: dict[str, Any] = {
                "account": creds.account,
                "user": creds.user,
                "role": creds.role,
                "application": "Prefect_Snowflake_Collection",
            }
            private_key = creds.resolve_private_key()
            if private_key is not None:
                connection_parameters["private_key"] = private_key
            elif creds.password is not None:
                connection_parameters["password"] = creds.password.get_secret_value()

        return connection_parameters

    @staticmethod
    def _slugify_service_name(service_name: str, flow_run_id: UUID) -> str | None:
        """Generates a service name to match the configured name, ensuring it's SPCS compatible."""
        # Must match `/?[a-zA-Z0-9][a-zA-Z0-9_]+` in the end.
        if not service_name:
            return None

        # Convert flow_run_id to a string.
        flow_run_id = str(flow_run_id)

        # Slugify flow_name and ensure that the generated name won't be too long for the max deployment name length (63).
        slugified_flow_name = slugify(
            service_name,
            separator="_",
            max_length=62 - len(flow_run_id),
            regex_pattern=r"[^a-zA-Z0-9_]+",  # Only allow lowercase, uppercase letters, numbers, underscores.
        ).strip("_")  # Remove leading and trailing underscores.

        return f"{slugified_flow_name}_{flow_run_id.replace('-', '_')}"

    def _get_and_stream_output(
        self,
        service: ServiceResource,
        container: ServiceContainer,
        last_log_time: datetime,
    ) -> datetime:
        """Fetches logs output from the job container and writes all entries after a given time to stderr.

        Args:
            service: The service we want to retrieve logs for.
            container: The service container.
            last_log_time: The timestamp of the last output line already streamed.

        Returns:
            The time of the most recent output line written by this call.

        """
        logs = self._get_logs(service=service, container=container)

        return self._stream_output(logs, last_log_time)

    def _get_logs(
        self,
        service: ServiceResource,
        container: ServiceContainer,
        max_lines: int = 100,
    ) -> str:
        """Gets the most recent service logs up to a given maximum.

        Args:
            service: The service we want to retrieve logs for.
            container: The service container.
            max_lines: The number of log lines to pull. Defaults to 100.

        Returns:
            A string containing the requested log entries, one per line.

        """
        instance_id = container.instance_id
        container_name = container.container_name

        return service.get_service_logs(
            instance_id=instance_id, container_name=container_name, num_lines=max_lines
        )

    def _stream_output(self, log_content: str, last_log_time: datetime) -> datetime:
        """Writes each entry from a string of log lines to stderr.

        Args:
            log_content: A string containing SPCS container logs.
            last_log_time: The timestamp of the last output line already streamed.

        Returns:
            The time of the most recent output line written by this call.

        """
        if not log_content:
            # Nothing to stream.
            return last_log_time

        log_lines = log_content.split("\n")

        last_written_time = last_log_time

        for log_line in log_lines:
            # Skip if the line is blank or whitespace.
            if not log_line.strip():
                continue

            line_parts = log_line.split(" ")
            # The timestamp should always be before the first space in the line.
            line_timestamp = line_parts[0]

            try:
                # Parse the timestamp and make it timezone-aware.
                line_time = dateutil.parser.parse(line_timestamp).replace(
                    tzinfo=datetime.timezone.utc
                )

                if line_time > last_written_time:
                    print(log_line, file=sys.stderr)
                    last_written_time = line_time
            except dateutil.parser.ParserError as e:
                self._logger.debug(
                    ("Unable to parse timestamp from SPCS log line: %s"),
                    log_line,
                    exc_info=e,
                )

        return last_written_time
