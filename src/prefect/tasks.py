import inspect
from functools import update_wrapper
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Tuple

from prefect.futures import PrefectFuture, RunType
from prefect.orion.schemas.core import State, StateType

if TYPE_CHECKING:
    from prefect.context import RunContext


class Task:
    """
    Base class representing Prefect worktasks.
    """

    def __init__(
        self,
        name: str = None,
        fn: Callable = None,
        description: str = None,
        tags: Iterable[str] = None,
    ):
        if not fn:
            raise TypeError("__init__() missing 1 required argument: 'fn'")
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn

        self.tags = set(tags if tags else [])

        # TODO: More interesting `task_key` generation?
        # Stable identifier for this task
        self.task_key = self.name

    def _run(
        self,
        context: "RunContext",
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ) -> None:
        context.flow_run.client.set_task_run_state(
            context.task_run.task_run_id, State(type=StateType.RUNNING)
        )

        try:
            result = self.fn(*call_args, **call_kwargs)
        except Exception as exc:
            state = State(
                type=StateType.FAILED,
                message="Flow run encountered an exception.",
            )
            result = exc
        else:
            state = State(
                type=StateType.COMPLETED,
                message="Flow run completed.",
            )

        context.flow_run.client.set_task_run_state(
            context.task_run.task_run_id,
            state=state,
        )

        # TODO: Send the data to the server as well? Will need to be serialized there
        #       but we don't want it serialized here
        state.data = result
        return state

    def __call__(self, *args: Any, **kwargs: Any) -> PrefectFuture:
        from prefect.context import FlowRunContext, RunContext, TaskRunContext

        flow_run_context = FlowRunContext.get()
        if not flow_run_context:
            raise RuntimeError("Tasks cannot be called outside of a flow.")

        if TaskRunContext.get():
            raise RuntimeError(
                "Tasks cannot be called from within tasks. Did you mean to call this "
                "task in a flow?"
            )

        # Load some objects from the flow run settings
        client = flow_run_context.client
        executor = flow_run_context.flow.executor

        task_run_id = client.create_task_run(
            task=self,
            flow_run_id=flow_run_context.flow_run_id,
        )

        context = RunContext(
            flow_run=flow_run_context,
            task_run=TaskRunContext(task_run_id=task_run_id, task=self),
        )

        callback = executor.submit(
            self._run,
            context=context,
            call_args=args,
            call_kwargs=kwargs,
        )

        return PrefectFuture(
            run_id=task_run_id,
            run_type=RunType.TaskRun,
            client=client,
            wait_callback=callback,
        )


def task(_fn: Callable = None, *, name: str = None, **task_init_kwargs: Any):
    # TOOD: See notes on decorator cleanup in `prefect.flows.flow`
    if _fn is None:
        return lambda _fn: Task(fn=_fn, name=name, **task_init_kwargs)
    return Task(fn=_fn, name=name, **task_init_kwargs)
