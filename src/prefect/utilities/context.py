from collections.abc import Generator
from contextlib import contextmanager
from contextvars import Context, ContextVar, Token
from typing import TYPE_CHECKING, Any, Optional, cast
from uuid import UUID

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun, TaskRun


@contextmanager
def temporary_context(context: Context) -> Generator[None, Any, None]:
    tokens: dict[ContextVar[Any], Token[Any]] = {}
    for key, value in context.items():
        token = key.set(value)
        tokens[key] = token
    try:
        yield
    finally:
        for key, token in tokens.items():
            key.reset(token)


def get_task_run_id() -> Optional[UUID]:
    from prefect.context import TaskRunContext

    context = TaskRunContext.get()
    if task_run := cast(Optional["TaskRun"], getattr(context, "task_run", None)):
        return task_run.id
    return None


def get_flow_run_id() -> Optional[UUID]:
    from prefect.context import FlowRunContext

    context = FlowRunContext.get()
    if flow_run := cast(Optional["FlowRun"], getattr(context, "flow_run", None)):
        return flow_run.id
    return None


def get_task_and_flow_run_ids() -> tuple[Optional[UUID], Optional[UUID]]:
    """
    Get the task run and flow run ids from the context, if available.

    Returns:
        tuple[Optional[UUID], Optional[UUID]]: a tuple of the task run id and flow run id
    """
    return get_task_run_id(), get_flow_run_id()
