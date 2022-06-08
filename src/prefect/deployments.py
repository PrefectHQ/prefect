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
import pathlib
import sys
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from os.path import abspath
from tempfile import NamedTemporaryFile
from typing import Any, AnyStr, Dict, Iterable, List, Optional, Set, Tuple, Union
from uuid import UUID

import fsspec
import yaml
from pydantic import Field, validator

import prefect.orion.schemas as schemas
from prefect.blocks.core import Block
from prefect.blocks.storage import LocalStorageBlock, StorageBlock, TempStorageBlock
from prefect.client import OrionClient, inject_client
from prefect.exceptions import (
    MissingDeploymentError,
    MissingFlowError,
    ObjectAlreadyExists,
    SpecValidationError,
    UnspecifiedDeploymentError,
    UnspecifiedFlowError,
)
from prefect.flow_runners import (
    FlowRunner,
    FlowRunnerSettings,
    SubprocessFlowRunner,
    UniversalFlowRunner,
)
from prefect.flows import Flow
from prefect.orion import schemas
from prefect.orion.schemas.core import raise_on_invalid_name
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.schedules import SCHEDULE_TYPES
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.utilities.asyncio import sync_compatible
from prefect.utilities.collections import extract_instances, listrepr
from prefect.utilities.filesystem import is_local_path, tmpchdir
from prefect.utilities.importtools import objects_from_script


class DeploymentSpec(PrefectBaseModel):
    """
    Specification for a flow deployment. Used to create or update deployments.

    The flow object or flow location must be provided. If a flow object is not provided,
    `load_flow` must be called to load the flow from the given flow location.

    Args:
        name: The name of the deployment
        flow: The flow object to associate with the deployment
        flow_location: The path to a script containing the flow to associate with the
            deployment. Inferred from `flow` if provided.
        flow_name: The name of the flow to associated with the deployment. Only required
            if loading the flow from a `flow_location` with multiple flows. Inferred
            from `flow` if provided.
        flow_runner: The [flow runner](/api-ref/prefect/flow-runners/) to be used for
            flow runs.
        flow_storage: A [prefect.blocks.storage](/api-ref/prefect/blocks/storage/) instance
            providing the [storage](/concepts/storage/) to be used for the flow
            definition and results.
        parameters: An optional dictionary of default parameters to set on flow runs
            from this deployment. If defined in Python, the values should be Pydantic
            compatible objects.
        schedule: An optional schedule instance to use with the deployment.
        tags: An optional set of tags to assign to the deployment.
    """

    name: str = None
    flow: Flow = None
    flow_name: str = None
    flow_location: str = None
    flow_storage: Optional[Union[StorageBlock, UUID]] = None
    parameters: Dict[str, Any] = None
    schedule: SCHEDULE_TYPES = None
    tags: List[str] = None
    flow_runner: Union[FlowRunner, FlowRunnerSettings] = Field(
        default_factory=UniversalFlowRunner
    )

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # After initialization; register this deployment. See `_register_new_specs`
        _register_spec(self)

    # Validation and inference ---------------------------------------------------------

    @validator("flow_location", pre=True)
    def ensure_paths_are_absolute_strings(cls, value):
        if isinstance(value, pathlib.Path):
            return str(value.absolute())
        elif isinstance(value, str) and is_local_path(value):
            return abspath(value)
        return value

    @sync_compatible
    @inject_client
    async def validate(self, client: OrionClient):

        # Ensure either flow location or flow were provided

        if not self.flow_location and not self.flow:
            raise SpecValidationError(
                "Either `flow_location` or `flow` must be provided."
            )

        # Load the flow from the flow location

        if self.flow_location and not self.flow:
            try:
                self.flow = load_flow_from_script(self.flow_location, self.flow_name)
            except MissingFlowError as exc:
                raise SpecValidationError(str(exc)) from exc

        # Infer the flow location from the flow

        elif self.flow and not self.flow_location:
            self.flow_location = self.flow.fn.__globals__.get("__file__")

        # Ensure the flow location matches the flow both are given

        elif self.flow and self.flow_location and is_local_path(self.flow_location):
            flow_file = self.flow.fn.__globals__.get("__file__")
            if flow_file:
                abs_given = abspath(str(self.flow_location))
                abs_flow = abspath(str(flow_file))
                if abs_given != abs_flow:
                    raise SpecValidationError(
                        f"The given flow location {abs_given!r} does not "
                        f"match the path of the given flow: '{abs_flow}'."
                    )

        # Ensure the flow location is absolute if local

        if self.flow_location and is_local_path(self.flow_location):
            self.flow_location = abspath(str(self.flow_location))

        # Ensure the flow location is set

        if not self.flow_location:
            raise SpecValidationError(
                "Failed to determine the location of your flow. "
                "Provide the path to your flow code with `flow_location`."
            )

        # Infer flow name from flow

        if self.flow and not self.flow_name:
            self.flow_name = self.flow.name

        # Ensure a given flow name matches the given flow's name

        elif self.flow.name != self.flow_name:
            raise SpecValidationError(
                "`flow.name` and `flow_name` must match. "
                f"Got {self.flow.name!r} and {self.flow_name!r}."
            )

        # Default the deployment name to the flow name

        if not self.name and self.flow_name:
            self.name = self.flow_name

        # Convert flow runner settings to concrete instances

        if isinstance(self.flow_runner, FlowRunnerSettings):
            self.flow_runner = FlowRunner.from_settings(self.flow_runner)

        # Do not allow the abstract flow runner type

        if type(self.flow_runner) is FlowRunner:
            raise SpecValidationError(
                "The base `FlowRunner` type cannot be used. Provide a flow runner "
                "implementation or flow runner settings instead."
            )

        # Determine the storage block

        # TODO: Some of these checks may be retained in the future, but will use block
        # capabilities instead of types to check for compatibility with flow runners

        if self.flow_storage is None:
            default_block_document = await client.get_default_storage_block_document()
            if default_block_document:
                self.flow_storage = Block._from_block_document(default_block_document)
        no_storage_message = "You have not configured default storage on the server or set a storage to use for this deployment"

        if isinstance(self.flow_storage, UUID):
            flow_storage_block_document = await client.read_block_document(
                self.flow_storage
            )
            self.flow_storage = Block._from_block_document(flow_storage_block_document)

        if isinstance(self.flow_runner, SubprocessFlowRunner):
            local_machine_message = (
                "this deployment will only be usable from the current machine."
            )
            if not self.flow_storage:
                warnings.warn(f"{no_storage_message}, {local_machine_message}")
                self.flow_storage = LocalStorageBlock()
            elif isinstance(self.flow_storage, (LocalStorageBlock, TempStorageBlock)):
                warnings.warn(
                    f"You have configured local storage, {local_machine_message}."
                )
        else:
            # All other flow runners require remote storage, ensure we've been given one
            flow_runner_message = f"this deployment is using a {self.flow_runner.typename.capitalize()} flow runner which requires remote storage"
            if not self.flow_storage:
                raise SpecValidationError(
                    f"{no_storage_message} but {flow_runner_message}."
                )
            elif isinstance(self.flow_storage, (LocalStorageBlock, TempStorageBlock)):
                raise SpecValidationError(
                    f"You have configured local storage but {flow_runner_message}."
                )

    # Methods --------------------------------------------------------------------------

    @sync_compatible
    @inject_client
    async def create_deployment(
        self, client: OrionClient, validate: bool = True
    ) -> UUID:
        """
        Create a deployment from the current specification.
        """
        if validate:
            await self.validate()

        flow_id = await client.create_flow(self.flow)

        # Read the flow file
        with fsspec.open(self.flow_location, "rb") as flow_file:
            flow_bytes = flow_file.read()

        # Ensure the storage is a registered block for later retrieval

        if not self.flow_storage._block_document_id:
            block_schema = await client.read_block_schema_by_checksum(
                self.flow_storage._calculate_schema_checksum()
            )

            block_name = f"{self.flow_name}-{self.name}-{self.flow.version}"
            i = 0
            while not self.flow_storage._block_document_id:
                try:
                    block_document = await client.create_block_document(
                        block_document=self.flow_storage._to_block_document(
                            name=f"{self.flow_name}-{self.name}-{self.flow.version}-{i}",
                            block_schema_id=block_schema.id,
                            block_type_id=block_schema.block_type_id,
                        )
                    )
                    self.flow_storage._block_document_id = block_document.id
                except ObjectAlreadyExists:
                    i += 1

        # Write the flow to storage
        storage_token = await self.flow_storage.write(flow_bytes)
        flow_data = DataDocument.encode(
            encoding="blockstorage",
            data={
                "data": storage_token,
                "block_document_id": self.flow_storage._block_document_id,
            },
        )

        deployment_id = await client.create_deployment(
            flow_id=flow_id,
            name=self.name,
            schedule=self.schedule,
            flow_data=flow_data,
            parameters=self.parameters,
            tags=self.tags,
            flow_runner=self.flow_runner,
        )

        return deployment_id

    # Pydantic -------------------------------------------------------------------------

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_invalid_name(v)
        return v

    class Config:
        arbitrary_types_allowed = True

    def __hash__(self) -> int:
        # Deployments are unique on name / flow name pair
        return hash((self.name, self.flow_name))


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
                deployment.load_flow()
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
) -> Tuple[Dict[DeploymentSpec, str], Set[Flow]]:
    """
    Load deployment specifications and flows from a python script.
    """
    with _register_new_specs() as specs:
        flows = load_flows_from_script(script_path)

    return (specs, flows)


def deployment_specs_from_script(path: str) -> Dict[DeploymentSpec, str]:
    """
    Load deployment specifications from a python script.
    """
    with _register_new_specs() as specs:
        objects_from_script(path)

    return specs


def deployment_specs_from_yaml(path: str) -> Dict[DeploymentSpec, dict]:
    """
    Load deployment specifications from a yaml file.
    """
    with fsspec.open(path, "r") as f:
        contents = f.read()

    # Parse into a yaml tree to retrieve separate documents
    nodes = yaml.compose_all(contents)

    specs = {}

    for node in nodes:
        line = node.start_mark.line + 1

        # Load deployments relative to the yaml file's directory
        with tmpchdir(path):
            raw_spec = yaml.safe_load(yaml.serialize(node))
            spec = DeploymentSpec.parse_obj(raw_spec)

        specs[spec] = {"file": str(path), "line": line}

    return specs


# Global for `DeploymentSpec` collection; see `_register_new_specs`
_DeploymentSpecContextVar = ContextVar("_DeploymentSpecContext")


@contextmanager
def _register_new_specs():
    """
    Collect any `DeploymentSpec` objects created during this context into a set.
    If multiple specs with the same name are created, the last will be used an the
    earlier will be used.

    This is convenient for `deployment_specs_from_script` which can collect deployment
    declarations without requiring them to be assigned to a global variable
    """
    specs = dict()
    token = _DeploymentSpecContextVar.set(specs)
    yield specs
    _DeploymentSpecContextVar.reset(token)


def _register_spec(spec: DeploymentSpec) -> None:
    """
    See `_register_new_specs`
    """
    specs = _DeploymentSpecContextVar.get(None)

    if specs is None:
        return

    # Retrieve information about the definition of the spec
    # This goes back two frames to where the spec was defined
    #   - This function (current frame)
    #   - DeploymentSpec.__init__
    #   - DeploymentSpec definition

    frame = sys._getframe().f_back.f_back

    # Replace the existing spec with the new one if they collide
    specs[spec] = {"file": frame.f_globals["__file__"], "line": frame.f_lineno}


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
