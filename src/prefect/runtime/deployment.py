"""
Access attributes of the current deployment run dynamically.

Note that if a deployment is not currently being run, all attributes will return empty values.

Example usage:
    ```python
    from prefect.runtime import deployment

    def get_task_runner():
        task_runner_config = deployment.parameters.get("runner_config", "default config here")
        return DummyTaskRunner(task_runner_specs=task_runner_config)
    ```

Available attributes:
    - `id`: the deployment's unique ID
    - `flow_run_id`: the current flow run ID for this deployment
    - `parameters`: the parameters that were passed to this run; note that these do not necessarily
        include default values set on the flow function, only the parameter values set on the deployment
        object or those directly provided via API for this run
"""
import os
from typing import Any, List, Optional

from prefect._internal.concurrency.api import create_call, from_sync
from prefect.context import FlowRunContext

from .flow_run import _get_flow_run

__all__ = ["id", "flow_run_id", "parameters"]


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


def get_id() -> Optional[str]:
    flow_run = FlowRunContext.get()
    deployment_id = getattr(flow_run, "deployment_id", None)
    if deployment_id is None:
        run_id = get_flow_run_id()
        if run_id is None:
            return None
        flow_run = from_sync.call_soon_in_new_thread(
            create_call(_get_flow_run, run_id)
        ).result()
        if flow_run.deployment_id:
            return str(flow_run.deployment_id)
        else:
            return None
    else:
        return str(deployment_id)


def get_parameters() -> dict:
    run_id = get_flow_run_id()
    if run_id is None:
        return {}

    flow_run = from_sync.call_soon_in_new_thread(
        create_call(_get_flow_run, run_id)
    ).result()
    return flow_run.parameters or {}


def get_flow_run_id() -> Optional[str]:
    return os.getenv("PREFECT__FLOW_RUN_ID")


FIELDS = {"id": get_id, "flow_run_id": get_flow_run_id, "parameters": get_parameters}
