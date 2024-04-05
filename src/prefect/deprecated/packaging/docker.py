"""
DEPRECATION WARNING:
This module is deprecated as of March 2024 and will not be available after September 2024.
"""

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.schemas.validators import (
    assign_default_base_image,
    base_image_xor_dockerfile,
    set_default_python_environment,
    validate_registry_url,
)

if HAS_PYDANTIC_V2:
    from pydantic.v1 import AnyHttpUrl, root_validator, validator
else:
    from pydantic import AnyHttpUrl, root_validator, validator
from typing_extensions import Literal

from prefect.deprecated.packaging.base import PackageManifest, Packager
from prefect.deprecated.packaging.serializers import SourceSerializer
from prefect.flows import Flow, load_flow_from_script
from prefect.software import CondaEnvironment, PythonEnvironment
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.dockerutils import (
    ImageBuilder,
    build_image,
    push_image,
    to_run_command,
)
from prefect.utilities.slugify import slugify


@deprecated_class(start_date="Mar 2024")
class DockerPackageManifest(PackageManifest):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

    Represents a flow packaged in a Docker image
    """

    type: Literal["docker"] = "docker"

    image: str
    image_flow_location: str

    async def unpackage(self) -> Flow:
        return load_flow_from_script(self.image_flow_location, self.flow_name)


@deprecated_class(start_date="Mar 2024")
class DockerPackager(Packager):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

    This packager builds a Docker image containing the flow and the runtime environment
    necessary to run the flow.  The resulting image is optionally pushed to a container
    registry, given by `registry_url`.
    """

    type: str = "docker"

    base_image: Optional[str] = None
    python_environment: Optional[Union[PythonEnvironment, CondaEnvironment]] = None
    dockerfile: Optional[Path] = None
    platform: Optional[str] = (None,)
    image_flow_location: str = "/flow.py"
    registry_url: Optional[AnyHttpUrl] = None

    @root_validator
    def set_default_base_image(cls, values):
        return assign_default_base_image(values)

    @root_validator
    def base_image_and_dockerfile_exclusive(cls, values: Mapping[str, Any]):
        return base_image_xor_dockerfile(values)

    @root_validator
    def default_python_environment(cls, values: Mapping[str, Any]):
        return set_default_python_environment(values)

    @validator("registry_url", pre=True)
    def ensure_registry_url_is_prefixed(cls, value):
        validate_registry_url(value)

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

        return DockerPackageManifest(
            **{
                **self.base_manifest(flow).dict(),
                **{
                    "image": image_reference,
                    "image_flow_location": self.image_flow_location,
                },
            }
        )

    async def _build_image(self, flow: Flow) -> str:
        if self.dockerfile:
            return await self._build_from_dockerfile()
        return await self._build_from_base_image(flow)

    async def _build_from_dockerfile(self) -> str:
        context = self.dockerfile.resolve().parent
        dockerfile = self.dockerfile.relative_to(context)
        return await run_sync_in_worker_thread(
            build_image,
            platform=self.platform,
            context=context,
            dockerfile=str(dockerfile),
        )

    async def _build_from_base_image(self, flow: Flow) -> str:
        with ImageBuilder(
            base_image=self.base_image, platform=self.platform
        ) as builder:
            for command in self.python_environment.install_commands():
                builder.add_line(to_run_command(command))

            source_info = json.loads(SourceSerializer().dumps(flow))

            builder.write_text(source_info["source"], self.image_flow_location)

            return await run_sync_in_worker_thread(
                builder.build, stream_progress_to=sys.stdout
            )
