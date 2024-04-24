"""Module containing Docker host settings."""
from typing import Any, Dict, Optional

import docker
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import get_run_logger
from prefect.blocks.core import Block

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field


class _ContextManageableDockerClient(docker.DockerClient):
    """
    Allow context managing Docker Client, but also allow it to be instantiated without.
    """

    def __enter__(self):
        """
        Enters the context manager.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the context manager and closes the DockerClient.
        """
        self.close()


class DockerHost(Block):
    """
    Block used to manage settings for interacting with a Docker host.

    Attributes:
        base_url: URL to the Docker server, e.g. `unix:///var/run/docker.sock`
            or `tcp://127.0.0.1:1234`. If this is not set, the client will
            be configured from environment variables.
        version: The version of the API to use. Set to auto to
            automatically detect the server's version.
        timeout: Default timeout for API calls, in seconds.
        max_pool_size: The maximum number of connections to save in the pool.
        client_kwargs: Additional keyword arguments to pass to
            `docker.from_env()` or `DockerClient`.

    Examples:
        Get a Docker Host client.
        ```python
        from prefect_docker import DockerHost

        docker_host = DockerHost(
        base_url="tcp://127.0.0.1:1234",
            max_pool_size=4
        )
        with docker_host.get_client() as client:
            ... # Use the client for Docker operations
        ```
    """

    _block_type_name = "Docker Host"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/14a315b79990200db7341e42553e23650b34bb96-250x250.png"  # noqa
    _description = "Store settings for interacting with a Docker host."

    base_url: Optional[str] = Field(
        default=None,
        description="URL to the Docker host.",
        title="Base URL",
        example="unix:///var/run/docker.sock",
    )
    version: str = Field(default="auto", description="The version of the API to use")
    timeout: Optional[int] = Field(
        default=None, description="Default timeout for API calls, in seconds."
    )
    max_pool_size: Optional[int] = Field(
        default=None,
        description="The maximum number of connections to save in the pool.",
    )
    client_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        title="Additional Configuration",
        description=(
            "Additional keyword arguments to pass to "
            "`docker.from_env()` or `DockerClient`."
        ),
    )

    def get_client(self) -> docker.DockerClient:
        """
        Gets a Docker Client to communicate with a Docker host.

        Returns:
            A Docker Client.
        """
        logger = get_run_logger()
        client_kwargs = {
            "version": self.version,
            "timeout": self.timeout,
            "max_pool_size": self.max_pool_size,
            **self.client_kwargs,
        }
        client_kwargs = {
            key: value for key, value in client_kwargs.items() if value is not None
        }
        if self.base_url is None:
            logger.debug(
                f"Creating a Docker client from "
                f"environment variables, using {self.version} version."
            )
            client = _ContextManageableDockerClient.from_env(**client_kwargs)
        else:
            logger.debug(
                f"Creating a Docker client to {self.base_url} "
                f"using {self.version} version."
            )
            client = _ContextManageableDockerClient(
                base_url=self.base_url, **client_kwargs
            )
        return client
