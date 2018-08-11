import subprocess
from cryptography.fernet import Fernet
import base64
import tempfile
import textwrap
from typing import Any, Iterable

import cloudpickle
import docker

import prefect
from prefect import Flow
from prefect.utilities.json import ObjectAttributesCodec, Serializable
from prefect.utilities.tests import set_temporary_config
from prefect.build import registry


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

    def build(self, flow: Flow) -> bytes:
        """
        Build the environment. Returns a key that must be passed to interact with the
        environment.
        """
        raise NotImplementedError()

    def run(self, key: bytes, cli_cmd: str) -> int:
        """Issue a CLI command to the environment."""
        raise NotImplementedError()


class ContainerEnvironment(Environment):
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
        with tempfile.TemporaryDirectory() as tempdir:
            self.pull_image()
            self.create_dockerfile(directory=tempdir)

            container = self.client.images.build(
                path=tempdir, tag=self.tag, forcerm=True
            )

            return container

    def run(self, command: str = None, tty: bool = False) -> None:
        """Run the flow in the Docker container

        Args:
            command: An initial command that will be executed on container run
            tty: Sets whether the container stays active once it is started

        Returns:
            A docker.models.containers.Container object

        """

        # Kill instance of this container currently running
        if self.running_container_id:
            self.client.containers.get(self.running_container_id).kill()

        running_container = self.client.containers.run(
            self.tag, command=command, tty=tty, detach=True
        )
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

    def create_dockerfile(self, directory: str = None) -> None:
        """Creates a dockerfile to use as the container.

        In order for the docker python library to build a container it needs a
        Dockerfile that it can use to define the container. This function takes the
        image and python_dependencies then writes them to a file called Dockerfile.

        Args:
            directory: A directory where the Dockerfile will be created

        Returns:
            None
        """
        path = "{}/Dockerfile".format(directory)
        with open(path, "w+") as dockerfile:

            # Generate RUN pip install commands for python dependencies
            pip_installs = ""
            if self.python_dependencies:
                pip_installs = r"RUN pip install " + " \\\n".join(
                    self.python_dependencies
                )

            # Generate the creation of environment variables from Secrets
            env_vars = ""
            if self.secrets:
                env_vars += "ENV "
                for secret in self.secrets:
                    env_vars += "{}={} \\\n".format(secret.name, secret.value)

            file_contents = textwrap.dedent(
                """\
                FROM {}

                RUN pip install pip --upgrade
                RUN pip install wheel
                {}
                {}

                # RUN echo "pip install prefect"
                # RUN echo "add the flow code"
            """.format(
                    self.image, env_vars, pip_installs
                )
            )

            dockerfile.write(file_contents)


class LocalEnvironment(Environment):
    """
    An environment for running a flow locally.
    """

    def __init__(self, encryption_key: bytes = None):
        """Initialize the LocalEnvironment class"""
        self.encryption_key = encryption_key or Fernet.generate_key().decode()

    def build(self, flow: Flow) -> bytes:
        """
        Returns:
            - bytes: An encrypted and pickled flow registry
        """
        return registry.serialize_registry(
            registry={flow.key(): flow}, encryption_key=self.encryption_key
        )

    def run(self, key: bytes, cli_cmd: str):

        with tempfile.NamedTemporaryFile() as tmp:
            with open(tmp.name, "wb") as f:
                f.write(key)

            env = [
                'PREFECT__REGISTRY__LOAD_ON_STARTUP="{}"'.format(tmp.name),
                'PREFECT__REGISTRY__ENCRYPTION_KEY="{}"'.format(self.encryption_key),
            ]

            return subprocess.check_output(" ".join(env + [cli_cmd]), shell=True)

