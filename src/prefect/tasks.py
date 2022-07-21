"""
Module containing the base workflow task class and decorator - for most use cases, using the [`@task` decorator][prefect.tasks.task] is preferred.
"""
# This file requires type-checking with pyright because mypy does not yet support PEP612
# See https://github.com/python/mypy/issues/8645

import datetime
import inspect
import warnings
from copy import copy
from functools import partial, update_wrapper
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    List,
    NoReturn,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import ParamSpec

from prefect.context import PrefectObjectRegistry
from prefect.exceptions import ReservedArgumentError
from prefect.futures import PrefectFuture
from prefect.states import State
from prefect.utilities.asyncutils import Async, Sync
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.hashing import hash_objects
from prefect.utilities.importtools import to_qualified_name

if TYPE_CHECKING:
    from prefect.context import TaskRunContext


T = TypeVar("T")  # Generic type var for capturing the inner return type of async funcs
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the task


def task_input_hash(
    context: "TaskRunContext", arguments: Dict[str, Any]
) -> Optional[str]:
    """
    A task cache key implementation which hashes all inputs to the task using a JSON or
    cloudpickle serializer. If any arguments are not JSON serializable, the pickle
    serializer is used as a fallback. If cloudpickle fails, this will return a null key
    indicating that a cache key could not be generated for the given inputs.

    Arguments:
        context: the active `TaskRunContext`
        arguments: a dictionary of arguments to be passed to the underlying task

    Returns:
        a string hash if hashing succeeded, else `None`
    """
    return hash_objects(
        # We use the task key to get the qualified name for the task and include the
        # task functions `co_code` bytes to avoid caching when the underlying function
        # changes
        context.task.task_key,
        context.task.fn.__code__.co_code,
        arguments,
    )


@PrefectObjectRegistry.register_instances
class Task(Generic[P, R]):
    """
    A Prefect task definition.

    !!! note
        We recommend using [the `@task` decorator][prefect.tasks.task] for most use-cases.

    Wraps a function with an entrypoint to the Prefect engine. Calling this class within a flow function
    creates a new task run.

    To preserve the input and output types, we use the generic type variables P and R for "Parameters" and
    "Returns" respectively.

    Args:
        name: An optional name for the task; if not provided, the name will be inferred
            from the given function.
        description: An optional string description for the task.
        tags: An optional set of tags to be associated with runs of this task. These
            tags are combined with any tags defined by a `prefect.tags` context at
            task runtime.
        version: An optional string specifying the version of this task definition
        cache_key_fn: An optional callable that, given the task run context and call
            parameters, generates a string key; if the key matches a previous completed
            state, that state result will be restored instead of running the task again.
        cache_expiration: An optional amount of time indicating how long cached states
            for this task should be restorable; if not provided, cached states will
            never expire.
        retries: An optional number of times to retry on task run failure.
        retry_delay_seconds: An optional number of seconds to wait before retrying the
            task after failure. This is only applicable if `retries` is nonzero.
    """

    # NOTE: These parameters (types, defaults, and docstrings) should be duplicated
    #       exactly in the @task decorator
    def __init__(
        self,
        fn: Callable[P, R],
        name: str = None,
        description: str = None,
        tags: Iterable[str] = None,
        version: str = None,
        cache_key_fn: Callable[
            ["TaskRunContext", Dict[str, Any]], Optional[str]
        ] = None,
        cache_expiration: datetime.timedelta = None,
        retries: int = 0,
        retry_delay_seconds: Union[float, int] = 0,
    ):
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn
        self.isasync = inspect.iscoroutinefunction(self.fn)

        self.name = name or self.fn.__name__
        self.version = version

        if "wait_for" in inspect.signature(self.fn).parameters:
            raise ReservedArgumentError(
                "'wait_for' is a reserved argument name and cannot be used in task functions."
            )

        self.tags = set(tags if tags else [])
        self.task_key = to_qualified_name(self.fn)

        self.cache_key_fn = cache_key_fn
        self.cache_expiration = cache_expiration

        # TaskRunPolicy settings
        # TODO: We can instantiate a `TaskRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds

        # Warn if this task's `name` conflicts with another task while having a
        # different function. This is to detect the case where two or more tasks
        # share a name or are lambdas, which should result in a warning, and to
        # differentiate it from the case where the task was 'copied' via
        # `with_options`, which should not result in a warning.
        registry = PrefectObjectRegistry.get()

        if registry and any(
            other
            for other in registry.get_instances(Task)
            if other.name == self.name and id(other.fn) != id(self.fn)
        ):
            file = inspect.getsourcefile(self.fn)
            line_number = inspect.getsourcelines(self.fn)[1]
            warnings.warn(
                f"A task named {self.name!r} and defined at '{file}:{line_number}' "
                "conflicts with another task. Consider specifying a unique `name` "
                "parameter in the task definition:\n\n "
                "`@task(name='my_unique_name', ...)`"
            )

    def with_options(
        self,
        *,
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
        """
        Create a new task from the current object, updating provided options.

        Args:
            name: A new name for the task.
            description: A new description for the task.
            tags: A new set of tags for the task. If given, existing tags are ignored,
                not merged.
            cache_key_fn: A new cache key function for the task.
            cache_expiration: A new cache expiration time for the task.
            retries: A new number of times to retry on task run failure.
            retry_delay_seconds: A new number of seconds to wait before retrying the
                task after failure. This is only applicable if `retries` is nonzero.

        Returns:
            A new `Task` instance.

        Examples:

            Create a new task from an existing task and update the name

            >>> @task(name="My task")
            >>> def my_task():
            >>>     return 1
            >>>
            >>> new_task = my_task.with_options(name="My new task")

            Create a new task from an existing task and update the retry settings

            >>> from random import randint
            >>>
            >>> @task(retries=1, retry_delay_seconds=5)
            >>> def my_task():
            >>>     x = randint(0, 5)
            >>>     if x >= 3:  # Make a task that fails sometimes
            >>>         raise ValueError("Retry me please!")
            >>>     return x
            >>>
            >>> new_task = my_task.with_options(retries=5, retry_delay_seconds=2)

            Use a task with updated options within a flow

            >>> @task(name="My task")
            >>> def my_task():
            >>>     return 1
            >>>
            >>> @flow
            >>> my_flow():
            >>>     new_task = my_task.with_options(name="My new task")
            >>>     new_task()
        """
        return Task(
            fn=self.fn,
            name=name or self.name,
            description=description or self.description,
            tags=tags or copy(self.tags),
            cache_key_fn=cache_key_fn or self.cache_key_fn,
            cache_expiration=cache_expiration or self.cache_expiration,
            retries=retries or self.retries,
            retry_delay_seconds=retry_delay_seconds or self.retry_delay_seconds,
        )

    @overload
    def __call__(
        self: "Task[P, NoReturn]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def __call__(
        self: "Task[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    def __call__(
        self,
        *args: P.args,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        **kwargs: P.kwargs,
    ):
        """
        Run the task and return the result.
        """
        from prefect.engine import enter_task_run_engine
        from prefect.task_runners import SequentialTaskRunner

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_task_run_engine(
            self,
            parameters=parameters,
            wait_for=wait_for,
            task_runner=SequentialTaskRunner(),
            return_type="result",
            mapped=False,
        )

    @overload
    def _run(
        self: "Task[P, NoReturn]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> PrefectFuture[None, Sync]:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def _run(
        self: "Task[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Awaitable[State[T]]:
        ...

    @overload
    def _run(
        self: "Task[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> State[T]:
        ...

    def _run(
        self,
        *args: P.args,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        **kwargs: P.kwargs,
    ) -> Union[State, Awaitable[State]]:
        """
        Run the task and return the final state.
        """
        from prefect.engine import enter_task_run_engine
        from prefect.task_runners import SequentialTaskRunner

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_task_run_engine(
            self,
            parameters=parameters,
            wait_for=wait_for,
            return_type="state",
            task_runner=SequentialTaskRunner(),
            mapped=False,
        )

    @overload
    def submit(
        self: "Task[P, NoReturn]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> PrefectFuture[None, Sync]:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def submit(
        self: "Task[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Awaitable[PrefectFuture[T, Async]]:
        ...

    @overload
    def submit(
        self: "Task[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> PrefectFuture[T, Sync]:
        ...

    def submit(
        self,
        *args: Any,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        **kwargs: Any,
    ) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:
        """
        Submit a run of the task to a worker.

        Must be called within a flow function. If writing an async task, this call must
        be awaited.

        Will create a new task run in the backing API and submit the task to the flow's
        task runner. This call only blocks execution while the task is being submitted,
        once it is submitted, the flow function will continue executing. However, note
        that the `SequentialTaskRunner` does not implement parallel execution for sync tasks
        and they are fully resolved on submission.

        Args:
            *args: Arguments to run the task with
            wait_for: Upstream task futures to wait for before starting the task
            **kwargs: Keyword arguments to run the task with

        Returns:
            A future allowing asynchronous access to the state of the task

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
            >>>     my_task.submit()

            Wait for a task to finish

            >>> @flow
            >>> def my_flow():
            >>>     my_task.submit().wait()

            Use the result from a task in a flow

            >>> @flow
            >>> def my_flow():
            >>>     print(my_task.submit().result())
            >>>
            >>> my_flow()
            hello

            Run an async task in an async flow

            >>> @task
            >>> async def my_async_task():
            >>>     pass
            >>>
            >>> @flow
            >>> async def my_flow():
            >>>     await my_async_task.submit()

            Run a sync task in an async flow

            >>> @flow
            >>> async def my_flow():
            >>>     my_task.submit()

            Enforce ordering between tasks that do not exchange data
            >>> @task
            >>> def task_1():
            >>>     pass
            >>>
            >>> @task
            >>> def task_2():
            >>>     pass
            >>>
            >>> @flow
            >>> def my_flow():
            >>>     x = task_1.submit()
            >>>
            >>>     # task 2 will wait for task_1 to complete
            >>>     y = task_2.submit(wait_for=[x])

        """

        from prefect.engine import enter_task_run_engine

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_task_run_engine(
            self,
            parameters=parameters,
            wait_for=wait_for,
            return_type="future",
            task_runner=None,  # Use the flow's task runner
            mapped=False,
        )

    @overload
    def map(
        self: "Task[P, NoReturn]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> List[PrefectFuture[None, Sync]]:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def map(
        self: "Task[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> List[Awaitable[PrefectFuture[T, Async]]]:
        ...

    @overload
    def map(
        self: "Task[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> List[PrefectFuture[T, Sync]]:
        ...

    def map(
        self,
        *args: Any,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        **kwargs: Any,
    ) -> List[Union[PrefectFuture, Awaitable[PrefectFuture]]]:
        """
        Submit a mapped run of the task to a worker.

        Must be called within a flow function. If writing an async task, this
        call must be awaited.

        Must be called with an iterable per task function argument. All
        iterables must be the same length.

        Will create as many task runs as the length of the iterable(s) in the
        backing API and submit the task runs to the flow's task runner. This
        call blocks if given a future as input while the future is resolved. It
        also blocks while the tasks are being submitted, once they are
        submitted, the flow function will continue executing. However, note
        that the `SequentialTaskRunner` does not implement parallel execution
        for sync tasks and they are fully resolved on submission.

        Args:
            *args: Iterable arguments to run the tasks with
            wait_for: Upstream task futures to wait for before starting the task
            **kwargs: Keyword iterable arguments to run the task with

        Returns:
            A list of futures allowing asynchronous access to the state of the
            tasks

        Examples:

            Define a task

            >>> from prefect import task
            >>> @task
            >>> def my_task(x):
            >>>     return x + 1

            Run a map in a flow

            >>> from prefect import flow
            >>> @flow
            >>> def my_flow():
            >>>     my_task.map([1, 2, 3])

            Wait for mapping to finish

            >>> @flow
            >>> def my_flow():
            >>>     futures = my_task.map([1, 2, 3])
            >>>     for future in futures:
            >>>         future.wait()

            Use the result from a map in a flow

            >>> @flow
            >>> def my_flow():
            >>>     futures = my_task.map([1, 2, 3])
            >>>     for future in futures:
            >>>         future.result()
            >>> my_flow()
            [2, 3, 4]

            Enforce ordering between tasks that do not exchange data
            >>> @task
            >>> def task_1():
            >>>     pass
            >>>
            >>> @task
            >>> def task_2():
            >>>     pass
            >>>
            >>> @flow
            >>> def my_flow():
            >>>     x = task_1.submit()
            >>>
            >>>     # task 2 will wait for task_1 to complete
            >>>     y = task_2.map([1, 2, 3], wait_for=[x])
        """

        from prefect.engine import enter_task_run_engine

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_task_run_engine(
            self,
            parameters=parameters,
            wait_for=wait_for,
            return_type="future",
            task_runner=None,
            mapped=True,
        )


@overload
def task(__fn: Callable[P, R]) -> Task[P, R]:
    ...


@overload
def task(
    *,
    name: str = None,
    description: str = None,
    tags: Iterable[str] = None,
    version: str = None,
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
    version: str = None,
    cache_key_fn: Callable[["TaskRunContext", Dict[str, Any]], Optional[str]] = None,
    cache_expiration: datetime.timedelta = None,
    retries: int = 0,
    retry_delay_seconds: Union[float, int] = 0,
):
    """
    Decorator to designate a function as a task in a Prefect workflow.

    This decorator may be used for asynchronous or synchronous functions.

    Args:
        name: An optional name for the task; if not provided, the name will be inferred
            from the given function.
        description: An optional string description for the task.
        tags: An optional set of tags to be associated with runs of this task. These
            tags are combined with any tags defined by a `prefect.tags` context at
            task runtime.
        version: An optional string specifying the version of this task definition
        cache_key_fn: An optional callable that, given the task run context and call
            parameters, generates a string key; if the key matches a previous completed
            state, that state result will be restored instead of running the task again.
        cache_expiration: An optional amount of time indicating how long cached states
            for this task should be restorable; if not provided, cached states will
            never expire.
        retries: An optional number of times to retry on task run failure
        retry_delay_seconds: An optional number of seconds to wait before retrying the
            task after failure. This is only applicable if `retries` is nonzero.

    Returns:
        A callable `Task` object which, when called, will submit the task for execution.

    Examples:
        Define a simple task

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
        >>>
        >>> @task(retries=3, retry_delay_seconds=5)
        >>> def my_task():
        >>>     x = randint(0, 5)
        >>>     if x >= 3:  # Make a task that fails sometimes
        >>>         raise ValueError("Retry me please!")
        >>>     return x

        Define a task that is cached for a day based on its inputs

        >>> from prefect.tasks import task_input_hash
        >>> from datetime import timedelta
        >>>
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
                version=version,
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
                version=version,
                cache_key_fn=cache_key_fn,
                cache_expiration=cache_expiration,
                retries=retries,
                retry_delay_seconds=retry_delay_seconds,
            ),
        )
