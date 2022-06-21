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

import os
from tempfile import NamedTemporaryFile
from typing import Any, AnyStr, Iterable, List, Set, Tuple

import fsspec
import yaml

import prefect.orion.schemas as schemas
from prefect.client import OrionClient, inject_client
from prefect.deprecated import deployments as deprecated
from prefect.exceptions import (
    MissingDeploymentError,
    MissingFlowError,
    UnspecifiedDeploymentError,
    UnspecifiedFlowError,
)
from prefect.flows import Flow
from prefect.orion import schemas
from prefect.utilities.collections import extract_instances, listrepr
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.importtools import objects_from_script


class DeploymentSpec(deprecated.DeploymentSpec):
    def __init__(self, **data: Any) -> None:
        # TODO: Add deprecation warning when we are ready to transition
        super().__init__(**data)


# Utilities for loading flows and deployment specifications ----------------------------


def select_flow(
    flows: Iterable[Flow], flow_name: str = None, from_message: str = None
) -> Flow:
    """
    Select the only flow in an iterable or a flow specified by name.

    Returns
        A single flow object

    Raises:
        MissingFlowError: If no flows exist in the iterable
        MissingFlowError: If a flow name is provided and that flow does not exist
        UnspecifiedFlowError: If multiple flows exist but no flow name was provided
    """
    # Convert to flows by name
    flows = {f.name: f for f in flows}

    # Add a leading space if given, otherwise use an empty string
    from_message = (" " + from_message) if from_message else ""

    if not flows:
        raise MissingFlowError(f"No flows found{from_message}.")

    elif flow_name and flow_name not in flows:
        raise MissingFlowError(
            f"Flow {flow_name!r} not found{from_message}. "
            f"Found the following flows: {listrepr(flows.keys())}"
        )

    elif not flow_name and len(flows) > 1:
        raise UnspecifiedFlowError(
            f"Found {len(flows)} flows{from_message}: {listrepr(sorted(flows.keys()))}. "
            "Specify a flow name to select a flow.",
        )

    if flow_name:
        return flows[flow_name]
    else:
        return list(flows.values())[0]


def select_deployment(
    deployments: Iterable[DeploymentSpec],
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


def load_flows_from_script(path: str) -> Set[Flow]:
    """
    Load all flow objects from the given python script. All of the code in the file
    will be executed.

    Returns:
        A set of flows

    Raises:
        FlowScriptError: If an exception is encountered while running the script
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry() as registry:
        with registry.block_code_execution():
            objects = objects_from_script(path)

    return set(extract_instances(objects.values(), types=Flow))


def load_flow_from_script(path: str, flow_name: str = None) -> Flow:
    """
    Extract a flow object from a script by running all of the code in the file.

    If the script has multiple flows in it, a flow name must be provided to specify
    the flow to return.

    Args:
        path: A path to a Python script containing flows
        flow_name: An optional flow name to look for in the script

    Returns:
        The flow object from the script

    Raises:
        See `load_flows_from_script` and `select_flow`
    """
    return select_flow(
        load_flows_from_script(path),
        flow_name=flow_name,
        from_message=f"in script '{path}'",
    )


def deployment_specs_and_flows_from_script(
    script_path: str,
) -> Tuple[List[DeploymentSpec], Set[Flow]]:
    """
    Load deployment specifications and flows from a python script.
    """

    # TODO: Refactor how flows are loaded and make it consistent with how
    # depolyment specrs are loaded. https://github.com/PrefectHQ/orion/issues/2012
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry() as registry:
        with registry.block_code_execution():
            flows = load_flows_from_script(script_path)
    return (registry.deployment_specs, flows)


def deployment_specs_from_script(path: str) -> List[DeploymentSpec]:
    """
    Load deployment specifications from a python script.
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry() as registry:
        with registry.block_code_execution():
            objects_from_script(path)
    return registry.deployment_specs


def deployment_specs_from_yaml(path: str) -> List[DeploymentSpec]:
    """
    Load deployment specifications from a yaml file.
    """
    with fsspec.open(path, "r") as f:
        contents = f.read()

    # Parse into a yaml tree to retrieve separate documents
    nodes = yaml.compose_all(contents)

    specs = []

    for node in nodes:
        line = node.start_mark.line + 1

        # Load deployments relative to the yaml file's directory
        with tmpchdir(path):
            raw_spec = yaml.safe_load(yaml.serialize(node))
            spec = DeploymentSpec.parse_obj(raw_spec)

        # Update the source to be from the YAML file instead of this utility
        spec._source = {"file": str(path), "line": line}
        specs.append(spec)

    return specs


def _register_spec(spec: DeploymentSpec) -> None:
    """
    Collect the `DeploymentSpec` object on the
    PrefectObjectRegistry.deployment_specs dictionary. If multiple specs with
    the same name are created, the last will be used.

    This is convenient for `deployment_specs_from_script` which can collect
    deployment declarations without requiring them to be assigned to a global
    variable.

    """
    from prefect.context import PrefectObjectRegistry

    registry = PrefectObjectRegistry.get()
    registry.deployment_specs.append(spec)


def load_flow_from_text(script_contents: AnyStr, flow_name: str):
    """
    Load a flow from a text script.

    The script will be written to a temporary local file path so errors can refer
    to line numbers and contextual tracebacks can be provided.
    """
    with NamedTemporaryFile(
        mode="wt" if isinstance(script_contents, str) else "wb",
        prefix=f"flow-script-{flow_name}",
        suffix=".py",
        delete=False,
    ) as tmpfile:
        tmpfile.write(script_contents)
        tmpfile.flush()
    try:
        flow = load_flow_from_script(tmpfile.name, flow_name=flow_name)
    finally:
        # windows compat
        tmpfile.close()
        os.remove(tmpfile.name)
    return flow


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
