from typing import Any

import docker

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class ListImages(Task):
    """
    Task for listing Docker images.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - repository_name (str, optional): Only show images belonging to this repository;
            if not provided then it will list all images from the local Docker server
        - all_layers (bool, optional): Show intermediate image layers
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
    """

    def __init__(
        self,
        repository_name: str = None,
        all_layers: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
        **kwargs: Any
    ):
        self.repository_name = repository_name
        self.all_layers = all_layers
        self.docker_server_url = docker_server_url

        super().__init__(**kwargs)

    @defaults_from_attrs("repository_name", "all_layers", "docker_server_url")
    def run(
        self,
        repository_name: str = None,
        all_layers: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
    ) -> list:
        """
        Task run method.

        Args:
            - repository_name (str, optional): Only show images belonging to this repository;
                if not provided then it will list all images from the local Docker server
            - all_layers (bool, optional): Show intermediate image layers
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided

        Return:
            - list: A list of dictionaries containing information about the images found
        """
        client = docker.APIClient(base_url=docker_server_url)

        return client.images(name=repository_name, all=all_layers)
