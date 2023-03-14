"""
Access attributes of the current deployment run dynamically.

Available attributes:
    - id: the deployment's unique ID
    - flow_run_id: the current flow run ID for this deployment
    - parameters: the parameters that were passed to this run
"""
import os
from typing import Any, List

from prefect.client.orchestration import get_client
from prefect.context import FlowRunContext


__all__ = ["id", "flow_run_id"]


def __getattr__(name: str) -> Any:
    """
    Attribute accessor for this submodule; note that imports also work with this:

        from prefect.runtime.flow_run import id
    """
    func = FIELDS.get(name)
    if func is None:
        raise AttributeError(f"{__name__} has no attribute {name!r}")
    else:
        return func()


def __dir__() -> List[str]:
    return sorted(__all__)


def get_id():
    flow_run = FlowRunContext.get()
    if flow_run is None:
        return os.getenv("PREFECT__FLOW_RUN_ID")
    else:
        return flow_run.flow_run.id


def get_flow_run_id():
    return os.getenv("PREFECT__FLOW_RUN_ID")


FIELDS = {"id": get_id, "flow_run_id": get_flow_run_id}
