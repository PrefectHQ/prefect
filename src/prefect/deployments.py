"""
Objects for specifying deployments and utilities for loading flows from deployments.

Deployments can be defined with the `Deployment` object.

To use your deployment, it must be registered with the API. The `Deployment.create()`
method can be used, or the `prefect deployment create` CLI.

Examples:
    Define a flow
    >>> from prefect import flow
    >>> @flow
    >>> def hello_world(name="world"):
    >>>     print(f"Hello, {name}!")

    Write a deployment that sets a new parameter default
    >>> from prefect.deployments import Deployment
    >>> Deployment(
    >>>     flow=hello_world,
    >>>     name="my-first-deployment",
    >>>     parameters={"name": "Earth"},
    >>>     tags=["foo", "bar"],
    >>> )

    Add a schedule to the deployment to run the flow hourly
    >>> from prefect.orion.schemas.schedules import IntervalSchedule
    >>> from datetime import timedelta
    >>> Deployment(
    >>>     ...
    >>>     schedule=IntervalSchedule(interval=timedelta(hours=1))
    >>> )

    Deployments can also be written in YAML and refer to the flow's location instead
    of the `Flow` object. If there are multiple flows in the file, a name will needed
    to load the correct flow.
    ```yaml
    name: my-first-deployment
    flow:
        path: ./path-to-the-flow-script.py
        name: hello-world
    tags:
    - foo
    - bar
    parameters:
      name: "Earth"
    schedule:
      interval: 3600
    ```
"""

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, TextIO, Union

import yaml
from pydantic import BaseModel, Field, parse_obj_as, root_validator, validator

from prefect.blocks.core import Block
from prefect.client import OrionClient, inject_client
from prefect.context import PrefectObjectRegistry
from prefect.exceptions import MissingDeploymentError, UnspecifiedDeploymentError
from prefect.filesystems import LocalFileSystem
from prefect.flows import Flow, load_flow_from_script
from prefect.infrastructure import DockerContainer, KubernetesJob, Process
from prefect.logging.loggers import flow_run_logger
from prefect.orion import schemas
from prefect.orion.schemas.data import DataDocument
from prefect.packaging.base import PackageManifest, Packager
from prefect.packaging.orion import OrionPackager
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.callables import ParameterSchema
from prefect.utilities.collections import listrepr
from prefect.utilities.dispatch import get_dispatch_key, lookup_type
from prefect.utilities.filesystem import tmpchdir, to_display_path
from prefect.utilities.importtools import load_flow_from_manifest_path


class FlowScript(BaseModel):
    """
    A simple Pydantic model defining the location of a flow script and, optionally,
    the flow object that begins the workflow.

    Args:
        path: Path to a script containing the flow to deploy. If you specify a string path, it will be cast to a `Path`.
        name: String specifying the name of the flow object to associate with the deployment. Optional if the flow can be inferred from the script.
    """

    path: Path
    name: Optional[str] = None

    @validator("path")
    def resolve_path_to_absolute_location(cls, value):
        return value.resolve()


FlowSource = Union[Flow, Path, FlowScript, PackageManifest]


@PrefectObjectRegistry.register_instances
class Deployment(BaseModel):
    """
    Defines the settings used to create a deployment on the API.

    Args:
        name: String specifying the name of the deployment.
        flow: The flow object to associate with the deployment. You may provide the flow object directly as `flow=my_flow` if available in the same file as the `Deployment`. Alternatively, you may provide a `Path`, `FlowScript`, or `PackageManifest` specifying how to access to the flow.
        packager: The [prefect.packaging](/api-ref/prefect/packaging/) packager to use for packaging the flow.
        parameters: Dictionary of default parameters to set on flow runs from this deployment. If defined in Python, the values should be Pydantic-compatible objects.
        schedule: [Schedule](/concepts/schedules/) instance specifying a schedule for running the deployment.
        tags: List containing tags to assign to the deployment.
    """

    # Metadata fields
    name: str = None
    tags: List[str] = Field(default_factory=list)

    # The source of the flow
    flow: FlowSource
    packager: Optional[Packager] = Field(default_factory=OrionPackager)

    # Flow run fields
    parameters: Dict[str, Any] = Field(default_factory=dict)
    schedule: schemas.schedules.SCHEDULE_TYPES = None

    infrastructure: Union[DockerContainer, KubernetesJob, Process] = Field(
        default_factory=Process
    )

    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)

    @root_validator(pre=True)
    def packager_cannot_be_provided_with_manifest(cls, values):
        if "packager" in values and isinstance(values.get("flow"), PackageManifest):
            raise ValueError(
                "A packager cannot be provided if a package manifest is provided "
                "instead of a flow. Provide a local flow instead or leave the packager "
                "field empty."
            )
        return values

    @root_validator
    def infrastructure_packager_compatibility(cls, values):
        infrastructure = values.get("infrastructure")
        flow = values.get("flow")
        packager = values.get("packager")

        if isinstance(flow, PackageManifest):
            manifest_cls = type(flow)
        elif packager:
            manifest_cls = lookup_type(PackageManifest, get_dispatch_key(packager))
        else:
            # We don't have a manifest so there's nothing to validate
            return values

        if "image" in manifest_cls.__fields__:
            if "image" not in infrastructure.__fields__:
                raise ValueError(
                    f"Packaged flow requires an image but {infrastructure.__class__.__name__!r} "
                    "does not have an image field."
                )
            elif "image" in infrastructure.__fields_set__:
                raise ValueError(
                    f"Packaged flow requires an image but the infrastructure already has "
                    f"image {infrastructure.image!r} configured. Exclude the image "
                    "from your infrastucture to allow Prefect to set it to the package "
                    "image tag."
                )

        return values

    @sync_compatible
    @inject_client
    async def create(
        self,
        client: OrionClient,
        stream_progress_to: Optional[TextIO] = None,
    ):
        """
        Create the deployment by registering with the API.
        """
        stream_progress_to = stream_progress_to or StringIO()
        if isinstance(self.flow, PackageManifest):
            manifest = self.flow
            flow_name = manifest.flow_name
        else:
            if isinstance(self.flow, FlowScript):
                stream_progress_to.write(
                    f"Retrieving flow from script at {to_display_path(self.flow.path)}..."
                )
            flow = await _source_to_flow(self.flow)
            flow_name = flow.name
            stream_progress_to.write(f"Packaging flow...")
            manifest = await self.packager.package(flow)

        flow_id = await client.create_flow_from_name(flow_name)

        updates = {}
        if "image" in manifest.__fields__:
            stream_progress_to.write(
                f"Updating infrastructure image to {manifest.image!r}..."
            )
            updates["image"] = manifest.image

        infrastructure = self.infrastructure.copy(update=updates)

        # Always save as an anonymous block even if we are given a block that is
        # already registered. This will make behavior consistent when we need to
        # update values on the infrastucture.
        infrastructure_document_id = await infrastructure._save(is_anonymous=True)

        flow_data = DataDocument.encode("package-manifest", manifest)

        stream_progress_to.write("Registering with server...")
        return await client.create_deployment(
            flow_id=flow_id,
            name=self.name or flow_name,
            flow_data=flow_data,
            schedule=self.schedule,
            parameters=self.parameters,
            tags=self.tags,
            infrastructure_document_id=infrastructure_document_id,
        )

    class Config:
        arbitrary_types_allowed = True
        extra = "forbid"


def select_deployment(
    deployments: Iterable[Deployment],
    deployment_name: str = None,
    flow_name: str = None,
    from_message: str = None,
) -> Flow:
    """
    Select the only deployment in an iterable or a deployment specified by either
    deployment or flow name.

    Returns
        A single deployment object

    Raises:
        MissingDeploymentError: If no deployments exist in the iterable
        MissingDeploymentError: If a deployment name is provided and that deployment does not exist
        UnspecifiedDeploymentError: If multiple deployments exist but no deployment name was provided
    """
    # Convert to deployments by name and flow name
    deployments = {d.name: d for d in deployments}

    if flow_name:
        # If given a lookup by flow name, ensure the deployments have a flow name
        # resolved
        for deployment in deployments.values():
            if not deployment.flow_name:
                deployment.resolve_flow()
        deployments_by_flow = {d.flow_name: d for d in deployments.values()}

    # Add a leading space if given, otherwise use an empty string
    from_message = (" " + from_message) if from_message else ""

    if not deployments:
        raise MissingDeploymentError(f"No deployments found{from_message}.")

    elif deployment_name and deployment_name not in deployments:
        raise MissingDeploymentError(
            f"Deployment {deployment_name!r} not found{from_message}. "
            f"Found the following deployments: {listrepr(deployments.keys())}"
        )

    elif flow_name and flow_name not in deployments_by_flow:
        raise MissingDeploymentError(
            f"Deployment for flow {flow_name!r} not found{from_message}. "
            "Found deployments for the following flows: "
            f"{listrepr(deployments_by_flow.keys())}"
        )

    elif not deployment_name and not flow_name and len(deployments) > 1:
        raise UnspecifiedDeploymentError(
            f"Found {len(deployments)} deployments{from_message}: {listrepr(deployments.keys())}. "
            "Specify a deployment or flow name to select a deployment.",
        )

    if deployment_name:
        deployment = deployments[deployment_name]
        if flow_name and deployment.flow_name != flow_name:
            raise MissingDeploymentError(
                f"Deployment {deployment_name!r} for flow {flow_name!r} not found. "
                f"Found deployment {deployment_name!r} but it is for flow "
                f"{deployment.flow_name!r}."
            )
        return deployment
    elif flow_name:
        return deployments_by_flow[flow_name]
    else:
        return list(deployments.values())[0]


@inject_client
async def load_flow_from_deployment(
    deployment: schemas.core.Deployment, client: OrionClient
) -> Flow:
    """
    Load a flow from the location/script provided in a deployment's storage document.
    """
    with open(deployment.manifest_path, "r") as f:
        manifest = json.load(f)
    return load_flow_from_manifest_path(manifest["import_path"])


@inject_client
async def load_flow_from_flow_run(
    flow_run: schemas.core.FlowRun, client: OrionClient
) -> Flow:
    """
    Load a flow from the location/script provided in a deployment's storage document.
    """
    deployment = await client.read_deployment(flow_run.deployment_id)
    storage_document = await client.read_block_document(deployment.storage_document_id)
    storage_block = Block._from_block_document(storage_document)

    sys.path.insert(0, ".")
    await storage_block.get_directory(from_path=None, local_path=".")

    flow_run_logger(flow_run).debug(
        f"Loading flow for deployment {deployment.name!r}..."
    )
    flow = await load_flow_from_deployment(deployment, client=client)
    return flow


async def _source_to_flow(flow_source: FlowSource) -> Flow:
    if isinstance(flow_source, Flow):
        return flow_source
    elif isinstance(flow_source, Path):
        return load_flow_from_script(flow_source.expanduser().resolve())
    elif isinstance(flow_source, FlowScript):
        return load_flow_from_script(
            flow_source.path.expanduser().resolve(), flow_name=flow_source.name
        )
    elif isinstance(flow_source, PackageManifest):
        return await flow_source.unpackage()
    else:
        raise TypeError(
            f"Unknown type {type(flow_source).__name__!r} for flow source. "
            "Expected one of 'Flow', 'FlowScript', or 'PackageManifest'."
        )


def load_deployments_from_yaml(
    path: str,
) -> PrefectObjectRegistry:
    """
    Load deployments from a yaml file.
    """
    with open(path, "r") as f:
        contents = f.read()

    # Parse into a yaml tree to retrieve separate documents
    nodes = yaml.compose_all(contents)

    with PrefectObjectRegistry(capture_failures=True) as registry:
        for node in nodes:
            with tmpchdir(path):
                deployment_dict = yaml.safe_load(yaml.serialize(node))
                # The return value is not necessary, just instantiating the Deployment
                # is enough to get it recorded on the registry
                parse_obj_as(Deployment, deployment_dict)

    return registry


class DeploymentYAML(BaseModel):
    @property
    def editable_fields(self) -> List[str]:
        editable_fields = [
            "name",
            "description",
            "tags",
            "schedule",
            "parameters",
            "infrastructure",
        ]
        return editable_fields

    @property
    def header(self) -> str:
        return f"###\n### A complete description of a Prefect Deployment for flow {self.flow_name!r}\n###\n"

    def yaml_dict(self) -> dict:
        # avoids issues with UUIDs showing up in YAML
        all_fields = json.loads(
            self.json(
                exclude={
                    "storage": {"_filesystem", "filesystem", "_remote_file_system"}
                }
            )
        )
        all_fields["storage"]["_block_type_slug"] = self.storage.get_block_type_slug()
        return all_fields

    def editable_fields_dict(self):
        "Returns YAML compatible dictionary of editable fields, in the correct order"
        all_fields = self.yaml_dict()
        return {field: all_fields[field] for field in self.editable_fields}

    def immutable_fields_dict(self):
        "Returns YAML compatible dictionary of immutable fields, in the correct order"
        all_fields = self.yaml_dict()
        return {k: v for k, v in all_fields.items() if k not in self.editable_fields}

    # top level metadata
    name: str = Field(..., description="The name of the deployment.")
    description: str = Field(
        None, description="An optional description of the deployment."
    )
    tags: List[str] = Field(default_factory=list)
    schedule: schemas.schedules.SCHEDULE_TYPES = None
    flow_name: str = Field(..., description="The name of the flow.")

    # flow data
    parameters: Dict[str, Any] = Field(default_factory=dict)
    manifest_path: str = Field(
        ...,
        description="The path to the flow's manifest file, relative to the chosen storage.",
    )
    infrastructure: Union[DockerContainer, KubernetesJob, Process] = Field(
        default_factory=Process
    )
    storage: Block = Field(default_factory=LocalFileSystem)
    parameter_openapi_schema: ParameterSchema = Field(
        ..., description="The parameter schema of the flow, including defaults."
    )

    @validator("storage", pre=True)
    def cast_storage_to_block_type(cls, value):
        if isinstance(value, dict):
            block = lookup_type(Block, value.pop("_block_type_slug"))
            return block(**value)
        return value
