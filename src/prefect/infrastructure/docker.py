import json
import re
import sys
import urllib.parse
import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Generator, List, Optional, Tuple

import anyio.abc
import packaging.version
from pydantic import Field, validator
from typing_extensions import Literal

import prefect
from prefect.blocks.core import Block, SecretStr
from prefect.docker import get_prefect_image_name, parse_image_tag
from prefect.infrastructure.base import Infrastructure, InfrastructureResult
from prefect.settings import PREFECT_API_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.collections import AutoEnum
from prefect.utilities.importtools import lazy_import
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    import docker
    from docker import DockerClient
    from docker.models.containers import Container
else:
    docker = lazy_import("docker")


# Labels to apply to all containers started by Prefect
CONTAINER_LABELS = {
    "io.prefect.version": prefect.__version__,
}


class ImagePullPolicy(AutoEnum):
    IF_NOT_PRESENT = AutoEnum.auto()
    ALWAYS = AutoEnum.auto()
    NEVER = AutoEnum.auto()


class BaseDockerLogin(Block, ABC):
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/2IfXXfMq66mrzJBDFFCHTp/6d8f320d9e4fc4393f045673d61ab612/Moby-logo.png?h=250"
    _block_schema_capabilities = ["docker-login"]

    @abstractmethod
    async def login(self) -> "DockerClient":
        """
        Log in and return an authenticated `DockerClient`.
        (DEPRECATED) Use `get_docker_client` instead of `login`.
        """

    @abstractmethod
    async def get_docker_client(self) -> "DockerClient":
        """
        Log in and return an authenticated `DockerClient`.
        """

    def _login(self, username, password, registry_url, reauth) -> "DockerClient":
        client = self._get_docker_client()

        client.login(
            username=username,
            password=password,
            registry=registry_url,
            # See https://github.com/docker/docker-py/issues/2256 for information on
            # the default value for reauth.
            reauth=reauth,
        )

        return client

    @staticmethod
    def _get_docker_client():
        try:

            with warnings.catch_warnings():
                # Silence warnings due to use of deprecated methods within dockerpy
                # See https://github.com/docker/docker-py/pull/2931
                warnings.filterwarnings(
                    "ignore",
                    message="distutils Version classes are deprecated.*",
                    category=DeprecationWarning,
                )

                docker_client = docker.from_env()

        except docker.errors.DockerException as exc:
            raise RuntimeError(f"Could not connect to Docker.") from exc

        return docker_client


class DockerRegistry(BaseDockerLogin):
    """
    Connects to a Docker registry.

    Requires a Docker Engine to be connectable.

    Attributes:
        username: The username to log into the registry with.
        password: The password to log into the registry with.
        registry_url: The URL to the registry. Generally, "http" or "https" can be
            omitted.
        reauth: If already logged into the registry, should login be performed again?
            This setting defaults to `True` to support common token authentication
            patterns such as ECR.
    """

    _block_type_name = "Docker Registry"
    username: str = Field(
        default=..., description="The username to log into the registry with."
    )
    password: SecretStr = Field(
        default=..., description="The password to log into the registry with."
    )
    registry_url: str = Field(
        default=...,
        description='The URL to the registry. Generally, "http" or "https" can be omitted.',
    )
    reauth: bool = Field(
        default=True,
        description="Whether or not to reauthenticate on each interaction.",
    )

    @sync_compatible
    async def login(self) -> "DockerClient":
        warnings.warn(
            "`login` is deprecated. Instead, use `get_docker_client` to obtain an authenticated `DockerClient`.",
            category=DeprecationWarning,
            stacklevel=3,
        )
        return await self.get_docker_client()

    @sync_compatible
    async def get_docker_client(self) -> "DockerClient":
        client = await run_sync_in_worker_thread(
            self._login,
            self.username,
            self.password.get_secret_value(),
            self.registry_url,
            self.reauth,
        )

        return client


class DockerContainerResult(InfrastructureResult):
    """Contains information about a completed Docker container"""


class DockerContainer(Infrastructure):
    """
    Runs a command in a container.

    Requires a Docker Engine to be connectable. Docker settings will be retrieved from
    the environment.

    Attributes:
        auto_remove: If set, the container will be removed on completion. Otherwise,
            the container will remain after exit for inspection.
        command: A list of strings specifying the command to run in the container to
            start the flow run. In most cases you should not override this.
        env: Environment variables to set for the container.
        image: An optional string specifying the tag of a Docker image to use.
            Defaults to the Prefect image.
        image_pull_policy: Specifies if the image should be pulled. One of 'ALWAYS',
            'NEVER', 'IF_NOT_PRESENT'.
        image_registry: A `DockerRegistry` block containing credentials to use if `image` is stored in a private
            image registry.
        labels: An optional dictionary of labels, mapping name to value.
        name: An optional name for the container.
        network_mode: Set the network mode for the created container. Defaults to 'host'
            if a local API url is detected, otherwise the Docker default of 'bridge' is
            used. If 'networks' is set, this cannot be set.
        networks: An optional list of strings specifying Docker networks to connect the
            container to.
        stream_output: If set, stream output from the container to local standard output.
        volumes: An optional list of volume mount strings in the format of
            "local_path:container_path".

    ## Connecting to a locally hosted Prefect API

    If using a local API URL on Linux, we will update the network mode default to 'host'
    to enable connectivity. If using another OS or an alternative network mode is used,
    we will replace 'localhost' in the API URL with 'host.docker.internal'. Generally,
    this will enable connectivity, but the API URL can be provided as an environment
    variable to override inference in more complex use-cases.

    Note, if using 'host.docker.internal' in the API URL on Linux, the API must be bound
    to 0.0.0.0 or the Docker IP address to allow connectivity. On macOS, this is not
    necessary and the API is connectable while bound to localhost.
    """

    type: Literal["docker-container"] = Field(
        default="docker-container", description="The type of infrastructure."
    )
    image: str = Field(
        default_factory=get_prefect_image_name,
        description="Tag of a Docker image to use. Defaults to the Prefect image.",
    )
    image_pull_policy: Optional[ImagePullPolicy] = Field(
        default=None, description="Specifies if the image should be pulled."
    )
    image_registry: Optional[DockerRegistry] = None
    networks: List[str] = Field(
        default_factory=list,
        description="A list of strings specifying Docker networks to connect the container to.",
    )
    network_mode: Optional[str] = Field(
        default=None,
        description="The network mode for the created container (e.g. host, bridge). If 'networks' is set, this cannot be set.",
    )
    auto_remove: bool = Field(
        default=False,
        description="If set, the container will be removed on completion.",
    )
    volumes: List[str] = Field(
        default_factory=list,
        description='A list of volume mount strings in the format of "local_path:container_path".',
    )
    stream_output: bool = Field(
        default=True,
        description="If set, the output will be streamed from the container to local standard output.",
    )

    _block_type_name = "Docker Container"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/2IfXXfMq66mrzJBDFFCHTp/6d8f320d9e4fc4393f045673d61ab612/Moby-logo.png?h=250"

    @validator("labels")
    def convert_labels_to_docker_format(cls, labels: Dict[str, str]):
        labels = labels or {}
        new_labels = {}
        for name, value in labels.items():
            if "/" in name:
                namespace, key = name.split("/", maxsplit=1)
                new_namespace = ".".join(reversed(namespace.split(".")))
                new_labels[f"{new_namespace}.{key}"] = value
            else:
                new_labels[name] = value
        return new_labels

    @validator("volumes")
    def check_volume_format(cls, volumes):
        for volume in volumes:
            if not ":" in volume:
                raise ValueError(
                    "Invalid volume specification. "
                    f"Expected format 'path:container_path', but got {volume!r}"
                )

        return volumes

    @sync_compatible
    async def run(
        self,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ) -> Optional[bool]:
        if not self.command:
            raise ValueError("Docker container cannot be run with empty command.")

        # The `docker` library uses requests instead of an async http library so it must
        # be run in a thread to avoid blocking the event loop.
        container = await run_sync_in_worker_thread(self._create_and_start_container)

        # Mark as started and return the container id
        if task_status:
            task_status.started(container.id)

        # Monitor the container
        container = await run_sync_in_worker_thread(
            self._watch_container_safe, container
        )

        exit_code = container.attrs["State"].get("ExitCode")
        return DockerContainerResult(
            status_code=exit_code if exit_code is not None else -1,
            identifier=container.id,
        )

    def preview(self):
        # TODO: build and document a more sophisticated preview
        docker_client = self._get_client()
        try:
            return json.dumps(self._build_container_settings(docker_client))
        finally:
            docker_client.close()

    def _build_container_settings(
        self,
        docker_client: "DockerClient",
    ) -> Dict:
        network_mode = self._get_network_mode()
        return dict(
            image=self.image,
            network=self.networks[0] if self.networks else None,
            network_mode=network_mode,
            command=self.command,
            environment=self._get_environment_variables(network_mode),
            auto_remove=self.auto_remove,
            labels={**CONTAINER_LABELS, **self.labels},
            extra_hosts=self._get_extra_hosts(docker_client),
            name=self._get_container_name(),
            volumes=self.volumes,
        )

    def _create_and_start_container(self) -> "Container":
        if self.image_registry:
            # If an image registry block was supplied, load an authenticated Docker
            # client from the block. Otherwise, use an unauthenticated client to
            # pull images from public registries.
            docker_client = self.image_registry.get_docker_client()
        else:
            docker_client = self._get_client()

        container_settings = self._build_container_settings(docker_client)

        if self._should_pull_image(docker_client):
            self.logger.info(f"Pulling image {self.image!r}...")
            self._pull_image(docker_client)

        container = self._create_container(docker_client, **container_settings)

        # Add additional networks after the container is created; only one network can
        # be attached at creation time
        if len(self.networks) > 1:
            for network_name in self.networks[1:]:
                network = docker_client.networks.get(network_name)
                network.connect(container)

        # Start the container
        container.start()

        docker_client.close()

        return container

    def _get_image_and_tag(self) -> Tuple[str, Optional[str]]:
        return parse_image_tag(self.image)

    def _determine_image_pull_policy(self) -> ImagePullPolicy:
        """
        Determine the appropriate image pull policy.

        1. If they specified an image pull policy, use that.

        2. If they did not specify an image pull policy and gave us
           the "latest" tag, use ImagePullPolicy.always.

        3. If they did not specify an image pull policy and did not
           specify a tag, use ImagePullPolicy.always.

        4. If they did not specify an image pull policy and gave us
           a tag other than "latest", use ImagePullPolicy.if_not_present.

        This logic matches the behavior of Kubernetes.
        See:https://kubernetes.io/docs/concepts/containers/images/#imagepullpolicy-defaulting
        """
        if not self.image_pull_policy:
            _, tag = self._get_image_and_tag()
            if tag == "latest" or not tag:
                return ImagePullPolicy.ALWAYS
            return ImagePullPolicy.IF_NOT_PRESENT
        return self.image_pull_policy

    def _get_network_mode(self) -> Optional[str]:
        # User's value takes precedence; this may collide with the incompatible options
        # mentioned below.
        if self.network_mode:
            if sys.platform != "linux" and self.network_mode == "host":
                warnings.warn(
                    f"{self.network_mode!r} network mode is not supported on platform "
                    f"{sys.platform!r} and may not work as intended."
                )
            return self.network_mode

        # Network mode is not compatible with networks or ports (we do not support ports
        # yet though)
        if self.networks:
            return None

        # Check for a local API connection
        api_url = self.env.get("PREFECT_API_URL", PREFECT_API_URL.value())

        if api_url:
            try:
                _, netloc, _, _, _, _ = urllib.parse.urlparse(api_url)
            except Exception as exc:
                warnings.warn(
                    f"Failed to parse host from API URL {api_url!r} with exception: "
                    f"{exc}\nThe network mode will not be inferred."
                )
                return None

            host = netloc.split(":")[0]

            # If using a locally hosted API, use a host network on linux
            if sys.platform == "linux" and (host == "127.0.0.1" or host == "localhost"):
                return "host"

        # Default to unset
        return None

    def _should_pull_image(self, docker_client: "DockerClient") -> bool:
        """
        Decide whether we need to pull the Docker image.
        """
        image_pull_policy = self._determine_image_pull_policy()

        if image_pull_policy is ImagePullPolicy.ALWAYS:
            return True
        elif image_pull_policy is ImagePullPolicy.NEVER:
            return False
        elif image_pull_policy is ImagePullPolicy.IF_NOT_PRESENT:
            try:
                # NOTE: images.get() wants the tag included with the image
                # name, while images.pull() wants them split.
                docker_client.images.get(self.image)
            except docker.errors.ImageNotFound:
                self.logger.debug(f"Could not find Docker image locally: {self.image}")
                return True
        return False

    def _pull_image(self, docker_client: "DockerClient"):
        """
        Pull the image we're going to use to create the container.
        """
        image, tag = self._get_image_and_tag()

        return docker_client.images.pull(image, tag)

    def _create_container(self, docker_client: "DockerClient", **kwargs) -> "Container":
        """
        Create a docker container with retries on name conflicts.

        If the container already exists with the given name, an incremented index is
        added.
        """
        # Create the container with retries on name conflicts (with an incremented idx)
        index = 0
        container = None
        name = original_name = kwargs.pop("name")

        while not container:
            from docker.errors import APIError

            try:
                display_name = repr(name) if name else "with auto-generated name"
                self.logger.info(f"Creating Docker container {display_name}...")
                container = docker_client.containers.create(name=name, **kwargs)
            except APIError as exc:
                if "Conflict" in str(exc) and "container name" in str(exc):
                    self.logger.info(
                        f"Docker container name {display_name} already exists; "
                        "retrying..."
                    )
                    index += 1
                    name = f"{original_name}-{index}"
                else:
                    raise

        self.logger.info(
            f"Docker container {container.name!r} has status {container.status!r}"
        )
        return container

    def _watch_container_safe(self, container: "Container") -> "Container":
        # Monitor the container capturing the latest snapshot while capturing
        # not found errors
        docker_client = self._get_client()

        try:
            for latest_container in self._watch_container(docker_client, container.id):
                container = latest_container
        except docker.errors.NotFound:
            # The container was removed during watching
            self.logger.warning(
                f"Docker container {container.name} was removed before we could wait "
                "for its completion."
            )
        finally:
            docker_client.close()

        return container

    def _watch_container(
        self, docker_client: "DockerClient", container_id: str
    ) -> Generator[None, None, "Container"]:
        container: "Container" = docker_client.containers.get(container_id)

        status = container.status
        self.logger.info(
            f"Docker container {container.name!r} has status {container.status!r}"
        )
        yield container

        if self.stream_output:
            try:
                for log in container.logs(stream=True):
                    log: bytes
                    print(log.decode().rstrip())
            except docker.errors.APIError as exc:
                if "marked for removal" in str(exc):
                    self.logger.warning(
                        f"Docker container {container.name} was marked for removal before "
                        "logs could be retrieved. Output will not be streamed. "
                    )
                else:
                    self.logger.exception(
                        "An unexpected Docker API error occured while streaming output "
                        f"from container {container.name}."
                    )

            container.reload()
            if container.status != status:
                self.logger.info(
                    f"Docker container {container.name!r} has status {container.status!r}"
                )
            yield container

        container.wait()
        self.logger.info(
            f"Docker container {container.name!r} has status {container.status!r}"
        )
        yield container

    def _get_client(self):
        try:

            with warnings.catch_warnings():
                # Silence warnings due to use of deprecated methods within dockerpy
                # See https://github.com/docker/docker-py/pull/2931
                warnings.filterwarnings(
                    "ignore",
                    message="distutils Version classes are deprecated.*",
                    category=DeprecationWarning,
                )

                docker_client = docker.from_env()

        except docker.errors.DockerException as exc:
            raise RuntimeError(f"Could not connect to Docker.") from exc

        return docker_client

    def _get_container_name(self) -> Optional[str]:
        """
        Generates a container name to match the configured name, ensuring it is Docker
        compatible.
        """
        # Must match `/?[a-zA-Z0-9][a-zA-Z0-9_.-]+` in the end
        if not self.name:
            return None

        return (
            slugify(
                self.name,
                lowercase=False,
                # Docker does not limit length but URL limits apply eventually so
                # limit the length for safety
                max_length=250,
                # Docker allows these characters for container names
                regex_pattern=r"[^a-zA-Z0-9_.-]+",
            ).lstrip(
                # Docker does not allow leading underscore, dash, or period
                "_-."
            )
            # Docker does not allow 0 character names so cast to null if the name is
            # empty after slufification
            or None
        )

    def _get_extra_hosts(self, docker_client) -> Dict[str, str]:
        """
        A host.docker.internal -> host-gateway mapping is necessary for communicating
        with the API on Linux machines. Docker Desktop on macOS will automatically
        already have this mapping.
        """
        if sys.platform == "linux" and (
            # Do not warn if the user has specified a host manually that does not use
            # a local address
            "PREFECT_API_URL" not in self.env
            or re.search(
                ".*(localhost)|(127.0.0.1)|(host.docker.internal).*",
                self.env["PREFECT_API_URL"],
            )
        ):
            user_version = packaging.version.parse(docker_client.version()["Version"])
            required_version = packaging.version.parse("20.10.0")

            if user_version < required_version:
                warnings.warn(
                    "`host.docker.internal` could not be automatically resolved to your "
                    "local ip address. This feature is not supported on Docker Engine "
                    f"v{user_version}, upgrade to v{required_version}+ if you "
                    "encounter issues."
                )
                return {}
            else:
                # Compatibility for linux -- https://github.com/docker/cli/issues/2290
                # Only supported by Docker v20.10.0+ which is our minimum recommend version
                return {"host.docker.internal": "host-gateway"}

    def _get_environment_variables(self, network_mode):
        # If the API URL has been set by the base environment rather than the by the
        # user, update the value to ensure connectivity when using a bridge network by
        # updating local connections to use the docker internal host unless the
        # network mode is "host" where localhost is available already.
        env = {**self._base_environment(), **self.env}

        if (
            "PREFECT_API_URL" in env
            and "PREFECT_API_URL" not in self.env
            and network_mode != "host"
        ):
            env["PREFECT_API_URL"] = (
                env["PREFECT_API_URL"]
                .replace("localhost", "host.docker.internal")
                .replace("127.0.0.1", "host.docker.internal")
            )

        # Drop null values allowing users to "unset" variables
        return {key: value for key, value in env.items() if value is not None}
