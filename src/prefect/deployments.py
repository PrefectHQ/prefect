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

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, parse_obj_as, root_validator, validator

from prefect.client import OrionClient, inject_client
from prefect.context import PrefectObjectRegistry
from prefect.exceptions import MissingDeploymentError, UnspecifiedDeploymentError
from prefect.flow_runners.base import (
    FlowRunner,
    FlowRunnerSettings,
    UniversalFlowRunner,
)
from prefect.flows import Flow, load_flow_from_script, load_flow_from_text
from prefect.orion import schemas
from prefect.orion.schemas.data import DataDocument
from prefect.packaging.base import PackageManifest, Packager
from prefect.packaging.orion import OrionPackager
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.collections import listrepr
from prefect.utilities.dispatch import get_dispatch_key, lookup_type
from prefect.utilities.filesystem import tmpchdir


class FlowScript(BaseModel):
    path: Path
    name: Optional[str] = None

    @validator("path")
    def resolve_path_to_absolute_location(cls, value):
        return value.resolve()


FlowSource = Union[Flow, Path, FlowScript, PackageManifest]


@PrefectObjectRegistry.register_instances
class Deployment(BaseModel):

    # Metadata fields
    name: str = None
    tags: List[str] = Field(default_factory=list)

    # The source of the flow
    flow: FlowSource
    packager: Optional[Packager] = Field(default_factory=OrionPackager)

    # Flow run fields
    parameters: Dict[str, Any] = Field(default_factory=dict)
    schedule: schemas.schedules.SCHEDULE_TYPES = None

    # TODO: Change to 'infrastructure'
    flow_runner: Union[FlowRunner, FlowRunnerSettings] = Field(
        default_factory=UniversalFlowRunner
    )

    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)

    @validator("flow_runner")
    def cast_flow_runner_settings(cls, value):
        if isinstance(value, FlowRunnerSettings):
            return FlowRunner.from_settings(value)
        return value

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
    def flow_runner_packager_compatibility(cls, values):
        flow_runner = values.get("flow_runner")
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
            if "image" not in flow_runner.__fields__:
                raise ValueError(
                    f"Packaged flow requires an image but the {flow_runner.typename!r} "
                    "flow runner does not have an image field."
                )
            elif "image" in flow_runner.__fields_set__:
                raise ValueError(
                    f"Packaged flow requires an image but the flow runner already has "
                    f"image {flow_runner.image!r} configured. Exclude the image "
                    "from your flow runner to allow Prefect to set it to the package "
                    "image tag."
                )

        return values

    @sync_compatible
    @inject_client
    async def create(self, client: OrionClient):
        if isinstance(self.flow, PackageManifest):
            manifest = self.flow
            flow_name = manifest.flow_name
        else:
            flow = await _source_to_flow(self.flow)
            flow_name = flow.name
            manifest = await self.packager.package(flow)

        flow_id = await client.create_flow_from_name(flow_name)

        if "image" in manifest.__fields__:
            self.flow_runner = self.flow_runner.copy(update={"image": manifest.image})

        flow_data = DataDocument.encode("package-manifest", manifest)

        return await client.create_deployment(
            flow_id=flow_id,
            name=self.name or flow_name,
            flow_data=flow_data,
            schedule=self.schedule,
            parameters=self.parameters,
            tags=self.tags,
            flow_runner=self.flow_runner,
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
    Load a flow from the location/script/pickle provided in a deployment's flow data
    document.
    """
    flow_model = await client.read_flow(deployment.flow_id)

    maybe_flow = await client.resolve_datadoc(deployment.flow_data)
    if isinstance(maybe_flow, (str, bytes)):
        flow = await run_sync_in_worker_thread(
            load_flow_from_text, maybe_flow, flow_model.name
        )
    elif isinstance(maybe_flow, PackageManifest):
        flow = await maybe_flow.unpackage()
    else:
        flow = maybe_flow

    if not isinstance(flow, Flow):
        raise TypeError(
            "Deployment `flow_data` did not resolve to a `Flow`. Found: {flow!r}."
        )

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
