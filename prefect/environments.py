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

        super().__init__(secrets=secrets)

    @property
    def python_dependencies(self) -> list:
        """Get the specified Python dependencies"""
        return self._python_dependencies

    def build(self) -> tuple:
        """Build the Docker container"""
        self.pull_image()

        path = os.path.dirname(os.path.realpath(__file__))

        self.create_dockerfile()

        return self.client.images.build(path=path, tag=self.tag, forcerm=True)

    def run(self) -> None:
        """Run the flow in the Docker container"""
        self.client.containers.run(self.tag, "echo 'flow.run placeholder'", detach=True)

    def pull_image(self) -> None:
        """Pull the image specified so it can be built"""
        self.client.images.pull(self.image)

    def create_dockerfile(self) -> None:
        """Creates a dockerfile to use as the container"""
        path = f"{os.path.dirname(os.path.realpath(__file__))}/Dockerfile"
        dockerfile = open(path, "w+")

        file_contents = textwrap.dedent(
            f"""\
            FROM {self.image}

            RUN apt-get update
            RUN apt-get install -y software-properties-common
            RUN add-apt-repository ppa:jonathonf/python-3.6
            RUN apt-get update
            RUN apt-get install -y build-essential python3.6 python3-pip
            RUN python3.6 -m pip install pip --upgrade
            RUN python3.6 -m pip install wheel
        """
        )

        dockerfile.write(file_contents)

# How will the docker file get the flow code in it?
# How should we go about installing prefect?