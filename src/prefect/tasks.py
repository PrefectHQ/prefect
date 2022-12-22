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

from typing_extensions import Literal, ParamSpec

from prefect.context import PrefectObjectRegistry
from prefect.futures import PrefectFuture
from prefect.results import ResultSerializer, ResultStorage
from prefect.states import State
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import Async, Sync
from prefect.utilities.callables import (
    get_call_parameters,
    raise_for_reserved_arguments,
)
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
        context.task.fn.__code__.co_code.hex(),
        arguments,
    )


def exponential_backoff(backoff_factor: float) -> Callable[[int], List[float]]:
    """
    A task retry backoff utility that configures exponential backoff for task retries.
    The exponential backoff design matches the urllib3 implementation.

    Arguments:
        backoff_factor: the base delay for the first retry, subsequent retries will
            increase the delay time by powers of 2.

    Returns:
        a callable that can be passed to the task constructor
    """

    def retry_backoff_callable(retries: int) -> List[float]:
        # no more than 50 retry delays can be configured on a task
        retries = min(retries, 50)

        return [backoff_factor * max(0, 2**r) for r in range(retries)]

    return retry_backoff_callable


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
        fn: The function defining the task.
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
        retry_delay_seconds: Optionally configures how long to wait before retrying the
            task after failure. This is only applicable if `retries` is nonzero. This
            setting can either be a number of seconds, a list of retry delays, or a
            callable that, given the total number of retries, generates a list of retry
            delays. If a number of seconds, that delay will be applied to all retries.
            If a list, each retry will wait for the corresponding delay before retrying.
            When passing a callable or a list, the number of configured retry delays
            cannot exceed 50.
        retry_jitter_factor: An optional factor that defines the factor to which a retry
            can be jittered in order to avoid a "thundering herd".
        persist_result: An optional toggle indicating whether the result of this task
            should be persisted to result storage. Defaults to `None`, which indicates
            that Prefect should choose whether the result should be persisted depending on
            the features being used.
        result_storage: An optional block to use to persist the result of this task.
            Defaults to the value set in the flow the task is called in.
        result_serializer: An optional serializer to use to serialize the result of this
            task for persistence. Defaults to the value set in the flow the task is
            called in.
        timeout_seconds: An optional number of seconds indicating a maximum runtime for
            the task. If the task exceeds this runtime, it will be marked as failed.
        log_prints: If set, `print` statements in the task will be redirected to the
            Prefect logger for the task run. Defaults to `None`, which indicates
            that the value from the flow should be used.
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
        retry_delay_seconds: Union[
            float,
            int,
            List[float],
            Callable[[int], List[float]],
        ] = 0,
        retry_jitter_factor: Optional[float] = None,
        persist_result: Optional[bool] = None,
        result_storage: Optional[ResultStorage] = None,
        result_serializer: Optional[ResultSerializer] = None,
        cache_result_in_memory: bool = True,
        timeout_seconds: Union[int, float] = None,
        log_prints: Optional[bool] = False,
    ):
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn
        self.isasync = inspect.iscoroutinefunction(self.fn)

        if not name:
            if not hasattr(self.fn, "__name__"):
                self.name = type(self.fn).__name__
            else:
                self.name = self.fn.__name__
        else:
            self.name = name

        self.version = version
        self.log_prints = log_prints

        raise_for_reserved_arguments(self.fn, ["return_state", "wait_for"])

        self.tags = set(tags if tags else [])

        if not hasattr(self.fn, "__qualname__"):
            self.task_key = to_qualified_name(type(self.fn))
        else:
            self.task_key = to_qualified_name(self.fn)

        self.cache_key_fn = cache_key_fn
        self.cache_expiration = cache_expiration

        # TaskRunPolicy settings
        # TODO: We can instantiate a `TaskRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here
        self.retries = retries

        if callable(retry_delay_seconds):
            self.retry_delay_seconds = retry_delay_seconds(retries)
        else:
            self.retry_delay_seconds = retry_delay_seconds

        if isinstance(self.retry_delay_seconds, list) and (
            len(self.retry_delay_seconds) > 50
        ):
            raise ValueError("Can not configure more than 50 retry delays per task.")

        if retry_jitter_factor is not None and retry_jitter_factor < 0:
            raise ValueError("`retry_jitter_factor` must be >= 0.")

        self.retry_jitter_factor = retry_jitter_factor

        self.persist_result = persist_result
        self.result_storage = result_storage
        self.result_serializer = result_serializer
        self.cache_result_in_memory = cache_result_in_memory
        self.timeout_seconds = float(timeout_seconds) if timeout_seconds else None
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
        retries: Optional[int] = NotSet,
        retry_delay_seconds: Union[
            float,
            int,
            List[float],
            Callable[[int], List[float]],
        ] = NotSet,
        retry_jitter_factor: Optional[float] = NotSet,
        persist_result: Optional[bool] = NotSet,
        result_storage: Optional[ResultStorage] = NotSet,
        result_serializer: Optional[ResultSerializer] = NotSet,
        cache_result_in_memory: Optional[bool] = None,
        timeout_seconds: Union[int, float] = None,
        log_prints: Optional[bool] = NotSet,
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
            retry_delay_seconds: Optionally configures how long to wait before retrying
                the task after failure. This is only applicable if `retries` is nonzero.
                This setting can either be a number of seconds, a list of retry delays,
                or a callable that, given the total number of retries, generates a list
                of retry delays. If a number of seconds, that delay will be applied to
                all retries. If a list, each retry will wait for the corresponding delay
                before retrying. When passing a callable or a list, the number of
                configured retry delays cannot exceed 50.
            retry_jitter_factor: An optional factor that defines the factor to which a
                retry can be jittered in order to avoid a "thundering herd".
            persist_result: A new option for enabling or disabling result persistence.
            result_storage: A new storage type to use for results.
            result_serializer: A new serializer to use for results.

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
            retries=retries if retries is not NotSet else self.retries,
            retry_delay_seconds=(
                retry_delay_seconds
                if retry_delay_seconds is not NotSet
                else self.retry_delay_seconds
            ),
            retry_jitter_factor=(
                retry_jitter_factor
                if retry_jitter_factor is not NotSet
                else self.retry_jitter_factor
            ),
            persist_result=(
                persist_result if persist_result is not NotSet else self.persist_result
            ),
            result_storage=(
                result_storage if result_storage is not NotSet else self.result_storage
            ),
            result_serializer=(
                result_serializer
                if result_serializer is not NotSet
                else self.result_serializer
            ),
            cache_result_in_memory=(
                cache_result_in_memory
                if cache_result_in_memory is not None
                else self.cache_result_in_memory
            ),
            timeout_seconds=(
                timeout_seconds if timeout_seconds is not None else self.timeout_seconds
            ),
            log_prints=(log_prints if log_prints is not NotSet else self.log_prints),
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

    @overload
    def __call__(
        self: "Task[P, T]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> State[T]:
        ...

    def __call__(
        self,
        *args: P.args,
        return_state: bool = False,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        **kwargs: P.kwargs,
    ):
        """
        Run the task and return the result. If `return_state` is True returns
        the result is wrapped in a Prefect State which provides error handling.
        """
        from prefect.engine import enter_task_run_engine
        from prefect.task_runners import SequentialTaskRunner

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return_type = "state" if return_state else "result"

        return enter_task_run_engine(
            self,
            parameters=parameters,
            wait_for=wait_for,
            task_runner=SequentialTaskRunner(),
            return_type=return_type,
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

    @overload
    def submit(
        self: "Task[P, T]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> State[T]:
        ...

    def submit(
        self,
        *args: Any,
        return_state: bool = False,
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
            return_state: Return the result of the flow run wrapped in a
                Prefect State.
            wait_for: Upstream task futures to wait for before starting the task
            **kwargs: Keyword arguments to run the task with

        Returns:
            If `return_state` is False a future allowing asynchronous access to
                the state of the task
            If `return_state` is True a future wrapped in a Prefect State allowing asynchronous access to
                the state of the task

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
        return_type = "state" if return_state else "future"

        return enter_task_run_engine(
            self,
            parameters=parameters,
            wait_for=wait_for,
            return_type=return_type,
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

    @overload
    def map(
        self: "Task[P, T]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> List[State[T]]:
        ...

    def map(
        self,
        *args: Any,
        return_state: bool = False,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        **kwargs: Any,
    ) -> List[Union[PrefectFuture, Awaitable[PrefectFuture]]]:
        """
        Submit a mapped run of the task to a worker.

        Must be called within a flow function. If writing an async task, this
        call must be awaited.

        Must be called with at least one iterable and all iterables must be
        the same length. Any arguments that are not iterable will be treated as
        a static value and each task run will recieve the same value.

        Will create as many task runs as the length of the iterable(s) in the
        backing API and submit the task runs to the flow's task runner. This
        call blocks if given a future as input while the future is resolved. It
        also blocks while the tasks are being submitted, once they are
        submitted, the flow function will continue executing. However, note
        that the `SequentialTaskRunner` does not implement parallel execution
        for sync tasks and they are fully resolved on submission.

        Args:
            *args: Iterable and static arguments to run the tasks with
            return_state: Return a list of Prefect States that wrap the results
                of each task run.
            wait_for: Upstream task futures to wait for before starting the
                task
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

            Create mapped tasks

            >>> from prefect import flow
            >>> @flow
            >>> def my_flow():
            >>>     my_task.map([1, 2, 3])

            Wait for all mapped tasks to finish

            >>> @flow
            >>> def my_flow():
            >>>     futures = my_task.map([1, 2, 3])
            >>>     for future in futures:
            >>>         future.wait()
            >>>     # Now all of the mapped tasks have finished
            >>>     my_task(10)

            Use the result from mapped tasks in a flow

            >>> @flow
            >>> def my_flow():
            >>>     futures = my_task.map([1, 2, 3])
            >>>     for future in futures:
            >>>         print(future.result())
            >>> my_flow()
            2
            3
            4

            Enforce ordering between tasks that do not exchange data
            >>> @task
            >>> def task_1(x):
            >>>     pass
            >>>
            >>> @task
            >>> def task_2(y):
            >>>     pass
            >>>
            >>> @flow
            >>> def my_flow():
            >>>     x = task_1.submit()
            >>>
            >>>     # task 2 will wait for task_1 to complete
            >>>     y = task_2.map([1, 2, 3], wait_for=[x])

            Use a non-iterable input as a constant across mapped tasks
            >>> @task
            >>> def display(prefix, item):
            >>>    print(prefix, item)
            >>>
            >>> @flow
            >>> def my_flow():
            >>>     display.map("Check it out: ", [1, 2, 3])
            >>>
            >>> my_flow()
            Check it out: 1
            Check it out: 2
            Check it out: 3

            Use `unmapped` to treat an iterable argument as a constant
            >>> from prefect import unmapped
            >>>
            >>> @task
            >>> def add_n_to_items(items, n):
            >>>     return [item + n for item in items]
            >>>
            >>> @flow
            >>> def my_flow():
            >>>     return add_n_to_items.map(unmapped([10, 20]), n=[1, 2, 3])
            >>>
            >>> my_flow()
            [[11, 21], [12, 22], [13, 23]]
        """

        from prefect.engine import enter_task_run_engine

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)
        return_type = "state" if return_state else "future"

        return enter_task_run_engine(
            self,
            parameters=parameters,
            wait_for=wait_for,
            return_type=return_type,
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
    retry_delay_seconds: Union[
        float,
        int,
        List[float],
        Callable[[int], List[float]],
    ] = 0,
    retry_jitter_factor: Optional[float] = None,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    timeout_seconds: Union[int, float] = None,
    log_prints: Optional[bool] = None,
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
    retry_delay_seconds: Union[
        float,
        int,
        List[float],
        Callable[[int], List[float]],
    ] = 0,
    retry_jitter_factor: Optional[float] = None,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    timeout_seconds: Union[int, float] = None,
    log_prints: Optional[bool] = None,
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
        retry_delay_seconds: Optionally configures how long to wait before retrying the
            task after failure. This is only applicable if `retries` is nonzero. This
            setting can either be a number of seconds, a list of retry delays, or a
            callable that, given the total number of retries, generates a list of retry
            delays. If a number of seconds, that delay will be applied to all retries.
            If a list, each retry will wait for the corresponding delay before retrying.
            When passing a callable or a list, the number of configured retry delays
            cannot exceed 50.
        retry_jitter_factor: An optional factor that defines the factor to which a retry
            can be jittered in order to avoid a "thundering herd".
        persist_result: An optional toggle indicating whether the result of this task
            should be persisted to result storage. Defaults to `None`, which indicates
            that Prefect should choose whether the result should be persisted depending on
            the features being used.
        result_storage: An optional block to use to persist the result of this task.
            Defaults to the value set in the flow the task is called in.
        result_serializer: An optional serializer to use to serialize the result of this
            task for persistence. Defaults to the value set in the flow the task is
            called in.
        timeout_seconds: An optional number of seconds indicating a maximum runtime for
            the task. If the task exceeds this runtime, it will be marked as failed.
        log_prints: If set, `print` statements in the task will be redirected to the
            Prefect logger for the task run. Defaults to `None`, which indicates
            that the value from the flow should be used.

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
                retry_jitter_factor=retry_jitter_factor,
                persist_result=persist_result,
                result_storage=result_storage,
                result_serializer=result_serializer,
                cache_result_in_memory=cache_result_in_memory,
                timeout_seconds=timeout_seconds,
                log_prints=log_prints,
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
                retry_jitter_factor=retry_jitter_factor,
                persist_result=persist_result,
                result_storage=result_storage,
                result_serializer=result_serializer,
                cache_result_in_memory=cache_result_in_memory,
                timeout_seconds=timeout_seconds,
                log_prints=log_prints,
            ),
        )
