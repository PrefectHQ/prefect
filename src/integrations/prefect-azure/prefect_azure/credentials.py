"""Credential classes used to perform authenticated interactions with Azure"""

import functools
from typing import TYPE_CHECKING, Any, Dict, Optional

from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as ADefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.resource import ResourceManagementClient
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, SecretStr, root_validator
else:
    from pydantic import Field, SecretStr, root_validator

try:
    from azure.cosmos import CosmosClient

    if TYPE_CHECKING:
        from azure.cosmos import ContainerProxy, DatabaseProxy
except ModuleNotFoundError:
    pass  # a descriptive error will be raised in get_client

try:
    from azure.storage.blob.aio import BlobClient, BlobServiceClient, ContainerClient
except ModuleNotFoundError:
    pass  # a descriptive error will be raised in get_client

try:
    from azureml.core.authentication import ServicePrincipalAuthentication
    from azureml.core.workspace import Workspace
except ModuleNotFoundError:
    pass  # a descriptive error will be raised in get_workspace

from prefect.blocks.core import Block

HELP_URLS = {
    "blob_storage": "https://docs.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python#copy-your-credentials-from-the-azure-portal",  # noqa
    "cosmos_db": "https://docs.microsoft.com/en-us/azure/cosmos-db/sql/create-sql-api-python#update-your-connection-string",  # noqa
    "ml_datastore": "https://github.com/Azure/MachineLearningNotebooks/blob/master/how-to-use-azureml/manage-azureml-service/authentication-in-azureml/authentication-in-azureml.ipynb",  # noqa
}
HELP_FMT = "Please visit {help_url} for retrieving the proper connection string."


def _raise_help_msg(key: str):
    """
    Raises a helpful error message.

    Args:
        key: the key to access HELP_URLS
    """

    def outer(func):
        """
        Used for decorator.
        """

        @functools.wraps(func)
        def inner(*args, **kwargs):
            """
            Used for decorator.
            """
            try:
                return func(*args, **kwargs)
            except NameError as exc:
                raise ImportError(
                    f"To use prefect_azure.{key}, install prefect-azure with the "
                    f"'{key}' extra: `pip install 'prefect_azure[{key}]'`"
                ) from exc
            except ValueError as exc:
                raise ValueError(HELP_FMT.format(help_url=HELP_URLS[key])) from exc

        return inner

    return outer


class AzureBlobStorageCredentials(Block):
    """
    Stores credentials for authenticating with Azure Blob Storage.

    Args:
        account_url: The URL for your Azure storage account. If provided, the account
            URL will be used to authenticate with the discovered default Azure
            credentials.
        connection_string: The connection string to your Azure storage account. If
            provided, the connection string will take precedence over the account URL.

    Example:
        Load stored Azure Blob Storage credentials and retrieve a blob service client:
        ```python
        from prefect_azure import AzureBlobStorageCredentials

        azure_credentials_block = AzureBlobStorageCredentials.load("BLOCK_NAME")

        blob_service_client = azure_credentials_block.get_blob_client()
        ```
    """

    _block_type_name = "Azure Blob Storage Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureBlobStorageCredentials"  # noqa

    connection_string: Optional[SecretStr] = Field(
        default=None,
        description=(
            "The connection string to your Azure storage account. If provided, the "
            "connection string will take precedence over the account URL."
        ),
    )
    account_url: Optional[str] = Field(
        default=None,
        title="Account URL",
        description=(
            "The URL for your Azure storage account. If provided, the account "
            "URL will be used to authenticate with the discovered default "
            "Azure credentials."
        ),
    )

    @root_validator
    def check_connection_string_or_account_url(
        cls, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Checks that either a connection string or account URL is provided, not both.
        """
        has_account_url = values.get("account_url") is not None
        has_conn_str = values.get("connection_string") is not None
        if not has_account_url and not has_conn_str:
            raise ValueError(
                "Must provide either a connection string or an account URL."
            )
        if has_account_url and has_conn_str:
            raise ValueError(
                "Must provide either a connection string or account URL, but not both."
            )
        return values

    @_raise_help_msg("blob_storage")
    def get_client(self) -> "BlobServiceClient":
        """
        Returns an authenticated base Blob Service client that can be used to create
        other clients for Azure services.

        Example:
            Create an authorized Blob Service session
            ```python
            import os
            import asyncio
            from prefect import flow
            from prefect_azure import AzureBlobStorageCredentials

            @flow
            async def example_get_client_flow():
                connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
                azure_credentials = AzureBlobStorageCredentials(
                    connection_string=connection_string,
                )
                async with azure_credentials.get_client() as blob_service_client:
                    # run other code here
                    pass

            asyncio.run(example_get_client_flow())
            ```
        """
        if self.connection_string is None:
            return BlobServiceClient(
                account_url=self.account_url,
                credential=ADefaultAzureCredential(),
            )

        return BlobServiceClient.from_connection_string(
            self.connection_string.get_secret_value()
        )

    @_raise_help_msg("blob_storage")
    def get_blob_client(self, container, blob) -> "BlobClient":
        """
        Returns an authenticated Blob client that can be used to
        download and upload blobs.

        Args:
            container: Name of the Blob Storage container to retrieve from.
            blob: Name of the blob within this container to retrieve.

        Example:
            Create an authorized Blob session
            ```python
            import os
            import asyncio
            from prefect import flow
            from prefect_azure import AzureBlobStorageCredentials

            @flow
            async def example_get_blob_client_flow():
                connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
                azure_credentials = AzureBlobStorageCredentials(
                    connection_string=connection_string,
                )
                async with azure_credentials.get_blob_client(
                    "container", "blob"
                ) as blob_client:
                    # run other code here
                    pass

            asyncio.run(example_get_blob_client_flow())
            ```
        """
        if self.connection_string is None:
            return BlobClient(
                account_url=self.account_url,
                container_name=container,
                credential=ADefaultAzureCredential(),
                blob_name=blob,
            )

        blob_client = BlobClient.from_connection_string(
            self.connection_string.get_secret_value(), container, blob
        )
        return blob_client

    @_raise_help_msg("blob_storage")
    def get_container_client(self, container) -> "ContainerClient":
        """
        Returns an authenticated Container client that can be used to create clients
        for Azure services.

        Args:
            container: Name of the Blob Storage container to retrieve from.

        Example:
            Create an authorized Container session
            ```python
            import os
            import asyncio
            from prefect import flow
            from prefect_azure import AzureBlobStorageCredentials

            @flow
            async def example_get_container_client_flow():
                connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
                azure_credentials = AzureBlobStorageCredentials(
                    connection_string=connection_string,
                )
                async with azure_credentials.get_container_client(
                    "container"
                ) as container_client:
                    # run other code here
                    pass

            asyncio.run(example_get_container_client_flow())
            ```
        """
        if self.connection_string is None:
            return ContainerClient(
                account_url=self.account_url,
                container_name=container,
                credential=ADefaultAzureCredential(),
            )

        container_client = ContainerClient.from_connection_string(
            self.connection_string.get_secret_value(), container
        )
        return container_client


class AzureCosmosDbCredentials(Block):
    """
    Block used to manage Cosmos DB authentication with Azure.
    Azure authentication is handled via the `azure` module through
    a connection string.

    Args:
        connection_string: Includes the authorization information required.

    Example:
        Load stored Azure Cosmos DB credentials:
        ```python
        from prefect_azure import AzureCosmosDbCredentials
        azure_credentials_block = AzureCosmosDbCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Azure Cosmos DB Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureCosmosDbCredentials"  # noqa

    connection_string: SecretStr = Field(
        default=..., description="Includes the authorization information required."
    )

    @_raise_help_msg("cosmos_db")
    def get_client(self) -> "CosmosClient":
        """
        Returns an authenticated Cosmos client that can be used to create
        other clients for Azure services.

        Example:
            Create an authorized Cosmos session
            ```python
            import os
            from prefect import flow
            from prefect_azure import AzureCosmosDbCredentials

            @flow
            def example_get_client_flow():
                connection_string = os.getenv("AZURE_COSMOS_CONNECTION_STRING")
                azure_credentials = AzureCosmosDbCredentials(
                    connection_string=connection_string,
                )
                cosmos_client = azure_credentials.get_client()
                return cosmos_client

            example_get_client_flow()
            ```
        """
        return CosmosClient.from_connection_string(
            self.connection_string.get_secret_value()
        )

    def get_database_client(self, database: str) -> "DatabaseProxy":
        """
        Returns an authenticated Database client.

        Args:
            database: Name of the database.

        Example:
            Create an authorized Cosmos session
            ```python
            import os
            from prefect import flow
            from prefect_azure import AzureCosmosDbCredentials

            @flow
            def example_get_client_flow():
                connection_string = os.getenv("AZURE_COSMOS_CONNECTION_STRING")
                azure_credentials = AzureCosmosDbCredentials(
                    connection_string=connection_string,
                )
                cosmos_client = azure_credentials.get_database_client()
                return cosmos_client

            example_get_database_client_flow()
            ```
        """
        cosmos_client = self.get_client()
        database_client = cosmos_client.get_database_client(database=database)
        return database_client

    def get_container_client(self, container: str, database: str) -> "ContainerProxy":
        """
        Returns an authenticated Container client used for querying.

        Args:
            container: Name of the Cosmos DB container to retrieve from.
            database: Name of the Cosmos DB database.

        Example:
            Create an authorized Container session
            ```python
            import os
            from prefect import flow
            from prefect_azure import AzureBlobStorageCredentials

            @flow
            def example_get_container_client_flow():
                connection_string = os.getenv("AZURE_COSMOS_CONNECTION_STRING")
                azure_credentials = AzureCosmosDbCredentials(
                    connection_string=connection_string,
                )
                container_client = azure_credentials.get_container_client(container)
                return container_client

            example_get_container_client_flow()
            ```
        """
        database_client = self.get_database_client(database)
        container_client = database_client.get_container_client(container=container)
        return container_client


class AzureMlCredentials(Block):
    """
    Block used to manage authentication with AzureML. Azure authentication is
    handled via the `azure` module.

    Args:
        tenant_id: The active directory tenant that the service identity belongs to.
        service_principal_id: The service principal ID.
        service_principal_password: The service principal password/key.
        subscription_id: The Azure subscription ID containing the workspace.
        resource_group: The resource group containing the workspace.
        workspace_name: The existing workspace name.

    Example:
        Load stored AzureML credentials:
        ```python
        from prefect_azure import AzureMlCredentials
        azure_ml_credentials_block = AzureMlCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "AzureML Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureMlCredentials"  # noqa

    tenant_id: str = Field(
        default=...,
        description="The active directory tenant that the service identity belongs to.",
    )
    service_principal_id: str = Field(
        default=..., description="The service principal ID."
    )
    service_principal_password: SecretStr = Field(
        default=..., description="The service principal password/key."
    )
    subscription_id: str = Field(
        default=...,
        description="The Azure subscription ID containing the workspace, in format: '00000000-0000-0000-0000-000000000000'.",  # noqa
    )
    resource_group: str = Field(
        default=..., description="The resource group containing the workspace."
    )
    workspace_name: str = Field(default=..., description="The existing workspace name.")

    @_raise_help_msg("ml_datastore")
    def get_workspace(self) -> "Workspace":
        """
        Returns an authenticated base Workspace that can be used in
        Azure's Datasets and Datastores.

        Example:
            Create an authorized workspace
            ```python
            import os
            from prefect import flow
            from prefect_azure import AzureMlCredentials
            @flow
            def example_get_workspace_flow():
                azure_credentials = AzureMlCredentials(
                    tenant_id="tenant_id",
                    service_principal_id="service_principal_id",
                    service_principal_password="service_principal_password",
                    subscription_id="subscription_id",
                    resource_group="resource_group",
                    workspace_name="workspace_name"
                )
                workspace_client = azure_credentials.get_workspace()
                return workspace_client
            example_get_workspace_flow()
            ```
        """
        service_principal_password = self.service_principal_password.get_secret_value()
        service_principal_authentication = ServicePrincipalAuthentication(
            tenant_id=self.tenant_id,
            service_principal_id=self.service_principal_id,
            service_principal_password=service_principal_password,
        )

        workspace = Workspace(
            subscription_id=self.subscription_id,
            resource_group=self.resource_group,
            workspace_name=self.workspace_name,
            auth=service_principal_authentication,
        )

        return workspace


class AzureContainerInstanceCredentials(Block):
    """
    Block used to manage Azure Container Instances authentication. Stores Azure Service
    Principal authentication data.
    """

    _block_type_name = "Azure Container Instance Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureContainerInstanceCredentials"  # noqa

    client_id: Optional[str] = Field(
        default=None,
        title="Client ID",
        description=(
            "The service principal client ID. "
            "If none of client_id, tenant_id, and client_secret are provided, "
            "will use DefaultAzureCredential; else will need to provide all three to "
            "use ClientSecretCredential."
        ),
    )
    tenant_id: Optional[str] = Field(
        default=None,
        title="Tenant ID",
        description=(
            "The service principal tenant ID."
            "If none of client_id, tenant_id, and client_secret are provided, "
            "will use DefaultAzureCredential; else will need to provide all three to "
            "use ClientSecretCredential."
        ),
    )
    client_secret: Optional[SecretStr] = Field(
        default=None,
        description=(
            "The service principal client secret."
            "If none of client_id, tenant_id, and client_secret are provided, "
            "will use DefaultAzureCredential; else will need to provide all three to "
            "use ClientSecretCredential."
        ),
    )
    credential_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        title="Additional Credential Keyword Arguments",
        description=(
            "Additional keyword arguments to pass to "
            "`ClientSecretCredential` or `DefaultAzureCredential`."
        ),
    )

    @root_validator
    def validate_credential_kwargs(cls, values):
        """
        Validates that if any of `client_id`, `tenant_id`, or `client_secret` are
        provided, all must be provided.
        """
        auth_args = ("client_id", "tenant_id", "client_secret")
        has_any = any(values.get(key) is not None for key in auth_args)
        has_all = all(values.get(key) is not None for key in auth_args)
        if has_any and not has_all:
            raise ValueError(
                "If any of `client_id`, `tenant_id`, or `client_secret` are provided, "
                "all must be provided."
            )
        return values

    def get_container_client(self, subscription_id: str):
        """
        Creates an Azure Container Instances client initialized with data from
        this block's fields and a provided Azure subscription ID.

        Args:
            subscription_id: A valid Azure subscription ID.

        Returns:
            An initialized `ContainerInstanceManagementClient`
        """

        return ContainerInstanceManagementClient(
            credential=self._create_credential(),
            subscription_id=subscription_id,
        )

    def get_resource_client(self, subscription_id: str):
        """
        Creates an Azure resource management client initialized with data from
        this block's fields and a provided Azure subscription ID.

        Args:
            subscription_id: A valid Azure subscription ID.

        Returns:
            An initialized `ResourceManagementClient`
        """

        return ResourceManagementClient(
            credential=self._create_credential(),
            subscription_id=subscription_id,
        )

    def _create_credential(self):
        """
        Creates an Azure credential initialized with data from this block's fields.

        Returns:
            An initialized Azure `TokenCredential` ready to use with Azure SDK client
            classes.
        """
        auth_args = (self.client_id, self.tenant_id, self.client_secret)
        if auth_args == (None, None, None):
            return DefaultAzureCredential(**self.credential_kwargs)

        return ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret.get_secret_value(),
            **self.credential_kwargs,
        )
