from typing import Any, Union

import docker

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class CreateContainer(Task):
    """
    Task for creating a Docker container and optionally running a command.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - image_name (str, optional): Name of the image to run
        - command (Union[list, str], optional): A single command or a list of commands to run
        - detach (bool, optional): Run container in the background
        - entrypoint (Union[str, list]): The entrypoint for the container
        - environment (Union[dict, list]): Environment variables to set inside the container,
            as a dictionary or a list of strings in the format ["SOMEVARIABLE=xxx"].
        - name (str, optional): A name to give the container
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        image_name: str = None,
        command: Union[list, str] = None,
        detach: bool = False,
        entrypoint: Union[list, str] = None,
        environment: Union[list, dict] = None,
        name: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        **kwargs: Any
    ):
        self.image_name = name
        self.command = command
        self.detach = detach
        self.entrypoint = entrypoint
        self.environment = environment
        self.name = name
        self.docker_server_url = docker_server_url

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "image_name",
        "command",
        "detach",
        "entrypoint",
        "environment",
        "docker_server_url",
    )
    def run(
        self,
        image_name: str = None,
        command: Union[list, str] = None,
        detach: bool = False,
        entrypoint: Union[list, str] = None,
        environment: Union[list, dict] = None,
        name: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
    ) -> None:
        """
        Task run method.

        Args:
            - image_name (str, optional): Name of the image to run
            - command (Union[list, str], optional): A single command or a list of commands to run
            - detach (bool, optional): Run container in the background
            - entrypoint (Union[str, list]): The entrypoint for the container
            - environment (Union[dict, list]): Environment variables to set inside the container,
                as a dictionary or a list of strings in the format ["SOMEVARIABLE=xxx"].
            - name (str, optional): A name to give the container
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided

        Return:
            - dict: A dictionary with an image ‘Id’ key and a ‘Warnings’ key

        Raises:
            - ValueError: if `image_name` is `None`
        """
        if not image_name:
            raise ValueError("An image name must be provided.")

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        container = client.create_container(
            image=image_name,
            command=command,
            detach=detach,
            entrypoint=entrypoint,
            environment=environment,
            name=name,
        )

        return container
