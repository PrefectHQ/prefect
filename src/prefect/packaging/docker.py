import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from pydantic import AnyHttpUrl, root_validator, validator
from slugify import slugify
from typing_extensions import Literal

from prefect.docker import ImageBuilder, build_image, push_image, to_run_command
from prefect.flow_runners.docker import get_prefect_image_name
from prefect.flows import Flow, load_flow_from_script
from prefect.packaging.base import PackageManifest, Packager
from prefect.packaging.serializers import SourceSerializer
from prefect.software import CondaEnvironment, PythonEnvironment
from prefect.utilities.asyncutils import run_sync_in_worker_thread


class DockerPackageManifest(PackageManifest):
    """
    Represents a flow packaged in a Docker image
    """

    type: Literal["docker"] = "docker"

    image: str
    image_flow_location: str

    async def unpackage(self) -> Flow:
        return load_flow_from_script(self.image_flow_location, self.flow_name)


class DockerPackager(Packager):
    """
    This packager builds a Docker image containing the flow and the runtime environment
    necessary to run the flow.  The resulting image is optionally pushed to a container
    registry, given by `registry_url`.
    """

    type: Literal["docker"] = "docker"

    base_image: Optional[str] = None
    python_environment: Optional[Union[PythonEnvironment, CondaEnvironment]] = None
    dockerfile: Optional[Path] = None
    image_flow_location: str = "/flow.py"
    registry_url: Optional[AnyHttpUrl] = None

    @root_validator
    def set_default_base_image(cls, values):
        if not values.get("base_image") and not values.get("dockerfile"):
            values["base_image"] = get_prefect_image_name(
                flavor="conda"
                if isinstance(values.get("python_environment"), CondaEnvironment)
                else None
            )
        return values

    @root_validator
    def base_image_and_dockerfile_exclusive(cls, values: Mapping[str, Any]):
        if values.get("base_image") and values.get("dockerfile"):
            raise ValueError(
                "Either `base_image` or `dockerfile` should be provided, but not both"
            )
        return values

    @root_validator
    def default_python_environment(cls, values: Mapping[str, Any]):
        if values.get("base_image") and not values.get("python_environment"):
            values["python_environment"] = PythonEnvironment.from_environment()
        return values

    @validator("registry_url", pre=True)
    def ensure_registry_url_is_prefixed(cls, value):
        if isinstance(value, str):
            if "://" not in value:
                return "https://" + value
        return value

    async def package(self, flow: Flow) -> DockerPackageManifest:
        """
        Package a flow as a Docker image and, optionally, push it to a registry
        """
        image_reference = await self._build_image(flow)

        if self.registry_url:
            image_name = f"{slugify(flow.name)}"
            image_reference = await run_sync_in_worker_thread(
                push_image, image_reference, self.registry_url, image_name
            )

        return self.base_manifest(flow).finalize(
            image=image_reference, image_flow_location=self.image_flow_location
        )

    async def _build_image(self, flow: Flow) -> str:
        if self.dockerfile:
            return await self._build_from_dockerfile()
        return await self._build_from_base_image(flow)

    async def _build_from_dockerfile(self) -> str:
        context = self.dockerfile.resolve().parent
        dockerfile = self.dockerfile.relative_to(context)
        return await run_sync_in_worker_thread(
            build_image, context=context, dockerfile=str(dockerfile)
        )

    async def _build_from_base_image(self, flow: Flow) -> str:
        with ImageBuilder(base_image=self.base_image) as builder:
            for command in self.python_environment.install_commands():
                builder.add_line(to_run_command(command))

            source_info = json.loads(SourceSerializer().dumps(flow))

            builder.write_text(source_info["source"], self.image_flow_location)

            return await run_sync_in_worker_thread(
                builder.build, stream_progress_to=sys.stdout
            )
