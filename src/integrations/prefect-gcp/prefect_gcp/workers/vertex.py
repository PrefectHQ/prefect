""" <!-- # noqa -->

Module containing the custom worker used for executing flow runs as Vertex AI Custom Jobs.

Get started by creating a Cloud Run work pool:

```bash
prefect work-pool create 'my-vertex-pool' --type vertex-ai
```

Then start a Cloud Run worker with the following command:

```bash
prefect worker start --pool 'my-vertex-pool'
```

## Configuration
Read more about configuring work pools
[here](https://docs.prefect.io/latest/concepts/work-pools/#work-pool-overview).
"""
import datetime
import re
import shlex
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import uuid4

import anyio
from pydantic import VERSION as PYDANTIC_VERSION

from prefect.exceptions import InfrastructureNotFound
from prefect.logging.loggers import PrefectLogAdapter
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.pydantic import JsonPatch
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, validator
else:
    from pydantic import Field, validator

from slugify import slugify

from prefect_gcp.credentials import GcpCredentials

# to prevent "Failed to load collection" from surfacing
# if google-cloud-aiplatform is not installed
try:
    from google.api_core.client_options import ClientOptions
    from google.cloud.aiplatform.gapic import JobServiceClient
    from google.cloud.aiplatform_v1.types.custom_job import (
        ContainerSpec,
        CustomJob,
        CustomJobSpec,
        Scheduling,
        WorkerPoolSpec,
    )
    from google.cloud.aiplatform_v1.types.job_service import CancelCustomJobRequest
    from google.cloud.aiplatform_v1.types.job_state import JobState
    from google.cloud.aiplatform_v1.types.machine_resources import DiskSpec, MachineSpec
    from google.protobuf.duration_pb2 import Duration
    from tenacity import retry, stop_after_attempt, wait_fixed, wait_random
except ModuleNotFoundError:
    pass

_DISALLOWED_GCP_LABEL_CHARACTERS = re.compile(r"[^-a-zA-Z0-9_]+")

if TYPE_CHECKING:
    from prefect.client.schemas import FlowRun
    from prefect.server.schemas.core import Flow
    from prefect.server.schemas.responses import DeploymentResponse


class VertexAIWorkerVariables(BaseVariables):
    """
    Default variables for the Vertex AI worker.

    The schema for this class is used to populate the `variables` section of the default
    base job template.
    """

    region: str = Field(
        description="The region where the Vertex AI Job resides.",
        example="us-central1",
    )
    image: str = Field(
        title="Image Name",
        description=(
            "The URI of a container image in the Container or Artifact Registry, "
            "used to run your Vertex AI Job. Note that Vertex AI will need access"
            "to the project and region where the container image is stored. See "
            "https://cloud.google.com/vertex-ai/docs/training/create-custom-container"
        ),
        example="gcr.io/your-project/your-repo:latest",
    )
    credentials: Optional[GcpCredentials] = Field(
        title="GCP Credentials",
        default_factory=GcpCredentials,
        description="The GCP Credentials used to initiate the "
        "Vertex AI Job. If not provided credentials will be "
        "inferred from the local environment.",
    )
    machine_type: str = Field(
        title="Machine Type",
        description=(
            "The machine type to use for the run, which controls "
            "the available CPU and memory. "
            "See https://cloud.google.com/vertex-ai/docs/reference/rest/v1/MachineSpec"
        ),
        default="n1-standard-4",
    )
    accelerator_type: Optional[str] = Field(
        title="Accelerator Type",
        description=(
            "The type of accelerator to attach to the machine. "
            "See https://cloud.google.com/vertex-ai/docs/reference/rest/v1/MachineSpec"
        ),
        example="NVIDIA_TESLA_K80",
        default=None,
    )
    accelerator_count: Optional[int] = Field(
        title="Accelerator Count",
        description=(
            "The number of accelerators to attach to the machine. "
            "See https://cloud.google.com/vertex-ai/docs/reference/rest/v1/MachineSpec"
        ),
        example=1,
        default=None,
    )
    boot_disk_type: str = Field(
        title="Boot Disk Type",
        description="The type of boot disk to attach to the machine.",
        default="pd-ssd",
    )
    boot_disk_size_gb: int = Field(
        title="Boot Disk Size (GB)",
        description="The size of the boot disk to attach to the machine, in gigabytes.",
        default=100,
    )
    maximum_run_time_hours: int = Field(
        default=1,
        title="Maximum Run Time (Hours)",
        description="The maximum job running time, in hours",
    )
    network: Optional[str] = Field(
        default=None,
        title="Network",
        description="The full name of the Compute Engine network"
        "to which the Job should be peered. Private services access must "
        "already be configured for the network. If left unspecified, the job "
        "is not peered with any network. "
        "For example: projects/12345/global/networks/myVPC",
    )
    reserved_ip_ranges: Optional[List[str]] = Field(
        default=None,
        title="Reserved IP Ranges",
        description="A list of names for the reserved ip ranges under the VPC "
        "network that can be used for this job. If set, we will deploy the job "
        "within the provided ip ranges. Otherwise, the job will be deployed to "
        "any ip ranges under the provided VPC network.",
    )
    service_account_name: Optional[str] = Field(
        default=None,
        title="Service Account Name",
        description=(
            "Specifies the service account to use "
            "as the run-as account in Vertex AI. The worker submitting jobs must have "
            "act-as permission on this run-as account. If unspecified, the AI "
            "Platform Custom Code Service Agent for the CustomJob's project is "
            "used. Takes precedence over the service account found in GCP credentials, "
            "and required if a service account cannot be detected in GCP credentials."
        ),
    )
    job_watch_poll_interval: float = Field(
        default=5.0,
        title="Poll Interval (Seconds)",
        description=(
            "The amount of time to wait between GCP API calls while monitoring the "
            "state of a Vertex AI Job."
        ),
    )


def _get_base_job_spec() -> Dict[str, Any]:
    """Returns a base job body to use for job spec validation.
    Note that the values are stubbed and are not used for the actual job."""
    return {
        "maximum_run_time_hours": "1",
        "worker_pool_specs": [
            {
                "replica_count": 1,
                "container_spec": {
                    "image_uri": "gcr.io/your-project/your-repo:latest",
                },
                "machine_spec": {
                    "machine_type": "n1-standard-4",
                },
                "disk_spec": {
                    "boot_disk_type": "pd-ssd",
                    "boot_disk_size_gb": "100",
                },
            }
        ],
    }


class VertexAIWorkerJobConfiguration(BaseJobConfiguration):
    """
    Configuration class used by the Vertex AI Worker to create a Job.

    An instance of this class is passed to the Vertex AI Worker's `run` method
    for each flow run. It contains all information necessary to execute
    the flow run as a Vertex AI Job.

    Attributes:
        region: The region where the Vertex AI Job resides.
        credentials: The GCP Credentials used to connect to Vertex AI.
        job_spec: The Vertex AI Job spec used to create the Job.
        job_watch_poll_interval: The interval between GCP API calls to check Job state.
    """

    region: str = Field(
        description="The region where the Vertex AI Job resides.",
        example="us-central1",
    )
    credentials: Optional[GcpCredentials] = Field(
        title="GCP Credentials",
        default_factory=GcpCredentials,
        description="The GCP Credentials used to initiate the "
        "Vertex AI Job. If not provided credentials will be "
        "inferred from the local environment.",
    )

    job_spec: Dict[str, Any] = Field(
        template={
            "service_account_name": "{{ service_account_name }}",
            "network": "{{ network }}",
            "reserved_ip_ranges": "{{ reserved_ip_ranges }}",
            "maximum_run_time_hours": "{{ maximum_run_time_hours }}",
            "worker_pool_specs": [
                {
                    "replica_count": 1,
                    "container_spec": {
                        "image_uri": "{{ image }}",
                        "command": "{{ command }}",
                        "args": [],
                    },
                    "machine_spec": {
                        "machine_type": "{{ machine_type }}",
                        "accelerator_type": "{{ accelerator_type }}",
                        "accelerator_count": "{{ accelerator_count }}",
                    },
                    "disk_spec": {
                        "boot_disk_type": "{{ boot_disk_type }}",
                        "boot_disk_size_gb": "{{ boot_disk_size_gb }}",
                    },
                }
            ],
        }
    )
    job_watch_poll_interval: float = Field(
        default=5.0,
        title="Poll Interval (Seconds)",
        description=(
            "The amount of time to wait between GCP API calls while monitoring the "
            "state of a Vertex AI Job."
        ),
    )

    @property
    def project(self) -> str:
        """property for accessing the project from the credentials."""
        return self.credentials.project

    @property
    def job_name(self) -> str:
        """
        The name can be up to 128 characters long and can be consist of any UTF-8 characters. Reference:
        https://cloud.google.com/python/docs/reference/aiplatform/latest/google.cloud.aiplatform.CustomJob#google_cloud_aiplatform_CustomJob_display_name
        """  # noqa
        unique_suffix = uuid4().hex
        job_name = f"{self.name}-{unique_suffix}"
        return job_name

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: Optional["DeploymentResponse"] = None,
        flow: Optional["Flow"] = None,
    ):
        super().prepare_for_flow_run(flow_run, deployment, flow)

        self._inject_formatted_env_vars()
        self._inject_formatted_command()
        self._ensure_existence_of_service_account()

    def _inject_formatted_env_vars(self):
        """Inject environment variables in the Vertex job_spec configuration,
        in the correct format, which is sourced from the BaseJobConfiguration.
        This method is invoked by `prepare_for_flow_run()`."""
        worker_pool_specs = self.job_spec["worker_pool_specs"]
        formatted_env_vars = [
            {"name": key, "value": value} for key, value in self.env.items()
        ]
        worker_pool_specs[0]["container_spec"]["env"] = formatted_env_vars

    def _inject_formatted_command(self):
        """Inject shell commands in the Vertex job_spec configuration,
        in the correct format, which is sourced from the BaseJobConfiguration.
        Here, we'll ensure that the default string format
        is converted to a list of strings."""
        worker_pool_specs = self.job_spec["worker_pool_specs"]

        existing_command = worker_pool_specs[0]["container_spec"].get("command")
        if existing_command is None:
            worker_pool_specs[0]["container_spec"]["command"] = shlex.split(
                self._base_flow_run_command()
            )
        elif isinstance(existing_command, str):
            worker_pool_specs[0]["container_spec"]["command"] = shlex.split(
                existing_command
            )

    def _ensure_existence_of_service_account(self):
        """Verify that a service account was provided, either in the credentials
        or as a standalone service account name override."""

        provided_service_account_name = self.job_spec.get("service_account_name")
        credential_service_account = self.credentials._service_account_email

        service_account_to_use = (
            provided_service_account_name or credential_service_account
        )

        if service_account_to_use is None:
            raise ValueError(
                "A service account is required for the Vertex job. "
                "A service account could not be detected in the attached credentials "
                "or in the service_account_name input. "
                "Please pass in valid GCP credentials or a valid service_account_name"
            )

        self.job_spec["service_account_name"] = service_account_to_use

    @validator("job_spec")
    def _ensure_job_spec_includes_required_attributes(cls, value: Dict[str, Any]):
        """
        Ensures that the job spec includes all required components.
        """
        patch = JsonPatch.from_diff(value, _get_base_job_spec())
        missing_paths = sorted([op["path"] for op in patch if op["op"] == "add"])
        if missing_paths:
            raise ValueError(
                "Job is missing required attributes at the following paths: "
                f"{', '.join(missing_paths)}"
            )
        return value


class VertexAIWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class VertexAIWorker(BaseWorker):
    """Prefect worker that executes flow runs within Vertex AI Jobs."""

    type = "vertex-ai"
    job_configuration = VertexAIWorkerJobConfiguration
    job_configuration_variables = VertexAIWorkerVariables
    _description = (
        "Execute flow runs within containers on Google Vertex AI. Requires "
        "a Google Cloud Platform account."
    )
    _display_name = "Google Vertex AI"
    _documentation_url = "https://prefecthq.github.io/prefect-gcp/vertex_worker/"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png"  # noqa

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: VertexAIWorkerJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ) -> VertexAIWorkerResult:
        """
        Executes a flow run within a Vertex AI Job and waits for the flow run
        to complete.

        Args:
            flow_run: The flow run to execute
            configuration: The configuration to use when executing the flow run.
            task_status: The task status object for the current flow run. If provided,
                the task will be marked as started.

        Returns:
            VertexAIWorkerResult: A result object containing information about the
                final state of the flow run
        """
        logger = self.get_flow_run_logger(flow_run)

        client_options = ClientOptions(
            api_endpoint=f"{configuration.region}-aiplatform.googleapis.com"
        )

        job_name = configuration.job_name

        job_spec = self._build_job_spec(configuration)
        with configuration.credentials.get_job_service_client(
            client_options=client_options
        ) as job_service_client:
            job_run = await self._create_and_begin_job(
                job_name, job_spec, job_service_client, configuration, logger
            )

            if task_status:
                task_status.started(job_run.name)

            final_job_run = await self._watch_job_run(
                job_name=job_name,
                full_job_name=job_run.name,
                job_service_client=job_service_client,
                current_state=job_run.state,
                until_states=(
                    JobState.JOB_STATE_SUCCEEDED,
                    JobState.JOB_STATE_FAILED,
                    JobState.JOB_STATE_CANCELLED,
                    JobState.JOB_STATE_EXPIRED,
                ),
                configuration=configuration,
                logger=logger,
                timeout=int(
                    datetime.timedelta(
                        hours=configuration.job_spec["maximum_run_time_hours"]
                    ).total_seconds()
                ),
            )

        error_msg = final_job_run.error.message

        # Vertex will include an error message upon valid
        # flow cancellations, so we'll avoid raising an error in that case
        if error_msg and "CANCELED" not in error_msg:
            raise RuntimeError(error_msg)

        status_code = 0 if final_job_run.state == JobState.JOB_STATE_SUCCEEDED else 1

        return VertexAIWorkerResult(
            identifier=final_job_run.display_name, status_code=status_code
        )

    def _build_job_spec(
        self, configuration: VertexAIWorkerJobConfiguration
    ) -> "CustomJobSpec":
        """
        Builds a job spec by gathering details.
        """
        # here, we extract the `worker_pool_specs` out of the job_spec
        worker_pool_specs = [
            WorkerPoolSpec(
                container_spec=ContainerSpec(**spec["container_spec"]),
                machine_spec=MachineSpec(**spec["machine_spec"]),
                replica_count=spec["replica_count"],
                disk_spec=DiskSpec(**spec["disk_spec"]),
            )
            for spec in configuration.job_spec.pop("worker_pool_specs", [])
        ]

        timeout = Duration().FromTimedelta(
            td=datetime.timedelta(
                hours=configuration.job_spec["maximum_run_time_hours"]
            )
        )
        scheduling = Scheduling(timeout=timeout)

        # construct the final job spec that we will provide to Vertex AI
        job_spec = CustomJobSpec(
            worker_pool_specs=worker_pool_specs,
            scheduling=scheduling,
            ignore_unknown_fields=True,
            **configuration.job_spec,
        )
        return job_spec

    async def _create_and_begin_job(
        self,
        job_name: str,
        job_spec: "CustomJobSpec",
        job_service_client: "JobServiceClient",
        configuration: VertexAIWorkerJobConfiguration,
        logger: PrefectLogAdapter,
    ) -> "CustomJob":
        """
        Builds a custom job and begins running it.
        """
        # create custom job
        custom_job = CustomJob(
            display_name=job_name,
            job_spec=job_spec,
            labels=self._get_compatible_labels(configuration=configuration),
        )

        # run job
        logger.info(f"Job {job_name!r} starting to run ")

        project = configuration.project
        resource_name = f"projects/{project}/locations/{configuration.region}"

        retry_policy = retry(
            stop=stop_after_attempt(3), wait=wait_fixed(1) + wait_random(0, 3)
        )

        custom_job_run = await run_sync_in_worker_thread(
            retry_policy(job_service_client.create_custom_job),
            parent=resource_name,
            custom_job=custom_job,
        )

        logger.info(
            f"Job {job_name!r} has successfully started; "
            f"the full job name is {custom_job_run.name!r}"
        )

        return custom_job_run

    async def _watch_job_run(
        self,
        job_name: str,
        full_job_name: str,  # different from job_name
        job_service_client: "JobServiceClient",
        current_state: "JobState",
        until_states: Tuple["JobState"],
        configuration: VertexAIWorkerJobConfiguration,
        logger: PrefectLogAdapter,
        timeout: int = None,
    ) -> "CustomJob":
        """
        Polls job run to see if status changed.
        """
        state = JobState.JOB_STATE_UNSPECIFIED
        last_state = current_state
        t0 = time.time()

        while state not in until_states:
            job_run = await run_sync_in_worker_thread(
                job_service_client.get_custom_job,
                name=full_job_name,
            )
            state = job_run.state
            if state != last_state:
                state_label = (
                    state.name.replace("_", " ")
                    .lower()
                    .replace("state", "state is now:")
                )
                # results in "New job state is now: succeeded"
                logger.info(f"{job_name} has new {state_label}")
                last_state = state
            else:
                # Intermittently, the job will not be described. We want to respect the
                # watch timeout though.
                logger.debug(f"Job {job_name} not found.")

            elapsed_time = time.time() - t0
            if timeout is not None and elapsed_time > timeout:
                raise RuntimeError(
                    f"Timed out after {elapsed_time}s while watching job for states "
                    "{until_states!r}"
                )
            time.sleep(configuration.job_watch_poll_interval)

        return job_run

    def _get_compatible_labels(
        self, configuration: VertexAIWorkerJobConfiguration
    ) -> Dict[str, str]:
        """
        Ensures labels are compatible with GCP label requirements.
        https://cloud.google.com/resource-manager/docs/creating-managing-labels

        Ex: the Prefect provided key of prefect.io/flow-name -> prefect-io_flow-name
        """
        compatible_labels = {}
        for key, val in configuration.labels.items():
            new_key = slugify(
                key,
                lowercase=True,
                replacements=[("/", "_"), (".", "-")],
                max_length=63,
                regex_pattern=_DISALLOWED_GCP_LABEL_CHARACTERS,
            )
            compatible_labels[new_key] = slugify(
                val,
                lowercase=True,
                replacements=[("/", "_"), (".", "-")],
                max_length=63,
                regex_pattern=_DISALLOWED_GCP_LABEL_CHARACTERS,
            )
        return compatible_labels

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: VertexAIWorkerJobConfiguration,
        grace_seconds: int = 30,
    ):
        """
        Stops a job running in Vertex AI upon flow cancellation,
        based on the provided infrastructure PID + run configuration.
        """
        if grace_seconds != 30:
            self._logger.warning(
                f"Kill grace period of {grace_seconds}s requested, but GCP does not "
                "support dynamic grace period configuration. See here for more info: "
                "https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.customJobs/cancel"  # noqa
            )

        client_options = ClientOptions(
            api_endpoint=f"{configuration.region}-aiplatform.googleapis.com"
        )
        with configuration.credentials.get_job_service_client(
            client_options=client_options
        ) as job_service_client:
            await run_sync_in_worker_thread(
                self._stop_job,
                client=job_service_client,
                vertex_job_name=infrastructure_pid,
            )

    def _stop_job(self, client: "JobServiceClient", vertex_job_name: str):
        """
        Calls the `cancel_custom_job` method on the Vertex AI Job Service Client.
        """
        cancel_custom_job_request = CancelCustomJobRequest(name=vertex_job_name)
        try:
            client.cancel_custom_job(
                request=cancel_custom_job_request,
            )
        except Exception as exc:
            if "does not exist" in str(exc):
                raise InfrastructureNotFound(
                    f"Cannot stop Vertex AI job; the job name {vertex_job_name!r} "
                    "could not be found."
                ) from exc
            raise
