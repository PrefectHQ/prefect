# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
Environments in the prefect library serve the purpose of taking fully executable flows,
serializing them, and then putting that flow into some type of environment where it can
be loaded and executed. Currently environments consists of a Docker Container environment
and a LocalEnvironment.

Environments will serve a big purpose on accompanying the execution lifecycle for the
Prefect Server and due to ongoing development this file is subject to large changes.
"""

import base64
import subprocess
import tempfile
import textwrap
from typing import Any, Iterable

import cloudpickle
import docker
from cryptography.fernet import Fernet

import prefect
from prefect.utilities.json import ObjectAttributesCodec, Serializable
from prefect.utilities.tests import set_temporary_config


class Secret(Serializable):
    """
    A Secret is a serializable object used to represent a secret key & value that is
    to live inside of an environment.

    Example secret variables could look something like:
    ```
    key: AWS_SECRET_KEY
    value: secret_encoded_value

    or

    key: TOGGLE
    value: False
    ```

    Args:
        - name (str): The name of the secret to be put into the environment

    The value of the Secret is not set upon initialization and instead functions as a
    property of the Secret. e.g. `my_secret.value = "1234"`
    """

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

    def build(self, flow: "prefect.Flow") -> bytes:
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

    *Note:* this class is still experimental, does not fully support all functions,
    and is subject to change.

    Args:
        - image (str): The image to pull that is used as a base for the Docker container
        - tag (str, optional): The tag for this container
        - python_dependencies (list, optional): The list of pip installable python packages
        that will be installed on build of the Docker container
        - secrets ([Secret], optional): Iterable list of Secrets that will be used as
        environment variables in the Docker container
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

    def build(self, flow) -> tuple:
        """Build the Docker container

        Args:
            - None

        Returns:
            - tuple with (`docker.models.images.Image`, iterable logs)

        """
        with tempfile.TemporaryDirectory() as tempdir:
            self.pull_image()
            self.create_dockerfile(directory=tempdir)

            container = self.client.images.build(
                path=tempdir, tag=self.tag, forcerm=True
            )

            return container

    def run(self, key: bytes, cli_cmd: str, tty: bool = False) -> None:
        """Run a command in the Docker container

        Args:
            - cli_cmd (str, optional): An initial cli_cmd that will be executed on container run
            - tty (bool, optional): Sets whether the container stays active once it is started

        Returns:
            - `docker.models.containers.Container` object

        """

        # Kill instance of this container currently running
        if self.running_container_id:
            self.client.containers.get(self.running_container_id).kill()

        running_container = self.client.containers.run(
            self.tag, command=cli_cmd, tty=tty, detach=True
        )
        self.running_container_id = running_container.id

        return running_container

    def pull_image(self) -> None:
        """Pull the image specified so it can be built.

        In order for the docker python library to use a base image it must be pulled
        from either the main docker registry or a separate registry that must be set in
        the environment variables.

        Args:
            - None

        Returns:
            - None
        """
        self.client.images.pull(self.image)

    def create_dockerfile(self, directory: str = None) -> None:
        """Creates a dockerfile to use as the container.

        In order for the docker python library to build a container it needs a
        Dockerfile that it can use to define the container. This function takes the
        image and python_dependencies then writes them to a file called Dockerfile.

        Args:
            - directory (str, optional): A directory where the Dockerfile will be created,
            if no directory is specified is will be created in the current working directory

        Returns:
            - None
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

    Args:
        - encryption_key (str, optional): a Fernet encryption key. One will be generated
        automatically if None is passed.
    """

    def __init__(self, encryption_key: str = None):
        self.encryption_key = encryption_key or Fernet.generate_key().decode()

    def build(self, flow: "prefect.Flow") -> bytes:
        """
        Build the LocalEnvironment

        Args:
            - flow (Flow): The prefect Flow object

        Returns:
            - bytes: The encrypted and pickled flow registry
        """
        tmp_registration = False
        if flow.id not in prefect.core.registry.REGISTRY:
            tmp_registration = True
            flow.register()
        serialized = prefect.core.registry.serialize_registry(
            include_ids=[flow.id], encryption_key=self.encryption_key
        )
        if tmp_registration:
            del prefect.core.registry.REGISTRY[flow.id]
        return serialized

    def run(self, key: bytes, cli_cmd: str):
        """
        Run a command in the LocalEnvironment. This functions by writing a pickled
        flow to temporary memory and then executing prefect CLI commands against it.

        Args:
            - key (bytes): The encrypted and pickled flow registry
            - cli_cmd (str): The prefect CLI command to be run

        Returns:
            - A subprocess with the command ran against the flow
        """
        with tempfile.NamedTemporaryFile() as tmp:
            with open(tmp.name, "wb") as f:
                f.write(key)

            env = [
                'PREFECT__REGISTRY__LOAD_ON_STARTUP="{}"'.format(tmp.name),
                'PREFECT__REGISTRY__ENCRYPTION_KEY="{}"'.format(self.encryption_key),
            ]

            return subprocess.check_output(" ".join(env + [cli_cmd]), shell=True)
