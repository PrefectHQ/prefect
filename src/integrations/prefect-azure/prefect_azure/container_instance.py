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

from enum import Enum

from pydantic import BaseModel, Field

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


class AzureContainerInstanceJobResult:
    """
    The result of an `AzureContainerInstanceJob` run.
    """
