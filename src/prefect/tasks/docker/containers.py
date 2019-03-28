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
        docker_server_url: str = "unix:///var/run/docker.sock",
        **kwargs: Any
    ):
        self.image_name = image_name
        self.command = command
        self.detach = detach
        self.entrypoint = entrypoint
        self.environment = environment
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
        docker_server_url: str = "unix:///var/run/docker.sock",
    ) -> str:
        """
        Task run method.

        Args:
            - image_name (str, optional): Name of the image to run
            - command (Union[list, str], optional): A single command or a list of commands to run
            - detach (bool, optional): Run container in the background
            - entrypoint (Union[str, list]): The entrypoint for the container
            - environment (Union[dict, list]): Environment variables to set inside the container,
                as a dictionary or a list of strings in the format ["SOMEVARIABLE=xxx"].
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided

        Returns:
            - str: A string representing the container id

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
        )

        return container.get("Id")


class GetContainerLogs(Task):
    """
    Task for getting the logs of a Docker container. *Note:* This does not stream logs.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - container_id (str, optional): The id of a container to retrieve logs from
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        **kwargs: Any
    ):
        self.container_id = container_id
        self.docker_server_url = docker_server_url

        super().__init__(**kwargs)

    @defaults_from_attrs("container_id", "docker_server_url")
    def run(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
    ) -> str:
        """
        Task run method.

        Args:
            - container_id (str, optional): The id of a container to retrieve logs from
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided

        Returns:
            - str: A string representation of the logs from the container

        Raises:
            - ValueError: if `container_id` is `None`
        """
        if not container_id:
            raise ValueError("A container id must be provided.")

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        return client.logs(container=container_id)


class ListContainers(Task):
    """
    Task for listing Docker containers.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - all_containers (bool, optional): Show all containers. Only running containers are shown by default
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        all_containers: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
        **kwargs: Any
    ):
        self.all_containers = all_containers
        self.docker_server_url = docker_server_url

        super().__init__(**kwargs)

    @defaults_from_attrs("all_containers", "docker_server_url")
    def run(
        self,
        all_containers: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
    ) -> list:
        """
        Task run method.

        Args:
            - all_containers (bool, optional): Show all containers. Only running containers are shown by default
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided

        Returns:
            - list: A list of dicts, one per container
        """
        client = docker.APIClient(base_url=docker_server_url, version="auto")

        return client.containers(all=all_containers)


class StartContainer(Task):
    """
    Task for starting a Docker container which runs the (optional) command it was created with.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - container_id (str, optional): The id of a container to start
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        **kwargs: Any
    ):
        self.container_id = container_id
        self.docker_server_url = docker_server_url

        super().__init__(**kwargs)

    @defaults_from_attrs("container_id", "docker_server_url")
    def run(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
    ) -> None:
        """
        Task run method.

        Args:
            - container_id (str, optional): The id of a container to start
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided

        Raises:
            - ValueError: if `container_id` is `None`
        """
        if not container_id:
            raise ValueError("A container id must be provided.")

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        client.start(container=container_id)


class StopContainer(Task):
    """
    Task for stopping a Docker container.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - container_id (str, optional): The id of a container to stop
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        **kwargs: Any
    ):
        self.container_id = container_id
        self.docker_server_url = docker_server_url

        super().__init__(**kwargs)

    @defaults_from_attrs("container_id", "docker_server_url")
    def run(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
    ) -> None:
        """
        Task run method.

        Args:
            - container_id (str, optional): The id of a container to stop
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided

        Raises:
            - ValueError: if `container_id` is `None`
        """
        if not container_id:
            raise ValueError("A container id must be provided.")

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        client.stop(container=container_id)
