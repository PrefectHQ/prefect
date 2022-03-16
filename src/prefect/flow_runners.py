"""
[Flow Runners](/concepts/flow-runners/) in Prefect are responsible for creating and 
monitoring infrastructure for flow runs associated with deployments. 

A flow runner can only be used with a deployment. When you run a flow directly by 
calling the flow yourself, you are responsible for the environment in which the flow 
executes.

For usage details, see the [Flow Runners](/concepts/flow-runners/) documentation.
"""

import asyncio
import enum
import os
import re
import subprocess
import sys
import urllib.parse
import warnings
from pathlib import Path
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID

import anyio
import anyio.abc
import packaging.version
import sniffio
from anyio.abc import TaskStatus
from anyio.streams.text import TextReceiveStream
from pydantic import BaseModel, Field, PrivateAttr, root_validator, validator
from slugify import slugify
from typing_extensions import Literal

import prefect
from prefect.logging import get_logger
from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.settings import PREFECT_API_URL
from prefect.utilities.asyncio import run_sync_in_worker_thread
from prefect.utilities.compat import ThreadedChildWatcher
from prefect.utilities.enum import AutoEnum

if TYPE_CHECKING:
    import docker
    import kubernetes
    from docker import DockerClient
    from docker.models.containers import Container
    from kubernetes.client import BatchV1Api, Configuration, CoreV1Api, V1Job, V1Pod
else:
    docker = None
    kubernetes = None

_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}
FlowRunnerT = TypeVar("FlowRunnerT", bound=Type["FlowRunner"])

# The flow runner should be able to run containers with this version or newer.
# Containers with versions of prefect before this version are not expected to run
# correctly.
MIN_COMPAT_PREFECT_VERSION = "2.0a13"


def python_version_minor() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def python_version_micro() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_prefect_image_name(
    prefect_version: str = None, python_version: str = None
) -> str:
    """
    Get the Prefect image name matching the current Prefect and Python versions.

    Args:
        prefect_version: An optional override for the Prefect version.
        python_version: An optional override for the Python version; must be at the
            minor level e.g. '3.9'.
    """
    parsed_version = (prefect_version or prefect.__version__).split("+")
    prefect_version = parsed_version[0] if len(parsed_version) == 1 else "dev"

    python_version = python_version or python_version_minor()

    tag = slugify(
        f"{prefect_version}-python{python_version}",
        lowercase=False,
        max_length=128,
        # Docker allows these characters for tag names
        regex_pattern=r"[^a-zA-Z0-9_.-]+",
    )

    return f"prefecthq/prefect:{tag}"


class FlowRunner(BaseModel):
    """
    Flow runners are responsible for creating infrastructure for flow runs and starting
    execution.

    This base implementation manages casting to and from the API representation of
    flow runner settings and defines the interface for `submit_flow_run`. It cannot
    be used to run flows.
    """

    typename: str

    def to_settings(self) -> FlowRunnerSettings:
        return FlowRunnerSettings(
            type=self.typename, config=self.dict(exclude={"typename"})
        )

    @classmethod
    def from_settings(cls, settings: FlowRunnerSettings) -> "FlowRunner":
        subcls = lookup_flow_runner(settings.type)
        return subcls(**(settings.config or {}))

    @property
    def logger(self):
        return get_logger(f"flow_runner.{self.typename}")

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        """
        Implementations should:

        - Create flow run infrastructure.
        - Start the flow run within it.
        - Call `task_status.started()` to indicate that submission was successful

        The method can then exit or continue to monitor the flow run asynchronously.

        The method _may_ return a boolean indicating successful completion of the run.
        This return value is not intended for general consumption and is primarily
        useful for testing.
        """
        raise NotImplementedError()

    class Config:
        extra = "forbid"


def register_flow_runner(cls: FlowRunnerT) -> FlowRunnerT:
    _FLOW_RUNNERS[cls.__fields__["typename"].default] = cls
    return cls


def lookup_flow_runner(typename: str) -> FlowRunner:
    """Return the flow runner class for the given `typename`"""
    try:
        return _FLOW_RUNNERS[typename]
    except KeyError:
        raise ValueError(f"Unregistered flow runner {typename!r}")


@register_flow_runner
class UniversalFlowRunner(FlowRunner):
    """
    The universal flow runner contains configuration options that can be used by any
    Prefect flow runner implementation.

    This flow runner cannot be used at runtime and should be converted into a subtype.

    Attributes:
        env: Environment variables to provide to the flow run
    """

    typename: Literal["universal"] = "universal"
    env: Dict[str, str] = Field(default_factory=dict)

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        raise RuntimeError(
            "The universal flow runner cannot be used to submit flow runs. If a flow "
            "run has a universal flow runner, it should be updated to the default "
            "runner type by the agent or user."
        )


@register_flow_runner
class SubprocessFlowRunner(UniversalFlowRunner):
    """
    Executes flow runs in a local subprocess.

    Attributes:
        stream_output: Stream output from the subprocess to local standard output
        condaenv: An optional name of an anaconda environment to run the flow in.
            A path can be provided instead, similar to `conda --prefix ...`.
        virtualenv: An optional path to a virtualenv environment to run the flow in.
            This also supports the python builtin `venv` environments.

    """

    typename: Literal["subprocess"] = "subprocess"
    stream_output: bool = False
    condaenv: Union[str, Path] = None
    virtualenv: Path = None

    @validator("condaenv")
    def coerce_pathlike_string_to_path(cls, value):
        if (
            not isinstance(value, Path)
            and value is not None
            and (value.startswith(os.sep) or value.startswith("~"))
        ):
            value = Path(value)
        return value

    @root_validator
    def ensure_only_one_env_was_given(cls, values):
        if values.get("condaenv") and values.get("virtualenv"):
            raise ValueError(
                "Received incompatible settings. You cannot provide both a conda and "
                "virtualenv to use."
            )
        return values

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:

        if sys.version_info < (3, 8) and sniffio.current_async_library() == "asyncio":
            # Python < 3.8 does not use a `ThreadedChildWatcher` by default which can
            # lead to errors in tests on unix as the previous default `SafeChildWatcher`
            # is not compatible with threaded event loops.
            asyncio.get_event_loop_policy().set_child_watcher(ThreadedChildWatcher())

        # Open a subprocess to execute the flow run
        self.logger.info(f"Opening subprocess for flow run '{flow_run.id}'...")

        command, env = self._generate_command_and_environment(flow_run.id)

        self.logger.debug(f"Using command: {' '.join(command)}")

        process_context = await anyio.open_process(
            command,
            stderr=subprocess.STDOUT,
            env=env,
        )

        # Mark this submission as successful
        task_status.started()

        # Wait for the process to exit
        # - We must the output stream so the buffer does not fill
        # - We can log the success/failure of the process
        async with process_context as process:
            async for text in TextReceiveStream(process.stdout):
                if self.stream_output:
                    print(text, end="")  # Output is already new-line terminated

        if process.returncode:
            self.logger.error(
                f"Subprocess for flow run '{flow_run.id}' exited with bad code: "
                f"{process.returncode}"
            )
        else:
            self.logger.info(f"Subprocess for flow run '{flow_run.id}' exited cleanly.")

        return not process.returncode

    def _generate_command_and_environment(
        self, flow_run_id: UUID
    ) -> Tuple[Sequence[str], Dict[str, str]]:
        # Copy the base environment
        env = os.environ.copy()

        # Set up defaults
        command = []
        python_executable = sys.executable

        if self.condaenv:
            command += ["conda", "run"]
            if isinstance(self.condaenv, Path):
                command += ["--prefix", str(self.condaenv.expanduser().resolve())]
            else:
                command += ["--name", self.condaenv]

            python_executable = "python"

        elif self.virtualenv:
            # This reproduces the relevant behavior of virtualenv's activation script
            # https://github.com/pypa/virtualenv/blob/main/src/virtualenv/activation/bash/activate.sh

            virtualenv_path = self.virtualenv.expanduser().resolve()
            python_executable = str(virtualenv_path / "bin" / "python")
            # Update the path to include the bin
            env["PATH"] = str(virtualenv_path / "bin") + os.pathsep + env["PATH"]
            env.pop("PYTHONHOME", None)
            env["VIRTUAL_ENV"] = str(virtualenv_path)

        # Add `prefect.engine` call
        command += [
            python_executable,
            "-m",
            "prefect.engine",
            flow_run_id.hex,
        ]

        # Override with any user-provided variables
        env.update(self.env)

        return command, env


class ImagePullPolicy(AutoEnum):
    IF_NOT_PRESENT = AutoEnum.auto()
    ALWAYS = AutoEnum.auto()
    NEVER = AutoEnum.auto()


@register_flow_runner
class DockerFlowRunner(UniversalFlowRunner):
    """
    Executes flow runs in a container.

    Requires a Docker Engine to be connectable.


    Attributes:
        image: An optional string specifying the tag of a Docker image to use.
        network_mode: Set the network mode for the created container. Defaults to 'host'
            if a local API url is detected, otherwise the Docker default of 'bridge' is
            used. If 'networks' is set, this cannot be set.
        networks: An optional list of strings specifying Docker networks to connect the
            container to.
        labels: An optional dictionary of labels, mapping name to value.
        auto_remove: If set, the container will be removed on completion. Otherwise,
            the container will remain after exit for inspection.
        volumes: An optional list of volume mount strings in the format of
            "local_path:container_path".
        stream_output: If set, stream output from the container to local standard output.

    ## Connecting to a locally hosted API

    If using a local API URL on Linux, we will update the network mode default to 'host'
    to enable connectivity. If using another OS or an alternative network mode is used,
    we will replace 'localhost' in the API URL with 'host.docker.internal'. Generally,
    this will enable connectivity, but the API URL can be provided as an environment
    variable to override inference in more complex use-cases.

    Note, if using 'host.docker.internal' in the API URL on Linux, the API must be bound
    to 0.0.0.0 or the Docker IP address to allow connectivity. On macOS, this is not
    necessary and the API is connectable while bound to localhost.
    """

    typename: Literal["docker"] = "docker"

    image: str = Field(default_factory=get_prefect_image_name)
    image_pull_policy: ImagePullPolicy = None
    networks: List[str] = Field(default_factory=list)
    network_mode: str = None
    labels: Dict[str, str] = None
    auto_remove: bool = False
    volumes: List[str] = Field(default_factory=list)
    stream_output: bool = True

    @validator("volumes")
    def check_volume_format(cls, volumes):
        for volume in volumes:
            if not ":" in volume:
                raise ValueError(
                    "Invalid volume specification. "
                    f"Expected format 'path:container_path', but got {volume!r}"
                )

        return volumes

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        # Throw an error immediately if the flow run won't be able to contact the API
        self._assert_orion_settings_are_compatible()

        # The `docker` library uses requests instead of an async http library so it must
        # be run in a thread to avoid blocking the event loop.
        container_id = await run_sync_in_worker_thread(
            self._create_and_start_container, flow_run
        )

        # Mark as started
        task_status.started()

        # Monitor the container
        return await run_sync_in_worker_thread(self._watch_container, container_id)

    def _assert_orion_settings_are_compatible(self):
        """
        If using the ephemeral server and sqlite, the flow run in the container will
        spin up an ephemeral server that uses a container-local database instead of
        the one the user expects. This will result in failure as the flow run will not
        exist.

        If the local sqlite database is mounted into the container, it will work,
        but concurrent access will cause database corruption as the WAL mode requires
        shared memory file locks, which are not available across the boundary of the
        Docker virtual machine.

        We could support an ephemeral server with postgresql, but then we would need to
        sync all of the server settings to the container's ephemeral server.
        """
        api_url = self.env.get("PREFECT_API_URL", PREFECT_API_URL.value())

        if not api_url:
            raise RuntimeError(
                "The docker flow runner cannot be used with an ephemeral server. "
                "Provide `PREFECT_API_URL` to connect to an Orion server."
            )

    def _create_and_start_container(self, flow_run: FlowRun) -> str:

        docker_client = self._get_client()

        network_mode = self._get_network_mode()

        container_settings = dict(
            image=self.image,
            network=self.networks[0] if self.networks else None,
            network_mode=network_mode,
            command=self._get_start_command(flow_run),
            environment=self._get_environment_variables(network_mode),
            auto_remove=self.auto_remove,
            labels=self._get_labels(flow_run),
            extra_hosts=self._get_extra_hosts(docker_client),
            name=self._get_container_name(flow_run),
            volumes=self.volumes,
        )
        self.logger.info(
            f"Flow run {flow_run.name!r} has container settings = {container_settings}"
        )

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

        return container.id

    def _get_image_and_tag(self) -> Tuple[str, Optional[str]]:
        parts = self.image.split(":")
        image = parts.pop(0)
        tag = parts[0] if parts else None
        return image, tag

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
            image, tag = self._get_image_and_tag()
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
            except self._docker.errors.ImageNotFound:
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
        name = original_name = kwargs.pop("name", "prefect-flow-run")

        while not container:
            try:
                container = docker_client.containers.create(name=name, **kwargs)
            except self._docker.errors.APIError as exc:
                if "Conflict" in str(exc) and "container name" in str(exc):
                    index += 1
                    name = f"{original_name}-{index}"
                else:
                    raise

        return container

    def _watch_container(self, container_id: str) -> bool:
        docker_client = self._get_client()

        try:
            container = docker_client.containers.get(container_id)
        except self._docker.errors.NotFound:
            self.logger.error(f"Flow run container {container_id!r} was removed.")
            return

        status = container.status
        self.logger.info(
            f"Flow run container {container.name!r} has status {container.status!r}"
        )

        for log in container.logs(stream=True):
            log: bytes
            if self.stream_output:
                print(log.decode().rstrip())

        container.reload()
        if container.status != status:
            self.logger.info(
                f"Flow run container {container.name!r} has status {container.status!r}"
            )

        result = container.wait()
        return result.get("StatusCode") == 0

    @property
    def _docker(self) -> ModuleType("docker"):
        """
        Delayed import of `docker` allowing configuration of the flow runner without
        the extra installed and improves `prefect` import times.
        """
        global docker

        if docker is None:
            try:
                import docker
            except ImportError as exc:
                raise RuntimeError(
                    "Using the `DockerFlowRunner` requires `docker-py` to be installed."
                ) from exc

        return docker

    def _get_client(self):
        try:
            docker_client = self._docker.from_env()
        except self._docker.errors.DockerException as exc:
            raise RuntimeError(f"Could not connect to Docker.") from exc

        return docker_client

    def _get_container_name(self, flow_run: FlowRun) -> str:
        """
        Generates a container name to match the flow run name, ensuring it is Docker
        compatible and unique.
        """
        # Must match `/?[a-zA-Z0-9][a-zA-Z0-9_.-]+` in the end

        return (
            slugify(
                flow_run.name,
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
            # Docker does not allow 0 character names so use the flow run id if name
            # would be empty after cleaning
            or flow_run.id
        )

    def _get_start_command(self, flow_run: FlowRun) -> List[str]:
        return [
            "python",
            "-m",
            "prefect.engine",
            f"{flow_run.id}",
        ]

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
        env = self.env.copy()

        # Set the container to connect to the same API as the flow runner by default

        if PREFECT_API_URL:
            api_url = PREFECT_API_URL.value()

            # Update local connections to use the docker internal host unless the
            # network mode is "host" where localhost is available
            if network_mode != "host":
                api_url = api_url.replace("localhost", "host.docker.internal").replace(
                    "127.0.0.1", "host.docker.internal"
                )

            env.setdefault("PREFECT_API_URL", api_url)

        return env

    def _get_labels(self, flow_run: FlowRun):
        labels = self.labels.copy() if self.labels else {}
        labels.update(
            {
                "io.prefect.flow-run-id": str(flow_run.id),
            }
        )
        return labels


class KubernetesImagePullPolicy(enum.Enum):
    IF_NOT_PRESENT = "IfNotPresent"
    ALWAYS = "Always"
    NEVER = "Never"


class KubernetesRestartPolicy(enum.Enum):
    ON_FAILURE = "OnFailure"
    NEVER = "Never"


@register_flow_runner
class KubernetesFlowRunner(UniversalFlowRunner):
    """
    Executes flow runs in a Kubernetes job.

    Requires a Kubernetes cluster to be connectable.

    Attributes:
        image: An optional string specifying the tag of a Docker image to use for the job.
        namespace: An optional string signifying the Kubernetes namespace to use.
        labels: An optional dictionary of labels to add to the job.
        image_pull_policy: The Kubernetes image pull policy to use for job containers.
        restart_policy: The Kubernetes restart policy to use for jobs.
        stream_output: If set, stream output from the container to local standard output.
    """

    typename: Literal["kubernetes"] = "kubernetes"

    image: str = Field(default_factory=get_prefect_image_name)
    namespace: str = "default"
    labels: Dict[str, str] = None
    image_pull_policy: KubernetesImagePullPolicy = None
    restart_policy: KubernetesRestartPolicy = KubernetesRestartPolicy.NEVER
    stream_output: bool = True

    _client: "CoreV1Api" = PrivateAttr(None)
    _batch_client: "BatchV1Api" = PrivateAttr(None)
    _k8s_config: "Configuration" = PrivateAttr(None)

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        self.logger.info("RUNNING")

        # Throw an error immediately if the flow run won't be able to contact the API
        self._assert_orion_settings_are_compatible()

        # Python won't let us use self._k8s.config.ConfigException, it seems
        from kubernetes.config import ConfigException

        # Try to load Kubernetes configuration within a cluster first. If that doesn't
        # work, try to load the configuration from the local environment, allowing
        # any further ConfigExceptions to bubble up.
        try:
            self._k8s.config.incluster_config.load_incluster_config()
        except ConfigException:
            self._k8s.config.load_kube_config()

        job_name = await run_sync_in_worker_thread(self._create_and_start_job, flow_run)

        # Mark as started
        task_status.started()

        # Monitor the job
        return await run_sync_in_worker_thread(self._watch_job, job_name)

    @property
    def batch_client(self) -> "BatchV1Api":
        if self._batch_client is None:
            self._batch_client = self._k8s.client.BatchV1Api()
        return self._batch_client

    @property
    def client(self) -> "CoreV1Api":
        if self._client is None:
            self._client = self._k8s.client.CoreV1Api(self._k8s.client.ApiClient())
        return self._client

    def _assert_orion_settings_are_compatible(self):
        """See note in DockerFlowRunner."""
        api_url = self.env.get("PREFECT_API_URL", PREFECT_API_URL.value())

        if not api_url:
            raise RuntimeError(
                "The Kubernetes flow runner cannot be used with an ephemeral server. "
                "Provide `PREFECT_API_URL` to connect to an Orion server."
            )

    def _get_job(self, job_id: str) -> Optional["V1Job"]:
        try:
            job = self.batch_client.read_namespaced_job(job_id, self.namespace)
        except self._k8s.client.ApiException:
            self.logger.error(f"Flow run job {job_id!r} was removed.", exc_info=True)
            return None
        return job

    def _get_job_pod(self, job_name: str) -> "V1Pod":
        """Get the first running pod for a job."""

        # Wait until we find a running pod for the job
        watch = self._k8s.watch.Watch()
        self.logger.info(f"Starting watch for pod to start. Job: {job_name}")
        for event in watch.stream(
            func=self.client.list_namespaced_pod,
            namespace=self.namespace,
            label_selector=f"job-name={job_name}",
            timeout_seconds=5,  # TODO: Make configurable?
        ):
            if event["object"].status.phase == "Running":
                watch.stop()
                return event["object"]
        self.logger.error(f"Pod never started. Job: {job_name}")

    def _watch_job(self, job_name: str) -> bool:
        job = self._get_job(job_name)
        if not job:
            return False

        self.logger.info(
            f"Flow run job {job.metadata.name!r} has status {job.status!r}"
        )

        pod = self._get_job_pod(job_name)
        if not pod:
            return False

        if self.stream_output:
            for log in self.client.read_namespaced_pod_log(
                pod.metadata.name, self.namespace, follow=True, _preload_content=False
            ).stream():
                print(log.decode().rstrip())

        # Wait for job to complete
        self.logger.info(f"Starting watch for job completion: {job_name}")
        watch = self._k8s.watch.Watch()
        for event in watch.stream(
            func=self.batch_client.list_namespaced_job,
            field_selector=f"metadata.name={job_name}",
            namespace=self.namespace,
            timeout_seconds=5,  # TODO: Make configurable?
        ):
            if event["object"].status.completion_time:
                watch.stop()
                break
        else:
            self.logger.error(f"Job {job_name!r} never completed.")
            return False

        pod_status = self.client.read_namespaced_pod_status(
            namespace=self.namespace, name=pod.metadata.name
        )
        return pod_status.status.container_statuses[0].state.terminated.exit_code == 0

    def _get_start_command(self, flow_run: FlowRun) -> List[str]:
        return [
            "python",
            "-m",
            "prefect.engine",
            f"{flow_run.id}",
        ]

    def _slugify_flow_run_name(self, flow_run: FlowRun):
        """
        Slugify a flow run name for use as a Kubernetes label or name.

        Keeps only alphanumeric characters and dashes, and caps the length
        of the slug at 45 chars.

        The 45 character length allows room for the k8s utility
        "generateName" to generate a unique name from the slug while
        keeping the total length of a name below 63 characters, which is
        the limit for e.g. label names that follow RFC 1123 (hostnames) and
        RFC 1035 (domain names).

        Args:
            flow_run: The flow run

        Returns:
            the slugified flow name
        """
        slug = slugify(
            flow_run.name,
            max_length=45,  # Leave enough space for generateName
            regex_pattern=r"[^a-zA-Z0-9-]+",
        )
        if not slug:
            return str(flow_run.id)
        return slug

    def _get_labels(self, flow_run: FlowRun):
        labels = self.labels.copy() if self.labels else {}
        flow_run_name_slug = self._slugify_flow_run_name(flow_run)
        labels.update(
            {
                "io.prefect.flow-run-id": str(flow_run.id),
                "io.prefect.flow-run-name": flow_run_name_slug,
                "app": "orion",
            }
        )
        return labels

    def _get_environment_variables(self):
        env = self.env.copy()
        env.setdefault("PREFECT_API_URL", "http://orion:4200/api")
        return env

    def _create_and_start_job(self, flow_run: FlowRun) -> str:
        k8s_env = [
            {"name": k, "value": v}
            for k, v in self._get_environment_variables().items()
        ]

        job_settings = dict(
            metadata={
                "generateName": self._slugify_flow_run_name(flow_run),
                "namespace": self.namespace,
                "labels": self._get_labels(flow_run),
            },
            spec={
                "template": {
                    "spec": {
                        "restartPolicy": self.restart_policy.value,
                        "containers": [
                            {
                                "name": "job",
                                "image": self.image,
                                "command": self._get_start_command(flow_run),
                                "env": k8s_env,
                            }
                        ],
                    }
                },
                "backoff_limit": 4,
            },
        )

        if self.image_pull_policy:
            job_settings["spec"]["template"]["spec"]["containers"][0][
                "imagePullPolicy"
            ] = self.image_pull_policy.value

        self.logger.info(
            f"Flow run {flow_run.name!r} has job settings = {job_settings}"
        )
        job = self.batch_client.create_namespaced_job(self.namespace, job_settings)

        return job.metadata.name

    @property
    def _k8s(self) -> ModuleType("kubernetes"):
        """
        Delayed import of `kubernetes` allowing configuration of the flow runner without
        the extra installed and improves `prefect` import times.
        """
        global kubernetes

        if kubernetes is None:
            try:
                import kubernetes
            except ImportError as exc:
                raise RuntimeError(
                    "Using the `KubernetesFlowRunner` requires `kubernetes` to be installed."
                ) from exc

        return kubernetes
