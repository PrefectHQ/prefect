from contextlib import ExitStack, contextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Optional,
    Union,
)

from prefect.exceptions import MissingContextError

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient, SyncPrefectClient

    from .engine import FlowRunContext
    from .task import TaskRunContext


def get_run_context() -> Union["FlowRunContext", "TaskRunContext"]:
    """
    Get the current run context from within a task or flow function.

    Returns:
        A `FlowRunContext` or `TaskRunContext` depending on the function type.

    Raises
        RuntimeError: If called outside of a flow or task run.
    """

    from .engine import FlowRunContext
    from .task import TaskRunContext

    task_run_ctx = TaskRunContext.get()
    if task_run_ctx:
        return task_run_ctx

    flow_run_ctx = FlowRunContext.get()
    if flow_run_ctx:
        return flow_run_ctx

    raise MissingContextError(
        "No run context available. You are not in a flow or task run context."
    )


def serialize_context() -> Dict[str, Any]:
    """
    Serialize the current context for use in a remote execution environment.
    """
    from .engine import EngineContext
    from .settings import SettingsContext
    from .tags import TagsContext
    from .task import TaskRunContext

    flow_run_context = EngineContext.get()
    task_run_context = TaskRunContext.get()
    tags_context = TagsContext.get()
    settings_context = SettingsContext.get()

    return {
        "flow_run_context": flow_run_context.serialize() if flow_run_context else {},
        "task_run_context": task_run_context.serialize() if task_run_context else {},
        "tags_context": tags_context.serialize() if tags_context else {},
        "settings_context": settings_context.serialize() if settings_context else {},
    }


@contextmanager
def hydrated_context(
    serialized_context: Optional[Dict[str, Any]] = None,
    client: Union["PrefectClient", "SyncPrefectClient", None] = None,
):
    from prefect.client.orchestration import get_client
    from prefect.results import ResultFactory
    from prefect.utilities.asyncutils import run_coro_as_sync

    from .settings import SettingsContext
    from .tags import tags

    with ExitStack() as stack:
        if serialized_context:
            # Set up settings context
            if settings_context := serialized_context.get("settings_context"):
                stack.enter_context(SettingsContext(**settings_context))
            # Set up parent flow run context
            client = client or get_client(sync_client=True)
            if flow_run_context := serialized_context.get("flow_run_context"):
                flow = flow_run_context["flow"]
                flow_run_context = FlowRunContext(
                    **flow_run_context,
                    client=client,
                    result_factory=run_coro_as_sync(ResultFactory.from_flow(flow)),  # type: ignore
                    task_runner=flow.task_runner.duplicate(),
                    detached=True,
                )
                stack.enter_context(flow_run_context)
            # Set up parent task run context
            if parent_task_run_context := serialized_context.get("task_run_context"):
                parent_task = parent_task_run_context["task"]
                task_run_context = TaskRunContext(
                    **parent_task_run_context,
                    client=client,
                    result_factory=run_coro_as_sync(
                        ResultFactory.from_autonomous_task(parent_task)
                    ),  # type: ignore
                )
                stack.enter_context(task_run_context)
            # Set up tags context
            if tags_context := serialized_context.get("tags_context"):
                stack.enter_context(tags(*tags_context["current_tags"]))
        yield
