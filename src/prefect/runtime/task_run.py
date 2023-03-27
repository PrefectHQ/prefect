"""
Access attributes of the current task run dynamically.

Note that if a task run cannot be discovered, all attributes will return empty values.

Available attributes:
    - `id`: the task run's unique ID
    - `name`: the name of the task run
    - `tags`: the task run's set of tags
    - `parameters`: the parameters the task was called with
"""
from typing import Any, Dict, List, Optional

from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.orchestration import get_client
from prefect.context import TaskRunContext

__all__ = ["id", "tags", "name", "parameters"]


def __getattr__(name: str) -> Any:
    """
    Attribute accessor for this submodule; note that imports also work with this:

        from prefect.runtime.task_run import id
    """
    func = FIELDS.get(name)
    if func is None:
        raise AttributeError(f"{__name__} has no attribute {name!r}")
    else:
        return func()


def __dir__() -> List[str]:
    return sorted(__all__)


async def _get_task_run(task_run_id):
    async with get_client() as client:
        return await client.read_task_run(task_run_id)


def get_id() -> str:
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx is not None:
        return str(task_run_ctx.task_run.id)


def get_tags() -> List[str]:
    task_run_ctx = TaskRunContext.get()
    run_id = get_id()
    if task_run_ctx is None and run_id is None:
        return []
    elif task_run_ctx is None:
        task_run = from_sync.call_soon_in_loop_thread(
            create_call(_get_task_run, run_id)
        ).result()

        return task_run.tags
    else:
        return task_run_ctx.task_run.tags


def get_name() -> Optional[str]:
    task_run_ctx = TaskRunContext.get()
    run_id = get_id()
    if task_run_ctx is None:
        task_run = from_sync.call_soon_in_loop_thread(
            create_call(_get_task_run, run_id)
        ).result()

        return task_run.name
    else:
        return task_run_ctx.task_run.name


def get_parameters() -> Dict[str, Any]:
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx is not None:
        return task_run_ctx.parameters
    else:
        return {}


FIELDS = {
    "id": get_id,
    "tags": get_tags,
    "name": get_name,
    "parameters": get_parameters,
}
