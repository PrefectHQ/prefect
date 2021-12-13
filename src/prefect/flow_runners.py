import subprocess
import sys
import sniffio
import asyncio
from typing import Dict, TypeVar, Type, Optional, List

import anyio
import anyio.abc
from slugify import slugify
from anyio.abc import TaskStatus
from anyio.streams.text import TextReceiveStream
from pydantic import BaseModel, Field
from typing_extensions import Literal

from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.utilities.compat import ThreadedChildWatcher
from prefect.utilities.logging import get_logger
from prefect.utilities.asyncio import run_sync_in_worker_thread

_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}
FlowRunnerT = TypeVar("FlowRunnerT", bound=Type["FlowRunner"])


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
        Implementions should:

        - Create flow run infrastructure.
        - Start the flow run within it.
        - Call `task_status.started()` to indicate that submission was successful

        The method can then exit or continue monitor the flow run asynchronously.

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
            "runner type."
        )


@register_flow_runner
class SubprocessFlowRunner(UniversalFlowRunner):
    """
    Executes flow runs in a local subprocess.

    Attributes:
        stream_output: Stream output from the subprocess to local standard output
    """

    typename: Literal["subprocess"] = "subprocess"
    stream_output: bool = False

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
        process_context = await anyio.open_process(
            ["python", "-m", "prefect.engine", flow_run.id.hex],
            stderr=subprocess.STDOUT,
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


@register_flow_runner
class DockerFlowRunner(UniversalFlowRunner):
    typename: Literal["docker"] = "docker"

    image: str = "prefect:main"
    networks: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = None
    auto_remove: bool = False

    def _get_container_name(self, flow_run: FlowRun) -> str:
        """
        Generatse a container name to match the flow run name, ensuring it is docker
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

    def _get_start_command(self, flow_run: FlowRun):
        return [
            "python",
            "-m",
            "prefect.engine",
            "{flow_run.id}",
        ]

    def _create_container(self, flow_run):
        import docker

        docker_client = docker.from_env()

        labels = self.labels.copy() if self.labels else {}
        labels.update(
            {
                "io.prefect.flow-run-id": str(flow_run.id),
            }
        )

        # Create the container with retries on name conflicts (with an incremented idx)
        index = 0
        container = None
        container_name = original_container_name = self._get_container_name(flow_run)
        while not container:
            try:
                container = docker_client.containers.create(
                    self.image,
                    name=container_name,
                    network=self.networks[0] if self.networks else None,
                    command=self._get_start_command(flow_run),
                    environment=self.env,
                    auto_remove=self.auto_remove,
                    labels=labels,
                )
            except docker.errors.APIError as exc:
                if "Conflict" in str(exc) and "container name" in str(exc):
                    index += 1
                    container_name = f"{original_container_name}-{index}"
                else:
                    raise

        # Add additional networks after the container is created; only one network can
        # be attached at creation time
        if len(self.networks) > 1:
            for network_name in self.networks[1:]:
                network = docker_client.networks.get(network_name)
                network.connect(container)

        return container

    def _create_and_start_container(self, flow_run: FlowRun) -> str:

        container = self._create_container(flow_run)

        # Start the container
        container.start()

        return container.id

    def _check_running_container(self, container_id: str) -> bool:
        """
        If the container is not running, returns `False`
        """
        import docker

        docker_client = docker.from_env()

        try:
            container = docker_client.containers.get(container_id)
        except docker.errors.ImageNotFound:
            self.logger.error(f"Flow run container {container_id!r} was removed.")
            return False

        self.logger.info(
            f"Flow run container {container.name!r} has status: {container.status!r}"
        )
        if container.status != "running":
            return False
        else:
            return True

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:

        # The `docker` library uses requests instead of an async http library so it must
        # be run in a thread to avoid blocking the event loop.
        container_id = await run_sync_in_worker_thread(
            self._create_and_start_container, flow_run
        )

        # Mark as started
        task_status.started()

        # Monitor the container
        container_running = True
        while container_running:
            container_running = await run_sync_in_worker_thread(
                self._check_running_container, container_id
            )
            await anyio.sleep(10)
