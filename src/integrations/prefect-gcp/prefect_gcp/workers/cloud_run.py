""" <!-- # noqa -->

Module containing the Cloud Run worker used for executing flow runs as Cloud Run jobs.

Get started by creating a Cloud Run work pool:

```bash
prefect work-pool create 'my-cloud-run-pool' --type cloud-run
```

Then start a Cloud Run worker with the following command:

```bash
prefect worker start --pool 'my-cloud-run-pool'
```

## Configuration
Read more about configuring work pools
[here](https://docs.prefect.io/latest/concepts/work-pools/#work-pool-overview).

## Advanced Configuration
!!! example "Using a custom Cloud Run job template"
    Below is the default job body template used by the Cloud Run Worker:
    ```json
    {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata":
            {
                "name": "{{ name }}",
                "annotations":
                {
                    "run.googleapis.com/launch-stage": "BETA",
                }
            },
            "spec":
            {
                "template":
                {
                    "spec":
                    {
                        "template":
                        {
                            "spec":
                            {
                                "containers":
                                [
                                    {
                                        "image": "{{ image }}",
                                        "args": "{{ args }}",
                                        "resources":
                                        {
                                            "limits":
                                            {
                                                "cpu": "{{ cpu }}",
                                                "memory": "{{ memory }}"
                                            },
                                            "requests":
                                            {
                                                "cpu": "{{ cpu }}",
                                                "memory": "{{ memory }}"
                                            }
                                        }
                                    }
                                ],
                                "timeoutSeconds": "{{ timeout }}",
                                "serviceAccountName": "{{ service_account_name }}"
                            }
                        }
                    }
                    }
                },
                "metadata":
                {
                    "annotations":
                    {
                        "run.googleapis.com/vpc-access-connector": "{{ vpc_connector_name }}"
                    }
                }
            },
        },
        "timeout": "{{ timeout }}",
        "keep_job": "{{ keep_job }}"
    }
    ```
    Each values enclosed in `{{ }}` is a placeholder that will be replaced with
    a value at runtime on a per-deployment basis. The values that can be used a
    placeholders are defined by the `variables` schema defined in the base job template.

    The default job body template and available variables can be customized on a work pool
    by work pool basis. By editing the default job body template you can:

    - Add additional placeholders to the default job template
    - Remove placeholders from the default job template
    - Pass values to Cloud Run that are not defined in the `variables` schema

    ### Adding additional placeholders
    For example, to allow for extra customization of a new annotation not described in
    the default job template, you can add the following:
    ```json
    {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata":
        {
            "name": "{{ name }}",
            "annotations":
            {
                "run.googleapis.com/my-custom-annotation": "{{ my_custom_annotation }}",
                "run.googleapis.com/launch-stage": "BETA",
            },
          ...
        },
      ...
    }
    ```
    `my_custom_annotation` can now be used as a placeholder in the job template and set
    on a per-deployment basis.

    ```yaml
    # deployment.yaml
    ...
    infra_overrides: {"my_custom_annotation": "my-custom-value"}
    ```

    Additionally, fields can be set to prevent configuration at the deployment
    level. For example to configure the `vpc_connector_name` field, the placeholder can
    be removed and replaced with an actual value. Now all deployments that point to this
    work pool will use the same `vpc_connector_name` value.

    ```json
    {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "spec":
        {
            "template":
            {
                "metadata":
                {
                    "annotations":
                    {
                        "run.googleapis.com/vpc-access-connector": "my-vpc-connector"
                    }
                },
                ...
            },
            ...
        }
    }
    ```
"""

import re
import shlex
import time
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import uuid4

import anyio
import googleapiclient
from anyio.abc import TaskStatus  # noqa
from google.api_core.client_options import ClientOptions
from googleapiclient import discovery
from googleapiclient.discovery import Resource
from pydantic import VERSION as PYDANTIC_VERSION

from prefect.exceptions import InfrastructureNotFound
from prefect.logging.loggers import PrefectLogAdapter
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.dockerutils import get_prefect_image_name
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

from prefect_gcp.cloud_run import Execution, Job
from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.utilities import slugify_name

if TYPE_CHECKING:
    from prefect.client.schemas import FlowRun
    from prefect.server.schemas.core import Flow
    from prefect.server.schemas.responses import DeploymentResponse


def _get_default_job_body_template() -> Dict[str, Any]:
    """Returns the default job body template used by the Cloud Run Job."""
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {
            "name": "{{ name }}",
            "annotations": {
                # See: https://cloud.google.com/run/docs/troubleshooting#launch-stage-validation  # noqa
                "run.googleapis.com/launch-stage": "BETA",
            },
        },
        "spec": {  # JobSpec
            "template": {  # ExecutionTemplateSpec
                "spec": {  # ExecutionSpec
                    "template": {  # TaskTemplateSpec
                        "spec": {  # TaskSpec
                            "containers": [
                                {
                                    "image": "{{ image }}",
                                    "command": "{{ command }}",
                                    "resources": {
                                        "limits": {
                                            "cpu": "{{ cpu }}",
                                            "memory": "{{ memory }}",
                                        },
                                        "requests": {
                                            "cpu": "{{ cpu }}",
                                            "memory": "{{ memory }}",
                                        },
                                    },
                                }
                            ],
                            "timeoutSeconds": "{{ timeout }}",
                            "serviceAccountName": "{{ service_account_name }}",
                        }
                    },
                },
                "metadata": {
                    "annotations": {
                        "run.googleapis.com/vpc-access-connector": "{{ vpc_connector_name }}"  # noqa
                    }
                },
            },
        },
    }


def _get_base_job_body() -> Dict[str, Any]:
    """Returns a base job body to use for job body validation."""
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {
            "annotations": {
                # See: https://cloud.google.com/run/docs/troubleshooting#launch-stage-validation  # noqa
                "run.googleapis.com/launch-stage": "BETA",
            },
        },
        "spec": {  # JobSpec
            "template": {  # ExecutionTemplateSpec
                "spec": {  # ExecutionSpec
                    "template": {  # TaskTemplateSpec
                        "spec": {"containers": [{}]},  # TaskSpec
                    },
                },
            },
        },
    }


class CloudRunWorkerJobConfiguration(BaseJobConfiguration):
    """
    Configuration class used by the Cloud Run Worker to create a Cloud Run Job.

    An instance of this class is passed to the Cloud Run worker's `run` method
    for each flow run. It contains all information necessary to execute
    the flow run as a Cloud Run Job.

    Attributes:
        region: The region where the Cloud Run Job resides.
        credentials: The GCP Credentials used to connect to Cloud Run.
        job_body: The job body used to create the Cloud Run Job.
        timeout: The length of time that Prefect will wait for a Cloud Run Job.
        keep_job: Whether to delete the Cloud Run Job after it completes.
    """

    region: str = Field(
        default="us-central1", description="The region where the Cloud Run Job resides."
    )
    credentials: Optional[GcpCredentials] = Field(
        title="GCP Credentials",
        default_factory=GcpCredentials,
        description="The GCP Credentials used to connect to Cloud Run. "
        "If not provided credentials will be inferred from "
        "the local environment.",
    )
    job_body: Dict[str, Any] = Field(template=_get_default_job_body_template())
    timeout: Optional[int] = Field(
        default=600,
        gt=0,
        le=3600,
        title="Job Timeout",
        description=(
            "The length of time that Prefect will wait for a Cloud Run Job to complete "
            "before raising an exception."
        ),
    )
    keep_job: Optional[bool] = Field(
        default=False,
        title="Keep Job After Completion",
        description="Keep the completed Cloud Run Job on Google Cloud Platform.",
    )

    @property
    def project(self) -> str:
        """property for accessing the project from the credentials."""
        return self.credentials.project

    @property
    def job_name(self) -> str:
        """property for accessing the name from the job metadata."""
        return self.job_body["metadata"]["name"]

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: Optional["DeploymentResponse"] = None,
        flow: Optional["Flow"] = None,
    ):
        """
        Prepares the job configuration for a flow run.

        Ensures that necessary values are present in the job body and that the
        job body is valid.

        Args:
            flow_run: The flow run to prepare the job configuration for
            deployment: The deployment associated with the flow run used for
                preparation.
            flow: The flow associated with the flow run used for preparation.
        """
        super().prepare_for_flow_run(flow_run, deployment, flow)

        self._populate_envs()
        self._populate_or_format_command()
        self._format_args_if_present()
        self._populate_image_if_not_present()
        self._populate_name_if_not_present()

    def _populate_envs(self):
        """Populate environment variables. BaseWorker.prepare_for_flow_run handles
        putting the environment variables in the `env` attribute. This method
        moves them into the jobs body"""
        envs = [{"name": k, "value": v} for k, v in self.env.items()]
        self.job_body["spec"]["template"]["spec"]["template"]["spec"]["containers"][0][
            "env"
        ] = envs

    def _populate_name_if_not_present(self):
        """Adds the flow run name to the job if one is not already provided."""
        try:
            if "name" not in self.job_body["metadata"]:
                base_job_name = slugify_name(self.name)
                job_name = f"{base_job_name}-{uuid4().hex}"
                self.job_body["metadata"]["name"] = job_name
        except KeyError:
            raise ValueError("Unable to verify name due to invalid job body template.")

    def _populate_image_if_not_present(self):
        """Adds the latest prefect image to the job if one is not already provided."""
        try:
            if (
                "image"
                not in self.job_body["spec"]["template"]["spec"]["template"]["spec"][
                    "containers"
                ][0]
            ):
                self.job_body["spec"]["template"]["spec"]["template"]["spec"][
                    "containers"
                ][0]["image"] = f"docker.io/{get_prefect_image_name()}"
        except KeyError:
            raise ValueError("Unable to verify image due to invalid job body template.")

    def _populate_or_format_command(self):
        """
        Ensures that the command is present in the job manifest. Populates the command
        with the `prefect -m prefect.engine` if a command is not present.
        """
        try:
            command = self.job_body["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0].get("command")
            if command is None:
                self.job_body["spec"]["template"]["spec"]["template"]["spec"][
                    "containers"
                ][0]["command"] = shlex.split(self._base_flow_run_command())
            elif isinstance(command, str):
                self.job_body["spec"]["template"]["spec"]["template"]["spec"][
                    "containers"
                ][0]["command"] = shlex.split(command)
        except KeyError:
            raise ValueError(
                "Unable to verify command due to invalid job body template."
            )

    def _format_args_if_present(self):
        try:
            args = self.job_body["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0].get("args")
            if args is not None and isinstance(args, str):
                self.job_body["spec"]["template"]["spec"]["template"]["spec"][
                    "containers"
                ][0]["args"] = shlex.split(args)
        except KeyError:
            raise ValueError("Unable to verify args due to invalid job body template.")

    @validator("job_body")
    def _ensure_job_includes_all_required_components(cls, value: Dict[str, Any]):
        """
        Ensures that the job body includes all required components.
        """
        patch = JsonPatch.from_diff(value, _get_base_job_body())
        missing_paths = sorted([op["path"] for op in patch if op["op"] == "add"])
        if missing_paths:
            raise ValueError(
                "Job is missing required attributes at the following paths: "
                f"{', '.join(missing_paths)}"
            )
        return value

    @validator("job_body")
    def _ensure_job_has_compatible_values(cls, value: Dict[str, Any]):
        """Ensure that the job body has compatible values."""
        patch = JsonPatch.from_diff(value, _get_base_job_body())
        incompatible = sorted(
            [
                f"{op['path']} must have value {op['value']!r}"
                for op in patch
                if op["op"] == "replace"
            ]
        )
        if incompatible:
            raise ValueError(
                "Job has incompatible values for the following attributes: "
                f"{', '.join(incompatible)}"
            )
        return value


class CloudRunWorkerVariables(BaseVariables):
    """
    Default variables for the Cloud Run worker.

    The schema for this class is used to populate the `variables` section of the default
    base job template.
    """

    region: str = Field(
        default="us-central1",
        description="The region where the Cloud Run Job resides.",
        example="us-central1",
    )
    credentials: Optional[GcpCredentials] = Field(
        title="GCP Credentials",
        default_factory=GcpCredentials,
        description="The GCP Credentials used to initiate the "
        "Cloud Run Job. If not provided credentials will be "
        "inferred from the local environment.",
    )
    image: Optional[str] = Field(
        default=None,
        title="Image Name",
        description=(
            "The image to use for a new Cloud Run Job. "
            "If not set, the latest Prefect image will be used. "
            "See https://cloud.google.com/run/docs/deploying#images."
        ),
        example="docker.io/prefecthq/prefect:2-latest",
    )
    cpu: Optional[str] = Field(
        default=None,
        title="CPU",
        description=(
            "The amount of compute allocated to the Cloud Run Job. "
            "(1000m = 1 CPU). See "
            "https://cloud.google.com/run/docs/configuring/cpu#setting-jobs."
        ),
        example="1000m",
        regex=r"^(\d*000)m$",
    )
    memory: Optional[str] = Field(
        default=None,
        title="Memory",
        description=(
            "The amount of memory allocated to the Cloud Run Job. "
            "Must be specified in units of 'G', 'Gi', 'M', or 'Mi'. "
            "See https://cloud.google.com/run/docs/configuring/memory-limits#setting."
        ),
        example="512Mi",
        regex=r"^\d+(?:G|Gi|M|Mi)$",
    )
    vpc_connector_name: Optional[str] = Field(
        default=None,
        title="VPC Connector Name",
        description="The name of the VPC connector to use for the Cloud Run Job.",
    )
    service_account_name: Optional[str] = Field(
        default=None,
        title="Service Account Name",
        description="The name of the service account to use for the task execution "
        "of Cloud Run Job. By default Cloud Run jobs run as the default "
        "Compute Engine Service Account. ",
        example="service-account@example.iam.gserviceaccount.com",
    )
    keep_job: Optional[bool] = Field(
        default=False,
        title="Keep Job After Completion",
        description="Keep the completed Cloud Run Job after it has run.",
    )
    timeout: Optional[int] = Field(
        default=600,
        gt=0,
        le=3600,
        title="Job Timeout",
        description=(
            "The length of time that Prefect will wait for Cloud Run Job state changes."
        ),
    )


class CloudRunWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class CloudRunWorker(BaseWorker):
    """Prefect worker that executes flow runs within Cloud Run Jobs."""

    type = "cloud-run"
    job_configuration = CloudRunWorkerJobConfiguration
    job_configuration_variables = CloudRunWorkerVariables
    _description = (
        "Execute flow runs within containers on Google Cloud Run. Requires "
        "a Google Cloud Platform account."
    )
    _display_name = "Google Cloud Run"
    _documentation_url = "https://prefecthq.github.io/prefect-gcp/cloud_run_worker/"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png"  # noqa

    def _create_job_error(self, exc, configuration):
        """Provides a nicer error for 404s when trying to create a Cloud Run Job."""
        # TODO consider lookup table instead of the if/else,
        # also check for documented errors
        if exc.status_code == 404:
            raise RuntimeError(
                f"Failed to find resources at {exc.uri}. Confirm that region"
                f" '{self.region}' is the correct region for your Cloud Run Job and"
                f" that {configuration.project} is the correct GCP project. If"
                f" your project ID is not correct, you are using a Credentials block"
                f" with permissions for the wrong project."
            ) from exc
        raise exc

    def _job_run_submission_error(self, exc, configuration):
        """Provides a nicer error for 404s when submitting job runs."""
        if exc.status_code == 404:
            pat1 = r"The requested URL [^ ]+ was not found on this server"
            # pat2 = (
            #     r"Resource '[^ ]+' of kind 'JOB' in region '[\w\-0-9]+' "
            #     r"in project '[\w\-0-9]+' does not exist"
            # )
            if re.findall(pat1, str(exc)):
                raise RuntimeError(
                    f"Failed to find resources at {exc.uri}. "
                    f"Confirm that region '{self.region}' is "
                    f"the correct region for your Cloud Run Job "
                    f"and that '{configuration.project}' is the "
                    f"correct GCP project. If your project ID is not "
                    f"correct, you are using a Credentials "
                    f"block with permissions for the wrong project."
                ) from exc
            else:
                raise exc

        raise exc

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: CloudRunWorkerJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ) -> CloudRunWorkerResult:
        """
        Executes a flow run within a Cloud Run Job and waits for the flow run
        to complete.

        Args:
            flow_run: The flow run to execute
            configuration: The configuration to use when executing the flow run.
            task_status: The task status object for the current flow run. If provided,
                the task will be marked as started.

        Returns:
            CloudRunWorkerResult: A result object containing information about the
                final state of the flow run
        """

        logger = self.get_flow_run_logger(flow_run)

        with self._get_client(configuration) as client:
            await run_sync_in_worker_thread(
                self._create_job_and_wait_for_registration,
                configuration,
                client,
                logger,
            )
            job_execution = await run_sync_in_worker_thread(
                self._begin_job_execution, configuration, client, logger
            )

            if task_status:
                task_status.started(configuration.job_name)

            result = await run_sync_in_worker_thread(
                self._watch_job_execution_and_get_result,
                configuration,
                client,
                job_execution,
                logger,
            )
            return result

    def _get_client(self, configuration: CloudRunWorkerJobConfiguration) -> Resource:
        """Get the base client needed for interacting with GCP APIs."""
        # region needed for 'v1' API
        api_endpoint = f"https://{configuration.region}-run.googleapis.com"
        gcp_creds = configuration.credentials.get_credentials_from_service_account()
        options = ClientOptions(api_endpoint=api_endpoint)

        return discovery.build(
            "run", "v1", client_options=options, credentials=gcp_creds
        ).namespaces()

    def _create_job_and_wait_for_registration(
        self,
        configuration: CloudRunWorkerJobConfiguration,
        client: Resource,
        logger: PrefectLogAdapter,
    ) -> None:
        """Create a new job wait for it to finish registering."""
        try:
            logger.info(f"Creating Cloud Run Job {configuration.job_name}")

            Job.create(
                client=client,
                namespace=configuration.credentials.project,
                body=configuration.job_body,
            )
        except googleapiclient.errors.HttpError as exc:
            self._create_job_error(exc, configuration)

        try:
            self._wait_for_job_creation(
                client=client, configuration=configuration, logger=logger
            )
        except Exception:
            logger.exception(
                "Encountered an exception while waiting for job run creation"
            )
            if not configuration.keep_job:
                logger.info(
                    f"Deleting Cloud Run Job {configuration.job_name} from "
                    "Google Cloud Run."
                )
                try:
                    Job.delete(
                        client=client,
                        namespace=configuration.credentials.project,
                        job_name=configuration.job_name,
                    )
                except Exception:
                    logger.exception(
                        "Received an unexpected exception while attempting to delete"
                        f" Cloud Run Job {configuration.job_name!r}"
                    )
            raise

    def _begin_job_execution(
        self,
        configuration: CloudRunWorkerJobConfiguration,
        client: Resource,
        logger: PrefectLogAdapter,
    ) -> Execution:
        """Submit a job run for execution and return the execution object."""
        try:
            logger.info(
                f"Submitting Cloud Run Job {configuration.job_name!r} for execution."
            )
            submission = Job.run(
                client=client,
                namespace=configuration.project,
                job_name=configuration.job_name,
            )

            job_execution = Execution.get(
                client=client,
                namespace=submission["metadata"]["namespace"],
                execution_name=submission["metadata"]["name"],
            )
        except Exception as exc:
            self._job_run_submission_error(exc, configuration)

        return job_execution

    def _watch_job_execution_and_get_result(
        self,
        configuration: CloudRunWorkerJobConfiguration,
        client: Resource,
        execution: Execution,
        logger: PrefectLogAdapter,
        poll_interval: int = 5,
    ) -> CloudRunWorkerResult:
        """Wait for execution to complete and then return result."""
        try:
            job_execution = self._watch_job_execution(
                client=client,
                job_execution=execution,
                timeout=configuration.timeout,
                poll_interval=poll_interval,
            )
        except Exception:
            logger.exception(
                "Received an unexpected exception while monitoring Cloud Run Job "
                f"{configuration.job_name!r}"
            )
            raise

        if job_execution.succeeded():
            status_code = 0
            logger.info(f"Job Run {configuration.job_name} completed successfully")
        else:
            status_code = 1
            error_msg = job_execution.condition_after_completion()["message"]
            logger.error(
                "Job Run {configuration.job_name} did not complete successfully. "
                f"{error_msg}"
            )

        logger.info(f"Job Run logs can be found on GCP at: {job_execution.log_uri}")

        if not configuration.keep_job:
            logger.info(
                f"Deleting completed Cloud Run Job {configuration.job_name!r} "
                "from Google Cloud Run..."
            )
            try:
                Job.delete(
                    client=client,
                    namespace=configuration.project,
                    job_name=configuration.job_name,
                )
            except Exception:
                logger.exception(
                    "Received an unexpected exception while attempting to delete Cloud"
                    f" Run Job {configuration.job_name}"
                )

        return CloudRunWorkerResult(
            identifier=configuration.job_name, status_code=status_code
        )

    def _watch_job_execution(
        self, client, job_execution: Execution, timeout: int, poll_interval: int = 5
    ):
        """
        Update job_execution status until it is no longer running or timeout is reached.
        """
        t0 = time.time()
        while job_execution.is_running():
            job_execution = Execution.get(
                client=client,
                namespace=job_execution.namespace,
                execution_name=job_execution.name,
            )

            elapsed_time = time.time() - t0
            if timeout is not None and elapsed_time > timeout:
                raise RuntimeError(
                    f"Timed out after {elapsed_time}s while waiting for Cloud Run Job "
                    "execution to complete. Your job may still be running on GCP."
                )

            time.sleep(poll_interval)

        return job_execution

    def _wait_for_job_creation(
        self,
        client: Resource,
        configuration: CloudRunWorkerJobConfiguration,
        logger: PrefectLogAdapter,
        poll_interval: int = 5,
    ):
        """Give created job time to register."""
        job = Job.get(
            client=client,
            namespace=configuration.project,
            job_name=configuration.job_name,
        )

        t0 = time.time()
        while not job.is_ready():
            ready_condition = (
                job.ready_condition
                if job.ready_condition
                else "waiting for condition update"
            )
            logger.info(f"Job is not yet ready... Current condition: {ready_condition}")
            job = Job.get(
                client=client,
                namespace=configuration.project,
                job_name=configuration.job_name,
            )

            elapsed_time = time.time() - t0
            if (
                configuration.timeout is not None
                and elapsed_time > configuration.timeout
            ):
                raise RuntimeError(
                    f"Timed out after {elapsed_time}s while waiting for Cloud Run Job "
                    "execution to complete. Your job may still be running on GCP."
                )

            time.sleep(poll_interval)

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: CloudRunWorkerJobConfiguration,
        grace_seconds: int = 30,
    ):
        """
        Stops a job for a cancelled flow run based on the provided infrastructure PID
        and run configuration.
        """
        if grace_seconds != 30:
            self._logger.warning(
                f"Kill grace period of {grace_seconds}s requested, but GCP does not "
                "support dynamic grace period configuration. See here for more info: "
                "https://cloud.google.com/run/docs/reference/rest/v1/namespaces.jobs/delete"  # noqa
            )

        with self._get_client(configuration) as client:
            await run_sync_in_worker_thread(
                self._stop_job,
                client=client,
                namespace=configuration.project,
                job_name=infrastructure_pid,
            )

    def _stop_job(self, client: Resource, namespace: str, job_name: str):
        try:
            Job.delete(client=client, namespace=namespace, job_name=job_name)
        except Exception as exc:
            if "does not exist" in str(exc):
                raise InfrastructureNotFound(
                    f"Cannot stop Cloud Run Job; the job name {job_name!r} "
                    "could not be found."
                ) from exc
            raise
