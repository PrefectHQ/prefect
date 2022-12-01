import io
import logging
from builtins import print
from contextlib import contextmanager
from functools import lru_cache
from typing import TYPE_CHECKING

import prefect
from prefect.exceptions import MissingContextError

if TYPE_CHECKING:
    from prefect.context import RunContext
    from prefect.flows import Flow
    from prefect.orion.schemas.core import FlowRun, TaskRun
    from prefect.tasks import Task


class PrefectLogAdapter(logging.LoggerAdapter):
    """
    Adapter that ensures extra kwargs are passed through correctly; without this
    the `extra` fields set on the adapter would overshadow any provided on a
    log-by-log basis.

    See https://bugs.python.org/issue32732 — the Python team has declared that this is
    not a bug in the LoggingAdapter and subclassing is the intended workaround.
    """

    def process(self, msg, kwargs):
        kwargs["extra"] = {**self.extra, **(kwargs.get("extra") or {})}
        return (msg, kwargs)


@lru_cache()
def get_logger(name: str = None) -> logging.Logger:
    """
    Get a `prefect` logger. These loggers are intended for internal use within the
    `prefect` package.

    See `get_run_logger` for retrieving loggers for use within task or flow runs.
    By default, only run-related loggers are connected to the `OrionHandler`.
    """

    parent_logger = logging.getLogger("prefect")

    if name:
        # Append the name if given but allow explicit full names e.g. "prefect.test"
        # should not become "prefect.prefect.test"
        if not name.startswith(parent_logger.name + "."):
            logger = parent_logger.getChild(name)
        else:
            logger = logging.getLogger(name)
    else:
        logger = parent_logger

    return logger


def get_run_logger(context: "RunContext" = None, **kwargs: str) -> logging.Logger:
    """
    Get a Prefect logger for the current task run or flow run.

    The logger will be named either `prefect.task_runs` or `prefect.flow_runs`.
    Contextual data about the run will be attached to the log records.

    These loggers are connected to the `OrionHandler` by default to send log records to
    the API.

    Arguments:
        context: A specific context may be provided as an override. By default, the
            context is inferred from global state and this should not be needed.
        **kwargs: Additional keyword arguments will be attached to the log records in
            addition to the run metadata

    Raises:
        RuntimeError: If no context can be found
    """
    # Check for existing contexts
    task_run_context = prefect.context.TaskRunContext.get()
    flow_run_context = prefect.context.FlowRunContext.get()

    # Apply the context override
    if context:
        if isinstance(context, prefect.context.FlowRunContext):
            flow_run_context = context
        elif isinstance(context, prefect.context.TaskRunContext):
            task_run_context = context
        else:
            raise TypeError(
                f"Received unexpected type {type(context).__name__!r} for context. "
                "Expected one of 'None', 'FlowRunContext', or 'TaskRunContext'."
            )

    # Determine if this is a task or flow run logger
    if task_run_context:
        logger = task_run_logger(
            task_run=task_run_context.task_run,
            task=task_run_context.task,
            flow_run=flow_run_context.flow_run if flow_run_context else None,
            flow=flow_run_context.flow if flow_run_context else None,
            **kwargs,
        )
    elif flow_run_context:
        logger = flow_run_logger(
            flow_run=flow_run_context.flow_run, flow=flow_run_context.flow, **kwargs
        )
    elif (
        get_logger("prefect.flow_run").disabled
        and get_logger("prefect.task_run").disabled
    ):
        logger = logging.getLogger("null")
    else:
        raise MissingContextError("There is no active flow or task run context.")

    return logger


def flow_run_logger(flow_run: "FlowRun", flow: "Flow" = None, **kwargs: str):
    """
    Create a flow run logger with the run's metadata attached.

    Additional keyword arguments can be provided to attach custom data to the log
    records.

    If the context is available, see `run_logger` instead.
    """
    return PrefectLogAdapter(
        get_logger("prefect.flow_runs"),
        extra={
            **{
                "flow_run_name": flow_run.name,
                "flow_run_id": str(flow_run.id),
                "flow_name": flow.name if flow else "<unknown>",
            },
            **kwargs,
        },
    )


def task_run_logger(
    task_run: "TaskRun",
    task: "Task" = None,
    flow_run: "FlowRun" = None,
    flow: "Flow" = None,
    **kwargs: str,
):
    """
    Create a task run logger with the run's metadata attached.

    Additional keyword arguments can be provided to attach custom data to the log
    records.

    If the context is available, see `run_logger` instead.
    """
    return PrefectLogAdapter(
        get_logger("prefect.task_runs"),
        extra={
            **{
                "task_run_id": str(task_run.id),
                "flow_run_id": str(task_run.flow_run_id),
                "task_run_name": task_run.name,
                "task_name": task.name if task else "<unknown>",
                "flow_run_name": flow_run.name if flow_run else "<unknown>",
                "flow_name": flow.name if flow else "<unknown>",
            },
            **kwargs,
        },
    )


@contextmanager
def disable_logger(name: str):
    """
    Get a logger by name and disables it within the context manager.
    Upon exiting the context manager, the logger is returned to its
    original state.
    """
    logger = logging.getLogger(name=name)

    # determine if it's already disabled
    base_state = logger.disabled
    try:
        # disable the logger
        logger.disabled = True
        yield
    finally:
        # return to base state
        logger.disabled = base_state


@contextmanager
def disable_run_logger():
    """
    Gets both `prefect.flow_run` and `prefect.task_run` and disables them
    within the context manager. Upon exiting the context manager, both loggers
    are returned to its original state.
    """
    with disable_logger("prefect.flow_run"), disable_logger("prefect.task_run"):
        yield


def print_as_log(*args, **kwargs):
    """
    A patch for `print` to send printed messages to the Prefect run logger.

    If no run is active, `print` will behave as if it were not patched.
    """
    from prefect.context import FlowRunContext, TaskRunContext

    context = TaskRunContext.get() or FlowRunContext.get()
    if not context or not context.log_prints:
        return print(*args, **kwargs)

    logger = get_run_logger()

    # Print to an in-memory buffer; so we do not need to implement `print`
    buffer = io.StringIO()
    kwargs["file"] = buffer
    print(*args, **kwargs)

    # Remove trailing whitespace to prevent duplicates
    logger.info(buffer.getvalue().rstrip())


@contextmanager
def patch_print():
    """
    Patches the Python builtin `print` method to use `print_as_log`
    """
    import builtins

    original = builtins.print

    try:
        builtins.print = print_as_log
        yield
    finally:
        builtins.print = original
