import inspect
from functools import update_wrapper
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Tuple
from uuid import UUID

from prefect.utilities.hashing import stable_hash, to_qualified_name
from prefect.futures import PrefectFuture, resolve_futures
from prefect.client import OrionClient
from prefect.orion.schemas.states import State, StateType


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

        # the task key is a hash of (name, fn, tags)
        # which is a stable representation of this unit of work.
        # note runtime tags are not part of the task key; they will be
        # recorded as metadata only.
        self.task_key = stable_hash(
            self.name,
            to_qualified_name(self.fn),
            str(sorted(self.tags or [])),
        )

        self.dynamic_key = 0

    def _run(
        self,
        task_run_id: UUID,
        flow_run_id: UUID,
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ) -> None:
        from prefect.context import TaskRunContext

        client = OrionClient()

        client.set_task_run_state(task_run_id, State(type=StateType.RUNNING))

        try:
            with TaskRunContext(
                task_run_id=task_run_id,
                flow_run_id=flow_run_id,
                task=self,
                client=client,
            ):
                result = self.fn(*call_args, **call_kwargs)
        except Exception as exc:
            state = State(
                type=StateType.FAILED,
                message="Task run encountered an exception.",
                data=exc,
            )
        else:
            state = State(
                type=StateType.COMPLETED,
                message="Task run completed.",
                data=result,
            )

        client.set_task_run_state(
            task_run_id,
            state=state,
        )

        return state

    def __call__(self, *args: Any, **kwargs: Any) -> PrefectFuture:
        from prefect.context import FlowRunContext, TaskRunContext

        flow_run_context = FlowRunContext.get()
        if not flow_run_context:
            raise RuntimeError("Tasks cannot be called outside of a flow.")

        if TaskRunContext.get():
            raise RuntimeError(
                "Tasks cannot be called from within tasks. Did you mean to call this "
                "task in a flow?"
            )

        task_run_id = flow_run_context.client.create_task_run(
            task=self,
            flow_run_id=flow_run_context.flow_run_id,
        )

        flow_run_context.client.set_task_run_state(
            task_run_id, State(type=StateType.PENDING)
        )

        callback = flow_run_context.executor.submit(
            self._run,
            task_run_id=task_run_id,
            flow_run_id=flow_run_context.flow_run_id,
            call_args=resolve_futures(args),
            call_kwargs=resolve_futures(kwargs),
        )

        # Increment the dynamic_key so future task calls are distinguishable from this
        # task run
        self.dynamic_key += 1

        return PrefectFuture(
            flow_run_id=flow_run_context.flow_run_id,
            task_run_id=task_run_id,
            client=flow_run_context.client,
            wait_callback=callback,
        )


def task(_fn: Callable = None, *, name: str = None, **task_init_kwargs: Any):
    # TOOD: See notes on decorator cleanup in `prefect.flows.flow`
    if _fn is None:
        return lambda _fn: Task(fn=_fn, name=name, **task_init_kwargs)
    return Task(fn=_fn, name=name, **task_init_kwargs)
