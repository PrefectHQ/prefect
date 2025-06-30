"""Classes and helper functions for creating a worker that can run job services in Snowpark Container Services."""

import datetime
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional
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
    JobService,
    ServiceContainer,
    ServiceResource,
    ServiceSpec,
)

from prefect.client.schemas.objects import FlowRun
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)

if TYPE_CHECKING:
    from prefect.server.schemas.core import Flow
    from prefect.server.schemas.responses import DeploymentResponse

SPCS_DEFAULT_CPU_REQUEST = "1"
SPCS_DEFAULT_MEMORY_REQUEST = "1G"
SPCS_DEFAULT_CPU_LIMIT = None
SPCS_DEFAULT_MEMORY_LIMIT = None

DEFAULT_CONTAINER_ENTRYPOINT = "/opt/prefect/entrypoint.sh"


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
                    "args": " {{ command }}",
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
    image_registry: str = Field(
        default=None,
        description="The fully qualified name of the Snowflake image registry.",
    )
    entrypoint: Optional[str] = Field(
        default=DEFAULT_CONTAINER_ENTRYPOINT,
        description=(
            "The entrypoint of the container you wish you run."
            "This value defaults to the entrypoint used by Prefect images and should only be changed when using a custom image that is not based on an official Prefect image."
        ),
    )
    snowflake_credentials: SnowflakeCredentials = Field(
        default_factory=SnowflakeCredentials,
        description="Snowflake credentials to use when creating job services.",
    )
    secrets: list[dict[str, str]] = Field(
        default_factory=list,
        description="Snowflake secrets to inject into the container as env variables or files.",
    )
    external_access_integrations: list[str] = Field(
        default_factory=list,
        description="The names of the external access integrations that the service should be created with.",
    )
    compute_pool: str = Field(
        default=None,
        description="The fully-qualified name of the compute pool to run services in.",
        examples=["common.compute.my_compute_pool"],
    )
    cpu_request: str = Field(
        default=SPCS_DEFAULT_CPU_REQUEST,
        description=f"CPU allocation request for the job service. If not provided, a default value of {SPCS_DEFAULT_CPU_REQUEST} will be used.",
    )
    cpu_limit: str = Field(
        default=SPCS_DEFAULT_CPU_LIMIT,
        description="CPU allocation limit for the job service. If not provided, there will be no limit.",
    )
    gpu_count: Optional[int] = Field(
        default=None,
        description="The number of GPUs to use. If not provided, no GPUs will be used.",
    )
    memory_request: str = Field(
        default=SPCS_DEFAULT_MEMORY_REQUEST,
        description=(
            "Memory allocation request for the job service."
            f"If not provided, a default value of {SPCS_DEFAULT_MEMORY_REQUEST} will be used unless present on the task definition."
        ),
    )
    memory_limit: str = Field(
        default=SPCS_DEFAULT_MEMORY_LIMIT,
        description="Memory allocation limit for the job service. If not provided, will be the same as the request.",
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
    query_warehouse: Optional[str] = Field(
        default=None, description="The query warehouse of the job service."
    )
    service_comment: Optional[str] = Field(
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
        deployment: Optional["DeploymentResponse"] = None,
        flow: Optional["Flow"] = None,
    ) -> None:
        """Prepares the job configuration for a flow run."""
        super().prepare_for_flow_run(flow_run, deployment, flow)

        # There's only one container.
        container = self.job_manifest["spec"]["containers"][0]

        # Ensure an image is set.
        container["image"] = self.image

        # Set the container's environment variables by grabbing them from the worker.
        container["env"] = {**self._base_environment(), **self.env}

        # Convert the entrypoint from a string to a list, because that's what SPCS expects
        if self.entrypoint:
            container["command"] = self.entrypoint.split(" ")

        # Convert the command from a string to a list, because that's what SPCS expects
        if self.command:
            container["args"] = self.command.split(" ")

        # Set memory_limit to the same value as memory_request, if not specified.
        if not self.memory_limit:
            container["resources"]["limits"]["memory"] = self.memory_request

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


class SPCSServiceTemplateVariables(BaseVariables):
    """Defines variables which can be overridden by deployments.

    Must include all variables in SPCSWorkerConfiguration. All validation should happen in SPCSWorkerConfiguration.
    """

    image: str = Field(
        default_factory=get_prefect_image_name,
        description="The image to use for the Prefect container in the task. This value defaults to a Prefect base image matching your local versions.",
        examples=["docker.io/prefecthq/prefect:3-latest"],
    )
    image_registry: str = Field(
        default=None,
        description="The fully qualified name of the Snowflake image registry.",
    )
    entrypoint: Optional[str] = Field(
        default=DEFAULT_CONTAINER_ENTRYPOINT,
        description=(
            "The entrypoint of the container you wish you run."
            "This value defaults to the entrypoint used by Prefect images and should only be changed when using a custom image that is not based on an official Prefect image."
        ),
    )
    snowflake_credentials: SnowflakeCredentials = Field(
        default_factory=SnowflakeCredentials,
        description="Snowflake credentials to use when creating job services.",
    )
    secrets: list[dict[str, str]] = Field(
        default_factory=list,
        description="Snowflake secrets to inject into the container as env variables or files.",
    )
    external_access_integrations: list[str] = Field(
        default_factory=list,
        description="The names of the external access integrations that the service should be created with.",
    )
    compute_pool: str = Field(
        description="The fully-qualified name of the compute pool to run services in.",
        examples=["common.compute.my_compute_pool"],
    )
    cpu_request: str = Field(
        default=SPCS_DEFAULT_CPU_REQUEST,
        description=f"CPU allocation request for the job service. If not provided, a default value of {SPCS_DEFAULT_CPU_REQUEST} will be used.",
    )
    cpu_limit: str = Field(
        default=SPCS_DEFAULT_CPU_LIMIT,
        description="CPU allocation limit for the job service. If not provided, there will be no limit.",
    )
    gpu_count: Optional[int] = Field(
        default=None,
        description="The number of GPUs to use. If not provided, no GPUs will be used.",
    )
    memory_request: str = Field(
        default=SPCS_DEFAULT_MEMORY_REQUEST,
        description=(
            "Memory allocation request for the job service."
            f"If not provided, a default value of {SPCS_DEFAULT_MEMORY_REQUEST} will be used unless present on the task definition."
        ),
    )
    memory_limit: str = Field(
        default=SPCS_DEFAULT_MEMORY_LIMIT,
        description="Memory allocation limit for the job service. If not provided, will be the same as the request.",
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
    query_warehouse: Optional[str] = Field(
        default=None, description="The query warehouse of the job service."
    )
    service_comment: Optional[str] = Field(
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

    async def run(
        self,
        flow_run: FlowRun,
        configuration: SPCSWorkerConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
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
        connection_parameters = self._get_snowflake_connection_parameters(configuration)

        session = snowflake.connector.connect(**connection_parameters)
        root = Root(session)

        # Create the execution environment and start execution
        job_service_name = await run_sync_in_worker_thread(
            self._create_and_start_service,
            root,
            flow_run,
            configuration,
        )

        if task_status:
            # Use a unique ID to mark the run as started.
            # This ID is later used to tear down infrastructure, if the flow run is cancelled.
            task_status.started(job_service_name)

        # Monitor the execution
        job_status = await run_sync_in_worker_thread(
            self._watch_service,
            job_service_name,
            root,
            configuration,
        )

        # We're done in Snowflake, close the connection.
        session.close()

        exit_code = (
            job_status if job_status is not None else -1
        )  # Get the result of the execution for reporting

        return SPCSWorkerResult(
            status_code=exit_code,
            identifier=job_service_name,
        )

    def _create_and_start_service(
        self,
        root: Root,
        flow_run: FlowRun,
        configuration: SPCSWorkerConfiguration,
    ) -> str:
        [database, schema, compute_pool] = configuration.compute_pool.split(".")

        job_manifest_yaml = yaml.dump(configuration.job_manifest)
        job_service_name = self._slugify_service_name(configuration.name, flow_run.id)

        self._logger.info(
            f"Starting job service {job_service_name} in compute pool {compute_pool}..."
        )

        job_service = JobService(
            name=job_service_name,
            compute_pool=compute_pool,
            spec=ServiceSpec(job_manifest_yaml),
            external_access_integrations=configuration.external_access_integrations
            if configuration.external_access_integrations
            else None,  # Don't set if list is empty.
            query_warehouse=configuration.query_warehouse,
            comment=configuration.service_comment,
        )

        root.databases[database].schemas[schema].services.execute_job_async(job_service)

        return job_service_name

    def _watch_service(
        self,
        job_service_name: str,
        root: Root,
        configuration: SPCSWorkerConfiguration,
    ) -> int:
        pool_start_datetime = datetime.datetime.now(datetime.timezone.utc)
        pool_start_time_seconds = pool_start_datetime.timestamp()
        pool_timeout = configuration.pool_start_timeout_seconds

        [database, schema, compute_pool] = configuration.compute_pool.split(".")
        pool = root.compute_pools[compute_pool]

        while True:
            pool_state = pool.fetch().state

            # Wait until the compute pool is active. It might be idle, resizing, etc.
            if pool_state == "ACTIVE":
                break

            elapsed_time = time.time() - pool_start_time_seconds

            if pool_timeout and elapsed_time > pool_timeout:
                raise RuntimeError(
                    f"Timed out after {elapsed_time} s while waiting for compute pool start."
                )

            self._logger.info(
                f"Compute pool {compute_pool} is in state {pool_state}, checking for ACTIVE state again in {configuration.service_watch_poll_interval} seconds."
            )
            time.sleep(configuration.service_watch_poll_interval)

        service_start_datetime = datetime.datetime.now(datetime.timezone.utc)
        service_start_time_seconds = service_start_datetime.timestamp()
        service_timeout = configuration.service_start_timeout_seconds

        service = root.databases[database].schemas[schema].services[job_service_name]
        last_log_time = service_start_datetime

        while True:
            # Sleep first, give the job service a chance to start.
            time.sleep(configuration.service_watch_poll_interval)

            try:
                # There should only be one container in the service.
                container = next(service.get_containers())
                service_status = container.service_status

                # If status == PENDING or similar, we'll get an exception if we try to retrieve logs.
                if configuration.stream_output and service_status in (
                    "RUNNING",
                    "DONE",
                    "FAILED",
                ):
                    last_log_time = self._get_and_stream_output(
                        service=service,
                        container=container,
                        last_log_time=last_log_time,
                    )

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

        return 0

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
            }
        else:
            connection_parameters = {
                "account": configuration.snowflake_credentials.account,
                "user": configuration.snowflake_credentials.user,
                "private_key": configuration.snowflake_credentials.resolve_private_key(),
                "role": configuration.snowflake_credentials.role,
            }

        return connection_parameters

    @staticmethod
    def _slugify_service_name(service_name: str, flow_run_id: UUID) -> Optional[str]:
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
