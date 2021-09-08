from contextlib import contextmanager
from contextvars import ContextVar
from os.path import abspath
from typing import Any, Set

from pydantic import root_validator

from prefect.flows import Flow
from prefect.orion.schemas.schedules import Schedule
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.utilities.collections import extract_instances, listrepr
from prefect.utilities.evaluation import exec_script

# See `_register_new_specs`
_DeploymentSpecContextVar = ContextVar("_DeploymentSpecContext")


class DeploymentSpec(PrefectBaseModel):
    name: str
    flow: Flow
    flow_name: str
    flow_location: str
    schedule: Schedule = None

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # After initialization; register this deployment
        _try_register_spec(self)

    @root_validator(pre=True)
    def infer_flow_from_location(cls, values):
        if "flow_location" in values and "flow" not in values:
            flow_loc = values["flow_location"]
            flow_name = values.get("flow_name")
            flows = {
                f.name: f
                for f in extract_instances(exec_script(flow_loc).values(), types=Flow)
            }
            if not flows:
                raise ValueError(f"No flows found at path {flow_loc!r}")
            elif flow_name and flow_name not in flows:
                raise ValueError(
                    f"Flow {flow_name!r} not found at path {flow_loc!r}. "
                    f"Found the following flows: {listrepr(flows.keys())}"
                )
            elif not flow_name and len(flows) > 1:
                raise ValueError(
                    f"Found {len(flows)} flows at {flow_loc!r}: {listrepr(flows.keys())}. "
                    "Provide a flow name to select a flow to deploy.",
                )

            if flow_name:
                flow = flows[flow_name]
            else:
                flow = list(flows.values())[0]

            values["flow"] = flow
        return values

    @root_validator(pre=True)
    def infer_flow_name_from_flow(cls, values):
        if "flow" in values:
            values.setdefault("flow_name", values["flow"].name)
        return values

    @root_validator(pre=True)
    def infer_name_from_flow(cls, values):
        if "flow" in values:
            values.setdefault("name", values["flow"].name)
        return values

    @root_validator(pre=True)
    def infer_location_from_flow(cls, values):
        if "flow" in values:
            flow_file = values["flow"].fn.__globals__.get("__file__")
            if flow_file:
                values.setdefault("flow_location", abspath(str(flow_file)))
        return values

    @root_validator
    def ensure_flow_name_matches_flow_object(cls, values):
        flow, flow_name = values.get("flow"), values.get("flow_name")
        if flow and flow_name and flow.name != flow_name:
            raise ValueError("flow.name and flow_name must match")
        return values

    class Config:
        arbitrary_types_allowed = True

    def __hash__(self) -> int:
        # Deployments are unique on name
        return hash(self.name)


def _try_register_spec(spec: DeploymentSpec) -> None:
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


def deployment_specs_from_script(script_path: str) -> Set[DeploymentSpec]:
    with _register_new_specs() as specs:
        exec_script(script_path)

    return specs
