from typing import Any, Union

from prefect import Task
from prefect.engine.signals import FAIL
from prefect.utilities.tasks import defaults_from_attrs


class CreateContainer(Task):
    """
    Task for creating a Docker container and optionally running a command.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - image_name (str, optional): Name of the image to run
        - container_name (str, optional): A name for the container
        - command (Union[list, str], optional): A single command or a list of commands to run
        - detach (bool, optional): Run container in the background
        - entrypoint (Union[str, list], optional): The entrypoint for the container
        - environment (Union[dict, list], optional): Environment variables to set inside the container,
            as a dictionary or a list of strings in the format ["SOMEVARIABLE=xxx"]
        - volumes (Union[str, list], optional): List of paths inside the container to use as volumes
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - host_config (dict, optional): Extra keyword arguments to pass through to the Docker call
            (cf. method `create_host_config`). See https://docker-py.readthedocs.io/en/stable/api.html
            for more details
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the Docker
            call (cf. method `create_container`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        image_name: str = None,
        container_name: str = None,
        command: Union[list, str] = None,
        detach: bool = False,
        entrypoint: Union[list, str] = None,
        environment: Union[list, dict] = None,
        volumes: Union[str, list] = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        host_config: dict = None,
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.image_name = image_name
        self.container_name = container_name
        self.command = command
        self.detach = detach
        self.entrypoint = entrypoint
        self.environment = environment
        self.volumes = volumes
        self.docker_server_url = docker_server_url
        self.host_config = host_config
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "image_name",
        "container_name",
        "command",
        "detach",
        "entrypoint",
        "environment",
        "volumes",
        "docker_server_url",
        "host_config",
        "extra_docker_kwargs",
    )
    def run(
        self,
        image_name: str = None,
        container_name: str = None,
        command: Union[list, str] = None,
        detach: bool = False,
        entrypoint: Union[list, str] = None,
        environment: Union[list, dict] = None,
        volumes: Union[str, list] = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        host_config: dict = None,
        extra_docker_kwargs: dict = None,
    ) -> str:
        """
        Task run method.

        Args:
            - image_name (str, optional): Name of the image to run
            - container_name (str, optional): A name for the container
            - command (Union[list, str], optional): A single command or a list of commands to run
            - detach (bool, optional): Run container in the background
            - entrypoint (Union[str, list]): The entrypoint for the container
            - environment (Union[dict, list]): Environment variables to set inside the container,
                as a dictionary or a list of strings in the format ["SOMEVARIABLE=xxx"]
            - volumes (Union[str, list], optional): List of paths inside the container to use as volumes
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - host_config (dict, optional): Extra keyword arguments to pass through to the Docker call
                (cf. method `create_host_config`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Dockercall (cf. method `create_container`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - str: A string representing the container id

        Raises:
            - ValueError: if `image_name` is `None`
        """
        if not image_name:
            raise ValueError("An image name must be provided.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        if host_config is not None:
            host_config = client.create_host_config(**host_config)

        self.logger.debug(
            f"Creating container from image {image_name} with command: {command}"
        )
        container = client.create_container(
            image=image_name,
            name=container_name,
            command=command,
            detach=detach,
            entrypoint=entrypoint,
            environment=environment,
            volumes=volumes,
            host_config=host_config,
            **(extra_docker_kwargs or dict()),
        )

        container_id = container.get("Id")

        self.logger.debug(
            f"Created container {container_id} from image {image_name} with command: {command}"
        )

        return container_id


class GetContainerLogs(Task):
    """
    Task for getting the logs of a Docker container. *Note:* This does not stream logs.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - container_id (str, optional): The id of a container to retrieve logs from
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the Docker
            call (cf. method `logs`). See https://docker-py.readthedocs.io/en/stable/api.html for more
            details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.container_id = container_id
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("container_id", "docker_server_url", "extra_docker_kwargs")
    def run(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> str:
        """
        Task run method.

        Args:
            - container_id (str, optional): The id of a container to retrieve logs from
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `logs`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - str: A string representation of the logs from the container

        Raises:
            - ValueError: if `container_id` is `None`
        """
        if not container_id:
            raise ValueError("A container id must be provided.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Gathering logs from container {container_id}")

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        api_result = client.logs(
            container=container_id, **(extra_docker_kwargs or dict())
        ).decode()

        self.logger.debug(f"Gathered logs from container {container_id}")

        return api_result


class ListContainers(Task):
    """
    Task for listing Docker containers.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - all_containers (bool, optional): Show all containers. Only running
            containers are shown by default
        - filters (dict, optional): Filter the results. See
            https://docker-py.readthedocs.io/en/stable/containers.html for more details
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the Docker
            call (cf. method `containers`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        all_containers: bool = False,
        filters: dict = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.all_containers = all_containers
        self.filters = filters
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "all_containers", "filters", "docker_server_url", "extra_docker_kwargs"
    )
    def run(
        self,
        all_containers: bool = False,
        filters: dict = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> list:
        """
        Task run method.

        Args:
            - all_containers (bool, optional): Show all containers. Only
                running containers are shown by default
            - filters (dict, optional): Filter the results. See
                https://docker-py.readthedocs.io/en/stable/containers.html for more details
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `container`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - list: A list of dicts, one per container
        """
        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug("Listing all containers")
        client = docker.APIClient(base_url=docker_server_url, version="auto")
        api_result = client.containers(
            all=all_containers, filters=filters, **(extra_docker_kwargs or dict())
        )
        self.logger.debug("Listed all containers")
        return api_result


class StartContainer(Task):
    """
    Task for starting a Docker container that runs the (optional) command it was created with.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - container_id (str, optional): The id of a container to start
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `start`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.container_id = container_id
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("container_id", "docker_server_url", "extra_docker_kwargs")
    def run(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> None:
        """
        Task run method.

        Args:
            - container_id (str, optional): The id of a container to start
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `start`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Raises:
            - ValueError: if `container_id` is `None`
        """
        if not container_id:
            raise ValueError("A container id must be provided.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Starting container {container_id}")
        client = docker.APIClient(base_url=docker_server_url, version="auto")

        client.start(container=container_id, **(extra_docker_kwargs or dict()))
        self.logger.debug(f"Started container {container_id}")


class StopContainer(Task):
    """
    Task for stopping a Docker container.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - container_id (str, optional): The id of a container to stop
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `stop`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.container_id = container_id
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("container_id", "docker_server_url", "extra_docker_kwargs")
    def run(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> None:
        """
        Task run method.

        Args:
            - container_id (str, optional): The id of a container to stop
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `stop`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Raises:
            - ValueError: if `container_id` is `None`
        """
        if not container_id:
            raise ValueError("A container id must be provided.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Stopping container {container_id}")
        client = docker.APIClient(base_url=docker_server_url, version="auto")

        client.stop(container=container_id, **(extra_docker_kwargs or dict()))
        self.logger.debug(f"Stopped container {container_id}")


class RemoveContainer(Task):
    """
    Task for removing a Docker container.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - container_id (str, optional): The id of a container to remove
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `remove_container`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.container_id = container_id
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("container_id", "docker_server_url", "extra_docker_kwargs")
    def run(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> None:
        """
        Task run method.

        Args:
            - container_id (str, optional): The id of a container to remove
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `remove_container`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Raises:
            - ValueError: if `container_id` is `None`
        """
        if not container_id:
            raise ValueError("A container id must be provided.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Removing container {container_id}")
        client = docker.APIClient(base_url=docker_server_url, version="auto")

        client.remove_container(
            container=container_id, **(extra_docker_kwargs or dict())
        )
        self.logger.debug(f"Removed container {container_id}")


class WaitOnContainer(Task):
    """
    Task for waiting on an already started Docker container.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - container_id (str, optional): The id of a container to start
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - raise_on_exit_code (bool, optional): whether to raise a `FAIL` signal
            for a nonzero exit code; defaults to `True`
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `wait`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        raise_on_exit_code: bool = True,
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.container_id = container_id
        self.docker_server_url = docker_server_url
        self.raise_on_exit_code = raise_on_exit_code
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "container_id", "docker_server_url", "raise_on_exit_code", "extra_docker_kwargs"
    )
    def run(
        self,
        container_id: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        raise_on_exit_code: bool = True,
        extra_docker_kwargs: dict = None,
    ) -> None:
        """
        Task run method.

        Args:
            - container_id (str, optional): The id of a container to wait on
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - raise_on_exit_code (bool, optional): whether to raise a `FAIL`
                signal for a nonzero exit code; defaults to `True`
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `wait`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - dict: a dictionary with `StatusCode` and `Error` keys

        Raises:
            - ValueError: if `container_id` is `None`
            - FAIL: if `raise_on_exit_code` is `True` and the container exits
                with a nonzero exit code
        """
        if not container_id:
            raise ValueError("A container id must be provided.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Waiting on container {container_id}")
        client = docker.APIClient(base_url=docker_server_url, version="auto")

        result = client.wait(container=container_id, **(extra_docker_kwargs or dict()))
        if raise_on_exit_code and (
            (result.get("Error") is not None) or result.get("StatusCode")
        ):
            try:
                logs = client.logs(container_id)
                self.logger.error(logs.decode())
            except Exception as exc:
                self.logger.exception(exc)
            raise FAIL(
                "{id} failed with exit code {code}: {msg}".format(
                    id=container_id,
                    code=result.get("StatusCode"),
                    msg=result.get("Error"),
                )
            )
        self.logger.debug(f"Container {container_id} has finished")

        return result
