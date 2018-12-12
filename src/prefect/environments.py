# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
Environments in the Prefect library serve as containers capable of serializing, loading and executing
flows. Currently, available environments consist of a Docker `ContainerEnvironment`
and a `LocalEnvironment`.

Environments will be a crucial element in the execution lifecycle for a Flow
through the Prefect Server.

**Note:** Due to ongoing development this file is subject to large changes.
"""

import base64
import logging
import os
import shlex
import subprocess
import tempfile
import textwrap
import uuid
from pathlib import Path
from typing import Optional

import docker
import toml
from cryptography.fernet import Fernet

import prefect
from prefect import config
from prefect.client import Secret
from prefect.serializers import Serializer


class Environment:
    """
    Base class for Environments
    """

    def __init__(self) -> None:
        pass

    def build(self, flow: "prefect.Flow") -> dict:
        """
        Build the environment. Returns a JSON object that can be used to interact with the
        environment.

        Args:
            - flow (prefect.Flow): the Flow to build the environment for

        Returns:
            - dict: a JSON document that can be used to recreate the environment later.
        """
        raise NotImplementedError()

    def run(self, env_key: dict, cli_cmd: str) -> Optional[bytes]:
        """
        Issue a CLI command to the environment.

        Args:
            - env_key (dict): the result of calling `self.build()`
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
        *Note*: Images must include Python 3.4+ and `pip`.
        - registry_url (str, optional): The registry to push the image to
        - python_dependencies (list, optional): The list of pip installable python packages
        that will be installed on build of the Docker container
        - secrets (list, optional): A list of secret value names to be loaded into the environment
    """

    def __init__(
        self,
        image: str,
        registry_url: str = None,
        python_dependencies: list = None,
        secrets: list = None,
    ) -> None:
        self.image = image
        self.registry_url = registry_url
        self.python_dependencies = python_dependencies or []
        self.secrets = secrets or []

    def build(
        self, flow: "prefect.Flow", push: bool = True
    ) -> "prefect.environments.ContainerEnvironment":
        """Build the Docker container

        Args:
            - flow (prefect.Flow): Flow to be placed in container
            - push (bool): Whether or not to push to registry after build

        Returns:
            - ContainerEnvironment: an instance of this environment
        """

        image_name = str(uuid.uuid4())
        image_tag = str(uuid.uuid4())

        with tempfile.TemporaryDirectory() as tempdir:

            # Write temp file of serialized registry to same location of Dockerfile
            self.serialized_registry_to_file(flow=flow, directory=tempdir)

            self.pull_image()

            path = config.user_config_path

            if Path(path).is_file():
                config_data = toml.load(path)
            else:
                config_data = {}

            # Make copy of config.toml in temporary directory
            with open("{}/config.toml".format(tempdir), "w") as config_file:
                toml.dump(config_data, config_file)

            self.create_dockerfile(directory=tempdir)

            client = docker.from_env()

            if not self.registry_url:
                raise ValueError("Registry not specified.")

            full_name = os.path.join(self.registry_url, image_name)

            logging.info("Building the flow's container environment...")
            client.images.build(
                path=tempdir, tag="{}:{}".format(full_name, image_tag), forcerm=True
            )

            if push:
                self.push(full_name, image_tag)

            # Remove the image locally after being pushed
            client.images.remove("{}:{}".format(full_name, image_tag))

            return dict(name=image_name, tag=image_tag)

    def run(self, env_key: dict, cli_cmd: str = None) -> None:
        """Run a command in the Docker container

        Args:
            - env_key (dict): a JSON document containing details about container, as produced
                by the `build()` method.
            - cli_cmd (str, optional): An initial cli_cmd that will be executed on container run

        Returns:
            - `docker.models.containers.Container` object

        """
        client = docker.from_env()

        running_container = client.containers.run(
            env_key["tag"], command=cli_cmd, detach=True
        )

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

        logging.info("Pushing image to the registry...")

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
                for dependency in self.python_dependencies:
                    pip_installs += "RUN pip install {}\n".format(dependency)

            # Generate the creation of environment variables from Secrets
            env_vars = ""
            if self.secrets:
                for name in self.secrets:
                    env_vars += "ENV {}={}\n".format(name, Secret(name).get())

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

                RUN mkdir /root/.prefect/
                COPY registry /root/.prefect/registry
                COPY config.toml /root/.prefect/config.toml

                ENV PREFECT__REGISTRY__STARTUP_REGISTRY_PATH="/root/.prefect/registry"
                ENV PREFECT__USER_CONFIG_PATH="/root/.prefect/config.toml"


                RUN git clone https://$PERSONAL_ACCESS_TOKEN@github.com/PrefectHQ/prefect.git
                RUN pip install ./prefect
            """.format(
                    image=self.image, pip_installs=pip_installs, env_vars=env_vars
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
    An environment for running a flow locally. This class may be used for debugging and
    testing.

    Args:
        - encryption_key (bytes, optional): a Fernet encryption key. One will be generated
        automatically if None is passed.
    """

    def __init__(self, encryption_key: bytes = None) -> None:
        # the config value might be an empty string, since configs don't support None
        if encryption_key is None:
            encryption_key = Fernet.generate_key()
        self.encryption_key = encryption_key

    def build(self, flow: "prefect.Flow") -> dict:
        """
        Build the LocalEnvironment

        Args:
            - flow (Flow): The prefect Flow object to build the environment for

        Returns:
            - dict: a dictionary containing the serialized registry
        """
        registry = {}  # type: dict
        flow.register(registry=registry)
        serialized = prefect.core.registry.serialize_registry(
            registry=registry, include_ids=[flow.id], encryption_key=self.encryption_key
        )
        return {"serialized registry": base64.b64encode(serialized).decode()}

    def run(self, env_key: dict, cli_cmd: str) -> bytes:
        """
        Run a command in the `LocalEnvironment`. This functions by writing a pickled
        flow to temporary memory and then executing prefect CLI commands against it.

        Args:
            - env_key (dict): a JSON document containing details about container, as produced
                by the `build()` method.
            - cli_cmd (str): The prefect CLI command to be run

        Returns:
            - bytes: the output of `subprocess.check_output` from the command run against the flow
        """
        with tempfile.NamedTemporaryFile() as tmp:
            with open(tmp.name, "wb") as f:
                f.write(base64.b64decode(env_key["serialized registry"]))

            env_vars = {
                "PREFECT__REGISTRY__STARTUP_REGISTRY_PATH": tmp.name,
                "PREFECT__REGISTRY__ENCRYPTION_KEY": self.encryption_key,
            }

            env = os.environ.copy()
            env.update(env_vars)

            return subprocess.check_output(
                shlex.split(cli_cmd), stderr=subprocess.STDOUT, env=env
            )
