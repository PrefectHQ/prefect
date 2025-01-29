"""
Access attributes of the current task run dynamically.

Note that if a task run cannot be discovered, all attributes will return empty values.

You can mock the runtime attributes for testing purposes by setting environment variables
prefixed with `PREFECT__RUNTIME__TASK_RUN`.

Available attributes:
    - `id`: the task run's unique ID
    - `name`: the name of the task run
    - `tags`: the task run's set of tags
    - `parameters`: the parameters the task was called with
    - `run_count`: the number of times this task run has been run
    - `task_name`: the name of the task
"""

from __future__ import annotations

import os
from typing import Any, Callable

from prefect.context import TaskRunContext
from prefect.settings import get_current_settings

__all__ = [
    "id",
    "tags",
    "name",
    "parameters",
    "run_count",
    "task_name",
    "api_url",
    "ui_url",
]


type_cast: dict[
    type[bool] | type[int] | type[float] | type[str] | type[None], Callable[[Any], Any]
] = {
    bool: lambda x: x.lower() == "true",
    int: int,
    float: float,
    str: str,
    # for optional defined attributes, when real value is NoneType, use str
    type(None): str,
}


def __getattr__(name: str) -> Any:
    """
    Attribute accessor for this submodule; note that imports also work with this:

        from prefect.runtime.task_run import id
    """

    func = FIELDS.get(name)

    # if `name` is an attribute but it is mocked through environment variable, the mocked type will be str,
    # which might be different from original one. For consistency, cast env var to the same type
    env_key = f"PREFECT__RUNTIME__TASK_RUN__{name.upper()}"

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


def __dir__() -> list[str]:
    return sorted(__all__)


def get_id() -> str | None:
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx is not None:
        return str(task_run_ctx.task_run.id)


def get_tags() -> list[str]:
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx is None:
        return []
    else:
        return task_run_ctx.task_run.tags


def get_run_count() -> int:
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx is None:
        return 0
    else:
        return task_run_ctx.task_run.run_count


def get_name() -> str | None:
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx is None:
        return None
    else:
        return task_run_ctx.task_run.name


def get_task_name() -> str | None:
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx is None:
        return None
    else:
        return task_run_ctx.task.name


def get_parameters() -> dict[str, Any]:
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx is not None:
        return task_run_ctx.parameters
    else:
        return {}


def get_task_run_api_url() -> str | None:
    if (api_url := get_current_settings().api.url) is None:
        return None
    if (task_run_id := get_id()) is None:
        return None
    return f"{api_url}/runs/task-run/{task_run_id}"


def get_task_run_ui_url() -> str | None:
    if (ui_url := get_current_settings().ui_url) is None:
        return None
    if (task_run_id := get_id()) is None:
        return None
    return f"{ui_url}/runs/task-run/{task_run_id}"


FIELDS: dict[str, Callable[[], Any | None]] = {
    "id": get_id,
    "tags": get_tags,
    "name": get_name,
    "parameters": get_parameters,
    "run_count": get_run_count,
    "task_name": get_task_name,
    "api_url": get_task_run_api_url,
    "ui_url": get_task_run_ui_url,
}
