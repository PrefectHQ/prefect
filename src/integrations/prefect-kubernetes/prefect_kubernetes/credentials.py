"""Module for defining Kubernetes credential handling and client generation."""

from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, Optional, Type, Union

import yaml
from kubernetes import config
from kubernetes.client import (
    ApiClient,
    AppsV1Api,
    BatchV1Api,
    Configuration,
    CoreV1Api,
    CustomObjectsApi,
)
from kubernetes.config.config_exception import ConfigException
from pydantic.version import VERSION as PYDANTIC_VERSION
from typing_extensions import Literal, Self

from prefect.blocks.core import Block
from prefect.utilities.collections import listrepr

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, validator
else:
    from pydantic import Field, validator


KubernetesClient = Union[AppsV1Api, BatchV1Api, CoreV1Api]

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
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/2d0b896006ad463b49c28aaac14f31e00e32cfab-250x250.png"
    _documentation_url = "https://prefecthq.github.io/prefect-kubernetes/credentials/#prefect_kubernetes.credentials.KubernetesClusterConfig"  # noqa
    config: Dict = Field(
        default=..., description="The entire contents of a kubectl config file."
    )
    context_name: str = Field(
        default=..., description="The name of the kubectl context to use."
    )

    @validator("config", pre=True)
    def parse_yaml_config(cls, value):
        if isinstance(value, str):
            return yaml.safe_load(value)
        return value

    @classmethod
    def from_file(cls: Type[Self], path: Path = None, context_name: str = None) -> Self:
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

    def get_api_client(self) -> "ApiClient":
        """
        Returns a Kubernetes API client for this cluster config.
        """
        return config.kube_config.new_client_from_config_dict(
            config_dict=self.config, context=self.context_name
        )

    def configure_client(self) -> None:
        """
        Activates this cluster configuration by loading the configuration into the
        Kubernetes Python client. After calling this, Kubernetes API clients can use
        this config's context.
        """
        config.kube_config.load_kube_config_from_dict(
            config_dict=self.config, context=self.context_name
        )


class KubernetesCredentials(Block):
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
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/2d0b896006ad463b49c28aaac14f31e00e32cfab-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-kubernetes/credentials/#prefect_kubernetes.credentials.KubernetesCredentials"  # noqa

    cluster_config: Optional[KubernetesClusterConfig] = None

    @contextmanager
    def get_client(
        self,
        client_type: Literal["apps", "batch", "core", "custom_objects"],
        configuration: Optional[Configuration] = None,
    ) -> Generator[KubernetesClient, None, None]:
        """Convenience method for retrieving a Kubernetes API client for deployment resources.

        Args:
            client_type: The resource-specific type of Kubernetes client to retrieve.

        Yields:
            An authenticated, resource-specific Kubernetes API client.

        Example:
            ```python
            from prefect_kubernetes.credentials import KubernetesCredentials

            with KubernetesCredentials.get_client("core") as core_v1_client:
                for pod in core_v1_client.list_namespaced_pod():
                    print(pod.metadata.name)
            ```
        """
        client_config = configuration or Configuration()

        with ApiClient(configuration=client_config) as generic_client:
            try:
                yield self.get_resource_specific_client(client_type)
            finally:
                generic_client.rest_client.pool_manager.clear()

    def get_resource_specific_client(
        self,
        client_type: str,
    ) -> Union[AppsV1Api, BatchV1Api, CoreV1Api]:
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

        Returns:
            KubernetesClient: An authenticated, resource-specific Kubernetes Client.

        Raises:
            ValueError: If `client_type` is not a valid Kubernetes API client type.
        """

        if self.cluster_config:
            self.cluster_config.configure_client()
        else:
            try:
                config.load_incluster_config()
            except ConfigException:
                config.load_kube_config()

        try:
            return K8S_CLIENT_TYPES[client_type]()
        except KeyError:
            raise ValueError(
                f"Invalid client type provided '{client_type}'."
                f" Must be one of {listrepr(K8S_CLIENT_TYPES.keys())}."
            )
