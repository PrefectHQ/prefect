"""
Access attributes of the current flow run dynamically.

Note that if a flow run cannot be discovered, all attributes will return empty values.

Available attributes:
    - `id`: the flow run's unique ID
    - `tags`: the flow run's set of tags
"""
import os
from typing import Any, List

from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.orchestration import get_client
from prefect.context import FlowRunContext

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


async def _get_flow_run(flow_run_id):
    async with get_client() as client:
        return await client.read_flow_run(flow_run_id)


def get_id() -> str:
    flow_run = FlowRunContext.get()
    if flow_run is None:
        return os.getenv("PREFECT__FLOW_RUN_ID")
    else:
        return str(flow_run.flow_run.id)


def get_tags():
    flow_run = FlowRunContext.get()
    run_id = get_id()
    if flow_run is None and run_id is None:
        return []
    elif flow_run is None:
        flow_run = from_sync.call_soon_in_new_thread(
            create_call(_get_flow_run, run_id)
        ).result()

        return flow_run.tags
    else:
        return flow_run.flow_run.tags


FIELDS = {"id": get_id, "tags": get_tags}
