import inspect
from uuid import UUID
from functools import update_wrapper
from typing import Any, Callable, Dict, Iterable, Tuple, TYPE_CHECKING

from prefect.futures import PrefectFuture
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
        task_run_id: UUID,
        future: PrefectFuture,
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ):
        client = context.flow_run.client

        client.set_task_run_state(task_run_id, State(type=StateType.RUNNING))

        try:
            result = self.fn(*call_args, **call_kwargs)
        except Exception as exc:
            result = exc
            state_type = StateType.FAILED
            message = "Task run encountered a user exception."
        else:
            state_type = StateType.COMPLETED
            message = "Task run completed."

        state = State(type=state_type, message=message)
        client.set_task_run_state(task_run_id, state=state)

        future.set_result(result, user_exception=state.is_failed())

    def __call__(self, *args: Any, **kwargs: Any) -> PrefectFuture:
        from prefect.context import FlowRunContext, TaskRunContext, RunContext

        flow_run_context = FlowRunContext.get()
        if not flow_run_context:
            raise RuntimeError("Tasks cannot be called outside of a flow.")

        if TaskRunContext.get():
            raise RuntimeError(
                "Tasks cannot be called from within tasks. Did you mean to call this "
                "task in a flow?"
            )

        client = flow_run_context.client

        task_run_id = client.create_task_run(
            task=self,
            flow_run_id=flow_run_context.flow_run_id,
        )
        client.set_task_run_state(task_run_id, State(type=StateType.PENDING))

        future = PrefectFuture(
            run_id=task_run_id,
        )

        context = RunContext(
            flow_run=flow_run_context,
            task_run=TaskRunContext(task_run_id=task_run_id, task=self),
        )

        # TODO: Submit `self._run` to an executor
        with context.task_run:
            self._run(
                context=context,
                task_run_id=task_run_id,
                future=future,
                call_args=args,
                call_kwargs=kwargs,
            )

        return future


def task(_fn: Callable = None, *, name: str = None, **task_init_kwargs: Any):
    # TOOD: See notes on decorator cleanup in `prefect.flows.flow`
    if _fn is None:
        return lambda _fn: Task(fn=_fn, name=name, **task_init_kwargs)
    return Task(fn=_fn, name=name, **task_init_kwargs)
