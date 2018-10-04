# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
Environments in the Prefect library serve as containers capable of serializing, loading and executing
flows. Currently, available environments consist of a Docker `ContainerEnvironment`
and a `LocalEnvironment`.

Environments will be a crucial element in the execution lifecycle for a Flow
through the Prefect Server.

**Note:** Due to ongoing development this file is subject to large changes.
"""

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
from typing import Any, Iterable, Optional
import uuid

import docker
from cryptography.fernet import Fernet
import toml

import prefect
from prefect.utilities.json import ObjectAttributesCodec, Serializable


class Secret(Serializable):
    """
    A Secret is a serializable object used to represent a secret key & value that is
    to live inside of an environment.

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

        Args:
            - flow (prefect.Flow): the Flow to build the environment for

        Returns:
            - bytes: a key required for interacting with the environment
        """
        raise NotImplementedError()

    def run(self, key: bytes, cli_cmd: str) -> Optional[bytes]:
        """Issue a CLI command to the environment.

        Args:
            - key (bytes): the environment key
            - cli_cmd (str): the command to issue
        """
        raise NotImplementedError()


class ContainerEnvironment(Environment):
    """
    Container class used to represent a Docker container.

    **Note:** this class is still experimental, does not fully support all functions,
    and is subject to change.

    Args:
        - image (str): The image to pull that is used as a base for the Docker container
        *Note*: An image that is provided must be able to handle `python` and `pip` commands
        - name (str, optional): The name the image will take on the registry
        - tag (str, optional): The tag for this container
        - python_dependencies (list, optional): The list of pip installable python packages
        that will be installed on build of the Docker container
        - secrets ([Secret], optional): Iterable list of Secrets that will be used as
        environment variables in the Docker container
    """

    def __init__(
        self,
        image: str,
        name: str = None,
        tag: str = None,
        python_dependencies: list = None,
        secrets: Iterable[Secret] = None,
    ) -> None:
        self._image = image
        self._name = name or str(uuid.uuid4())
        self._tag = tag or str(uuid.uuid4())
        self._python_dependencies = python_dependencies or []
        self.last_container_id = None

        super().__init__(secrets=secrets)

    @property
    def python_dependencies(self) -> list:
        """Get the specified Python dependencies"""
        return self._python_dependencies

    @property
    def image(self) -> str:
        """Get the container's base image"""
        return self._image

    @property
    def name(self) -> str:
        """Get the name of the image"""
        return self._name

    @property
    def tag(self) -> str:
        """Get the container's tag"""
        return self._tag

    @property
    def client(self) -> "docker.client.DockerClient":
        """Get the environment's client"""
        return docker.from_env()

    def build(self, flow: "prefect.Flow", push: bool = True) -> tuple:
        """Build the Docker container

        Args:
            - flow (prefect.Flow): Flow to be placed in container
            - push (bool): Whether or not to push to registry after build

        Returns:
            - tuple: tuple consisting of (`docker.models.images.Image`, iterable logs)
        """
        with tempfile.TemporaryDirectory() as tempdir:

            # Write temp file of serialized registry to same location of Dockerfile
            self.serialized_registry_to_file(flow=flow, directory=tempdir)

            self.pull_image()

            path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

            if Path(path).is_file():
                config_data = toml.load(path)
            else:
                config_data = {}

            # Make copy of config.toml in temporary directory
            with open("{}/config.toml".format(tempdir), "w") as config_file:
                toml.dump(config_data, config_file)

            self.create_dockerfile(directory=tempdir)

            client = docker.from_env()

            if not config_data["REGISTRY_URL"]:
                raise Exception("Registry not specified.")

            image_name = os.path.join(config_data["REGISTRY_URL"], self.name)

            print("Building the flow's container environment...")
            client.images.build(
                path=tempdir, tag="{}:{}".format(image_name, self.tag), forcerm=True
            )

            if push:
                self.push(image_name, self.tag)

            # Remove the image locally after being pushed
            client.images.remove("{}:{}".format(image_name, self.tag))

            return {"image_name": self.name, "image_tag": self.tag, "flow_id": flow.id}

    def run(self, key: bytes, cli_cmd: str) -> None:
        """Run a command in the Docker container

        Args:
            - cli_cmd (str, optional): An initial cli_cmd that will be executed on container run

        Returns:
            - `docker.models.containers.Container` object

        """
        client = docker.from_env()

        running_container = client.containers.run(
            self.tag, command=cli_cmd, detach=True
        )
        self.last_container_id = running_container.id

        return running_container

    def push(self, image_name: str, image_tag: str) -> None:
        """Push this environment to a registry

        Args:
            - image_name (str): Name for the image
            - image_tag (str): Tag for the image

        Returns:
            - None
        """
        client = docker.from_env()

        # Another possibility would be to name/tag each push with the flow's ID
        # This would ensure the uniqueness each time a flow is built and allow for
        # only the need of specifying the flow ID when talking to the registry
        print("Pushing image to the registry...")
        client.images.push(image_name, tag=image_tag)

    def pull_image(self) -> None:
        """Pull the image specified so it can be built.

        In order for the docker python library to use a base image it must be pulled
        from either the main docker registry or a separate registry that must be set in
        the environment variables.
        """
        client = docker.from_env()
        client.images.pull(self.image)

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
                for secret in self.secrets:
                    env_vars += "ENV {}={}\n".format(secret.name, secret.value)

            # Due to prefect being a private repo it currently will require a
            # personal access token. Once pip installable this will change and there won't
            # be a need for the personal access token or git anymore.
            # *Note*: this currently prevents alpine images from being used

            file_contents = textwrap.dedent(
                """\
                FROM {image}

                RUN apt-get -qq -y update && apt-get -qq -y install --no-install-recommends --no-install-suggests git

                RUN pip install pip --upgrade
                RUN pip install wheel
                {env_vars}
                {pip_installs}

                RUN mkdir $HOME/.prefect/
                COPY registry $HOME/.prefect/registry
                COPY config.toml $HOME/.prefect/config.toml

                ENV PREFECT__REGISTRY__STARTUP_REGISTRY_PATH="$HOME/.prefect/registry"

                RUN git clone -b josh/ie https://$PERSONAL_ACCESS_TOKEN@github.com/PrefectHQ/prefect.git
                RUN cd prefect; git checkout tags/0.3.2; cd ..
                RUN pip install ./prefect
            """.format(
                    image=self.image, env_vars=env_vars, pip_installs=pip_installs
                )
            )

            dockerfile.write(file_contents)

    def serialized_registry_to_file(
        self, flow: "prefect.Flow", directory: str = None
    ) -> None:
        """
        Write a serialized registry to a temporary file so it can be added to the container

        Args:
            - flow (prefect.Flow): The flow to be contained in the serialized registry
            - directory (str, optional): A directory where the Dockerfile will be created,
            if no directory is specified is will be created in the current working directory

        Returns:
            - None
        """

        registry = {}
        flow.register(registry=registry)
        serialized_registry = prefect.core.registry.serialize_registry(
            registry=registry, include_ids=[flow.id]
        )

        path = "{}/registry".format(directory)
        with open(path, "wb+") as registry_file:
            registry_file.write(serialized_registry)


class LocalEnvironment(Environment):
    """
    An environment for running a flow locally.

    Args:
        - encryption_key (str, optional): a Fernet encryption key. One will be generated
        automatically if None is passed.
    """

    def __init__(self, encryption_key: str = None) -> None:
        self.encryption_key = encryption_key or Fernet.generate_key().decode()

    def build(self, flow: "prefect.Flow") -> bytes:
        """
        Build the LocalEnvironment

        Args:
            - flow (Flow): The prefect Flow object to build the environment for

        Returns:
            - bytes: The encrypted and pickled flow registry
        """
        registry = {}  # type: dict
        flow.register(registry=registry)
        serialized = prefect.core.registry.serialize_registry(
            registry=registry, include_ids=[flow.id], encryption_key=self.encryption_key
        )
        return serialized

    def run(self, key: bytes, cli_cmd: str) -> bytes:
        """
        Run a command in the `LocalEnvironment`. This functions by writing a pickled
        flow to temporary memory and then executing prefect CLI commands against it.

        Args:
            - key (bytes): The encrypted and pickled flow registry
            - cli_cmd (str): The prefect CLI command to be run

        Returns:
            - bytes: the output of `subprocess.check_output` from the command run against the flow
        """
        with tempfile.NamedTemporaryFile() as tmp:
            with open(tmp.name, "wb") as f:
                f.write(key)

            env = [
                'PREFECT__REGISTRY__STARTUP_REGISTRY_PATH="{}"'.format(tmp.name),
                'PREFECT__REGISTRY__ENCRYPTION_KEY="{}"'.format(self.encryption_key),
            ]

            return subprocess.check_output(" ".join(env + [cli_cmd]), shell=True)
