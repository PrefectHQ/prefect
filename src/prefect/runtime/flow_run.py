"""
Access attributes of the current flow run dynamically.

Note that if a flow run cannot be discovered, all attributes will return empty values.

You can mock the runtime attributes for testing purposes by setting environment variables
prefixed with `PREFECT__RUNTIME__FLOW_RUN`.

Available attributes:
    - `id`: the flow run's unique ID
    - `tags`: the flow run's set of tags
    - `scheduled_start_time`: the flow run's expected scheduled start time; defaults to now if not present
"""
import os
from typing import Any, Dict, List, Optional

import dateparser
import pendulum

from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.orchestration import get_client
from prefect.context import FlowRunContext, TaskRunContext

__all__ = [
    "id",
    "tags",
    "scheduled_start_time",
    "name",
    "flow_name",
    "parameters",
    "parent_flow_run_id",
    "parent_deployment_id",
]


type_cast = {
    bool: lambda x: x.lower() == "true",
    int: int,
    float: float,
    str: str,
    # use dateparser to cast different formats of date in string, and then instance to pendulum.DateTime
    # tzinfo is ignored (UTC forced)
    pendulum.DateTime: lambda x: pendulum.instance(
        dateparser.parse(x).replace(tzinfo=None), "UTC"
    ),
    # for optional defined attributes, when real value is NoneType, use str
    type(None): str,
}


def __getattr__(name: str) -> Any:
    """
    Attribute accessor for this submodule; note that imports also work with this:

        from prefect.runtime.flow_run import id
    """

    func = FIELDS.get(name)

    # if `name` is an attribute but it is mocked through environment variable, the mocked type will be str,
    # which might be different from original one. For consistency, cast env var to the same type
    env_key = f"PREFECT__RUNTIME__FLOW_RUN__{name.upper()}"

    if func is None:
        if env_key in os.environ:
            return os.environ[env_key]
        else:
            raise AttributeError(f"{__name__} has no attribute {name!r}")

    real_value = func()
    if env_key in os.environ:
        mocked_value = os.environ[env_key]
        # cast `mocked_value` to the same type as `real_value`
        try:
            cast_func = type_cast[type(real_value)]
            return cast_func(mocked_value)
        except KeyError:
            raise ValueError(
                "This runtime context attribute cannot be mocked using an"
                " environment variable. Please use monkeypatch instead."
            )
    else:
        return real_value


def __dir__() -> List[str]:
    return sorted(__all__)


async def _get_flow_run(flow_run_id):
    async with get_client() as client:
        return await client.read_flow_run(flow_run_id)


async def _get_task_run(task_run_id):
    async with get_client() as client:
        return await client.read_task_run(task_run_id)


async def _get_flow_from_run(flow_run_id):
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id)
        return await client.read_flow(flow_run.flow_id)


def get_id() -> str:
    flow_run_ctx = FlowRunContext.get()
    task_run_ctx = TaskRunContext.get()
    if flow_run_ctx is not None:
        return str(flow_run_ctx.flow_run.id)
    if task_run_ctx is not None:
        return str(task_run_ctx.task_run.flow_run_id)
    else:
        return os.getenv("PREFECT__FLOW_RUN_ID")


def get_tags() -> List[str]:
    flow_run_ctx = FlowRunContext.get()
    run_id = get_id()
    if flow_run_ctx is None and run_id is None:
        return []
    elif flow_run_ctx is None:
        flow_run = from_sync.call_soon_in_loop_thread(
            create_call(_get_flow_run, run_id)
        ).result()

        return flow_run.tags
    else:
        return flow_run_ctx.flow_run.tags


def get_name() -> Optional[str]:
    flow_run_ctx = FlowRunContext.get()
    run_id = get_id()
    if flow_run_ctx is None and run_id is None:
        return None
    elif flow_run_ctx is None:
        flow_run = from_sync.call_soon_in_loop_thread(
            create_call(_get_flow_run, run_id)
        ).result()

        return flow_run.name
    else:
        return flow_run_ctx.flow_run.name


def get_flow_name() -> Optional[str]:
    flow_run_ctx = FlowRunContext.get()
    run_id = get_id()
    if flow_run_ctx is None and run_id is None:
        return None
    elif flow_run_ctx is None:
        flow = from_sync.call_soon_in_loop_thread(
            create_call(_get_flow_from_run, run_id)
        ).result()

        return flow.name
    else:
        return flow_run_ctx.flow.name


def get_scheduled_start_time() -> pendulum.DateTime:
    flow_run_ctx = FlowRunContext.get()
    run_id = get_id()
    if flow_run_ctx is None and run_id is None:
        return pendulum.now("utc")
    elif flow_run_ctx is None:
        flow_run = from_sync.call_soon_in_loop_thread(
            create_call(_get_flow_run, run_id)
        ).result()

        return flow_run.expected_start_time
    else:
        return flow_run_ctx.flow_run.expected_start_time


def get_parameters() -> Dict[str, Any]:
    flow_run_ctx = FlowRunContext.get()
    run_id = get_id()
    if flow_run_ctx is not None:
        # Use the unserialized parameters from the context if available
        return flow_run_ctx.parameters
    elif run_id is not None:
        flow_run = from_sync.call_soon_in_loop_thread(
            create_call(_get_flow_run, run_id)
        ).result()

        return flow_run.parameters
    else:
        return {}


def get_parent_flow_run_id() -> Optional[str]:
    flow_run_ctx = FlowRunContext.get()
    run_id = get_id()
    if flow_run_ctx is not None:
        parent_task_run_id = flow_run_ctx.flow_run.parent_task_run_id
    elif run_id is not None:
        flow_run = from_sync.call_soon_in_loop_thread(
            create_call(_get_flow_run, run_id)
        ).result()
        parent_task_run_id = flow_run.parent_task_run_id
    else:
        parent_task_run_id = None

    if parent_task_run_id is not None:
        parent_task_run = from_sync.call_soon_in_loop_thread(
            create_call(_get_task_run, parent_task_run_id)
        ).result()
        return parent_task_run.flow_run_id
    return None


def get_parent_deployment_id() -> Dict[str, Any]:
    parent_flow_run_id = get_parent_flow_run_id()
    if parent_flow_run_id is None:
        return None

    parent_flow_run = from_sync.call_soon_in_loop_thread(
        create_call(_get_flow_run, parent_flow_run_id)
    ).result()
    return parent_flow_run.deployment_id if parent_flow_run else None


FIELDS = {
    "id": get_id,
    "tags": get_tags,
    "scheduled_start_time": get_scheduled_start_time,
    "name": get_name,
    "flow_name": get_flow_name,
    "parameters": get_parameters,
    "parent_flow_run_id": get_parent_flow_run_id,
    "parent_deployment_id": get_parent_deployment_id,
}
