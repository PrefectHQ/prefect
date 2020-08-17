import json
from typing import Any

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
        - filters (dict, optional): Filter the results. See
            https://docker-py.readthedocs.io/en/stable/images.html for more details
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `images`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        repository_name: str = None,
        all_layers: bool = False,
        filters: dict = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.repository_name = repository_name
        self.all_layers = all_layers
        self.filters = filters
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "repository_name",
        "all_layers",
        "filters",
        "docker_server_url",
        "extra_docker_kwargs",
    )
    def run(
        self,
        repository_name: str = None,
        all_layers: bool = False,
        filters: dict = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> list:
        """
        Task run method.

        Args:
            - repository_name (str, optional): Only show images belonging to this repository;
                if not provided then it will list all images from the local Docker server
            - all_layers (bool, optional): Show intermediate image layers
            - filters (dict, optional): Filter the results. See
                https://docker-py.readthedocs.io/en/stable/images.html for more details
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `images`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - list: A list of dictionaries containing information about the images found
        """
        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Listing images from {repository_name}")
        client = docker.APIClient(base_url=docker_server_url, version="auto")
        api_result = client.images(
            name=repository_name,
            all=all_layers,
            filters=filters,
            **(extra_docker_kwargs or dict()),
        )
        self.logger.debug(f"Listed images from {repository_name}")

        return api_result


class PullImage(Task):
    """
    Task for pulling a Docker image.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - repository (str, optional): The repository to pull the image from
        - tag (str, optional): The tag of the image to pull; if not specified then the
            `latest` tag will be pulled
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `pull`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        repository: str = None,
        tag: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.repository = repository
        self.tag = tag
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "repository", "tag", "docker_server_url", "extra_docker_kwargs"
    )
    def run(
        self,
        repository: str = None,
        tag: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> str:
        """
        Task run method.

        Args:
            - repository (str, optional): The repository to pull the image from
            - tag (str, optional): The tag of the image to pull; if not specified then the
                `latest` tag will be pulled
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `pull`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - str: The output from Docker for pulling the image

        Raises:
            - ValueError: if `repository` is `None`
        """
        if not repository:
            raise ValueError("A repository to pull the image from must be specified.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        client = docker.APIClient(base_url=docker_server_url, version="auto")
        self.logger.debug(f"Pulling image {repository}:{tag}")
        api_result = client.pull(
            repository=repository, tag=tag, **(extra_docker_kwargs or dict())
        )

        self.logger.debug(f"Pulled image {repository}:{tag}")
        return api_result


class PushImage(Task):
    """
    Task for pushing a Docker image.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - repository (str, optional): The repository to push the image to
        - tag (str, optional): The tag for the image to push; if not specified then the
            `latest` tag will be pushed
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `push`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        repository: str = None,
        tag: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.repository = repository
        self.tag = tag
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "repository", "tag", "docker_server_url", "extra_docker_kwargs"
    )
    def run(
        self,
        repository: str = None,
        tag: str = None,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> str:
        """
        Task run method.

        Args:
            - repository (str, optional): The repository to push the image to
            - tag (str, optional): The tag for the image to push; if not specified then the
                `latest` tag will be pushed
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `push`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - str: The output from Docker for pushing the image

        Raises:
            - ValueError: if `repository` is `None`
        """
        if not repository:
            raise ValueError("A repository to push the image to must be specified.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Pushing image {repository}:{tag} to the registry")
        client = docker.APIClient(base_url=docker_server_url, version="auto")
        api_result = client.push(
            repository=repository, tag=tag, **(extra_docker_kwargs or dict())
        )
        self.logger.debug(f"Pushed image {repository}:{tag} to the registry")
        return api_result


class RemoveImage(Task):
    """
    Task for removing a Docker image.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - image (str, optional): The image to remove
        - force (bool, optional): Force removal of the image
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `remove_image`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        image: str = None,
        force: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.image = image
        self.force = force
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("image", "force", "docker_server_url", "extra_docker_kwargs")
    def run(
        self,
        image: str = None,
        force: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> None:
        """
        Task run method.

        Args:
            - image (str, optional): The image to remove
            - force (bool, optional): Force removal of the image
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `remove_image`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Raises:
            - ValueError: if `image` is `None`
        """
        if not image:
            raise ValueError("The name of an image to remove must be provided.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Removing image {image}")

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        client.remove_image(image=image, force=force, **(extra_docker_kwargs or dict()))
        self.logger.debug(f"Removed image {image}")


class TagImage(Task):
    """
    Task for tagging a Docker image.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - image (str, optional): The image to tag
        - repository (str, optional): The repository to set for the tag
        - tag (str, optional): The tag name for the image
        - force (bool, optional): Force tagging of the image
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `tag`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        image: str = None,
        repository: str = None,
        tag: str = None,
        force: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.image = image
        self.repository = repository
        self.tag = tag
        self.force = force
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "image",
        "repository",
        "tag",
        "force",
        "docker_server_url",
        "extra_docker_kwargs",
    )
    def run(
        self,
        image: str = None,
        repository: str = None,
        tag: str = None,
        force: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> bool:
        """
        Task run method.

        Args:
            - image (str, optional): The image to tag
            - repository (str, optional): The repository to set for the tag
            - tag (str, optional): The tag name for the image
            - force (bool, optional): Force tagging of the image
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `tag`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - bool: Whether or not the tagging was successful

        Raises:
            - ValueError: if either `image` or `repository` are `None`
        """
        if not image or not repository:
            raise ValueError("Both image and repository must be provided.")

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Tagging image {repository}/{image}:{tag}")

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        api_result = client.tag(
            image=image,
            repository=repository,
            tag=tag,
            force=force,
            **(extra_docker_kwargs or dict()),
        )
        self.logger.debug(f"Tagged image {repository}/{image}:{tag}")
        return api_result


class BuildImage(Task):
    """
    Task for building a Docker image.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - path (str, optional): The path to the directory containing the Dockerfile
        - tag (str, optional): The tag to give the final image
        - nocache (bool, optional): Don't use cache when set to `True`
        - rm (bool, optional): Remove intermediate containers; defaults to `True`
        - forcerm (bool, optional): Always remove intermediate containers, even after
            unsuccessful builds; defaults to `False`
        - docker_server_url (str, optional): URL for the Docker server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
            can be provided
        - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
            Docker call (cf. method `build`). See
            https://docker-py.readthedocs.io/en/stable/api.html for more details
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        path: str = None,
        tag: str = None,
        nocache: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
        **kwargs: Any,
    ):
        self.path = path
        self.tag = tag
        self.nocache = nocache
        self.rm = rm
        self.forcerm = forcerm
        self.docker_server_url = docker_server_url
        self.extra_docker_kwargs = extra_docker_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "path",
        "tag",
        "nocache",
        "rm",
        "forcerm",
        "docker_server_url",
        "extra_docker_kwargs",
    )
    def run(
        self,
        path: str = None,
        tag: str = None,
        nocache: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        docker_server_url: str = "unix:///var/run/docker.sock",
        extra_docker_kwargs: dict = None,
    ) -> None:
        """
        Task run method.

        Args:
            - path (str, optional): The path to the directory containing the Dockerfile
            - tag (str, optional): The tag to give the final image
            - nocache (bool, optional): Don't use cache when set to `True`
            - rm (bool, optional): Remove intermediate containers; defaults to `True`
            - forcerm (bool, optional): Always remove intermediate containers, even after
                unsuccessful builds; defaults to `False`
            - docker_server_url (str, optional): URL for the Docker server. Defaults to
                `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`
                can be provided
            - extra_docker_kwargs (dict, optional): Extra keyword arguments to pass through to the
                Docker call (cf. method `build`). See
                https://docker-py.readthedocs.io/en/stable/api.html for more details

        Returns:
            - List[dict]: a cleaned dictionary of the output of `client.build`

        Raises:
            - ValueError: if either `path` is `None`
        """
        if not path:
            raise ValueError(
                "A path to a directory containing a Dockerfile must be provided."
            )

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        self.logger.debug(f"Building image from {path} with tag {tag}")

        client = docker.APIClient(base_url=docker_server_url, version="auto")

        payload = [
            line
            for line in client.build(
                path=path,
                tag=tag,
                nocache=nocache,
                rm=rm,
                forcerm=forcerm,
                **(extra_docker_kwargs or dict()),
            )
        ]
        self.logger.debug(f"Built image from {path} with tag {tag}")
        output = [
            json.loads(line.decode("utf-8"))
            for resp in payload
            for line in resp.split(b"\r\n")
            if line
        ]
        return output
