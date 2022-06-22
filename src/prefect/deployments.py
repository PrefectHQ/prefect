"""
Objects for specifying deployments and utilities for loading flows from deployments.

The primary object is the `DeploymentSpec` which can be used to define a deployment.
Once a specification is written, it can be used with the Orion client or CLI to create
a deployment in the backend.

Examples:
    Define a flow
    >>> from prefect import flow
    >>> @flow
    >>> def hello_world(name="world"):
    >>>     print(f"Hello, {name}!")

    Write a deployment specification that sets a new parameter default
    >>> from prefect.deployments import DeploymentSpec
    >>> DeploymentSpec(
    >>>     flow=hello_world,
    >>>     name="my-first-deployment",
    >>>     parameters={"name": "Earth"},
    >>>     tags=["foo", "bar"],
    >>> )

    Add a schedule to the deployment specification to run the flow hourly
    >>> from prefect.orion.schemas.schedules import IntervalSchedule
    >>> from datetime import timedelta
    >>> DeploymentSpec(
    >>>     ...
    >>>     schedule=IntervalSchedule(interval=timedelta(hours=1))
    >>> )

    Deployment specifications can also be written in YAML and refer to the flow's
    location instead of the `Flow` object
    ```yaml
    name: my-first-deployment
    flow_location: ./path-to-the-flow-script.py
    flow_name: hello-world
    tags:
    - foo
    - bar
    parameters:
      name: "Earth"
    schedule:
      interval: 3600
    ```
"""

from typing import Any, Dict, Iterable, List, Optional, Union

from pydantic import BaseModel, Field

import prefect.orion.schemas as schemas
from prefect.client import OrionClient, inject_client
from prefect.deprecated import deployments as deprecated
from prefect.exceptions import MissingDeploymentError, UnspecifiedDeploymentError
from prefect.flow_runners.base import FlowRunner, FlowRunnerSettings
from prefect.flows import Flow, load_flow_from_script, load_flow_from_text
from prefect.orion import schemas
from prefect.packaging.base import PackageManifest, Packager
from prefect.packaging.file import FilePackager
from prefect.utilities.collections import listrepr


class FlowScript:
    path: str
    name: Optional[str] = None


FlowSource = Union[Flow, FlowScript, PackageManifest]


def source_to_flow(flow_source: FlowSource) -> Flow:
    if isinstance(flow_source, Flow):
        return flow_source
    elif isinstance(flow_source, FlowScript):
        return load_flow_from_script(flow_source.path, name=flow_source.name)
    elif isinstance(flow_source, PackageManifest):
        raise TypeError("Cannot resolve a package manifest directly into a flow.")
    else:
        raise TypeError(
            "Unknown type {type(flow_source).__name__!r} for flow source. "
            "Expected one of 'Flow', 'FlowScript', or 'PackageManifest'."
        )


class Deployment(BaseModel):

    # Metadata fields
    name: str = None
    tags: List[str] = Field(default_factory=list)

    # The source of the flow
    flow: FlowSource
    packager: Optional[Packager] = Field(default_factory=FilePackager)

    # Flow run fields
    parameters: Dict[str, Any] = Field(default_factory=dict)
    schedule: schemas.schedules.SCHEDULE_TYPES = None

    # TODO: Change to 'infrastructure'
    flow_runner: Union[FlowRunner, FlowRunnerSettings] = None

    @inject_client
    async def create(self, client: OrionClient):
        if "packager" in self.__fields_set__ and isinstance(self.flow, PackageManifest):
            raise ValueError(
                "A packager cannot be provided if a package manifest is provided "
                "instead of a flow. Provide a local flow instead or leave the packager "
                "field empty."
            )


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
        flow = load_flow_from_text(maybe_flow, flow_model.name)
    else:
        if not isinstance(maybe_flow, Flow):
            raise TypeError(
                "Deployment `flow_data` did not resolve to a `Flow`. "
                f"Found {maybe_flow}"
            )
        flow = maybe_flow

    return flow


# Backwards compatibility


class DeploymentSpec(deprecated.DeploymentSpec):
    def __init__(self, **data: Any) -> None:
        # TODO: Add deprecation warning when we are ready to transition
        super().__init__(**data)
