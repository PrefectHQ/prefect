import asyncio
import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Generator, List, Optional

import anyio
import anyio.abc
import sniffio
from pydantic import Field, validator

from prefect.client.schemas import FlowRun
from prefect.docker import (
    format_outlier_version_name,
    get_prefect_image_name,
    parse_image_tag,
)
from prefect.experimental.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)
from prefect.settings import get_current_settings
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.filesystem import relative_path_to_current_platform
from prefect.utilities.importtools import lazy_import
from prefect.utilities.processutils import run_process
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    import docker
    from docker import DockerClient
    from docker.models.containers import Container
    from prefect.server.schemas.core import Flow
    from prefect.server.schemas.responses import DeploymentResponse
else:
    docker = lazy_import("docker")


CONTAINER_LABELS = {}


class ImagePullPolicy(AutoEnum):
    IF_NOT_PRESENT = AutoEnum.auto()
    ALWAYS = AutoEnum.auto()
    NEVER = AutoEnum.auto()


class DockerJobConfiguration(BaseJobConfiguration):
    image: str = Field(
        default_factory=get_prefect_image_name,
        description="Tag of a Docker image to use as a default. Defaults to the Prefect image.",
    )
    image_pull_policy: Optional[ImagePullPolicy] = Field(
        default=None, description="Specifies an image pull policy."
    )
    auto_remove: bool = Field(
        default=False,
        description="If set, the container will be removed on completion.",
    )
    volumes: List[str] = Field(
        default_factory=list,
        description=(
            "A list of volume mount strings in the format of"
            ' "local_path:container_path".'
        ),
    )
    stream_output: bool = Field(
        default=True,
        description=(
            "If set, the output will be streamed from the container to local standard"
            " output."
        ),
    )

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: Optional["DeploymentResponse"] = None,
        flow: Optional["Flow"] = None,
    ):
        super().prepare_for_flow_run(flow_run, deployment, flow)

        self.env = {**os.environ, **self.env}
        self.command = (
            "python -m prefect.engine"
            if self.command == self._base_flow_run_command()
            else self.command
        )


class DockerVariables(BaseVariables):
    stream_output: bool = Field(
        default=True,
        description=(
            "If enabled, workers will stream output from flow run processes to "
            "local standard output."
        ),
    )


class DockerWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class DockerWorker(BaseWorker):
    type = "docker"
    job_configuration = DockerJobConfiguration
    job_configuration_variables = DockerVariables

    _description = "Worker that executes flow runs via Docker."
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/2IfXXfMq66mrzJBDFFCHTp/6d8f320d9e4fc4393f045673d61ab612/Moby-logo.png?h=250"

    async def run(
        self,
        flow_run: FlowRun,
        configuration: DockerJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ):

        # The `docker` library uses requests instead of an async http library so it must
        # be run in a thread to avoid blocking the event loop.
        container = await run_sync_in_worker_thread(
            self._create_and_start_container, configuration=configuration
        )
        container_pid = self._get_infrastructure_pid(container_id=container.id)

        # Mark as started and return the infrastructure id
        if task_status:
            task_status.started(container_pid)

        # Monitor the container
        container = await run_sync_in_worker_thread(
            self._watch_container_safe,
            container,
            stream_output=configuration.stream_output,
        )

        exit_code = container.attrs["State"].get("ExitCode")
        return DockerWorkerResult(
            status_code=exit_code if exit_code is not None else -1,
            identifier=container_pid,
        )

    def _get_infrastructure_pid(self, container_id: str) -> str:
        """Generates a Docker infrastructure_pid string in the form of
        `<docker_host_base_url>:<container_id>`.
        """
        docker_client = self._get_client()
        base_url = docker_client.api.base_url
        docker_client.close()
        return f"{base_url}:{container_id}"

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

    def _watch_container_safe(
        self, container: "Container", stream_output: bool = False
    ) -> "Container":
        # Monitor the container capturing the latest snapshot while capturing
        # not found errors
        docker_client = self._get_client()

        try:
            for latest_container in self._watch_container(
                docker_client, container.id, stream_output=stream_output
            ):
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
        self,
        docker_client: "DockerClient",
        container_id: str,
        stream_output: bool = False,
    ) -> Generator[None, None, "Container"]:
        container: "Container" = docker_client.containers.get(container_id)

        status = container.status
        self.logger.info(
            f"Docker container {container.name!r} has status {container.status!r}"
        )
        yield container

        if stream_output:
            try:
                for log in container.logs(stream=True):
                    log: bytes
                    print(log.decode().rstrip())
            except docker.errors.APIError as exc:
                if "marked for removal" in str(exc):
                    self.logger.warning(
                        f"Docker container {container.name} was marked for removal"
                        " before logs could be retrieved. Output will not be"
                        " streamed. "
                    )
                else:
                    self.logger.exception(
                        "An unexpected Docker API error occured while streaming output "
                        f"from container {container.name}."
                    )

            container.reload()
            if container.status != status:
                self.logger.info(
                    f"Docker container {container.name!r} has status"
                    f" {container.status!r}"
                )
            yield container

        container.wait()
        self.logger.info(
            f"Docker container {container.name!r} has status {container.status!r}"
        )
        yield container

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
                self.logger.info(f"Creating Docker container {display_name!r}...")
                container = docker_client.containers.create(name=name, **kwargs)
            except APIError as exc:
                if "Conflict" in str(exc) and "container name" in str(exc):
                    self.logger.info(
                        f"Docker container name {display_name!r} already exists; "
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

    def _create_and_start_container(self, configuration) -> "Container":

        # pull image
        docker_client = self._get_client()
        image, tag = parse_image_tag(configuration.image)
        self.logger.info(f"Pulling image {image!r}...")
        docker_client.images.pull(image, tag)

        container_settings = dict(
            image=image,
            command=configuration.command,
            environment=configuration.env,
            auto_remove=configuration.auto_remove,
            labels={"io.prefect.version": prefect.__version__},
            network_mode="host",
            volumes=configuration.volumes,
        )
        container = self._create_container(docker_client, **container_settings)

        # Start the container
        container.start()

        docker_client.close()

        return container
