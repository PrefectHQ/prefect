import os
import textwrap
from typing import Any, Iterable

import docker

from prefect.utilities.json import ObjectAttributesCodec, Serializable


class Secret(Serializable):
    _json_codec = ObjectAttributesCodec

    def __init__(self, name: str) -> None:
        self.name = name
        self._value = None

    @property
    def value(self) -> Any:
        """Get the secret's value"""
        return self._value

    @value.setter
    def value(self, value: Any) -> None:
        """Set the secret's value"""
        self._value = value


class Environment(Serializable):
    """
    Base class for Environments
    """

    _json_codec = ObjectAttributesCodec

    def __init__(self, secrets: Iterable[Secret] = None) -> None:
        self.secrets = secrets or []

    def build(self) -> None:
        """Build the environment"""
        raise NotImplementedError()


class Container(Environment):
    """
    Container class used to represent a Docker container
    """

    def __init__(
        self,
        image: str,
        tag: str = None,
        python_dependencies: list = None,
        secrets: Iterable[Secret] = None,
    ) -> None:
        if tag is None:
            tag = image

        self.image = image
        self.tag = tag
        self._python_dependencies = python_dependencies
        self.client = docker.from_env()
        self.running_container_id = None

        super().__init__(secrets=secrets)

    @property
    def python_dependencies(self) -> list:
        """Get the specified Python dependencies"""
        return self._python_dependencies

    def build(self) -> tuple:
        """Build the Docker container

        Args:
            None

        Returns:
            tuple with (docker.models.images.Image, iterable logs)

        """
        path = os.path.dirname(os.path.realpath(__file__))

        self.pull_image()
        self.create_dockerfile()

        container = self.client.images.build(path=path, tag=self.tag, forcerm=True)

        # Remove the temporary Dockerfile
        os.remove("{}/Dockerfile".format(path))

        return container

    def run(self) -> None:
        """Run the flow in the Docker container

        Args:
            None

        Returns:
            A docker.models.containers.Container object

        """

        # Kill instance of this container currently running
        if self.running_container_id:
            self.client.containers.get(self.running_container_id).kill()

        running_container = self.client.containers.run(self.tag, detach=True)
        self.running_container_id = running_container.id

        return running_container

    def pull_image(self) -> None:
        """Pull the image specified so it can be built.

        In order for the docker python library to use a base image it must be pulled
        from either the main docker registry or a separate registry that must be set in
        the environment variables.

        Args:
            None

        Returns:
            None
        """
        self.client.images.pull(self.image)

    def create_dockerfile(self) -> None:
        """Creates a dockerfile to use as the container.

        In order for the docker python library to build a container it needs a
        Dockerfile that it can use to define the container. This function takes the
        image and python_dependencies then writes them to a file called Dockerfile.

        Args:
            None

        Returns:
            None
        """
        path = "{}/Dockerfile".format(os.path.dirname(os.path.realpath(__file__)))
        dockerfile = open(path, "w+")

        # Generate RUN pip install commands for python dependencies
        pip_installs = ""
        for dependency in self.python_dependencies:
            pip_installs += "RUN python3.6 -m pip install {}\n".format(dependency)

        file_contents = textwrap.dedent(
            """\
            FROM {}

            RUN apt-get update
            RUN apt-get install -y software-properties-common
            RUN add-apt-repository ppa:jonathonf/python-3.6
            RUN apt-get update
            RUN apt-get install -y build-essential python3.6 python3-pip
            RUN python3.6 -m pip install pip --upgrade
            RUN python3.6 -m pip install wheel
            {}

            RUN echo "pip install prefect"
            RUN echo "add the flow code"
        """.format(
                self.image, pip_installs
            )
        )

        dockerfile.write(file_contents)
