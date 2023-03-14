"""
Access attributes of the current deployment run dynamically.

Available attributes:
    - id: the deployment's unique ID
    - flow_run_id: the current flow run ID for this deployment
    - parameters: the parameters that were passed to this run; note that these do not necessarily
        include default values set on the flow function, only the parameter values passed from the API
"""
import os
import warnings
from typing import Any, List

from prefect.client.orchestration import get_client
from prefect.context import FlowRunContext
from prefect.utilities.asyncutils import sync


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
    deployment_id = getattr(flow_run, "deployment_id", None)
    if deployment_id is None:
        run_id = os.getenv("PREFECT__FLOW_RUN_ID")
        if run_id is None:
            return
        client = get_client()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            flow_run = sync(client.read_flow_run, run_id)
        return str(flow_run.deployment_id)
    else:
        return str(deployment_id)


def get_parameters():
    run_id = os.getenv("PREFECT__FLOW_RUN_ID")
    if run_id is None:
        return

    client = get_client()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flow_run = sync(client.read_flow_run, run_id)
    return flow_run.parameters or {}


def get_flow_run_id():
    return os.getenv("PREFECT__FLOW_RUN_ID")


FIELDS = {"id": get_id, "flow_run_id": get_flow_run_id, "parameters": get_parameters}
