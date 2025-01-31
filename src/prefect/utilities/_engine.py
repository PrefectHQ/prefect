"""Internal engine utilities"""

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any, Union
from uuid import uuid4

from prefect.context import FlowRunContext
from prefect.flows import Flow
from prefect.tasks import Task, TaskRunNameCallbackWithParameters


def dynamic_key_for_task_run(
    context: FlowRunContext, task: "Task[..., Any]", stable: bool = True
) -> Union[int, str]:
    if (
        stable is False or context.detached
    ):  # this task is running on remote infrastructure
        return str(uuid4())
    elif context.flow_run is None:  # this is an autonomous task run
        context.task_run_dynamic_keys[task.task_key] = getattr(
            task, "dynamic_key", str(uuid4())
        )

    elif task.task_key not in context.task_run_dynamic_keys:
        context.task_run_dynamic_keys[task.task_key] = 0
    else:
        dynamic_key = context.task_run_dynamic_keys[task.task_key]
        if TYPE_CHECKING:
            assert isinstance(dynamic_key, int)
        context.task_run_dynamic_keys[task.task_key] = dynamic_key + 1

    return context.task_run_dynamic_keys[task.task_key]


def resolve_custom_flow_run_name(
    flow: "Flow[..., Any]", parameters: dict[str, Any]
) -> str:
    if callable(flow.flow_run_name):
        flow_run_name = flow.flow_run_name()
        if not TYPE_CHECKING:
            if not isinstance(flow_run_name, str):
                raise TypeError(
                    f"Callable {flow.flow_run_name} for 'flow_run_name' returned type"
                    f" {type(flow_run_name).__name__} but a string is required."
                )
    elif isinstance(flow.flow_run_name, str):
        flow_run_name = flow.flow_run_name.format(**parameters)
    else:
        raise TypeError(
            "Expected string or callable for 'flow_run_name'; got"
            f" {type(flow.flow_run_name).__name__} instead."
        )

    return flow_run_name


def resolve_custom_task_run_name(
    task: "Task[..., Any]", parameters: dict[str, Any]
) -> str:
    if callable(task.task_run_name):
        # If the callable accepts a 'parameters' kwarg, pass the entire parameters dict
        if TaskRunNameCallbackWithParameters.is_callback_with_parameters(
            task.task_run_name
        ):
            task_run_name = task.task_run_name(parameters=parameters)
        else:
            # If it doesn't expect parameters, call it without arguments
            task_run_name = task.task_run_name()

        if not TYPE_CHECKING:
            if not isinstance(task_run_name, str):
                raise TypeError(
                    f"Callable {task.task_run_name} for 'task_run_name' returned type"
                    f" {type(task_run_name).__name__} but a string is required."
                )
    elif isinstance(task.task_run_name, str):
        task_run_name = task.task_run_name.format(**parameters)
    else:
        raise TypeError(
            "Expected string or callable for 'task_run_name'; got"
            f" {type(task.task_run_name).__name__} instead."
        )

    return task_run_name


def get_hook_name(hook: Callable[..., Any]) -> str:
    return (
        hook.__name__
        if hasattr(hook, "__name__")
        else (
            hook.func.__name__ if isinstance(hook, partial) else hook.__class__.__name__
        )
    )
