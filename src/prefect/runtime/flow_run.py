"""
Access attributes of the current flow run dynamically.

Available attributes:
    - id: the flow run's unique ID
    - tags: the flow run's set of tags
"""
import os
import warnings
from typing import Any, List

from prefect.client.orchestration import get_client
from prefect.context import FlowRunContext
from prefect.utilities.asyncutils import sync


__all__ = ["id", "tags"]


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


def get_tags():
    flow_run = FlowRunContext.get()
    run_id = get_id()
    if flow_run is None and run_id is None:
        return []
    elif flow_run is None:
        client = get_client()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            flow_run = sync(client.read_flow_run, run_id)

        return flow_run.tags
    else:
        return flow_run.flow_run.tags


FIELDS = {"id": get_id, "tags": get_tags}
