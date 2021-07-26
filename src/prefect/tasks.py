import inspect
from uuid import UUID
from functools import update_wrapper
from typing import Any, Awaitable, Callable, Dict, Iterable, Tuple, Union

from prefect import _context
from prefect.flows import FlowRunContext
from prefect.futures import PrefectFuture


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

    def _run(
        self,
        flow_run: FlowRunContext,
        task_run_id: UUID,
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ):
        # TODO: Orchestrate states
        return self.fn(*call_args, **call_kwargs)

    def __call__(
        self, *args: Any, **kwargs: Any
    ) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:

        flow_run = _context.flow_run.get(None)
        if not flow_run:
            raise RuntimeError("Tasks cannot be called outside of a flow.")

        task_run_id = ""  # flow_run.client.create_task_run(...)

        # TODO: Submit `self._run` to an executor
        result = self._run(
            flow_run="flow_run",
            task_run_id=task_run_id,
            call_args=args,
            call_kwargs=kwargs,
        )

        return PrefectFuture(run_id=task_run_id, result=result)


def task(_fn: Callable = None, *, name: str = None, **task_init_kwargs: Any):
    # TOOD: See notes on decorator cleanup in `prefect.flows.flow`
    if _fn is None:
        return lambda _fn: Task(fn=_fn, name=name, **task_init_kwargs)
    return Task(fn=_fn, name=name, **task_init_kwargs)
