import abc
import pathlib
import sys
from os.path import abspath
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import fsspec
import yaml
from pydantic import Field, PrivateAttr, validator

from prefect.blocks.storage import StorageBlock
from prefect.client import OrionClient, inject_client
from prefect.context import PrefectObjectRegistry, registry_from_script
from prefect.exceptions import DeploymentValidationError, MissingFlowError
from prefect.flow_runners import FlowRunner, FlowRunnerSettings, UniversalFlowRunner
from prefect.flows import Flow, load_flow_from_script
from prefect.orion.schemas.core import raise_on_invalid_name
from prefect.orion.schemas.schedules import SCHEDULE_TYPES
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.packaging.script import ScriptPackager
from prefect.utilities.asyncio import sync_compatible
from prefect.utilities.filesystem import is_local_path, tmpchdir


class DeploymentSpec(PrefectBaseModel, abc.ABC):
    """
    A type for specifying a deployment of a flow.

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
        parameters: An optional dictionary of default parameters to set on flow runs
            from this deployment. If defined in Python, the values should be Pydantic
            compatible objects.
        schedule: An optional schedule instance to use with the deployment.
        tags: An optional set of tags to assign to the deployment.
        flow_storage: A [prefect.blocks.storage](/api-ref/prefect/blocks/storage/) instance
            providing the [storage](/concepts/storage/) to be used for the flow
            definition and results.
    """

    name: str = None
    flow: Flow = None
    flow_name: str = None
    flow_location: str = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    schedule: SCHEDULE_TYPES = None
    tags: List[str] = Field(default_factory=list)
    flow_runner: Union[FlowRunner, FlowRunnerSettings] = None
    flow_storage: Optional[Union[StorageBlock, UUID]] = None

    # Meta types
    _validated: bool = PrivateAttr(False)
    _source: Dict = PrivateAttr()

    # Hide the `_packager` which is a new interface
    _packager: ScriptPackager = PrivateAttr()

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        # After initialization; register this deployment specification.
        from prefect import deployments

        # Detect the definition location for reporting validation failures
        # Walk up one frame to the user's declaration
        frame = sys._getframe().f_back

        # Walk an additional frame for use of the deprecated alias
        if frame.f_globals["__file__"] == deployments.__file__:
            frame = frame.f_back

        self._source = {
            "file": frame.f_globals["__file__"],
            "line": frame.f_lineno,
        }

        _register_spec(self)

    @validator("name")
    def validate_name_characters(cls, v):
        raise_on_invalid_name(v)
        return v

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
            raise DeploymentValidationError(
                "Either `flow_location` or `flow` must be provided.", self
            )

        # Load the flow from the flow location

        if self.flow_location and not self.flow:
            try:
                self.flow = load_flow_from_script(self.flow_location, self.flow_name)
            except MissingFlowError as exc:
                raise DeploymentValidationError(str(exc), self) from exc

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
                    raise DeploymentValidationError(
                        f"The given flow location {abs_given!r} does not "
                        f"match the path of the given flow: '{abs_flow}'.",
                        self,
                    )

        # Ensure the flow location is absolute if local

        if self.flow_location and is_local_path(self.flow_location):
            self.flow_location = abspath(str(self.flow_location))

        # Ensure the flow location is set

        if not self.flow_location:
            raise DeploymentValidationError(
                "Failed to determine the location of your flow. "
                "Provide the path to your flow code with `flow_location`.",
                self,
            )

        # Infer flow name from flow

        if self.flow and not self.flow_name:
            self.flow_name = self.flow.name

        # Ensure a given flow name matches the given flow's name

        elif self.flow.name != self.flow_name:
            raise DeploymentValidationError(
                "`flow.name` and `flow_name` must match. "
                f"Got {self.flow.name!r} and {self.flow_name!r}.",
                self,
            )

        # Default the deployment name to the flow name

        if not self.name and self.flow_name:
            self.name = self.flow_name

        # Default the flow runner to the universal flow runner

        self.flow_runner = self.flow_runner or UniversalFlowRunner()

        # Convert flow runner settings to concrete instances

        if isinstance(self.flow_runner, FlowRunnerSettings):
            self.flow_runner = FlowRunner.from_settings(self.flow_runner)

        # Do not allow the abstract flow runner type

        if type(self.flow_runner) is FlowRunner:
            raise DeploymentValidationError(
                "The base `FlowRunner` type cannot be used. Provide a flow runner "
                "implementation or flow runner settings instead.",
                self,
            )

        # Check packaging compatibility

        self._packager = ScriptPackager(storage=self.flow_storage)
        await self._packager.check_compat(self, client=client)

        self._validated = True

    @sync_compatible
    @inject_client
    async def create(self, client: OrionClient) -> UUID:
        """
        Create a deployment from the current specification.

        Deployments with the same name will be replaced.

        Returns the ID of the deployment.
        """
        await self.validate()
        schema = await self._packager.package(self, client=client)
        return await client._create_deployment_from_schema(schema)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def __get_validators__(cls):
        # Allow us to use the 'validate' name while retaining pydantic's validator
        for validator in super().__get_validators__():
            if validator == cls.validate:
                yield super().validate
            else:
                yield validator


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


def deployment_specs_from_script(path: str) -> List[DeploymentSpec]:
    return registry_from_script(path).get_instances_of(DeploymentSpec)


def _register_spec(spec: DeploymentSpec) -> None:
    """
    Collect the `DeploymentSpec` object on the
    PrefectObjectRegistry.deployment_specs dictionary. If multiple specs with
    the same name are created, the last will be used.

    This is convenient for `deployment_specs_from_script` which can collect
    deployment declarations without requiring them to be assigned to a global
    variable.

    """
    registry = PrefectObjectRegistry.get()
    registry.register(spec)
