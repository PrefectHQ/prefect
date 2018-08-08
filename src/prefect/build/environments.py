import base64
import tempfile
import textwrap
from typing import Any, Iterable

import cloudpickle
import docker

import prefect
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


class PickleEnvironment(Environment):
    """A pickle environment type for pickling a flow"""

    from cryptography.fernet import Fernet

    def __init__(self, encryption_key: str = None):
        """Initialize the PickleEnvironment class"""
        if encryption_key:
            self.encryption_key = self.encryption_key
        else:
            self.encryption_key = self.Fernet.generate_key()

    def build(self, flow: "prefect.Flow") -> bytes:
        """
        Pickles a flow and returns the bytes

        Args:
            flow: A prefect Flow object

        Returns:
            An encrypted pickled flow
        """
        serialized_pickle = base64.b64encode(cloudpickle.dumps(flow))
        serialized_pickle = self.Fernet(self.encryption_key).encrypt(serialized_pickle)
        return serialized_pickle

    def run(self):
        """Run"""
        pass

    def info(self, pickle: bytes) -> dict:
        """
        Returns the serialized flow from a pickle

        Args:
            pickle: A pickled Flow object

        Returns:
            A dictionary of the serialized flow

        Raises:
            TypeError if the unpickeld object is not a Flow
        """

        serialized_pickle = self.Fernet(self.encryption_key).decrypt(pickle).decode()
        flow = cloudpickle.loads(base64.b64decode(serialized_pickle))

        if not isinstance(flow, prefect.Flow):
            raise TypeError("Object is not a pickled Flow")

        return flow.serialize()
