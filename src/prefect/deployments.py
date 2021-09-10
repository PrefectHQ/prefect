from contextlib import contextmanager
from contextvars import ContextVar
from os.path import abspath
import pathlib
import runpy
from typing import Any, Set

import yaml
from pydantic import root_validator, validator

from prefect.exceptions import (
    FlowScriptError,
    MissingFlowError,
    UnspecifiedFlowError,
)
from prefect.flows import Flow
from prefect.orion.schemas.schedules import SCHEDULE_TYPES
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.utilities.collections import extract_instances, listrepr
from prefect.utilities.filesystem import tmpchdir

# See `_register_new_specs`
_DeploymentSpecContextVar = ContextVar("_DeploymentSpecContext")


class DeploymentSpec(PrefectBaseModel):
    name: str
    flow: Flow
    flow_name: str
    flow_location: str
    schedule: SCHEDULE_TYPES = None

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # After initialization; register this deployment
        _register_spec(self)

    @root_validator
    def infer_location_from_flow(cls, values):
        if "flow" in values:
            flow_file = values["flow"].fn.__globals__.get("__file__")
            if flow_file:
                values.setdefault("flow_location", abspath(str(flow_file)))
        return values

    @validator("flow_location", pre=True)
    def ensure_flow_location_is_str(cls, value):
        return str(value)

    @validator("flow_location", pre=True)
    def ensure_flow_location_is_absolute(cls, value):
        return str(pathlib.Path(value).absolute())

    @root_validator(pre=True)
    def infer_flow_from_location(cls, values):
        if "flow_location" in values and "flow" not in values:

            values["flow"] = load_flow_from_script(
                values["flow_location"], values.get("flow_name")
            )

        return values

    @root_validator
    def infer_flow_name_from_flow(cls, values):
        if "flow" in values:
            values.setdefault("flow_name", values["flow"].name)
        return values

    @root_validator
    def ensure_flow_name_matches_flow_object(cls, values):
        flow, flow_name = values.get("flow"), values.get("flow_name")
        if flow and flow_name and flow.name != flow_name:
            raise ValueError(
                "`flow.name` and `flow_name` must match. "
                f"Got {flow.name!r} and {flow_name!r}."
            )
        return values

    class Config:
        arbitrary_types_allowed = True

    def __hash__(self) -> int:
        # Deployments are unique on name / flow name pair
        return hash((self.name, self.flow_name))


def load_flow_from_script(script_path: str, flow_name: str = None):
    try:

        variables = runpy.run_path(script_path)
    except Exception as exc:
        raise FlowScriptError(
            f"Flow script at {script_path!r} encountered an exception"
        ) from exc

    flows = {f.name: f for f in extract_instances(variables.values(), types=Flow)}

    if not flows:
        raise MissingFlowError(f"No flows found at path {script_path!r}")

    elif flow_name and flow_name not in flows:
        raise MissingFlowError(
            f"Flow {flow_name!r} not found at path {script_path!r}. "
            f"Found the following flows: {listrepr(flows.keys())}"
        )

    elif not flow_name and len(flows) > 1:
        raise UnspecifiedFlowError(
            f"Found {len(flows)} flows at {script_path!r}: {listrepr(flows.keys())}. "
            "Specify a flow name to select a flow to deploy.",
        )

    if flow_name:
        return flows[flow_name]
    else:
        return list(flows.values())[0]


def deployment_specs_from_script(script_path: str) -> Set[DeploymentSpec]:
    with _register_new_specs() as specs:
        import runpy

        runpy.run_path(script_path)

    return specs


def deployment_specs_from_yaml(path: str) -> Set[DeploymentSpec]:
    with open(path, "r") as f:
        contents = yaml.safe_load(f.read())

    # Load deployments relative to the yaml file's directory
    with tmpchdir(path):
        if isinstance(contents, list):
            specs = {DeploymentSpec.parse_obj(spec) for spec in contents}
        else:
            specs = {DeploymentSpec.parse_obj(contents)}

    return specs


def _register_spec(spec: DeploymentSpec) -> None:
    specs = _DeploymentSpecContextVar.get(None)

    if specs is None:
        return

    # Replace the existing spec with the new one if they collide
    specs.discard(spec)
    specs.add(spec)


@contextmanager
def _register_new_specs():
    """
    Collect any `DeploymentSpec` objects created during this context into a set.
    If multiple specs with the same name are created, the last will be used an the
    earlier will be used.

    This is convenient for `deployment_specs_from_script` which can collect deployment
    declarations without requiring them to be assigned to a global variable
    """
    specs = set()
    token = _DeploymentSpecContextVar.set(specs)
    yield specs
    _DeploymentSpecContextVar.reset(token)
