"""
DEPRECATION WARNING:

This module is deprecated as of March 2024 and will not be available after September 2024.
It has been replaced by the Cloud Run and Cloud Run V2 workers, which offer enhanced functionality and better performance.

For upgrade instructions, see https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.

Integrations with Google Cloud Run Job.

Examples:

    Run a job using Google Cloud Run Jobs:
    ```python
    CloudRunJob(
        image="gcr.io/my-project/my-image",
        region="us-east1",
        credentials=my_gcp_credentials
    ).run()
    ```

    Run a job that runs the command `echo hello world` using Google Cloud Run Jobs:
    ```python
    CloudRunJob(
        image="gcr.io/my-project/my-image",
        region="us-east1",
        credentials=my_gcp_credentials
        command=["echo", "hello world"]
    ).run()
    ```

"""  # noqa

from __future__ import annotations

import json
import re
import shlex
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

import googleapiclient
from anyio.abc import TaskStatus
from google.api_core.client_options import ClientOptions
from googleapiclient import discovery
from googleapiclient.discovery import Resource
from pydantic import VERSION as PYDANTIC_VERSION

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect.exceptions import InfrastructureNotFound
from prefect.infrastructure.base import Infrastructure, InfrastructureResult
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import BaseModel, Field, root_validator, validator
else:
    from pydantic import BaseModel, Field, root_validator, validator

from typing_extensions import Literal

from prefect.blocks.core import BlockNotSavedError
from prefect.workers.utilities import (
    get_default_base_job_template_for_infrastructure_type,
)
from prefect_gcp.credentials import GcpCredentials


class Job(BaseModel):
    """
    Utility class to call GCP `jobs` API and
    interact with the returned objects.
    """

    metadata: dict
    spec: dict
    status: dict
    name: str
    ready_condition: dict
    execution_status: dict

    def _is_missing_container(self):
        """
        Check if Job status is not ready because
        the specified container cannot be found.
        """
        if (
            self.ready_condition.get("status") == "False"
            and self.ready_condition.get("reason") == "ContainerMissing"
        ):
            return True
        return False

    def is_ready(self) -> bool:
        """Whether a job is finished registering and ready to be executed"""
        if self._is_missing_container():
            raise Exception(f"{self.ready_condition['message']}")
        return self.ready_condition.get("status") == "True"

    def has_execution_in_progress(self) -> bool:
        """See if job has a run in progress."""
        return (
            self.execution_status == {}
            or self.execution_status.get("completionTimestamp") is None
        )

    @staticmethod
    def _get_ready_condition(job: dict) -> dict:
        """Utility to access JSON field containing ready condition."""
        if job["status"].get("conditions"):
            for condition in job["status"]["conditions"]:
                if condition["type"] == "Ready":
                    return condition

        return {}

    @staticmethod
    def _get_execution_status(job: dict):
        """Utility to access JSON field containing execution status."""
        if job["status"].get("latestCreatedExecution"):
            return job["status"]["latestCreatedExecution"]

        return {}

    @classmethod
    def get(cls, client: Resource, namespace: str, job_name: str):
        """Make a get request to the GCP jobs API and return a Job instance."""
        request = client.jobs().get(name=f"namespaces/{namespace}/jobs/{job_name}")
        response = request.execute()

        return cls(
            metadata=response["metadata"],
            spec=response["spec"],
            status=response["status"],
            name=response["metadata"]["name"],
            ready_condition=cls._get_ready_condition(response),
            execution_status=cls._get_execution_status(response),
        )

    @staticmethod
    def create(client: Resource, namespace: str, body: dict):
        """Make a create request to the GCP jobs API."""
        request = client.jobs().create(parent=f"namespaces/{namespace}", body=body)
        response = request.execute()
        return response

    @staticmethod
    def delete(client: Resource, namespace: str, job_name: str):
        """Make a delete request to the GCP jobs API."""
        request = client.jobs().delete(name=f"namespaces/{namespace}/jobs/{job_name}")
        response = request.execute()
        return response

    @staticmethod
    def run(client: Resource, namespace: str, job_name: str):
        """Make a run request to the GCP jobs API."""
        request = client.jobs().run(name=f"namespaces/{namespace}/jobs/{job_name}")
        response = request.execute()
        return response


class Execution(BaseModel):
    """
    Utility class to call GCP `executions` API and
    interact with the returned objects.
    """

    name: str
    namespace: str
    metadata: dict
    spec: dict
    status: dict
    log_uri: str

    def is_running(self) -> bool:
        """Returns True if Execution is not completed."""
        return self.status.get("completionTime") is None

    def condition_after_completion(self):
        """Returns Execution condition if Execution has completed."""
        for condition in self.status["conditions"]:
            if condition["type"] == "Completed":
                return condition

    def succeeded(self):
        """Whether or not the Execution completed is a successful state."""
        completed_condition = self.condition_after_completion()
        if completed_condition and completed_condition["status"] == "True":
            return True

        return False

    @classmethod
    def get(cls, client: Resource, namespace: str, execution_name: str):
        """
        Make a get request to the GCP executions API
        and return an Execution instance.
        """
        request = client.executions().get(
            name=f"namespaces/{namespace}/executions/{execution_name}"
        )
        response = request.execute()

        return cls(
            name=response["metadata"]["name"],
            namespace=response["metadata"]["namespace"],
            metadata=response["metadata"],
            spec=response["spec"],
            status=response["status"],
            log_uri=response["status"]["logUri"],
        )


class CloudRunJobResult(InfrastructureResult):
    """Result from a Cloud Run Job."""


@deprecated_class(
    start_date="Mar 2024",
    help=(
        "Use the Cloud Run or Cloud Run v2 worker instead."
        " Refer to the upgrade guide for more information:"
        " https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/."
    ),
)
class CloudRunJob(Infrastructure):
    """
    <span class="badge-api experimental"/>

    Infrastructure block used to run GCP Cloud Run Jobs.

    Project name information is provided by the Credentials object, and should always
    be correct as long as the Credentials object is for the correct project.

    Note this block is experimental. The interface may change without notice.
    """

    _block_type_slug = "cloud-run-job"
    _block_type_name = "GCP Cloud Run Job"
    _description = "Infrastructure block used to run GCP Cloud Run Jobs. Note this block is experimental. The interface may change without notice."  # noqa
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-gcp/cloud_run/#prefect_gcp.cloud_run.CloudRunJob"  # noqa: E501

    type: Literal["cloud-run-job"] = Field(
        "cloud-run-job", description="The slug for this task type."
    )
    image: str = Field(
        ...,
        title="Image Name",
        description=(
            "The image to use for a new Cloud Run Job. This value must "
            "refer to an image within either Google Container Registry "
            "or Google Artifact Registry, like `gcr.io/<project_name>/<repo>/`."
        ),
    )
    region: str = Field(..., description="The region where the Cloud Run Job resides.")
    credentials: GcpCredentials  # cannot be Field; else it shows as Json

    # Job settings
    cpu: Optional[int] = Field(
        default=None,
        title="CPU",
        description=(
            "The amount of compute allocated to the Cloud Run Job. "
            "The int must be valid based on the rules specified at "
            "https://cloud.google.com/run/docs/configuring/cpu#setting-jobs ."
        ),
    )
    memory: Optional[int] = Field(
        default=None,
        title="Memory",
        description="The amount of memory allocated to the Cloud Run Job.",
    )
    memory_unit: Optional[Literal["G", "Gi", "M", "Mi"]] = Field(
        default=None,
        title="Memory Units",
        description=(
            "The unit of memory. See "
            "https://cloud.google.com/run/docs/configuring/memory-limits#setting "
            "for additional details."
        ),
    )
    vpc_connector_name: Optional[str] = Field(
        default=None,
        title="VPC Connector Name",
        description="The name of the VPC connector to use for the Cloud Run Job.",
    )
    args: Optional[List[str]] = Field(
        default=None,
        description=(
            "Arguments to be passed to your Cloud Run Job's entrypoint command."
        ),
    )
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to be passed to your Cloud Run Job.",
    )

    # Cleanup behavior
    keep_job: Optional[bool] = Field(
        default=False,
        title="Keep Job After Completion",
        description="Keep the completed Cloud Run Job on Google Cloud Platform.",
    )
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
    max_retries: Optional[int] = Field(
        default=3,
        ge=0,
        le=10,
        title="Max Retries",
        description=(
            "The maximum retries setting specifies the number of times a task is "
            "allowed to restart in case of failure before being failed permanently."
        ),
    )
    # For private use
    _job_name: str = None
    _execution: Optional[Execution] = None

    @property
    def job_name(self):
        """Create a unique and valid job name."""

        if self._job_name is None:
            # get `repo` from `gcr.io/<project_name>/repo/other`
            components = self.image.split("/")
            image_name = components[2]
            # only alphanumeric and '-' allowed for a job name
            modified_image_name = image_name.replace(":", "-").replace(".", "-")
            # make 50 char limit for final job name, which will be '<name>-<uuid>'
            if len(modified_image_name) > 17:
                modified_image_name = modified_image_name[:17]
            name = f"{modified_image_name}-{uuid4().hex}"
            self._job_name = name

        return self._job_name

    @property
    def memory_string(self):
        """Returns the string expected for memory resources argument."""
        if self.memory and self.memory_unit:
            return str(self.memory) + self.memory_unit
        return None

    @validator("image")
    def _remove_image_spaces(cls, value):
        """Deal with spaces in image names."""
        if value is not None:
            return value.strip()

    @root_validator
    def _check_valid_memory(cls, values):
        """Make sure memory conforms to expected values for API.
        See: https://cloud.google.com/run/docs/configuring/memory-limits#setting
        """  # noqa
        if (values.get("memory") is not None and values.get("memory_unit") is None) or (
            values.get("memory_unit") is not None and values.get("memory") is None
        ):
            raise ValueError(
                "A memory value and unit must both be supplied to specify a memory"
                " value other than the default memory value."
            )
        return values

    def get_corresponding_worker_type(self) -> str:
        """Return the corresponding worker type for this infrastructure block."""
        return "cloud-run"

    async def generate_work_pool_base_job_template(self) -> dict:
        """
        Generate a base job template for a cloud-run work pool with the same
        configuration as this block.

        Returns:
            - dict: a base job template for a cloud-run work pool
        """
        base_job_template = await get_default_base_job_template_for_infrastructure_type(
            self.get_corresponding_worker_type(),
        )
        assert (
            base_job_template is not None
        ), "Failed to generate default base job template for Cloud Run worker."
        for key, value in self.dict(exclude_unset=True, exclude_defaults=True).items():
            if key == "command":
                base_job_template["variables"]["properties"]["command"][
                    "default"
                ] = shlex.join(value)
            elif key in [
                "type",
                "block_type_slug",
                "_block_document_id",
                "_block_document_name",
                "_is_anonymous",
                "memory_unit",
            ]:
                continue
            elif key == "credentials":
                if not self.credentials._block_document_id:
                    raise BlockNotSavedError(
                        "It looks like you are trying to use a block that"
                        " has not been saved. Please call `.save` on your block"
                        " before publishing it as a work pool."
                    )
                base_job_template["variables"]["properties"]["credentials"][
                    "default"
                ] = {
                    "$ref": {
                        "block_document_id": str(self.credentials._block_document_id)
                    }
                }
            elif key == "memory" and self.memory_string:
                base_job_template["variables"]["properties"]["memory"][
                    "default"
                ] = self.memory_string
            elif key == "cpu" and self.cpu is not None:
                base_job_template["variables"]["properties"]["cpu"][
                    "default"
                ] = f"{self.cpu * 1000}m"
            elif key == "args":
                # Not a default variable, but we can add it to the template
                base_job_template["variables"]["properties"]["args"] = {
                    "title": "Arguments",
                    "type": "string",
                    "description": "Arguments to be passed to your Cloud Run Job's entrypoint command.",  # noqa
                    "default": value,
                }
                base_job_template["job_configuration"]["job_body"]["spec"]["template"][
                    "spec"
                ]["template"]["spec"]["containers"][0]["args"] = "{{ args }}"
            elif key in base_job_template["variables"]["properties"]:
                base_job_template["variables"]["properties"][key]["default"] = value
            else:
                self.logger.warning(
                    f"Variable {key!r} is not supported by Cloud Run work pools."
                    " Skipping."
                )

        return base_job_template

    def _create_job_error(self, exc):
        """Provides a nicer error for 404s when trying to create a Cloud Run Job."""
        # TODO consider lookup table instead of the if/else,
        # also check for documented errors
        if exc.status_code == 404:
            raise RuntimeError(
                f"Failed to find resources at {exc.uri}. Confirm that region"
                f" '{self.region}' is the correct region for your Cloud Run Job and"
                f" that {self.credentials.project} is the correct GCP project. If"
                f" your project ID is not correct, you are using a Credentials block"
                f" with permissions for the wrong project."
            ) from exc
        raise exc

    def _job_run_submission_error(self, exc):
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
                    f"and that '{self.credentials.project}' is the "
                    f"correct GCP project. If your project ID is not "
                    f"correct, you are using a Credentials "
                    f"block with permissions for the wrong project."
                ) from exc
            else:
                raise exc

        raise exc

    def _cpu_as_k8s_quantity(self) -> str:
        """Return the CPU integer in the format expected by GCP Cloud Run Jobs API.
        See: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
        See also: https://cloud.google.com/run/docs/configuring/cpu#setting-jobs
        """  # noqa
        return str(self.cpu * 1000) + "m"

    @sync_compatible
    async def run(self, task_status: Optional[TaskStatus] = None):
        """Run the configured job on a Google Cloud Run Job."""
        with self._get_client() as client:
            await run_sync_in_worker_thread(
                self._create_job_and_wait_for_registration, client
            )
            job_execution = await run_sync_in_worker_thread(
                self._begin_job_execution, client
            )

            if task_status:
                task_status.started(self.job_name)

            result = await run_sync_in_worker_thread(
                self._watch_job_execution_and_get_result,
                client,
                job_execution,
                5,
            )
            return result

    @sync_compatible
    async def kill(self, identifier: str, grace_seconds: int = 30) -> None:
        """
        Kill a task running Cloud Run.

        Args:
            identifier: The Cloud Run Job name. This should match a
                value yielded by CloudRunJob.run.
        """
        if grace_seconds != 30:
            self.logger.warning(
                f"Kill grace period of {grace_seconds}s requested, but GCP does not "
                "support dynamic grace period configuration. See here for more info: "
                "https://cloud.google.com/run/docs/reference/rest/v1/namespaces.jobs/delete"  # noqa
            )

        with self._get_client() as client:
            await run_sync_in_worker_thread(
                self._kill_job,
                client=client,
                namespace=self.credentials.project,
                job_name=identifier,
            )

    def _kill_job(self, client: Resource, namespace: str, job_name: str) -> None:
        """
        Thin wrapper around Job.delete, wrapping a try/except since
        Job is an independent class that doesn't have knowledge of
        CloudRunJob and its associated logic.
        """
        try:
            Job.delete(client=client, namespace=namespace, job_name=job_name)
        except Exception as exc:
            if "does not exist" in str(exc):
                raise InfrastructureNotFound(
                    f"Cannot stop Cloud Run Job; the job name {job_name!r} "
                    "could not be found."
                ) from exc
            raise

    def _create_job_and_wait_for_registration(self, client: Resource) -> None:
        """Create a new job wait for it to finish registering."""
        try:
            self.logger.info(f"Creating Cloud Run Job {self.job_name}")
            Job.create(
                client=client,
                namespace=self.credentials.project,
                body=self._jobs_body(),
            )
        except googleapiclient.errors.HttpError as exc:
            self._create_job_error(exc)

        try:
            self._wait_for_job_creation(client=client, timeout=self.timeout)
        except Exception:
            self.logger.exception(
                "Encountered an exception while waiting for job run creation"
            )
            if not self.keep_job:
                self.logger.info(
                    f"Deleting Cloud Run Job {self.job_name} from Google Cloud Run."
                )
                try:
                    Job.delete(
                        client=client,
                        namespace=self.credentials.project,
                        job_name=self.job_name,
                    )
                except Exception:
                    self.logger.exception(
                        "Received an unexpected exception while attempting to delete"
                        f" Cloud Run Job {self.job_name!r}"
                    )
            raise

    def _begin_job_execution(self, client: Resource) -> Execution:
        """Submit a job run for execution and return the execution object."""
        try:
            self.logger.info(
                f"Submitting Cloud Run Job {self.job_name!r} for execution."
            )
            submission = Job.run(
                client=client,
                namespace=self.credentials.project,
                job_name=self.job_name,
            )

            job_execution = Execution.get(
                client=client,
                namespace=submission["metadata"]["namespace"],
                execution_name=submission["metadata"]["name"],
            )

            command = (
                " ".join(self.command) if self.command else "default container command"
            )

            self.logger.info(
                f"Cloud Run Job {self.job_name!r}: Running command {command!r}"
            )
        except Exception as exc:
            self._job_run_submission_error(exc)

        return job_execution

    def _watch_job_execution_and_get_result(
        self, client: Resource, execution: Execution, poll_interval: int
    ) -> CloudRunJobResult:
        """Wait for execution to complete and then return result."""
        try:
            job_execution = self._watch_job_execution(
                client=client,
                job_execution=execution,
                timeout=self.timeout,
                poll_interval=poll_interval,
            )
        except Exception:
            self.logger.exception(
                "Received an unexpected exception while monitoring Cloud Run Job "
                f"{self.job_name!r}"
            )
            raise

        if job_execution.succeeded():
            status_code = 0
            self.logger.info(f"Job Run {self.job_name} completed successfully")
        else:
            status_code = 1
            error_msg = job_execution.condition_after_completion()["message"]
            self.logger.error(
                f"Job Run {self.job_name} did not complete successfully. {error_msg}"
            )

        self.logger.info(
            f"Job Run logs can be found on GCP at: {job_execution.log_uri}"
        )

        if not self.keep_job:
            self.logger.info(
                f"Deleting completed Cloud Run Job {self.job_name!r} from Google Cloud"
                " Run..."
            )
            try:
                Job.delete(
                    client=client,
                    namespace=self.credentials.project,
                    job_name=self.job_name,
                )
            except Exception:
                self.logger.exception(
                    "Received an unexpected exception while attempting to delete Cloud"
                    f" Run Job {self.job_name}"
                )

        return CloudRunJobResult(identifier=self.job_name, status_code=status_code)

    def _jobs_body(self) -> dict:
        """Create properly formatted body used for a Job CREATE request.
        See: https://cloud.google.com/run/docs/reference/rest/v1/namespaces.jobs
        """
        jobs_metadata = {"name": self.job_name}

        annotations = {
            # See: https://cloud.google.com/run/docs/troubleshooting#launch-stage-validation  # noqa
            "run.googleapis.com/launch-stage": "BETA",
        }
        # add vpc connector if specified
        if self.vpc_connector_name:
            annotations[
                "run.googleapis.com/vpc-access-connector"
            ] = self.vpc_connector_name

        # env and command here
        containers = [self._add_container_settings({"image": self.image})]

        # apply this timeout to each task
        timeout_seconds = str(self.timeout)

        body = {
            "apiVersion": "run.googleapis.com/v1",
            "kind": "Job",
            "metadata": jobs_metadata,
            "spec": {  # JobSpec
                "template": {  # ExecutionTemplateSpec
                    "metadata": {"annotations": annotations},
                    "spec": {  # ExecutionSpec
                        "template": {  # TaskTemplateSpec
                            "spec": {
                                "containers": containers,
                                "timeoutSeconds": timeout_seconds,
                                "maxRetries": self.max_retries,
                            }  # TaskSpec
                        }
                    },
                }
            },
        }
        return body

    def preview(self) -> str:
        """Generate a preview of the job definition that will be sent to GCP."""
        body = self._jobs_body()
        container_settings = body["spec"]["template"]["spec"]["template"]["spec"][
            "containers"
        ][0]["env"]
        body["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"] = [
            container_setting
            for container_setting in container_settings
            if container_setting["name"] != "PREFECT_API_KEY"
        ]
        return json.dumps(body, indent=2)

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
        self, client: Resource, timeout: int, poll_interval: int = 5
    ):
        """Give created job time to register."""
        job = Job.get(
            client=client, namespace=self.credentials.project, job_name=self.job_name
        )

        t0 = time.time()
        while not job.is_ready():
            ready_condition = (
                job.ready_condition
                if job.ready_condition
                else "waiting for condition update"
            )
            self.logger.info(
                f"Job is not yet ready... Current condition: {ready_condition}"
            )
            job = Job.get(
                client=client,
                namespace=self.credentials.project,
                job_name=self.job_name,
            )

            elapsed_time = time.time() - t0
            if timeout is not None and elapsed_time > timeout:
                raise RuntimeError(
                    f"Timed out after {elapsed_time}s while waiting for Cloud Run Job "
                    "execution to complete. Your job may still be running on GCP."
                )

            time.sleep(poll_interval)

    def _get_client(self) -> Resource:
        """Get the base client needed for interacting with GCP APIs."""
        # region needed for 'v1' API
        api_endpoint = f"https://{self.region}-run.googleapis.com"
        gcp_creds = self.credentials.get_credentials_from_service_account()
        options = ClientOptions(api_endpoint=api_endpoint)

        return discovery.build(
            "run", "v1", client_options=options, credentials=gcp_creds
        ).namespaces()

    # CONTAINER SETTINGS
    def _add_container_settings(self, base_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add settings related to containers for Cloud Run Jobs to a dictionary.
        Includes environment variables, entrypoint command, entrypoint arguments,
        and cpu and memory limits.
        See: https://cloud.google.com/run/docs/reference/rest/v1/Container
        and https://cloud.google.com/run/docs/reference/rest/v1/Container#ResourceRequirements
        """  # noqa
        container_settings = base_settings.copy()
        container_settings.update(self._add_env())
        container_settings.update(self._add_resources())
        container_settings.update(self._add_command())
        container_settings.update(self._add_args())
        return container_settings

    def _add_args(self) -> dict:
        """Set the arguments that will be passed to the entrypoint for a Cloud Run Job.
        See: https://cloud.google.com/run/docs/reference/rest/v1/Container
        """  # noqa
        return {"args": self.args} if self.args else {}

    def _add_command(self) -> dict:
        """Set the command that a container will run for a Cloud Run Job.
        See: https://cloud.google.com/run/docs/reference/rest/v1/Container
        """  # noqa
        return {"command": self.command}

    def _add_resources(self) -> dict:
        """Set specified resources limits for a Cloud Run Job.
        See: https://cloud.google.com/run/docs/reference/rest/v1/Container#ResourceRequirements
        See also: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
        """  # noqa
        resources = {"limits": {}, "requests": {}}

        if self.cpu is not None:
            cpu = self._cpu_as_k8s_quantity()
            resources["limits"]["cpu"] = cpu
            resources["requests"]["cpu"] = cpu
        if self.memory_string is not None:
            resources["limits"]["memory"] = self.memory_string
            resources["requests"]["memory"] = self.memory_string

        return {"resources": resources} if resources["requests"] else {}

    def _add_env(self) -> dict:
        """Add environment variables for a Cloud Run Job.

        Method `self._base_environment()` gets necessary Prefect environment variables
        from the config.

        See: https://cloud.google.com/run/docs/reference/rest/v1/Container#envvar for
        how environment variables are specified for Cloud Run Jobs.
        """  # noqa
        env = {**self._base_environment(), **self.env}
        cloud_run_env = [{"name": k, "value": v} for k, v in env.items()]
        return {"env": cloud_run_env}
