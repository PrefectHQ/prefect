"""
Integrations with the Azure Container Instances service.
Note this module is experimental. The interfaces within may change without notice.

The `AzureContainerInstanceJob` infrastructure block in this module is ideally
configured via the Prefect UI and run via a Prefect agent, but it can be called directly
as demonstrated in the following examples.

Examples:
    Run a command using an Azure Container Instances container.
    ```python
    AzureContainerInstanceJob(command=["echo", "hello world"]).run()
    ```

    Run a command and stream the container's output to the local terminal.
    ```python
    AzureContainerInstanceJob(
        command=["echo", "hello world"],
        stream_output=True,
    )
    ```

    Run a command with a specific image
    ```python
    AzureContainerInstanceJob(command=["echo", "hello world"], image="alpine:latest")
    ```

    Run a task with custom memory and CPU requirements
    ```python
    AzureContainerInstanceJob(command=["echo", "hello world"], memory=1.0, cpu=1.0)
    ```

    Run a task with custom memory and CPU requirements
    ```python
    AzureContainerInstanceJob(command=["echo", "hello world"], memory=1.0, cpu=1.0)
    ```

    Run a task with custom memory, CPU, and GPU requirements
    ```python
    AzureContainerInstanceJob(command=["echo", "hello world"], memory=1.0, cpu=1.0,
    gpu_count=1, gpu_sku="V100")
    ```

    Run a task with custom environment variables
    ```python
    AzureContainerInstanceJob(
        command=["echo", "hello $PLANET"],
        env={"PLANET": "earth"}
    )
    ```

    Run a task that uses a private ACR registry with a managed identity
    ```python
    AzureContainerInstanceJob(
        command=["echo", "hello $PLANET"],
        image="my-registry.azurecr.io/my-image",
        image_registry=ACRManagedIdentity(
            registry_url="my-registry.azurecr.io",
            identity="/my/managed/identity/123abc"
        )
    )
    ```
"""

import datetime
import json
import random
import shlex
import string
import sys
import time
import uuid
from copy import deepcopy
from enum import Enum
from typing import Dict, List, Optional, Union

import anyio
import dateutil.parser
from anyio.abc import TaskStatus
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.core.polling import LROPoller
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (
    Container,
    ContainerGroup,
    ContainerGroupIdentity,
    ContainerGroupRestartPolicy,
    ContainerGroupSubnetId,
    DnsConfiguration,
    EnvironmentVariable,
    GpuResource,
    ImageRegistryCredential,
    Logs,
    OperatingSystemTypes,
    ResourceRequests,
    ResourceRequirements,
    UserAssignedIdentities,
)
from pydantic import VERSION as PYDANTIC_VERSION

import prefect.infrastructure.container
from prefect.blocks.core import BlockNotSavedError
from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.infrastructure.base import Infrastructure, InfrastructureResult
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.dockerutils import get_prefect_image_name

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import BaseModel, Field, SecretStr
else:
    from pydantic import BaseModel, Field, SecretStr

from slugify import slugify
from typing_extensions import Literal

from prefect_azure.credentials import AzureContainerInstanceCredentials

ACI_DEFAULT_CPU = 1.0
ACI_DEFAULT_MEMORY = 1.0
ACI_DEFAULT_GPU = 0.0
DEFAULT_CONTAINER_ENTRYPOINT = "/opt/prefect/entrypoint.sh"
# environment variables that ACI should treat as secure variables so they
# won't appear in logs
ENV_SECRETS = ["PREFECT_API_KEY"]

# The maximum time to wait for container group deletion before giving up and
# moving on. Deletion is usually quick, so exceeding this timeout means something
# has gone wrong and we should raise an exception to inform the user they should
# check their Azure account for orphaned container groups.
CONTAINER_GROUP_DELETION_TIMEOUT_SECONDS = 30


class ContainerGroupProvisioningState(str, Enum):
    """
    Terminal provisioning states for ACI container groups. Per the Azure docs,
    the states in this Enum are the only ones that can be relied on as dependencies.
    """

    SUCCEEDED = "Succeeded"
    FAILED = "Failed"


class ContainerRunState(str, Enum):
    """
    Terminal run states for ACI containers.
    """

    RUNNING = "Running"
    TERMINATED = "Terminated"


class ACRManagedIdentity(BaseModel):
    """
    Use a Managed Identity to access Azure Container registry. Requires the
    user-assigned managed identity be available to the ACI container group.
    """

    registry_url: str = Field(
        default=...,
        title="Registry URL",
        description=(
            "The URL to the registry, such as myregistry.azurecr.io. Generally, 'http' "
            "or 'https' can be omitted."
        ),
    )
    identity: str = Field(
        default=...,
        description=(
            "The user-assigned Azure managed identity for the private registry."
        ),
    )


class AzureContainerInstanceJobResult(InfrastructureResult):
    """
    The result of an `AzureContainerInstanceJob` run.
    """


class AzureContainerInstanceJob(Infrastructure):
    """
    Run a command using a container on Azure Container Instances.
    Note this block is experimental. The interface may change without notice.
    """

    _block_type_name = "Azure Container Instance Job"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png"  # noqa
    _description = "Run tasks using Azure Container Instances. Note this block is experimental. The interface may change without notice."  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-azure/container_instance/#prefect_azure.container_instance.AzureContainerInstanceJob"  # noqa

    type: Literal["container-instance-job"] = Field(
        default="container-instance-job", description="The slug for this task type."
    )
    aci_credentials: AzureContainerInstanceCredentials = Field(
        default_factory=AzureContainerInstanceCredentials,
        description=(
            "Credentials for Azure Container Instances; "
            "if not provided will attempt to use DefaultAzureCredentials."
        ),
    )
    resource_group_name: str = Field(
        default=...,
        title="Azure Resource Group Name",
        description=(
            "The name of the Azure Resource Group in which to run Prefect ACI tasks."
        ),
    )
    subscription_id: SecretStr = Field(
        default=...,
        title="Azure Subscription ID",
        description="The ID of the Azure subscription to create containers under.",
    )
    identities: Optional[List[str]] = Field(
        title="Identities",
        default=None,
        description=(
            "A list of user-assigned identities to associate with the container group. "
            "The identities should be an ARM resource IDs in the form: "
            "'/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{identityName}'."  # noqa
        ),
    )
    image: Optional[str] = Field(
        default_factory=get_prefect_image_name,
        description=(
            "The image to use for the Prefect container in the task. This value "
            "defaults to a Prefect base image matching your local versions."
        ),
    )
    entrypoint: Optional[str] = Field(
        default=DEFAULT_CONTAINER_ENTRYPOINT,
        description=(
            "The entrypoint of the container you wish you run. This value "
            "defaults to the entrypoint used by Prefect images and should only be "
            "changed when using a custom image that is not based on an official "
            "Prefect image. Any commands set on deployments will be passed "
            "to the entrypoint as parameters."
        ),
    )
    image_registry: Optional[
        Union[
            prefect.infrastructure.container.DockerRegistry,
            ACRManagedIdentity,
        ]
    ] = Field(
        default=None,
        title="Image Registry (Optional)",
        description=(
            "To use any private container registry with a username and password, "
            "choose DockerRegistry. To use a private Azure Container Registry "
            "with a managed identity, choose ACRManagedIdentity."
        ),
    )
    cpu: float = Field(
        title="CPU",
        default=ACI_DEFAULT_CPU,
        description=(
            "The number of virtual CPUs to assign to the task container. "
            f"If not provided, a default value of {ACI_DEFAULT_CPU} will be used."
        ),
    )
    gpu_count: Optional[int] = Field(
        title="GPU Count",
        default=None,
        description=(
            "The number of GPUs to assign to the task container. "
            "If not provided, no GPU will be used."
        ),
    )
    gpu_sku: Optional[str] = Field(
        title="GPU SKU",
        default=None,
        description=(
            "The Azure GPU SKU to use. See the ACI documentation for a list of "
            "GPU SKUs available in each Azure region."
        ),
    )
    memory: float = Field(
        default=ACI_DEFAULT_MEMORY,
        description=(
            "The amount of memory in gigabytes to provide to the ACI task. Valid "
            "amounts are specified in the Azure documentation. If not provided, a "
            f"default value of  {ACI_DEFAULT_MEMORY} will be used unless present "
            "on the task definition."
        ),
    )
    subnet_ids: Optional[List[str]] = Field(
        default=None,
        title="Subnet IDs",
        description="A list of Azure subnet IDs the container should be connected to.",
    )
    dns_servers: Optional[List[str]] = Field(
        default=None,
        title="DNS Servers",
        description="A list of custom DNS Servers the container should use.",
    )
    stream_output: Optional[bool] = Field(
        default=None,
        description=(
            "If `True`, logs will be streamed from the Prefect container to the local "
            "console."
        ),
    )
    env: Dict[str, Optional[str]] = Field(
        title="Environment Variables",
        default_factory=dict,
        description=(
            "Environment variables to provide to the task run. These variables are set "
            "on the Prefect container at task runtime. These will not be set on the "
            "task definition."
        ),
    )
    # Execution settings
    task_start_timeout_seconds: int = Field(
        default=240,
        description=(
            "The amount of time to watch for the start of the ACI container. "
            "before marking it as failed."
        ),
    )
    task_watch_poll_interval: float = Field(
        default=5.0,
        description=(
            "The number of seconds to wait between Azure API calls while monitoring "
            "the state of an Azure Container Instances task."
        ),
    )

    @sync_compatible
    async def run(
        self, task_status: Optional[TaskStatus] = None
    ) -> AzureContainerInstanceJobResult:
        """
        Runs the configured task using an ACI container.

        Args:
            task_status: An optional `TaskStatus` to update when the container starts.

        Returns:
            An `AzureContainerInstanceJobResult` with the container's exit code.
        """

        run_start_time = datetime.datetime.now(datetime.timezone.utc)

        container = self._configure_container()
        container_group = self._configure_container_group(container)
        created_container_group = None

        aci_client = self.aci_credentials.get_container_client(
            self.subscription_id.get_secret_value()
        )

        self.logger.info(
            f"{self._log_prefix}: Preparing to run command {' '.join(self.command)!r} "
            f"in container {container.name!r} ({self.image})..."
        )
        try:
            self.logger.info(f"{self._log_prefix}: Waiting for container creation...")
            # Create the container group and wait for it to start
            creation_status_poller = await run_sync_in_worker_thread(
                aci_client.container_groups.begin_create_or_update,
                self.resource_group_name,
                container.name,
                container_group,
            )
            created_container_group = await run_sync_in_worker_thread(
                self._wait_for_task_container_start, creation_status_poller
            )

            # If creation succeeded, group provisioning state should be 'Succeeded'
            # and the group should have a single container
            if self._provisioning_succeeded(created_container_group):
                self.logger.info(f"{self._log_prefix}: Running command...")
                if task_status:
                    task_status.started(value=created_container_group.name)
                status_code = await run_sync_in_worker_thread(
                    self._watch_task_and_get_exit_code,
                    aci_client,
                    created_container_group,
                    run_start_time,
                )
                self.logger.info(f"{self._log_prefix}: Completed command run.")
            else:
                raise RuntimeError(f"{self._log_prefix}: Container creation failed.")

        finally:
            if created_container_group:
                await self._wait_for_container_group_deletion(
                    aci_client, created_container_group
                )

        return AzureContainerInstanceJobResult(
            identifier=created_container_group.name, status_code=status_code
        )

    async def kill(
        self,
        container_group_name: str,
        grace_seconds: int = CONTAINER_GROUP_DELETION_TIMEOUT_SECONDS,
    ):
        """
        Kill a flow running in an ACI container group.

        Args:
            container_group_name: The container group name yielded by
                `AzureContainerInstanceJob.run`.
        """
        # ACI does not provide a way to specify grace period, but it gives
        # applications ~30 seconds to gracefully terminate before killing
        # a container group.
        if grace_seconds != CONTAINER_GROUP_DELETION_TIMEOUT_SECONDS:
            self.logger.warning(
                f"{self._log_prefix}: Kill grace period of {grace_seconds}s requested, "
                f"but ACI does not support grace period configuration."
            )

        aci_client = self.aci_credentials.get_container_client(
            self.subscription_id.get_secret_value()
        )

        # get the container group to check that it still exists
        try:
            container_group = aci_client.container_groups.get(
                resource_group_name=self.resource_group_name,
                container_group_name=container_group_name,
            )
        except ResourceNotFoundError as exc:
            # the container group no longer exists, so there's nothing to cancel
            raise InfrastructureNotFound(
                f"Cannot stop ACI job: container group {container_group_name} "
                "no longer exists."
            ) from exc

        # get the container state to check if the container has terminated
        container = self._get_container(container_group)
        container_state = container.instance_view.current_state.state

        # the container group needs to be deleted regardless of whether the container
        # already terminated
        await self._wait_for_container_group_deletion(aci_client, container_group)

        # if the container had already terminated, raise an exception to let the agent
        # know the flow was not cancelled
        if container_state == ContainerRunState.TERMINATED:
            raise InfrastructureNotAvailable(
                f"Cannot stop ACI job: container group {container_group.name} exists, "
                f"but container {container.name} has already terminated."
            )

    def preview(self) -> str:
        """
        Provides a summary of how the container will be created when `run` is called.

        Returns:
           A string containing the summary.
        """
        preview = {
            "container_name": "<generated when run>",
            "resource_group_name": self.resource_group_name,
            "memory": self.memory,
            "cpu": self.cpu,
            "gpu_count": self.gpu_count,
            "gpu_sku": self.gpu_sku,
            "env": self._get_environment(),
        }

        return json.dumps(preview)

    def get_corresponding_worker_type(self) -> str:
        """Return the corresponding worker type for this infrastructure block."""
        from prefect_azure.workers.container_instance import AzureContainerWorker

        return AzureContainerWorker.type

    async def generate_work_pool_base_job_template(self) -> dict:
        """
        Generate a base job template for an `Azure Container Instance` work pool
        with the same configuration as this block.

        Returns:
            - dict: a base job template for an `Azure Container Instance` work pool
        """
        from prefect_azure.workers.container_instance import AzureContainerWorker

        base_job_template = deepcopy(
            AzureContainerWorker.get_default_base_job_template()
        )
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
            ]:
                continue
            elif key == "subscription_id":
                base_job_template["variables"]["properties"]["subscription_id"][
                    "default"
                ] = value.get_secret_value()
            elif key == "aci_credentials":
                if not self.aci_credentials._block_document_id:
                    raise BlockNotSavedError(
                        "It looks like you are trying to use a block that"
                        " has not been saved. Please call `.save` on your block"
                        " before publishing it as a work pool."
                    )
                base_job_template["variables"]["properties"]["aci_credentials"][
                    "default"
                ] = {
                    "$ref": {
                        "block_document_id": str(
                            self.aci_credentials._block_document_id
                        )
                    }
                }
            elif key == "image_registry":
                if not self.image_registry._block_document_id:
                    raise BlockNotSavedError(
                        "It looks like you are trying to use a block that"
                        " has not been saved. Please call `.save` on your block"
                        " before publishing it as a work pool."
                    )
                base_job_template["variables"]["properties"]["image_registry"][
                    "default"
                ] = {
                    "$ref": {
                        "block_document_id": str(self.image_registry._block_document_id)
                    }
                }
            elif key in base_job_template["variables"]["properties"]:
                base_job_template["variables"]["properties"][key]["default"] = value
            else:
                self.logger.warning(
                    f"Variable {key!r} is not supported by `Azure Container Instance`"
                    " work pools. Skipping."
                )

        return base_job_template

    def _configure_container(self) -> Container:
        """
        Configures an Azure `Container` using data from the block's fields.

        Returns:
            An instance of `Container` ready to submit to Azure.
        """

        # setup container environment variables
        environment = [
            EnvironmentVariable(name=k, secure_value=v)
            if k in ENV_SECRETS
            else EnvironmentVariable(name=k, value=v)
            for (k, v) in self._get_environment().items()
        ]

        # all container names in a resource group must be unique
        if self.name:
            slugified_name = slugify(
                self.name,
                max_length=52,
                regex_pattern=r"[^a-zA-Z0-9-]+",
            )
            random_suffix = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=10)
            )
            container_name = slugified_name + "-" + random_suffix
        else:
            container_name = str(uuid.uuid4())

        container_resource_requirements = self._configure_container_resources()

        # add the entrypoint if provided, because creating an ACI container with a
        # command overrides the container's built-in entrypoint.
        if self.entrypoint:
            self.command.insert(0, self.entrypoint)

        return Container(
            name=container_name,
            image=self.image,
            command=self.command,
            resources=container_resource_requirements,
            environment_variables=environment,
        )

    def _configure_container_resources(self) -> ResourceRequirements:
        """
        Configures the container's memory, CPU, and GPU resources.

        Returns:
            A `ResourceRequirements` instance initialized with data from this
            `AzureContainerInstanceJob` block.
        """

        gpu_resource = (
            GpuResource(count=self.gpu_count, sku=self.gpu_sku)
            if self.gpu_count and self.gpu_sku
            else None
        )
        container_resource_requests = ResourceRequests(
            memory_in_gb=self.memory, cpu=self.cpu, gpu=gpu_resource
        )

        return ResourceRequirements(requests=container_resource_requests)

    def _configure_container_group(self, container: Container) -> ContainerGroup:
        """
        Configures the container group needed to start a container on ACI.

        Args:
            container: An initialized instance of `Container`.

        Returns:
            An initialized `ContainerGroup` ready to submit to Azure.
        """

        # Load the resource group, so we can set the container group location
        # correctly.

        resource_group_client = self.aci_credentials.get_resource_client(
            self.subscription_id.get_secret_value()
        )

        resource_group = resource_group_client.resource_groups.get(
            self.resource_group_name
        )

        image_registry_credentials = self._create_image_registry_credentials(
            self.image_registry
        )

        identity = (
            ContainerGroupIdentity(
                type="UserAssigned",
                # The Azure API only uses the dict keys and ignores values when
                # creating a container group. Using empty `UserAssignedIdentities`
                # instances as dict values satisfies Python type checkers.
                user_assigned_identities={
                    identity: UserAssignedIdentities() for identity in self.identities
                },
            )
            if self.identities
            else None
        )

        subnet_ids = (
            [ContainerGroupSubnetId(id=subnet_id) for subnet_id in self.subnet_ids]
            if self.subnet_ids
            else None
        )

        dns_config = (
            DnsConfiguration(name_servers=self.dns_servers)
            if self.dns_servers
            else None
        )

        return ContainerGroup(
            location=resource_group.location,
            identity=identity,
            containers=[container],
            os_type=OperatingSystemTypes.linux,
            restart_policy=ContainerGroupRestartPolicy.never,
            image_registry_credentials=image_registry_credentials,
            subnet_ids=subnet_ids,
            dns_config=dns_config,
        )

    @staticmethod
    def _create_image_registry_credentials(
        image_registry: Union[
            prefect.infrastructure.container.DockerRegistry,
            ACRManagedIdentity,
            None,
        ],
    ):
        """
        Create image registry credentials based on the type of image_registry provided.

        Args:
            image_registry: An instance of a DockerRegistry or
            ACRManagedIdentity object.

        Returns:
            A list containing an ImageRegistryCredential object if the input is a
            `DockerRegistry` or `ACRManagedIdentity`, or None if the
            input doesn't match any of the expected types.
        """
        if image_registry and isinstance(
            image_registry, prefect.infrastructure.container.DockerRegistry
        ):
            return [
                ImageRegistryCredential(
                    server=image_registry.registry_url,
                    username=image_registry.username,
                    password=image_registry.password.get_secret_value(),
                )
            ]
        elif image_registry and isinstance(image_registry, ACRManagedIdentity):
            return [
                ImageRegistryCredential(
                    server=image_registry.registry_url,
                    identity=image_registry.identity,
                )
            ]
        else:
            return None

    def _wait_for_task_container_start(
        self, creation_status_poller: LROPoller[ContainerGroup]
    ) -> ContainerGroup:
        """
        Wait for the result of group and container creation.

        Args:
            creation_status_poller: Poller returned by the Azure SDK.

        Raises:
            RuntimeError: Raised if the timeout limit is exceeded before the
            container starts.

        Returns:
            A `ContainerGroup` representing the current status of the group being
            watched.
        """

        t0 = time.time()
        timeout = self.task_start_timeout_seconds

        while not creation_status_poller.done():
            elapsed_time = time.time() - t0

            if timeout and elapsed_time > timeout:
                raise RuntimeError(
                    (
                        f"Timed out after {elapsed_time}s while watching waiting for "
                        "container start."
                    )
                )
            time.sleep(self.task_watch_poll_interval)

        return creation_status_poller.result()

    def _watch_task_and_get_exit_code(
        self,
        client: ContainerInstanceManagementClient,
        container_group: ContainerGroup,
        run_start_time: datetime.datetime,
    ) -> int:
        """
        Waits until the container finishes running and obtains its exit code.

        Args:
            client: An initialized Azure `ContainerInstanceManagementClient`
            container_group: The `ContainerGroup` in which the container resides.

        Returns:
            An `int` representing the container's exit code.
        """

        status_code = -1
        running_container = self._get_container(container_group)
        current_state = running_container.instance_view.current_state.state

        # get any logs the container has already generated
        last_log_time = run_start_time
        if self.stream_output:
            last_log_time = self._get_and_stream_output(
                client, container_group, last_log_time
            )

        # set exit code if flow run already finished:
        if current_state == ContainerRunState.TERMINATED:
            status_code = running_container.instance_view.current_state.exit_code

        while current_state != ContainerRunState.TERMINATED:
            try:
                container_group = client.container_groups.get(
                    resource_group_name=self.resource_group_name,
                    container_group_name=container_group.name,
                )
            except ResourceNotFoundError:
                self.logger.exception(
                    f"{self._log_prefix}: Container group was deleted before flow run "
                    "completed, likely due to flow cancellation."
                )

                # since the flow was cancelled, exit early instead of raising an
                # exception
                return status_code

            container = self._get_container(container_group)
            current_state = container.instance_view.current_state.state

            if current_state == ContainerRunState.TERMINATED:
                status_code = container.instance_view.current_state.exit_code
                # break instead of waiting for next loop iteration because
                # trying to read logs from a terminated container raises an exception
                break

            if self.stream_output:
                last_log_time = self._get_and_stream_output(
                    client, container_group, last_log_time
                )

            time.sleep(self.task_watch_poll_interval)

        return status_code

    async def _wait_for_container_group_deletion(
        self,
        aci_client: ContainerInstanceManagementClient,
        container_group: ContainerGroup,
    ):
        self.logger.info(f"{self._log_prefix}: Deleting container...")

        deletion_status_poller = await run_sync_in_worker_thread(
            aci_client.container_groups.begin_delete,
            resource_group_name=self.resource_group_name,
            container_group_name=container_group.name,
        )

        t0 = time.time()
        timeout = CONTAINER_GROUP_DELETION_TIMEOUT_SECONDS

        while not deletion_status_poller.done():
            elapsed_time = time.time() - t0

            if timeout and elapsed_time > timeout:
                raise RuntimeError(
                    (
                        f"Timed out after {elapsed_time}s while waiting for deletion of"
                        f" container group {container_group.name}. To verify the group "
                        "has been deleted, check the Azure Portal or run "
                        f"az container show --name {container_group.name} --resource-group {self.resource_group_name}"  # noqa
                    )
                )
            await anyio.sleep(self.task_watch_poll_interval)

        self.logger.info(f"{self._log_prefix}: Container deleted.")

    def _get_container(self, container_group: ContainerGroup) -> Container:
        """
        Extracts the job container from a container group.
        """
        return container_group.containers[0]

    def _get_and_stream_output(
        self,
        client: ContainerInstanceManagementClient,
        container_group: ContainerGroup,
        last_log_time: datetime.datetime,
    ) -> datetime.datetime:
        """
        Fetches logs output from the job container and writes all entries after
        a given time to stderr.

        Args:
            client: An initialized `ContainerInstanceManagementClient`
            container_group: The container group that holds the job container.
            last_log_time: The timestamp of the last output line already streamed.

        Returns:
            The time of the most recent output line written by this call.
        """
        logs = self._get_logs(client, container_group)
        return self._stream_output(logs, last_log_time)

    def _get_logs(
        self,
        client: ContainerInstanceManagementClient,
        container_group: ContainerGroup,
        max_lines: int = 100,
    ) -> str:
        """
        Gets the most container logs up to a given maximum.

        Args:
            client: An initialized `ContainerInstanceManagementClient`
            container_group: The container group that holds the job container.
            max_lines: The number of log lines to pull. Defaults to 100.

        Returns:
            A string containing the requested log entries, one per line.
        """
        container = self._get_container(container_group)

        logs: Union[Logs, None] = None
        try:
            logs = client.containers.list_logs(
                resource_group_name=self.resource_group_name,
                container_group_name=container_group.name,
                container_name=container.name,
                tail=max_lines,
                timestamps=True,
            )
        except HttpResponseError:
            # Trying to get logs when the container is under heavy CPU load sometimes
            # results in an error, but we won't want to raise an exception and stop
            # monitoring the flow. Instead, log the error and carry on so we can try to
            # get all missed logs on the next check.
            self.logger.warning(
                f"{self._log_prefix}: Unable to retrieve logs from container "
                f"{container.name}. Trying again in {self.task_watch_poll_interval}s"
            )

        return logs.content if logs else ""

    def _stream_output(
        self, log_content: Union[str, None], last_log_time: datetime.datetime
    ) -> datetime.datetime:
        """
        Writes each entry from a string of log lines to stderr.

        Args:
            log_content: A string containing Azure container logs.
            last_log_time: The timestamp of the last output line already streamed.

        Returns:
            The time of the most recent output line written by this call.
        """
        if not log_content:
            # nothing to stream
            return last_log_time

        log_lines = log_content.split("\n")

        last_written_time = last_log_time

        for log_line in log_lines:
            # skip if the line is blank or whitespace
            if not log_line.strip():
                continue

            line_parts = log_line.split(" ")
            # timestamp should always be before first space in line
            line_timestamp = line_parts[0]
            line = " ".join(line_parts[1:])

            try:
                line_time = dateutil.parser.parse(line_timestamp)
                if line_time > last_written_time:
                    self._write_output_line(line)
                    last_written_time = line_time
            except dateutil.parser.ParserError as e:
                self.logger.debug(
                    (
                        f"{self._log_prefix}: Unable to parse timestamp from Azure "
                        "log line: %s"
                    ),
                    log_line,
                    exc_info=e,
                )

        return last_written_time

    def _get_environment(self):
        """
        Generates a dictionary of all environment variables to send to the
        ACI container.
        """
        return {**self._base_environment(), **self.env}

    @property
    def _log_prefix(self) -> str:
        """
        Internal property for generating a prefix for logs where `name` may be null
        """
        if self.name is not None:
            return f"AzureContainerInstanceJob {self.name!r}"
        else:
            return "AzureContainerInstanceJob"

    @staticmethod
    def _provisioning_succeeded(container_group: ContainerGroup) -> bool:
        """
        Determines whether ACI container group provisioning was successful.

        Args:
            container_group: a container group returned by the Azure SDK.

        Returns:
            True if provisioning was successful, False otherwise.
        """
        if not container_group:
            return False

        return (
            container_group.provisioning_state
            == ContainerGroupProvisioningState.SUCCEEDED
            and len(container_group.containers) == 1
        )

    @staticmethod
    def _write_output_line(line: str):
        """
        Writes a line of output to stderr.
        """
        print(line, file=sys.stderr)
