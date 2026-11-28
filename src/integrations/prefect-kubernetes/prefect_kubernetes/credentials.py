"""Module for defining Kubernetes credential handling and client generation."""

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, Type, Union

import yaml
from kubernetes_asyncio import config
from kubernetes_asyncio.client import (
    ApiClient,
    AppsV1Api,
    BatchV1Api,
    Configuration,
    CoreV1Api,
    CustomObjectsApi,
)
from kubernetes_asyncio.config.config_exception import ConfigException
from pydantic import Field, SecretStr, field_validator
from typing_extensions import Literal, Self

from prefect.blocks.abstract import CredentialsBlock
from prefect.blocks.core import Block
from prefect.utilities.collections import listrepr

KubernetesClient = Union[AppsV1Api, BatchV1Api, CoreV1Api, CustomObjectsApi]

K8S_CLIENT_TYPES = {
    "apps": AppsV1Api,
    "batch": BatchV1Api,
    "core": CoreV1Api,
    "custom_objects": CustomObjectsApi,
}


class KubernetesClusterConfig(Block):
    """
    Stores configuration for interaction with Kubernetes clusters.

    See `from_file` for creation.

    Attributes:
        config: The entire loaded YAML contents of a kubectl config file
        context_name: The name of the kubectl context to use

    Example:
        Load a saved Kubernetes cluster config:
        ```python
        from prefect_kubernetes.credentials import import KubernetesClusterConfig

        cluster_config_block = KubernetesClusterConfig.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Kubernetes Cluster Config"
    _logo_url = "https://raw.githubusercontent.com/PrefectHQ/prefect/420d0d6a78bb6df1fc18bcf188fdad43c1d22ea9/assets/block-logos/kubernetes.png"
    _documentation_url = "https://www.prefect.io/docs/integrations/prefect-kubernetes"  # noqa
    config: Dict = Field(
        default=..., description="The entire contents of a kubectl config file."
    )
    context_name: str = Field(
        default=..., description="The name of the kubectl context to use."
    )

    @field_validator("config", mode="before")
    @classmethod
    def parse_yaml_config(cls, value):
        if isinstance(value, str):
            return yaml.safe_load(value)
        return value

    @classmethod
    def from_file(
        cls: Type[Self], path: Optional[Path] = None, context_name: Optional[str] = None
    ) -> Self:
        """
        Create a cluster config from the a Kubernetes config file.

        By default, the current context in the default Kubernetes config file will be
        used.

        An alternative file or context may be specified.

        The entire config file will be loaded and stored.
        """

        path = Path(path or config.kube_config.KUBE_CONFIG_DEFAULT_LOCATION)
        path = path.expanduser().resolve()

        # Determine the context
        (
            existing_contexts,
            current_context,
        ) = config.kube_config.list_kube_config_contexts(config_file=str(path))
        context_names = {ctx["name"] for ctx in existing_contexts}
        if context_name:
            if context_name not in context_names:
                raise ValueError(
                    f"Context {context_name!r} not found. "
                    f"Specify one of: {listrepr(context_names, sep=', ')}."
                )
        else:
            context_name = current_context["name"]

        # Load the entire config file
        config_file_contents = path.read_text()
        config_dict = yaml.safe_load(config_file_contents)
        return cls(config=config_dict, context_name=context_name)

    async def get_api_client(self) -> "ApiClient":
        """
        Returns a Kubernetes API client for this cluster config.
        """
        return await config.kube_config.new_client_from_config_dict(
            config_dict=self.config, context=self.context_name
        )

    async def configure_client(self) -> None:
        """
        Activates this cluster configuration by loading the configuration into the
        Kubernetes Python client. After calling this, Kubernetes API clients can use
        this config's context.
        """
        await config.kube_config.load_kube_config_from_dict(
            config_dict=self.config, context=self.context_name
        )


class BaseKubernetesCredentials(CredentialsBlock, ABC):
    """Abstract base class for Kubernetes credentials blocks.

    Subclasses must implement `get_client` to yield an authenticated,
    resource-specific Kubernetes API client.
    """

    _logo_url = "https://raw.githubusercontent.com/PrefectHQ/prefect/420d0d6a78bb6df1fc18bcf188fdad43c1d22ea9/assets/block-logos/kubernetes.png"  # noqa
    _documentation_url = "https://www.prefect.io/docs/integrations/prefect-kubernetes"  # noqa

    @abstractmethod
    def get_client(
        self,
        client_type: Literal["apps", "batch", "core", "custom_objects"],
        configuration: Optional[Configuration] = None,
    ) -> AbstractAsyncContextManager[KubernetesClient]:
        """Return an async context manager yielding a resource-specific Kubernetes client.

        Args:
            client_type: The resource-specific type of Kubernetes client to retrieve.
            configuration: Optional `kubernetes_asyncio.client.Configuration` to use.

        Yields:
            An authenticated, resource-specific Kubernetes API client.
        """

    async def get_resource_specific_client(
        self,
        client_type: str,
        api_client: ApiClient,
    ) -> KubernetesClient:
        """Instantiate a resource-specific Kubernetes API client.

        Args:
            client_type: The Kubernetes API client type for interacting with specific
                Kubernetes resources.
            api_client: A configured `ApiClient` instance.

        Returns:
            KubernetesClient: An authenticated, resource-specific Kubernetes client.

        Raises:
            ValueError: If `client_type` is not a valid Kubernetes API client type.
        """
        try:
            return K8S_CLIENT_TYPES[client_type](api_client)
        except KeyError:
            raise ValueError(
                f"Invalid client type provided '{client_type}'."
                f" Must be one of {listrepr(K8S_CLIENT_TYPES.keys())}."
            )


class KubernetesCredentials(BaseKubernetesCredentials):
    """Credentials block for generating configured Kubernetes API clients.

    Attributes:
        cluster_config: A `KubernetesClusterConfig` block holding a JSON kube
            config for a specific kubernetes context.

    Example:
        Load stored Kubernetes credentials:
        ```python
        from prefect_kubernetes.credentials import KubernetesCredentials

        kubernetes_credentials = KubernetesCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Kubernetes Credentials"

    cluster_config: Optional[KubernetesClusterConfig] = None

    @asynccontextmanager
    async def get_client(
        self,
        client_type: Literal["apps", "batch", "core", "custom_objects"],
        configuration: Optional[Configuration] = None,
    ) -> AsyncGenerator[KubernetesClient, None]:
        """Convenience method for retrieving a Kubernetes API client for deployment resources.

        Args:
            client_type: The resource-specific type of Kubernetes client to retrieve.
            configuration: Optional `kubernetes_asyncio.client.Configuration` to use.

        Yields:
            An authenticated, resource-specific Kubernetes API client.

        Example:
            ```python
            from prefect_kubernetes.credentials import KubernetesCredentials

            async with KubernetesCredentials.get_client("core") as core_v1_client:
                pods = await core_v1_client.list_namespaced_pod()
                for pod in pods.items:
                    print(pod.metadata.name)
            ```
        """
        client_configuration = configuration or Configuration()
        if self.cluster_config:
            config_dict = self.cluster_config.config
            context = self.cluster_config.context_name

            # Use Configuration to load configuration from a dictionary
            await config.load_kube_config_from_dict(
                config_dict=config_dict,
                context=context,
                client_configuration=client_configuration,
            )
        else:
            try:
                config.load_incluster_config(client_configuration=client_configuration)
            except config.ConfigException:
                # If in-cluster config fails, load the local kubeconfig
                await config.load_kube_config(
                    client_configuration=client_configuration,
                )
        async with ApiClient(configuration=client_configuration) as api_client:
            try:
                yield await self.get_resource_specific_client(
                    client_type, api_client=api_client
                )
            finally:
                await api_client.close()

    async def get_resource_specific_client(
        self,
        client_type: str,
        api_client: ApiClient,
    ) -> KubernetesClient:
        """
        Utility function for configuring a generic Kubernetes client.
        It will attempt to connect to a Kubernetes cluster in three steps with
        the first successful connection attempt becoming the mode of communication with
        a cluster:

        1. It will first attempt to use a `KubernetesCredentials` block's
        `cluster_config` to configure a client using
        `KubernetesClusterConfig.configure_client`.

        2. Attempt in-cluster connection (will only work when running on a pod).

        3. Attempt out-of-cluster connection using the default location for a
        kube config file.

        Args:
            client_type: The Kubernetes API client type for interacting with specific
                Kubernetes resources.
            api_client: A configured `ApiClient` instance.

        Returns:
            KubernetesClient: An authenticated, resource-specific Kubernetes Client.

        Raises:
            ValueError: If `client_type` is not a valid Kubernetes API client type.
        """

        if self.cluster_config:
            await self.cluster_config.configure_client()
        else:
            try:
                config.load_incluster_config()
            except ConfigException:
                await config.load_kube_config()

        return await super().get_resource_specific_client(
            client_type, api_client=api_client
        )


class KubernetesApiKeyCredentials(BaseKubernetesCredentials):
    """Credentials block for authenticating with a Kubernetes cluster using an API key.

    Attributes:
        host: The URL of the Kubernetes API server.
        api_key: The API key or bearer token for authenticating with the
            Kubernetes API server.
        api_key_prefix: The prefix for the API key in the Authorization header.
            Defaults to `'Bearer'`. Set to `None` to send the API key without a prefix.
        ssl_ca_cert: Path to a CA certificate file used to verify the Kubernetes
            API server.
        verify_ssl: Whether to verify SSL certificates when connecting to the
            Kubernetes API server.

    Example:
        Load stored Kubernetes API key credentials:
        ```python
        from prefect_kubernetes.credentials import KubernetesApiKeyCredentials

        kubernetes_credentials = KubernetesApiKeyCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Kubernetes API Key Credentials"

    host: str = Field(
        default=...,
        description="The URL of the Kubernetes API server.",
    )
    api_key: SecretStr = Field(
        default=...,
        description="The API key or bearer token for authenticating with the Kubernetes API server.",
    )
    api_key_prefix: Optional[str] = Field(
        default="Bearer",
        description="The prefix for the API key in the Authorization header.",
    )
    ssl_ca_cert: Optional[str] = Field(
        default=None,
        description="Path to a CA certificate file used to verify the Kubernetes API server.",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates when connecting to the Kubernetes API server.",
    )

    @asynccontextmanager
    async def get_client(
        self,
        client_type: Literal["apps", "batch", "core", "custom_objects"],
        configuration: Optional[Configuration] = None,
    ) -> AsyncGenerator[KubernetesClient, None]:
        """Convenience method for retrieving a Kubernetes API client authenticated with an API key.

        Args:
            client_type: The resource-specific type of Kubernetes client to retrieve.
            configuration: Optional `kubernetes_asyncio.client.Configuration` to use.

        Yields:
            An authenticated, resource-specific Kubernetes API client.

        Example:
            ```python
            from prefect_kubernetes.credentials import KubernetesApiKeyCredentials

            credentials = KubernetesApiKeyCredentials(
                host="https://my-cluster.example.com:6443",
                api_key="my-token",
            )
            async with credentials.get_client("core") as core_v1_client:
                pods = await core_v1_client.list_namespaced_pod("default")
            ```
        """
        if configuration is not None:
            client_configuration = configuration
            client_configuration.host = self.host
        else:
            client_configuration = Configuration(host=self.host)

        client_configuration.api_key["BearerToken"] = self.api_key.get_secret_value()
        if self.api_key_prefix is not None:
            client_configuration.api_key_prefix["BearerToken"] = self.api_key_prefix
        client_configuration.verify_ssl = self.verify_ssl
        if self.ssl_ca_cert is not None:
            client_configuration.ssl_ca_cert = self.ssl_ca_cert

        async with ApiClient(configuration=client_configuration) as api_client:
            try:
                yield await self.get_resource_specific_client(
                    client_type, api_client=api_client
                )
            finally:
                await api_client.close()
