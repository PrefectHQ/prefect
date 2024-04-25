import re
import shlex
import time
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional
from uuid import uuid4

from anyio.abc import TaskStatus
from google.api_core.client_options import ClientOptions
from googleapiclient import discovery

# noinspection PyProtectedMember
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
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
    from pydantic.v1 import Field, PrivateAttr, validator
else:
    from pydantic import Field, PrivateAttr, validator

from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.models.cloud_run_v2 import CloudRunJobV2Result, ExecutionV2, JobV2
from prefect_gcp.utilities import slugify_name

if TYPE_CHECKING:
    from prefect.client.schemas import FlowRun
    from prefect.server.schemas.core import Flow
    from prefect.server.schemas.responses import DeploymentResponse


def _get_default_job_body_template() -> Dict[str, Any]:
    """
    Returns the default job body template for the Cloud Run worker.

    Returns:
        The default job body template.
    """
    return {
        "client": "prefect",
        "launchStage": "{{ launch_stage }}",
        "template": {
            "template": {
                "serviceAccount": "{{ service_account_name }}",
                "maxRetries": "{{ max_retries }}",
                "timeout": "{{ timeout }}",
                "vpcAccess": {"connector": "{{ vpc_connector_name }}"},
                "containers": [
                    {
                        "env": [],
                        "image": "{{ image }}",
                        "command": "{{ command }}",
                        "args": "{{ args }}",
                        "resources": {
                            "limits": {
                                "cpu": "{{ cpu }}",
                                "memory": "{{ memory }}",
                            },
                        },
                    },
                ],
            }
        },
    }


def _get_base_job_body() -> Dict[str, Any]:
    """
    Returns the base job body for the Cloud Run worker's job body validation.

    Returns:
        The base job body.
    """
    return {
        "template": {
            "template": {
                "containers": [],
            },
        },
    }


class CloudRunWorkerJobV2Configuration(BaseJobConfiguration):
    """
    The configuration for the Cloud Run worker V2.

    The schema for this class is used to populate the `job_body` section of the
    default base job template.
    """

    credentials: GcpCredentials = Field(
        title="GCP Credentials",
        default_factory=GcpCredentials,
        description=(
            "The GCP Credentials used to connect to Cloud Run. "
            "If not provided credentials will be inferred from "
            "the local environment."
        ),
    )
    job_body: Dict[str, Any] = Field(
        template=_get_default_job_body_template(),
    )
    keep_job: bool = Field(
        default=False,
        title="Keep Job After Completion",
        description="Keep the completed Cloud run job on Google Cloud Platform.",
    )
    region: str = Field(
        default="us-central1",
        description="The region in which to run the Cloud Run job",
    )
    timeout: int = Field(
        default=600,
        gt=0,
        le=86400,
        description=(
            "The length of time that Prefect will wait for a Cloud Run Job to "
            "complete before raising an exception."
        ),
    )
    _job_name: str = PrivateAttr(default=None)

    @property
    def project(self) -> str:
        """
        Returns the GCP project associated with the credentials.

        Returns:
            str: The GCP project associated with the credentials.
        """
        return self.credentials.project

    @property
    def job_name(self) -> str:
        """
        Returns the name of the job.

        Returns:
            str: The name of the job.
        """
        if self._job_name is None:
            base_job_name = slugify_name(self.name)
            job_name = f"{base_job_name}-{uuid4().hex}"
            self._job_name = job_name

        return self._job_name

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
        super().prepare_for_flow_run(
            flow_run=flow_run,
            deployment=deployment,
            flow=flow,
        )

        self._populate_env()
        self._populate_or_format_command()
        self._format_args_if_present()
        self._populate_image_if_not_present()
        self._populate_timeout()
        self._remove_vpc_access_if_unset()

    def _populate_timeout(self):
        """
        Populates the job body with the timeout.
        """
        self.job_body["template"]["template"]["timeout"] = f"{self.timeout}s"

    def _populate_env(self):
        """
        Populates the job body with environment variables.
        """
        envs = [{"name": k, "value": v} for k, v in self.env.items()]

        self.job_body["template"]["template"]["containers"][0]["env"] = envs

    def _populate_image_if_not_present(self):
        """
        Populates the job body with the image if not present.
        """
        if "image" not in self.job_body["template"]["template"]["containers"][0]:
            self.job_body["template"]["template"]["containers"][0][
                "image"
            ] = f"docker.io/{get_prefect_image_name()}"

    def _populate_or_format_command(self):
        """
        Populates the job body with the command if not present.
        """
        command = self.job_body["template"]["template"]["containers"][0].get("command")

        if command is None:
            self.job_body["template"]["template"]["containers"][0][
                "command"
            ] = shlex.split(self._base_flow_run_command())
        elif isinstance(command, str):
            self.job_body["template"]["template"]["containers"][0][
                "command"
            ] = shlex.split(command)

    def _format_args_if_present(self):
        """
        Formats the job body args if present.
        """
        args = self.job_body["template"]["template"]["containers"][0].get("args")

        if args is not None and isinstance(args, str):
            self.job_body["template"]["template"]["containers"][0][
                "args"
            ] = shlex.split(args)

    def _remove_vpc_access_if_unset(self):
        """
        Removes vpcAccess if unset.
        """

        if "vpcAccess" not in self.job_body["template"]["template"]:
            return

        vpc_access = self.job_body["template"]["template"]["vpcAccess"]

        # if vpcAccess is unset or connector is unset, remove the entire vpcAccess block
        # otherwise leave the user provided value.
        if not vpc_access or (
            len(vpc_access) == 1
            and "connector" in vpc_access
            and vpc_access["connector"] is None
        ):
            self.job_body["template"]["template"].pop("vpcAccess")

    # noinspection PyMethodParameters
    @validator("job_body")
    def _ensure_job_includes_all_required_components(cls, value: Dict[str, Any]):
        """
        Ensures that the job body includes all required components.

        Args:
            value: The job body to validate.
        Returns:
            The validated job body.
        """
        patch = JsonPatch.from_diff(value, _get_base_job_body())

        missing_paths = sorted([op["path"] for op in patch if op["op"] == "add"])

        if missing_paths:
            raise ValueError(
                f"Job body is missing required components: {', '.join(missing_paths)}"
            )

        return value

    # noinspection PyMethodParameters
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


class CloudRunWorkerV2Variables(BaseVariables):
    """
    Default variables for the Cloud Run worker V2.

    The schema for this class is used to populate the `variables` section of the
    default base job template.
    """

    credentials: GcpCredentials = Field(
        title="GCP Credentials",
        default_factory=GcpCredentials,
        description=(
            "The GCP Credentials used to connect to Cloud Run. "
            "If not provided credentials will be inferred from "
            "the local environment."
        ),
    )
    region: str = Field(
        default="us-central1",
        description="The region in which to run the Cloud Run job",
    )
    image: Optional[str] = Field(
        default="prefecthq/prefect:2-latest",
        title="Image Name",
        description=(
            "The image to use for the Cloud Run job. "
            "If not provided the default Prefect image will be used."
        ),
    )
    args: List[str] = Field(
        default_factory=list,
        description=(
            "The arguments to pass to the Cloud Run Job V2's entrypoint command."
        ),
    )
    keep_job: bool = Field(
        default=False,
        title="Keep Job After Completion",
        description="Keep the completed Cloud run job on Google Cloud Platform.",
    )
    launch_stage: Literal[
        "ALPHA",
        "BETA",
        "GA",
        "DEPRECATED",
        "EARLY_ACCESS",
        "PRELAUNCH",
        "UNIMPLEMENTED",
        "LAUNCH_TAG_UNSPECIFIED",
    ] = Field(
        "BETA",
        description=(
            "The launch stage of the Cloud Run Job V2. "
            "See https://cloud.google.com/run/docs/about-features-categories "
            "for additional details."
        ),
    )
    max_retries: int = Field(
        default=0,
        title="Max Retries",
        description="The number of times to retry the Cloud Run job.",
    )
    cpu: str = Field(
        default="1000m",
        title="CPU",
        description="The CPU to allocate to the Cloud Run job.",
    )
    memory: str = Field(
        default="512Mi",
        title="Memory",
        description=(
            "The memory to allocate to the Cloud Run job along with the units, which"
            "could be: G, Gi, M, Mi."
        ),
        example="512Mi",
        pattern=r"^\d+(?:G|Gi|M|Mi)$",
    )
    timeout: int = Field(
        default=600,
        gt=0,
        le=86400,
        title="Job Timeout",
        description=(
            "The length of time that Prefect will wait for a Cloud Run Job to "
            "complete before raising an exception (maximum of 86400 seconds, 1 day)."
        ),
    )
    vpc_connector_name: Optional[str] = Field(
        default=None,
        title="VPC Connector Name",
        description="The name of the VPC connector to use for the Cloud Run job.",
    )
    service_account_name: Optional[str] = Field(
        default=None,
        title="Service Account Name",
        description=(
            "The name of the service account to use for the task execution "
            "of Cloud Run Job. By default Cloud Run jobs run as the default "
            "Compute Engine Service Account."
        ),
        example="service-account@example.iam.gserviceaccount.com",
    )


class CloudRunWorkerV2Result(BaseWorkerResult):
    """
    The result of a Cloud Run worker V2 job.
    """


class CloudRunWorkerV2(BaseWorker):
    """
    The Cloud Run worker V2.
    """

    type = "cloud-run-v2"
    job_configuration = CloudRunWorkerJobV2Configuration
    job_configuration_variables = CloudRunWorkerV2Variables
    _description = "Execute flow runs within containers on Google Cloud Run (V2 API). Requires a Google Cloud Platform account."  # noqa
    _display_name = "Google Cloud Run V2"
    _documentation_url = "https://prefecthq.github.io/prefect-gcp/worker_v2/"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/4SpnOBvMYkHp6z939MDKP6/549a91bc1ce9afd4fb12c68db7b68106/social-icon-google-cloud-1200-630.png?h=250"  # noqa

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: CloudRunWorkerJobV2Configuration,
        task_status: Optional[TaskStatus] = None,
    ) -> CloudRunJobV2Result:
        """
        Runs the flow run on Cloud Run and waits for it to complete.

        Args:
            flow_run: The flow run to run.
            configuration: The configuration for the job.
            task_status: The task status to update.

        Returns:
            The result of the job.
        """
        logger = self.get_flow_run_logger(flow_run)

        with self._get_client(configuration=configuration) as cr_client:
            await run_sync_in_worker_thread(
                self._create_job_and_wait_for_registration,
                configuration=configuration,
                cr_client=cr_client,
                logger=logger,
            )

            execution = await run_sync_in_worker_thread(
                self._begin_job_execution,
                configuration=configuration,
                cr_client=cr_client,
                logger=logger,
            )

            if task_status:
                task_status.started(configuration.job_name)

            result = await run_sync_in_worker_thread(
                self._watch_job_execution_and_get_result,
                configuration=configuration,
                cr_client=cr_client,
                execution=execution,
                logger=logger,
            )

            return result

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: CloudRunWorkerJobV2Configuration,
        grace_seconds: int = 30,
    ):
        """
        Stops the Cloud Run job.

        Args:
            infrastructure_pid: The ID of the infrastructure to stop.
            configuration: The configuration for the job.
            grace_seconds: The number of seconds to wait before stopping the job.
        """
        if grace_seconds != 30:
            self._logger.warning(
                f"Kill grace period of {grace_seconds}s requested, but GCP does not "
                "support dynamic grace period configuration. See here for more info: "
                "https://cloud.google.com/run/docs/reference/rest/v1/namespaces.jobs/delete"  # noqa
            )

        with self._get_client(configuration=configuration) as cr_client:
            await run_sync_in_worker_thread(
                self._stop_job,
                cr_client=cr_client,
                configuration=configuration,
                job_name=infrastructure_pid,
            )

    @staticmethod
    def _get_client(
        configuration: CloudRunWorkerJobV2Configuration,
    ) -> ResourceWarning:
        """
        Get the base client needed for interacting with GCP Cloud Run V2 API.

        Returns:
            Resource: The base client needed for interacting with GCP Cloud Run V2 API.
        """
        api_endpoint = "https://run.googleapis.com"
        gcp_creds = configuration.credentials.get_credentials_from_service_account()

        options = ClientOptions(api_endpoint=api_endpoint)

        return (
            discovery.build(
                "run",
                "v2",
                client_options=options,
                credentials=gcp_creds,
                num_retries=3,  # Set to 3 in case of intermittent/connection issues
            )
            .projects()
            .locations()
        )

    def _create_job_and_wait_for_registration(
        self,
        configuration: CloudRunWorkerJobV2Configuration,
        cr_client: Resource,
        logger: PrefectLogAdapter,
    ):
        """
        Creates the Cloud Run job and waits for it to register.

        Args:
            configuration: The configuration for the job.
            cr_client: The Cloud Run client.
            logger: The logger to use.
        """
        try:
            logger.info(f"Creating Cloud Run JobV2 {configuration.job_name}")

            JobV2.create(
                cr_client=cr_client,
                project=configuration.project,
                location=configuration.region,
                job_id=configuration.job_name,
                body=configuration.job_body,
            )
        except HttpError as exc:
            self._create_job_error(
                exc=exc,
                configuration=configuration,
            )

        try:
            self._wait_for_job_creation(
                cr_client=cr_client,
                configuration=configuration,
                logger=logger,
            )
        except Exception as exc:
            logger.critical(
                f"Failed to create Cloud Run JobV2 {configuration.job_name}.\n{exc}"
            )

            if not configuration.keep_job:
                try:
                    JobV2.delete(
                        cr_client=cr_client,
                        project=configuration.project,
                        location=configuration.region,
                        job_name=configuration.job_name,
                    )
                except Exception as exc2:
                    logger.critical(
                        f"Failed to delete Cloud Run JobV2 {configuration.job_name}."
                        f"\n{exc2}"
                    )

            raise

    @staticmethod
    def _wait_for_job_creation(
        cr_client: Resource,
        configuration: CloudRunWorkerJobV2Configuration,
        logger: PrefectLogAdapter,
        poll_interval: int = 5,
    ):
        """
        Waits for the Cloud Run job to be created.

        Args:
            cr_client: The Cloud Run client.
            configuration: The configuration for the job.
            logger: The logger to use.
            poll_interval: The interval to poll the Cloud Run job, defaults to 5
                seconds.
        """
        job = JobV2.get(
            cr_client=cr_client,
            project=configuration.project,
            location=configuration.region,
            job_name=configuration.job_name,
        )

        t0 = time.time()

        while not job.is_ready():
            if not (ready_condition := job.get_ready_condition()):
                ready_condition = "waiting for condition update"

            logger.info(f"Current Job Condition: {ready_condition}")

            job = JobV2.get(
                cr_client=cr_client,
                project=configuration.project,
                location=configuration.region,
                job_name=configuration.job_name,
            )

            elapsed_time = time.time() - t0

            if elapsed_time > configuration.timeout:
                raise RuntimeError(
                    f"Timeout of {configuration.timeout} seconds reached while "
                    f"waiting for Cloud Run Job V2 {configuration.job_name} to be "
                    "created."
                )

            time.sleep(poll_interval)

    @staticmethod
    def _create_job_error(
        exc: HttpError,
        configuration: CloudRunWorkerJobV2Configuration,
    ):
        """
        Creates a formatted error message for the Cloud Run V2 API errors
        """
        # noinspection PyUnresolvedReferences
        if exc.status_code == 404:
            raise RuntimeError(
                f"Failed to find resources at {exc.uri}. Confirm that region"
                f" '{configuration.region}' is the correct region for your Cloud"
                f" Run Job and that {configuration.project} is the correct GCP "
                f" project. If your project ID is not correct, you are using a "
                f"Credentials block with permissions for the wrong project."
            ) from exc

        raise exc

    def _begin_job_execution(
        self,
        cr_client: Resource,
        configuration: CloudRunWorkerJobV2Configuration,
        logger: PrefectLogAdapter,
    ) -> ExecutionV2:
        """
        Begins the Cloud Run job execution.

        Args:
            cr_client: The Cloud Run client.
            configuration: The configuration for the job.
            logger: The logger to use.

        Returns:
            The Cloud Run job execution.
        """
        try:
            logger.info(
                f"Submitting Cloud Run Job V2 {configuration.job_name} for execution..."
            )

            submission = JobV2.run(
                cr_client=cr_client,
                project=configuration.project,
                location=configuration.region,
                job_name=configuration.job_name,
            )

            job_execution = ExecutionV2.get(
                cr_client=cr_client,
                execution_id=submission["metadata"]["name"],
            )

            command = (
                " ".join(configuration.command)
                if configuration.command
                else "default container command"
            )

            logger.info(
                f"Cloud Run Job V2 {configuration.job_name} submitted for execution "
                f"with command: {command}"
            )

            return job_execution
        except Exception as exc:
            self._job_run_submission_error(
                exc=exc,
                configuration=configuration,
            )
            raise

    def _watch_job_execution_and_get_result(
        self,
        cr_client: Resource,
        configuration: CloudRunWorkerJobV2Configuration,
        execution: ExecutionV2,
        logger: PrefectLogAdapter,
        poll_interval: int = 5,
    ) -> CloudRunJobV2Result:
        """
        Watch the job execution and get the result.

        Args:
            cr_client (Resource): The base client needed for interacting with GCP
                Cloud Run V2 API.
            configuration (CloudRunWorkerJobV2Configuration): The configuration for
                the job.
            execution (ExecutionV2): The execution to watch.
            logger (PrefectLogAdapter): The logger to use.
            poll_interval (int): The number of seconds to wait between polls.
                Defaults to 5 seconds.

        Returns:
            The result of the job.
        """
        try:
            execution = self._watch_job_execution(
                cr_client=cr_client,
                configuration=configuration,
                execution=execution,
                poll_interval=poll_interval,
            )
        except Exception as exc:
            logger.critical(
                f"Encountered an exception while waiting for job run completion - "
                f"{exc}"
            )
            raise

        if execution.succeeded():
            status_code = 0
            logger.info(f"Cloud Run Job V2 {configuration.job_name} succeeded")
        else:
            status_code = 1
            error_mg = execution.condition_after_completion().get("message")
            logger.error(
                f"Cloud Run Job V2 {configuration.job_name} failed - {error_mg}"
            )

        logger.info(f"Job run logs can be found on GCP at: {execution.logUri}")

        if not configuration.keep_job:
            logger.info(
                f"Deleting completed Cloud Run Job {configuration.job_name!r} from "
                "Google Cloud Run..."
            )

            try:
                JobV2.delete(
                    cr_client=cr_client,
                    project=configuration.project,
                    location=configuration.region,
                    job_name=configuration.job_name,
                )
            except Exception as exc:
                logger.critical(
                    "Received an exception while deleting the Cloud Run Job V2 "
                    f"- {configuration.job_name} - {exc}"
                )

        return CloudRunJobV2Result(
            identifier=configuration.job_name,
            status_code=status_code,
        )

    # noinspection DuplicatedCode
    @staticmethod
    def _watch_job_execution(
        cr_client: Resource,
        configuration: CloudRunWorkerJobV2Configuration,
        execution: ExecutionV2,
        poll_interval: int,
    ) -> ExecutionV2:
        """
        Update execution status until it is no longer running or timeout is reached.

        Args:
            cr_client (Resource): The base client needed for interacting with GCP
                Cloud Run V2 API.
            configuration (CloudRunWorkerJobV2Configuration): The configuration for
                the job.
            execution (ExecutionV2): The execution to watch.
            poll_interval (int): The number of seconds to wait between polls.

        Returns:
            The execution.
        """
        t0 = time.time()

        while execution.is_running():
            execution = ExecutionV2.get(
                cr_client=cr_client,
                execution_id=execution.name,
            )

            elapsed_time = time.time() - t0

            if elapsed_time > configuration.timeout:
                raise RuntimeError(
                    f"Timeout of {configuration.timeout} seconds reached while "
                    f"waiting for Cloud Run Job V2 {configuration.job_name} to "
                    "complete."
                )

            time.sleep(poll_interval)

        return execution

    @staticmethod
    def _job_run_submission_error(
        exc: Exception,
        configuration: CloudRunWorkerJobV2Configuration,
    ):
        """
        Creates a formatted error message for the Cloud Run V2 API errors

        Args:
            exc: The exception to format.
            configuration: The configuration for the job.
        """
        # noinspection PyUnresolvedReferences
        if exc.status_code == 404:
            pat1 = r"The requested URL [^ ]+ was not found on this server"

            if re.findall(pat1, str(exc)):
                # noinspection PyUnresolvedReferences
                raise RuntimeError(
                    f"Failed to find resources at {exc.uri}. "
                    f"Confirm that region '{configuration.region}' is "
                    f"the correct region for your Cloud Run Job "
                    f"and that '{configuration.project}' is the "
                    f"correct GCP project. If your project ID is not "
                    f"correct, you are using a Credentials "
                    f"block with permissions for the wrong project."
                ) from exc
            else:
                raise exc

    @staticmethod
    def _stop_job(
        cr_client: Resource,
        configuration: CloudRunWorkerJobV2Configuration,
        job_name: str,
    ):
        """
        Stops/deletes the Cloud Run job.

        Args:
            cr_client: The Cloud Run client.
            configuration: The configuration for the job.
            job_name: The name of the job to stop.
        """
        try:
            JobV2.delete(
                cr_client=cr_client,
                project=configuration.project,
                location=configuration.region,
                job_name=job_name,
            )
        except Exception as exc:
            if "does not exist" in str(exc):
                raise InfrastructureNotFound(
                    f"Cannot stop Cloud Run Job; the job name {job_name!r} "
                    "could not be found."
                ) from exc
            raise
