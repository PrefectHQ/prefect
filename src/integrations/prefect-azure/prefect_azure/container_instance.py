"""
Helpers for the Azure Container Instance worker.

Use a work pool of type `azure-container-instance` and an Azure Container
Instance worker to run flow runs in Azure Container Instances.

Examples:
    ```bash
    prefect work-pool create --type azure-container-instance my-aci-work-pool
    prefect worker start --pool my-aci-work-pool --type azure-container-instance
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
    Legacy result type retained for compatibility with earlier integrations.
    """
