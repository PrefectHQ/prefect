"""
Base workflow task class and decorator
"""
# This file requires type-checking with pyright because mypy does not yet support PEP612
# See https://github.com/python/mypy/issues/8645

import datetime
import inspect
from functools import update_wrapper, partial
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    Optional,
    Union,
    cast,
    overload,
    TypeVar,
    Generic,
    Coroutine,
    NoReturn,
)

from typing_extensions import ParamSpec

from prefect.futures import PrefectFuture
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.hashing import hash_objects, stable_hash, to_qualified_name

if TYPE_CHECKING:
    from prefect.context import TaskRunContext


T = TypeVar("T")  # Generic type var for capturing the inner return type of async funcs
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the task


def task_input_hash(context: "TaskRunContext", arguments: Dict[str, Any]):
    """
    A task cache key implementation which hashes all inputs to the task using a JSON or
    cloudpickle serializer. If any arguments are not JSON serializable, the pickle
    serializer is used as a fallback. If cloudpickle fails, this will return a null key
    indicating that a cache key could not be generated for the given inputs.
    """
    return hash_objects(context.task.fn, arguments)


class Task(Generic[P, R]):
    """
    A Prefect task definition

    See the `@task` decorator for usage details.

    Wraps a user's function with an entrypoint to the Prefect engine. To preserve the
    input and output signatures of the user's functions, we use the generic type
    variables P and R for "Parameters" and "Return Type" respectively.
    """

    def __init__(
        self,
        fn: Callable[P, R],
        name: str = None,
        description: str = None,
        tags: Iterable[str] = None,
        cache_key_fn: Callable[
            ["TaskRunContext", Dict[str, Any]], Optional[str]
        ] = None,
        cache_expiration: datetime.timedelta = None,
        retries: int = 0,
        retry_delay_seconds: Union[float, int] = 0,
    ):
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn
        self.isasync = inspect.iscoroutinefunction(self.fn)

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

    @overload
    def __call__(
        self: "Task[P, NoReturn]", *args: P.args, **kwargs: P.kwargs
    ) -> PrefectFuture[T]:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def __call__(
        self: "Task[P, Coroutine[Any, Any, T]]", *args: P.args, **kwargs: P.kwargs
    ) -> Awaitable[PrefectFuture[T]]:
        ...

    @overload
    def __call__(
        self: "Task[P, T]", *args: P.args, **kwargs: P.kwargs
    ) -> PrefectFuture[T]:
        ...

    def __call__(
        self, *args: Any, **kwargs: Any
    ) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:
        """
        Run the task.

        Must be called within a flow function.

        If writing an async task, this call must be awaited.

        Will create a new task run in the backing API and submit the task to the flow's
        executor. This call only blocks execution while the task is being submitted,
        once it is submitted, the flow function will continue executing. However, note
        that the `LocalExecutor` does not implement parallel execution for sync tasks
        and they are fully resolved on submission.

        Args:
            *args: Arguments to run the flow with
            **kwargs: Keyword arguments to run the flow with

        Returns:
            A future allowing access to the state of the task

        Examples:

            Define a task

            >>> from prefect import task
            >>> @task
            >>> def my_task():
            >>>     return "hello"

            Run a task in a flow

            >>> from prefect import flow
            >>> @flow
            >>> def my_flow():
            >>>     my_task()

            Wait for a task to finish

            >>> @flow
            >>> def my_flow():
            >>>     my_task().wait()

            Use the result from a task in a flow

            >>> @flow
            >>> def my_flow():
            >>>     print(get_result(my_task()))
            >>> my_flow()
            hello

            Run an async task in an async flow

            >>> @task
            >>> async def my_async_task():
            >>>     pass
            >>> @flow
            >>> async def my_flow():
            >>>     await my_async_task()

            Run a sync task in an async flow

            >>> @flow
            >>> async def my_flow():
            >>>     my_task()
        """

        from prefect.engine import enter_task_run_engine

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_task_run_engine(self, parameters)

    def update_dynamic_key(self):
        """
        Callback after task calls complete submission so this task will have a
        different dynamic key for future task runs
        """
        # Increment the key
        self.dynamic_key += 1


@overload
def task(__fn: Callable[P, R]) -> Task[P, R]:
    ...


@overload
def task(
    *,
    name: str = None,
    description: str = None,
    tags: Iterable[str] = None,
    cache_key_fn: Callable[["TaskRunContext", Dict[str, Any]], Optional[str]] = None,
    cache_expiration: datetime.timedelta = None,
    retries: int = 0,
    retry_delay_seconds: Union[float, int] = 0,
) -> Callable[[Callable[P, R]], Task[P, R]]:
    ...


def task(
    __fn=None,
    *,
    name: str = None,
    description: str = None,
    tags: Iterable[str] = None,
    cache_key_fn: Callable[["TaskRunContext", Dict[str, Any]], Optional[str]] = None,
    cache_expiration: datetime.timedelta = None,
    retries: int = 0,
    retry_delay_seconds: Union[float, int] = 0,
):
    """
    Decorator to designate a function as a task in a Prefect workflow.

    This decorator may be used for asynchronous or synchronous functions.

    Args:
        name: An optional name for the task. If not provided, the name will be inferred
            from the given function.
        description: An optional string description for the task.
        tags: An optional set of tags to be associated with runs of this task. These
            tags are combined with any tags defined by a `prefect.tags` context at
            task runtime.
        cache_key_fn: An optional callable that, given the task run context and call
            parameters, generates a string key. If the key matches a previous completed
            state, that state result will be restored instead of running the task again.
        cache_expiration: An optional amount of time indicating how long cached states
            for this task should be restorable. If not provided, cached states will
            never expire.
        retries: An optional number of times to retry on task run failure
        retry_delay_seconds: An optional number of seconds to wait before retrying the
            task after failure. This is only applicable if `retries` is nonzero.

    Returns:
        A callable `Task` object which, when called, will submit the task for execution.

    Examples:
        Define a simple task

        >>> from prefect import task
        >>> @task
        >>> def add(x, y):
        >>>     return x + y

        Define an async task

        >>> @task
        >>> async def add(x, y):
        >>>     return x + y

        Define a task with tags and a description

        >>> @task(tags={"a", "b"}, description="This task is empty but its my first!")
        >>> def my_task():
        >>>     pass

        Define a task with a custom name

        >>> @task(name="The Ultimate Task")
        >>> def my_task():
        >>>     pass

        Define a task that retries 3 times with a 5 second delay between attempts

        >>> from random import randint
        >>> @task(retries=3, retry_delay_seconds=5)
        >>> def my_task():
        >>>     x = randint(0, 5)
        >>>     if x >= 3:  # Make a task that fails sometimes
        >>>         raise ValueError("Retry me please!")
        >>>     return x

        Define a task that is cached for a day based on its inputs

        >>> from prefect.tasks import task_input_hash
        >>> from datetime import timedelta
        >>> @task(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=1))
        >>> def my_task():
        >>>     return "hello"


    """
    if __fn:
        return cast(
            Task[P, R],
            Task(
                fn=__fn,
                name=name,
                description=description,
                tags=tags,
                cache_key_fn=cache_key_fn,
                cache_expiration=cache_expiration,
                retries=retries,
                retry_delay_seconds=retry_delay_seconds,
            ),
        )
    else:
        return cast(
            Callable[[Callable[P, R]], Task[P, R]],
            partial(
                task,
                name=name,
                description=description,
                tags=tags,
                cache_key_fn=cache_key_fn,
                cache_expiration=cache_expiration,
                retries=retries,
                retry_delay_seconds=retry_delay_seconds,
            ),
        )
