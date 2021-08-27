import datetime
import inspect
from functools import update_wrapper
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Optional, Union

from prefect.futures import PrefectFuture
from prefect.utilities.asyncio import get_prefect_event_loop
from prefect.utilities.hashing import hash_objects, stable_hash, to_qualified_name

if TYPE_CHECKING:
    from prefect.context import TaskRunContext


def task_input_hash(context: "TaskRunContext", arguments: Dict[str, Any]):
    return hash_objects(context.task.fn, arguments)


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
        cache_key_fn: Callable[
            ["TaskRunContext", Dict[str, Any]], Optional[str]
        ] = None,
        cache_expiration: datetime.timedelta = None,
        retries: int = 0,
        retry_delay_seconds: Union[float, int] = 0,
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
        self.cache_key_fn = cache_key_fn
        self.cache_expiration = cache_expiration

        # TaskRunPolicy settings
        # TODO: We can instantiate a `TaskRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds

    def __call__(self, *args: Any, **kwargs: Any) -> PrefectFuture:
        from prefect.engine import task_call

        loop = get_prefect_event_loop("tasks")
        return loop.run_coro(task_call(self, *args, **kwargs))

    def update_dynamic_key(self):
        """
        Callback after task calls complete submission so this task will have a
        different dynamic key for future task runs
        """
        # Increment the key
        self.dynamic_key += 1


def task(_fn: Callable = None, *, name: str = None, **task_init_kwargs: Any):
    # TODO: See notes on decorator cleanup in `prefect.flows.flow`
    if _fn is None:
        return lambda _fn: Task(fn=_fn, name=name, **task_init_kwargs)
    return Task(fn=_fn, name=name, **task_init_kwargs)
