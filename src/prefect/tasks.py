"""
Module containing the base workflow task class and decorator - for most use cases, using the `@task` decorator is preferred.
"""

# This file requires type-checking with pyright because mypy does not yet support PEP612
# See https://github.com/python/mypy/issues/8645
from __future__ import annotations

import asyncio
import datetime
import inspect
from copy import copy
from functools import partial, update_wrapper
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    Iterable,
    NoReturn,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID, uuid4

from typing_extensions import (
    Literal,
    ParamSpec,
    Self,
    Sequence,
    TypeAlias,
    TypedDict,
    TypeIs,
    Unpack,
)

import prefect.states
from prefect._internal.uuid7 import uuid7
from prefect.assets import Asset
from prefect.cache_policies import DEFAULT, NO_CACHE, CachePolicy
from prefect.client.orchestration import get_client
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import (
    RunInput,
    StateDetails,
    TaskRunPolicy,
    TaskRunResult,
)
from prefect.context import (
    FlowRunContext,
    TagsContext,
    TaskRunContext,
    serialize_context,
)
from prefect.futures import PrefectDistributedFuture, PrefectFuture, PrefectFutureList
from prefect.logging.loggers import get_logger
from prefect.results import (
    ResultSerializer,
    ResultStorage,
    ResultStore,
    get_or_create_default_task_scheduling_storage,
)
from prefect.settings.context import get_current_settings
from prefect.states import Pending, Scheduled, State
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import run_coro_as_sync, sync_compatible
from prefect.utilities.callables import (
    expand_mapping_parameters,
    get_call_parameters,
    raise_for_reserved_arguments,
)
from prefect.utilities.hashing import hash_objects
from prefect.utilities.importtools import to_qualified_name
from prefect.utilities.urls import url_for

if TYPE_CHECKING:
    import logging

    from prefect.client.orchestration import PrefectClient
    from prefect.context import TaskRunContext
    from prefect.transactions import Transaction

T = TypeVar("T")
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the task

NUM_CHARS_DYNAMIC_KEY = 8

logger: "logging.Logger" = get_logger("tasks")

FutureOrResult: TypeAlias = Union[PrefectFuture[T], T]
OneOrManyFutureOrResult: TypeAlias = Union[
    FutureOrResult[T], Iterable[FutureOrResult[T]]
]


class TaskRunNameCallbackWithParameters(Protocol):
    @classmethod
    def is_callback_with_parameters(cls, callable: Callable[..., str]) -> TypeIs[Self]:
        sig = inspect.signature(callable)
        return "parameters" in sig.parameters

    def __call__(self, parameters: dict[str, Any]) -> str: ...


StateHookCallable: TypeAlias = Callable[
    ["Task[..., Any]", TaskRun, State], Union[Awaitable[None], None]
]
RetryConditionCallable: TypeAlias = Callable[
    ["Task[..., Any]", TaskRun, State], Union[Awaitable[bool], bool]
]
TaskRunNameValueOrCallable: TypeAlias = Union[
    Callable[[], str], TaskRunNameCallbackWithParameters, str
]


class TaskOptions(TypedDict, total=False):
    """
    A TypedDict representing all available task configuration options.

    This can be used with `Unpack` to provide type hints for **kwargs.
    """

    name: Optional[str]
    description: Optional[str]
    tags: Optional[Iterable[str]]
    version: Optional[str]
    cache_policy: Union[CachePolicy, type[NotSet]]
    cache_key_fn: Union[
        Callable[["TaskRunContext", dict[str, Any]], Optional[str]], None
    ]
    cache_expiration: Optional[datetime.timedelta]
    task_run_name: Optional[TaskRunNameValueOrCallable]
    retries: Optional[int]
    retry_delay_seconds: Union[
        float, int, list[float], Callable[[int], list[float]], None
    ]
    retry_jitter_factor: Optional[float]
    persist_result: Optional[bool]
    result_storage: Optional[ResultStorage]
    result_serializer: Optional[ResultSerializer]
    result_storage_key: Optional[str]
    cache_result_in_memory: bool
    timeout_seconds: Union[int, float, None]
    log_prints: Optional[bool]
    refresh_cache: Optional[bool]
    on_completion: Optional[list[StateHookCallable]]
    on_failure: Optional[list[StateHookCallable]]
    on_rollback: Optional[list[Callable[["Transaction"], None]]]
    on_commit: Optional[list[Callable[["Transaction"], None]]]
    retry_condition_fn: Optional[RetryConditionCallable]
    viz_return_value: Any
    asset_deps: Optional[list[Union[Asset, str]]]


def task_input_hash(
    context: "TaskRunContext", arguments: dict[str, Any]
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


def exponential_backoff(backoff_factor: float) -> Callable[[int], list[float]]:
    """
    A task retry backoff utility that configures exponential backoff for task retries.
    The exponential backoff design matches the urllib3 implementation.

    Arguments:
        backoff_factor: the base delay for the first retry, subsequent retries will
            increase the delay time by powers of 2.

    Returns:
        a callable that can be passed to the task constructor
    """

    def retry_backoff_callable(retries: int) -> list[float]:
        # no more than 50 retry delays can be configured on a task
        retries = min(retries, 50)

        return [backoff_factor * max(0, 2**r) for r in range(retries)]

    return retry_backoff_callable


def _infer_parent_task_runs(
    flow_run_context: Optional[FlowRunContext],
    task_run_context: Optional[TaskRunContext],
    parameters: dict[str, Any],
) -> list[TaskRunResult]:
    """
    Attempt to infer the parent task runs for this task run based on the
    provided flow run and task run contexts, as well as any parameters. It is
    assumed that the task run is running within those contexts.
    If any parameter comes from a running task run, that task run is considered
    a parent. This is expected to happen when task inputs are yielded from
    generator tasks.
    """
    parents: list[TaskRunResult] = []

    # check if this task has a parent task run based on running in another
    # task run's existing context. A task run is only considered a parent if
    # it is in the same flow run (because otherwise presumably the child is
    # in a subflow, so the subflow serves as the parent) or if there is no
    # flow run
    if task_run_context:
        # there is no flow run
        if not flow_run_context:
            parents.append(TaskRunResult(id=task_run_context.task_run.id))
        # there is a flow run and the task run is in the same flow run
        elif flow_run_context and task_run_context.task_run.flow_run_id == getattr(
            flow_run_context.flow_run, "id", None
        ):
            parents.append(TaskRunResult(id=task_run_context.task_run.id))

    # parent dependency tracking: for every provided parameter value, try to
    # load the corresponding task run state. If the task run state is still
    # running, we consider it a parent task run. Note this is only done if
    # there is an active flow run context because dependencies are only
    # tracked within the same flow run.
    if flow_run_context:
        for v in parameters.values():
            upstream_state = None

            if isinstance(v, State):
                upstream_state = v
            elif isinstance(v, PrefectFuture):
                upstream_state = v.state
            else:
                res = flow_run_context.run_results.get(id(v))
                if res:
                    upstream_state, _ = res

            if upstream_state and upstream_state.is_running():
                parents.append(
                    TaskRunResult(id=upstream_state.state_details.task_run_id)
                )

    return parents


def _generate_task_key(fn: Callable[..., Any]) -> str:
    """Generate a task key based on the function name and source code.

    We may eventually want some sort of top-level namespace here to
    disambiguate tasks with the same function name in different modules,
    in a more human-readable way, while avoiding relative import problems (see #12337).

    As long as the task implementations are unique (even if named the same), we should
    not have any collisions.

    Args:
        fn: The function to generate a task key for.
    """
    if not hasattr(fn, "__qualname__"):
        return to_qualified_name(type(fn))

    qualname = fn.__qualname__.split(".")[-1]

    try:
        code_obj = getattr(fn, "__code__", None)
        if code_obj is None:
            code_obj = fn.__call__.__code__
    except AttributeError:
        raise AttributeError(
            f"{fn} is not a standard Python function object and could not be converted to a task."
        ) from None

    code_hash = (
        h[:NUM_CHARS_DYNAMIC_KEY] if (h := hash_objects(code_obj)) else "unknown"
    )

    return f"{qualname}-{code_hash}"


class Task(Generic[P, R]):
    """
    A Prefect task definition.

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
        cache_policy: A cache policy that determines the level of caching for this task
        cache_key_fn: An optional callable that, given the task run context and call
            parameters, generates a string key; if the key matches a previous completed
            state, that state result will be restored instead of running the task again.
        cache_expiration: An optional amount of time indicating how long cached states
            for this task should be restorable; if not provided, cached states will
            never expire.
        task_run_name: An optional name to distinguish runs of this task; this name can be provided
            as a string template with the task's keyword arguments as variables,
            or a function that returns a string.
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
        persist_result: A toggle indicating whether the result of this task
            should be persisted to result storage. Defaults to `None`, which
            indicates that the global default should be used (which is `True` by
            default).
        result_storage: An optional block to use to persist the result of this task.
            Defaults to the value set in the flow the task is called in.
        result_storage_key: An optional key to store the result in storage at when persisted.
            Defaults to a unique identifier.
        result_serializer: An optional serializer to use to serialize the result of this
            task for persistence. Defaults to the value set in the flow the task is
            called in.
        timeout_seconds: An optional number of seconds indicating a maximum runtime for
            the task. If the task exceeds this runtime, it will be marked as failed.
        log_prints: If set, `print` statements in the task will be redirected to the
            Prefect logger for the task run. Defaults to `None`, which indicates
            that the value from the flow should be used.
        refresh_cache: If set, cached results for the cache key are not used.
            Defaults to `None`, which indicates that a cached result from a previous
            execution with matching cache key is used.
        on_failure: An optional list of callables to run when the task enters a failed state.
        on_completion: An optional list of callables to run when the task enters a completed state.
        on_commit: An optional list of callables to run when the task's idempotency record is committed.
        on_rollback: An optional list of callables to run when the task rolls back.
        retry_condition_fn: An optional callable run when a task run returns a Failed state. Should
            return `True` if the task should continue to its retry policy (e.g. `retries=3`), and `False` if the task
            should end as failed. Defaults to `None`, indicating the task should always continue
            to its retry policy.
        viz_return_value: An optional value to return when the task dependency tree is visualized.
        asset_deps: An optional list of upstream assets that this task depends on.
    """

    # NOTE: These parameters (types, defaults, and docstrings) should be duplicated
    #       exactly in the @task decorator
    def __init__(
        self,
        fn: Callable[P, R] | "classmethod[Any, P, R]" | "staticmethod[P, R]",
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        version: Optional[str] = None,
        cache_policy: Union[CachePolicy, type[NotSet]] = NotSet,
        cache_key_fn: Optional[
            Callable[["TaskRunContext", dict[str, Any]], Optional[str]]
        ] = None,
        cache_expiration: Optional[datetime.timedelta] = None,
        task_run_name: Optional[TaskRunNameValueOrCallable] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[
            Union[
                float,
                int,
                list[float],
                Callable[[int], list[float]],
            ]
        ] = None,
        retry_jitter_factor: Optional[float] = None,
        persist_result: Optional[bool] = None,
        result_storage: Optional[ResultStorage] = None,
        result_serializer: Optional[ResultSerializer] = None,
        result_storage_key: Optional[str] = None,
        cache_result_in_memory: bool = True,
        timeout_seconds: Union[int, float, None] = None,
        log_prints: Optional[bool] = False,
        refresh_cache: Optional[bool] = None,
        on_completion: Optional[list[StateHookCallable]] = None,
        on_failure: Optional[list[StateHookCallable]] = None,
        on_rollback: Optional[list[Callable[["Transaction"], None]]] = None,
        on_commit: Optional[list[Callable[["Transaction"], None]]] = None,
        retry_condition_fn: Optional[RetryConditionCallable] = None,
        viz_return_value: Optional[Any] = None,
        asset_deps: Optional[list[Union[str, Asset]]] = None,
    ):
        # Validate if hook passed is list and contains callables
        hook_categories = [on_completion, on_failure]
        hook_names = ["on_completion", "on_failure"]
        for hooks, hook_name in zip(hook_categories, hook_names):
            if hooks is not None:
                try:
                    hooks = list(hooks)
                except TypeError:
                    raise TypeError(
                        f"Expected iterable for '{hook_name}'; got"
                        f" {type(hooks).__name__} instead. Please provide a list of"
                        f" hooks to '{hook_name}':\n\n"
                        f"@task({hook_name}=[hook1, hook2])\ndef"
                        " my_task():\n\tpass"
                    )

                for hook in hooks:
                    if not callable(hook):
                        raise TypeError(
                            f"Expected callables in '{hook_name}'; got"
                            f" {type(hook).__name__} instead. Please provide a list of"
                            f" hooks to '{hook_name}':\n\n"
                            f"@task({hook_name}=[hook1, hook2])\ndef"
                            " my_task():\n\tpass"
                        )

        if isinstance(fn, classmethod):
            fn = cast(Callable[P, R], fn.__func__)
            self._isclassmethod = True

        if isinstance(fn, staticmethod):
            fn = cast(Callable[P, R], fn.__func__)
            self._isstaticmethod = True

        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.description: str | None = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn

        # the task is considered async if its function is async or an async
        # generator
        self.isasync: bool = asyncio.iscoroutinefunction(
            self.fn
        ) or inspect.isasyncgenfunction(self.fn)

        # the task is considered a generator if its function is a generator or
        # an async generator
        self.isgenerator: bool = inspect.isgeneratorfunction(
            self.fn
        ) or inspect.isasyncgenfunction(self.fn)

        if not name:
            if not hasattr(self.fn, "__name__"):
                self.name = type(self.fn).__name__
            else:
                self.name = self.fn.__name__
        else:
            self.name: str = name

        if task_run_name is not None:
            if not isinstance(task_run_name, str) and not callable(task_run_name):
                raise TypeError(
                    "Expected string or callable for 'task_run_name'; got"
                    f" {type(task_run_name).__name__} instead."
                )
        self.task_run_name = task_run_name

        self.version = version
        self.log_prints = log_prints

        raise_for_reserved_arguments(self.fn, ["return_state", "wait_for"])

        self.tags: set[str] = set(tags if tags else [])

        self.task_key: str = _generate_task_key(self.fn)

        # determine cache and result configuration
        settings = get_current_settings()
        if settings.tasks.default_no_cache and cache_policy is NotSet:
            cache_policy = NO_CACHE

        if cache_policy is not NotSet and cache_key_fn is not None:
            logger.warning(
                f"Both `cache_policy` and `cache_key_fn` are set on task {self}. `cache_key_fn` will be used."
            )

        if cache_key_fn:
            cache_policy = CachePolicy.from_cache_key_fn(cache_key_fn)

        # TODO: manage expiration and cache refresh
        self.cache_key_fn = cache_key_fn
        self.cache_expiration = cache_expiration
        self.refresh_cache = refresh_cache

        # result persistence settings
        if persist_result is None:
            if any(
                [
                    cache_policy
                    and cache_policy != NO_CACHE
                    and cache_policy != NotSet,
                    cache_key_fn is not None,
                    result_storage_key is not None,
                    result_storage is not None,
                    result_serializer is not None,
                ]
            ):
                persist_result = True

        # Check for global cache disable setting
        if settings.tasks.disable_caching:
            cache_policy = NO_CACHE

        if persist_result is False:
            self.cache_policy = None if cache_policy is None else NO_CACHE
            if cache_policy and cache_policy is not NotSet and cache_policy != NO_CACHE:
                logger.warning(
                    "Ignoring `cache_policy` because `persist_result` is False"
                )
        elif cache_policy is NotSet and result_storage_key is None:
            self.cache_policy = DEFAULT
        elif cache_policy != NO_CACHE and result_storage_key:
            # TODO: handle this situation with double storage
            self.cache_policy = None
        else:
            self.cache_policy: Union[CachePolicy, type[NotSet], None] = cache_policy

        # TaskRunPolicy settings
        # TODO: We can instantiate a `TaskRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here

        self.retries: int = (
            retries if retries is not None else settings.tasks.default_retries
        )
        if retry_delay_seconds is None:
            retry_delay_seconds = settings.tasks.default_retry_delay_seconds

        if callable(retry_delay_seconds):
            self.retry_delay_seconds = retry_delay_seconds(self.retries)
        elif not isinstance(retry_delay_seconds, (list, int, float, type(None))):
            raise TypeError(
                f"Invalid `retry_delay_seconds` provided; must be an int, float, list or callable. Received type {type(retry_delay_seconds)}"
            )
        else:
            self.retry_delay_seconds: Union[float, int, list[float], None] = (
                retry_delay_seconds
            )

        if isinstance(self.retry_delay_seconds, list) and (
            len(self.retry_delay_seconds) > 50
        ):
            raise ValueError("Can not configure more than 50 retry delays per task.")

        if retry_jitter_factor is not None and retry_jitter_factor < 0:
            raise ValueError("`retry_jitter_factor` must be >= 0.")

        self.retry_jitter_factor = retry_jitter_factor
        self.persist_result = persist_result

        if result_storage and not isinstance(result_storage, str):
            if getattr(result_storage, "_block_document_id", None) is None:
                raise TypeError(
                    "Result storage configuration must be persisted server-side."
                    " Please call `.save()` on your block before passing it in."
                )

        self.result_storage = result_storage
        self.result_serializer = result_serializer
        self.result_storage_key = result_storage_key
        self.cache_result_in_memory = cache_result_in_memory
        self.timeout_seconds: Union[float, None] = (
            float(timeout_seconds) if timeout_seconds else None
        )
        self.on_rollback_hooks: list[Callable[["Transaction"], None]] = (
            on_rollback or []
        )
        self.on_commit_hooks: list[Callable[["Transaction"], None]] = on_commit or []
        self.on_completion_hooks: list[StateHookCallable] = on_completion or []
        self.on_failure_hooks: list[StateHookCallable] = on_failure or []

        # retry_condition_fn must be a callable or None. If it is neither, raise a TypeError
        if retry_condition_fn is not None and not (callable(retry_condition_fn)):
            raise TypeError(
                "Expected `retry_condition_fn` to be callable, got"
                f" {type(retry_condition_fn).__name__} instead."
            )

        self.retry_condition_fn = retry_condition_fn
        self.viz_return_value = viz_return_value

        from prefect.assets import Asset

        self.asset_deps: list[Asset] = (
            [Asset(key=a) if isinstance(a, str) else a for a in asset_deps]
            if asset_deps
            else []
        )

    @property
    def ismethod(self) -> bool:
        return hasattr(self.fn, "__prefect_self__")

    @property
    def isclassmethod(self) -> bool:
        return getattr(self, "_isclassmethod", False)

    @property
    def isstaticmethod(self) -> bool:
        return getattr(self, "_isstaticmethod", False)

    def __get__(self, instance: Any, owner: Any) -> "Task[P, R]":
        """
        Implement the descriptor protocol so that the task can be used as an instance method.
        When an instance method is loaded, this method is called with the "self" instance as
        an argument. We return a copy of the task with that instance bound to the task's function.
        """
        # wrapped function is a classmethod
        if self.isclassmethod:
            bound_task = copy(self)
            setattr(bound_task.fn, "__prefect_cls__", owner)
            return bound_task

        # if the task is being accessed on an instance, bind the instance to the __prefect_self__ attribute
        # of the task's function. This will allow it to be automatically added to the task's parameters
        if instance:
            bound_task = copy(self)
            bound_task.fn.__prefect_self__ = instance  # type: ignore[attr-defined]
            return bound_task

        return self

    def with_options(
        self,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        cache_policy: Union[CachePolicy, type[NotSet]] = NotSet,
        cache_key_fn: Optional[
            Callable[["TaskRunContext", dict[str, Any]], Optional[str]]
        ] = None,
        task_run_name: Optional[
            Union[TaskRunNameValueOrCallable, type[NotSet]]
        ] = NotSet,
        cache_expiration: Optional[datetime.timedelta] = None,
        retries: Union[int, type[NotSet]] = NotSet,
        retry_delay_seconds: Union[
            float,
            int,
            list[float],
            Callable[[int], list[float]],
            type[NotSet],
        ] = NotSet,
        retry_jitter_factor: Union[float, type[NotSet]] = NotSet,
        persist_result: Union[bool, type[NotSet]] = NotSet,
        result_storage: Union[ResultStorage, type[NotSet]] = NotSet,
        result_serializer: Union[ResultSerializer, type[NotSet]] = NotSet,
        result_storage_key: Union[str, type[NotSet]] = NotSet,
        cache_result_in_memory: Optional[bool] = None,
        timeout_seconds: Union[int, float, None] = None,
        log_prints: Union[bool, type[NotSet]] = NotSet,
        refresh_cache: Union[bool, type[NotSet]] = NotSet,
        on_completion: Optional[list[StateHookCallable]] = None,
        on_failure: Optional[list[StateHookCallable]] = None,
        retry_condition_fn: Optional[RetryConditionCallable] = None,
        viz_return_value: Optional[Any] = None,
        asset_deps: Optional[list[Union[str, Asset]]] = None,
    ) -> "Task[P, R]":
        """
        Create a new task from the current object, updating provided options.

        Args:
            name: A new name for the task.
            description: A new description for the task.
            tags: A new set of tags for the task. If given, existing tags are ignored,
                not merged.
            cache_key_fn: A new cache key function for the task.
            cache_expiration: A new cache expiration time for the task.
            task_run_name: An optional name to distinguish runs of this task; this name can be provided
                as a string template with the task's keyword arguments as variables,
                or a function that returns a string.
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
            result_storage_key: A new key for the persisted result to be stored at.
            timeout_seconds: A new maximum time for the task to complete in seconds.
            log_prints: A new option for enabling or disabling redirection of `print` statements.
            refresh_cache: A new option for enabling or disabling cache refresh.
            on_completion: A new list of callables to run when the task enters a completed state.
            on_failure: A new list of callables to run when the task enters a failed state.
            retry_condition_fn: An optional callable run when a task run returns a Failed state.
                Should return `True` if the task should continue to its retry policy, and `False`
                if the task should end as failed. Defaults to `None`, indicating the task should
                always continue to its retry policy.
            viz_return_value: An optional value to return when the task dependency tree is visualized.

        Returns:
            A new `Task` instance.

        Examples:

            Create a new task from an existing task and update the name:

            ```python
            @task(name="My task")
            def my_task():
                return 1

            new_task = my_task.with_options(name="My new task")
            ```

            Create a new task from an existing task and update the retry settings:

            ```python
            from random import randint

            @task(retries=1, retry_delay_seconds=5)
            def my_task():
                x = randint(0, 5)
                if x >= 3:  # Make a task that fails sometimes
                    raise ValueError("Retry me please!")
                return x

            new_task = my_task.with_options(retries=5, retry_delay_seconds=2)
            ```

            Use a task with updated options within a flow:

            ```python
            @task(name="My task")
            def my_task():
                return 1

            @flow
            my_flow():
                new_task = my_task.with_options(name="My new task")
                new_task()
            ```

        """
        return Task(
            fn=self.fn,
            name=name or self.name,
            description=description or self.description,
            tags=tags or copy(self.tags),
            cache_policy=cache_policy
            if cache_policy is not NotSet
            else self.cache_policy,
            cache_key_fn=cache_key_fn or self.cache_key_fn,
            cache_expiration=cache_expiration or self.cache_expiration,
            task_run_name=task_run_name
            if task_run_name is not NotSet
            else self.task_run_name,
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
            result_storage_key=(
                result_storage_key
                if result_storage_key is not NotSet
                else self.result_storage_key
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
            refresh_cache=(
                refresh_cache if refresh_cache is not NotSet else self.refresh_cache
            ),
            on_completion=on_completion or self.on_completion_hooks,
            on_failure=on_failure or self.on_failure_hooks,
            retry_condition_fn=retry_condition_fn or self.retry_condition_fn,
            viz_return_value=viz_return_value or self.viz_return_value,
            asset_deps=asset_deps or self.asset_deps,
        )

    def on_completion(self, fn: StateHookCallable) -> StateHookCallable:
        self.on_completion_hooks.append(fn)
        return fn

    def on_failure(self, fn: StateHookCallable) -> StateHookCallable:
        self.on_failure_hooks.append(fn)
        return fn

    def on_commit(
        self, fn: Callable[["Transaction"], None]
    ) -> Callable[["Transaction"], None]:
        self.on_commit_hooks.append(fn)
        return fn

    def on_rollback(
        self, fn: Callable[["Transaction"], None]
    ) -> Callable[["Transaction"], None]:
        self.on_rollback_hooks.append(fn)
        return fn

    async def create_run(
        self,
        client: Optional["PrefectClient"] = None,
        id: Optional[UUID] = None,
        parameters: Optional[dict[str, Any]] = None,
        flow_run_context: Optional[FlowRunContext] = None,
        parent_task_run_context: Optional[TaskRunContext] = None,
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        extra_task_inputs: Optional[dict[str, set[RunInput]]] = None,
        deferred: bool = False,
    ) -> TaskRun:
        from prefect.utilities._engine import dynamic_key_for_task_run
        from prefect.utilities.engine import collect_task_run_inputs_sync

        if flow_run_context is None:
            flow_run_context = FlowRunContext.get()
        if parent_task_run_context is None:
            parent_task_run_context = TaskRunContext.get()
        if parameters is None:
            parameters = {}
        if client is None:
            client = get_client()

        async with client:
            if not flow_run_context:
                dynamic_key = f"{self.task_key}-{str(uuid4().hex)}"
                task_run_name = self.name
            else:
                dynamic_key = dynamic_key_for_task_run(
                    context=flow_run_context, task=self
                )
                task_run_name = f"{self.name}-{dynamic_key}"

            if deferred:
                state = Scheduled()
                state.state_details.deferred = True
            else:
                state = Pending()

            # store parameters for background tasks so that task worker
            # can retrieve them at runtime
            if deferred and (parameters or wait_for):
                from prefect.task_worker import store_parameters

                parameters_id = uuid4()
                state.state_details.task_parameters_id = parameters_id

                # TODO: Improve use of result storage for parameter storage / reference
                self.persist_result = True

                store = await ResultStore(
                    result_storage=await get_or_create_default_task_scheduling_storage()
                ).update_for_task(self)
                context = serialize_context()
                data: dict[str, Any] = {"context": context}
                if parameters:
                    data["parameters"] = parameters
                if wait_for:
                    data["wait_for"] = wait_for
                await store_parameters(store, parameters_id, data)

            # collect task inputs
            task_inputs = {
                k: collect_task_run_inputs_sync(v) for k, v in parameters.items()
            }

            # collect all parent dependencies
            if task_parents := _infer_parent_task_runs(
                flow_run_context=flow_run_context,
                task_run_context=parent_task_run_context,
                parameters=parameters,
            ):
                task_inputs["__parents__"] = task_parents

            # check wait for dependencies
            if wait_for:
                task_inputs["wait_for"] = collect_task_run_inputs_sync(wait_for)

            # Join extra task inputs
            for k, extras in (extra_task_inputs or {}).items():
                task_inputs[k] = task_inputs[k].union(extras)

            # create the task run
            task_run = client.create_task_run(
                task=self,
                name=task_run_name,
                flow_run_id=(
                    getattr(flow_run_context.flow_run, "id", None)
                    if flow_run_context and flow_run_context.flow_run
                    else None
                ),
                dynamic_key=str(dynamic_key),
                id=id,
                state=state,
                task_inputs=task_inputs,
                extra_tags=TagsContext.get().current_tags,
            )
            # the new engine uses sync clients but old engines use async clients
            if inspect.isawaitable(task_run):
                task_run = await task_run

            return task_run

    async def create_local_run(
        self,
        client: Optional["PrefectClient"] = None,
        id: Optional[UUID] = None,
        parameters: Optional[dict[str, Any]] = None,
        flow_run_context: Optional[FlowRunContext] = None,
        parent_task_run_context: Optional[TaskRunContext] = None,
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        extra_task_inputs: Optional[dict[str, set[RunInput]]] = None,
        deferred: bool = False,
    ) -> TaskRun:
        from prefect.utilities._engine import dynamic_key_for_task_run
        from prefect.utilities.engine import (
            collect_task_run_inputs_sync,
        )

        if flow_run_context is None:
            flow_run_context = FlowRunContext.get()
        if parent_task_run_context is None:
            parent_task_run_context = TaskRunContext.get()
        if parameters is None:
            parameters = {}
        if client is None:
            client = get_client()

        async with client:
            if not flow_run_context:
                dynamic_key = f"{self.task_key}-{str(uuid4().hex)}"
                task_run_name = self.name
            else:
                dynamic_key = dynamic_key_for_task_run(
                    context=flow_run_context, task=self, stable=False
                )
                task_run_name = f"{self.name}-{dynamic_key[:3]}"

            if deferred:
                state = Scheduled()
                state.state_details.deferred = True
            else:
                state = Pending()

            # store parameters for background tasks so that task worker
            # can retrieve them at runtime
            if deferred and (parameters or wait_for):
                from prefect.task_worker import store_parameters

                parameters_id = uuid4()
                state.state_details.task_parameters_id = parameters_id

                # TODO: Improve use of result storage for parameter storage / reference
                self.persist_result = True

                store = await ResultStore(
                    result_storage=await get_or_create_default_task_scheduling_storage()
                ).update_for_task(self)
                context = serialize_context()
                data: dict[str, Any] = {"context": context}
                if parameters:
                    data["parameters"] = parameters
                if wait_for:
                    data["wait_for"] = wait_for
                await store_parameters(store, parameters_id, data)

            # collect task inputs
            task_inputs = {
                k: collect_task_run_inputs_sync(v) for k, v in parameters.items()
            }

            # collect all parent dependencies
            if task_parents := _infer_parent_task_runs(
                flow_run_context=flow_run_context,
                task_run_context=parent_task_run_context,
                parameters=parameters,
            ):
                task_inputs["__parents__"] = task_parents

            # check wait for dependencies
            if wait_for:
                task_inputs["wait_for"] = collect_task_run_inputs_sync(wait_for)

            # Join extra task inputs
            for k, extras in (extra_task_inputs or {}).items():
                task_inputs[k] = task_inputs[k].union(extras)

            flow_run_id = (
                getattr(flow_run_context.flow_run, "id", None)
                if flow_run_context and flow_run_context.flow_run
                else None
            )
            task_run_id = id or uuid7()

            state = prefect.states.Pending(
                state_details=StateDetails(
                    task_run_id=task_run_id,
                    flow_run_id=flow_run_id,
                )
            )
            task_run = TaskRun(
                id=task_run_id,
                name=task_run_name,
                flow_run_id=flow_run_id,
                task_key=self.task_key,
                dynamic_key=str(dynamic_key),
                task_version=self.version,
                empirical_policy=TaskRunPolicy(
                    retries=self.retries,
                    retry_delay=self.retry_delay_seconds,
                    retry_jitter_factor=self.retry_jitter_factor,
                ),
                tags=list(set(self.tags).union(TagsContext.get().current_tags or [])),
                task_inputs=task_inputs or {},
                expected_start_time=state.timestamp,
                state_id=state.id,
                state_type=state.type,
                state_name=state.name,
                state=state,
                created=state.timestamp,
                updated=state.timestamp,
            )

            return task_run

    @overload
    def __call__(
        self: "Task[P, NoReturn]",
        *args: P.args,
        return_state: Literal[False] = False,
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: P.kwargs,
    ) -> None:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def __call__(
        self: "Task[P, R]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R: ...

    # Keyword parameters `return_state` and `wait_for` aren't allowed after the
    # ParamSpec `*args` parameter, so we lose return type typing when either of
    # those are provided.
    # TODO: Find a way to expose this functionality without losing type information
    @overload
    def __call__(
        self: "Task[P, R]",
        *args: P.args,
        return_state: Literal[True] = True,
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: P.kwargs,
    ) -> State[R]: ...

    @overload
    def __call__(
        self: "Task[P, R]",
        *args: P.args,
        return_state: Literal[False] = False,
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: P.kwargs,
    ) -> R: ...

    def __call__(
        self: "Union[Task[P, R], Task[P, NoReturn]]",
        *args: P.args,
        return_state: bool = False,
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: P.kwargs,
    ) -> Union[R, State[R], None]:
        """
        Run the task and return the result. If `return_state` is True returns
        the result is wrapped in a Prefect State which provides error handling.
        """
        from prefect.utilities.visualization import (
            get_task_viz_tracker,
            track_viz_task,
        )

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return_type = "state" if return_state else "result"

        task_run_tracker = get_task_viz_tracker()
        if task_run_tracker:
            return track_viz_task(
                self.isasync, self.name, parameters, self.viz_return_value
            )

        from prefect.task_engine import run_task

        return run_task(
            task=self,
            parameters=parameters,
            wait_for=wait_for,
            return_type=return_type,
        )

    @overload
    def submit(
        self: "Task[P, R]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> PrefectFuture[R]: ...

    @overload
    def submit(
        self: "Task[P, Coroutine[Any, Any, R]]",
        *args: P.args,
        return_state: Literal[False],
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: P.kwargs,
    ) -> PrefectFuture[R]: ...

    @overload
    def submit(
        self: "Task[P, R]",
        *args: P.args,
        return_state: Literal[False],
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: P.kwargs,
    ) -> PrefectFuture[R]: ...

    @overload
    def submit(
        self: "Task[P, Coroutine[Any, Any, R]]",
        *args: P.args,
        return_state: Literal[True],
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: P.kwargs,
    ) -> State[R]: ...

    @overload
    def submit(
        self: "Task[P, R]",
        *args: P.args,
        return_state: Literal[True],
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: P.kwargs,
    ) -> State[R]: ...

    def submit(
        self: "Union[Task[P, R], Task[P, Coroutine[Any, Any, R]]]",
        *args: Any,
        return_state: bool = False,
        wait_for: Optional[OneOrManyFutureOrResult[Any]] = None,
        **kwargs: Any,
    ):
        """
        Submit a run of the task to the engine.

        Will create a new task run in the backing API and submit the task to the flow's
        task runner. This call only blocks execution while the task is being submitted,
        once it is submitted, the flow function will continue executing.

        This method is always synchronous, even if the underlying user function is asynchronous.

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

            ```python
            from prefect import task
            @task
            def my_task():
                return "hello"
            ```

            Run a task in a flow

            ```python
            from prefect import flow
            @flow
            def my_flow():
                my_task.submit()
            ```

            Wait for a task to finish

            ```python
            @flow
            def my_flow():
                my_task.submit().wait()
            ```

            Use the result from a task in a flow

            ```python
            @flow
            def my_flow():
                print(my_task.submit().result())

            my_flow()
            # hello
            ```

            Run an async task in an async flow

            ```python
            @task
            async def my_async_task():
                pass

            @flow
            async def my_flow():
                my_async_task.submit()
            ```

            Run a sync task in an async flow

            ```python
            @flow
            async def my_flow():
                my_task.submit()
            ```

            Enforce ordering between tasks that do not exchange data

            ```python
            @task
            def task_1():
                pass

            @task
            def task_2():
                pass

            @flow
            def my_flow():
                x = task_1.submit()

                # task 2 will wait for task_1 to complete
                y = task_2.submit(wait_for=[x])
            ```

        """

        from prefect.utilities.visualization import (
            VisualizationUnsupportedError,
            get_task_viz_tracker,
        )

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)
        flow_run_context = FlowRunContext.get()

        if not flow_run_context:
            raise RuntimeError(
                "Unable to determine task runner to use for submission. If you are"
                " submitting a task outside of a flow, please use `.delay`"
                " to submit the task run for deferred execution."
            )

        task_viz_tracker = get_task_viz_tracker()
        if task_viz_tracker:
            raise VisualizationUnsupportedError(
                "`task.submit()` is not currently supported by `flow.visualize()`"
            )

        task_runner = flow_run_context.task_runner
        future = task_runner.submit(self, parameters, wait_for)
        if return_state:
            future.wait()
            return future.state
        else:
            return future

    @overload
    def map(
        self: "Task[P, R]",
        *args: Any,
        return_state: Literal[True],
        wait_for: Optional[Iterable[Union[PrefectFuture[R], R]]] = ...,
        deferred: bool = ...,
        **kwargs: Any,
    ) -> list[State[R]]: ...

    @overload
    def map(
        self: "Task[P, R]",
        *args: Any,
        wait_for: Optional[Iterable[Union[PrefectFuture[R], R]]] = ...,
        deferred: bool = ...,
        **kwargs: Any,
    ) -> PrefectFutureList[R]: ...

    @overload
    def map(
        self: "Task[P, R]",
        *args: Any,
        return_state: Literal[True],
        wait_for: Optional[Iterable[Union[PrefectFuture[R], R]]] = ...,
        deferred: bool = ...,
        **kwargs: Any,
    ) -> list[State[R]]: ...

    @overload
    def map(
        self: "Task[P, R]",
        *args: Any,
        wait_for: Optional[Iterable[Union[PrefectFuture[R], R]]] = ...,
        deferred: bool = ...,
        **kwargs: Any,
    ) -> PrefectFutureList[R]: ...

    @overload
    def map(
        self: "Task[P, Coroutine[Any, Any, R]]",
        *args: Any,
        return_state: Literal[True],
        wait_for: Optional[Iterable[Union[PrefectFuture[R], R]]] = ...,
        deferred: bool = ...,
        **kwargs: Any,
    ) -> list[State[R]]: ...

    @overload
    def map(
        self: "Task[P, Coroutine[Any, Any, R]]",
        *args: Any,
        return_state: Literal[False],
        wait_for: Optional[Iterable[Union[PrefectFuture[R], R]]] = ...,
        deferred: bool = ...,
        **kwargs: Any,
    ) -> PrefectFutureList[R]: ...

    def map(
        self,
        *args: Any,
        return_state: bool = False,
        wait_for: Optional[Iterable[Union[PrefectFuture[R], R]]] = None,
        deferred: bool = False,
        **kwargs: Any,
    ) -> Union[list[State[R]], PrefectFutureList[R]]:
        """
        Submit a mapped run of the task to a worker.

        Must be called within a flow run context. Will return a list of futures
        that should be waited on before exiting the flow context to ensure all
        mapped tasks have completed.

        Must be called with at least one iterable and all iterables must be
        the same length. Any arguments that are not iterable will be treated as
        a static value and each task run will receive the same value.

        Will create as many task runs as the length of the iterable(s) in the
        backing API and submit the task runs to the flow's task runner. This
        call blocks if given a future as input while the future is resolved. It
        also blocks while the tasks are being submitted, once they are
        submitted, the flow function will continue executing.

        This method is always synchronous, even if the underlying user function is asynchronous.

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

            ```python
            from prefect import task
            @task
            def my_task(x):
                return x + 1
            ```

            Create mapped tasks

            ```python
            from prefect import flow
            @flow
            def my_flow():
                return my_task.map([1, 2, 3])
            ```

            Wait for all mapped tasks to finish

            ```python
            @flow
            def my_flow():
                futures = my_task.map([1, 2, 3])
                futures.wait():
                # Now all of the mapped tasks have finished
                my_task(10)
            ```

            Use the result from mapped tasks in a flow

            ```python
            @flow
            def my_flow():
                futures = my_task.map([1, 2, 3])
                for x in futures.result():
                    print(x)
            my_flow()
            # 2
            # 3
            # 4
            ```

            Enforce ordering between tasks that do not exchange data

            ```python
            @task
            def task_1(x):
                pass

            @task
            def task_2(y):
                pass

            @flow
            def my_flow():
                x = task_1.submit()

                # task 2 will wait for task_1 to complete
                y = task_2.map([1, 2, 3], wait_for=[x])
                return y
            ```

            Use a non-iterable input as a constant across mapped tasks

            ```python
            @task
            def display(prefix, item):
               print(prefix, item)

            @flow
            def my_flow():
                return display.map("Check it out: ", [1, 2, 3])

            my_flow()
            # Check it out: 1
            # Check it out: 2
            # Check it out: 3
            ```

            Use `unmapped` to treat an iterable argument as a constant

            ```python
            from prefect import unmapped

            @task
            def add_n_to_items(items, n):
                return [item + n for item in items]

            @flow
            def my_flow():
                return add_n_to_items.map(unmapped([10, 20]), n=[1, 2, 3])

            my_flow()
            # [[11, 21], [12, 22], [13, 23]]
            ```
        """

        from prefect.task_runners import TaskRunner
        from prefect.utilities.visualization import (
            VisualizationUnsupportedError,
            get_task_viz_tracker,
        )

        # Convert the call args/kwargs to a parameter dict; do not apply defaults
        # since they should not be mapped over
        parameters = get_call_parameters(self.fn, args, kwargs, apply_defaults=False)
        flow_run_context = FlowRunContext.get()

        task_viz_tracker = get_task_viz_tracker()
        if task_viz_tracker:
            raise VisualizationUnsupportedError(
                "`task.map()` is not currently supported by `flow.visualize()`"
            )

        if deferred:
            parameters_list = expand_mapping_parameters(self.fn, parameters)
            futures = [
                self.apply_async(kwargs=parameters, wait_for=wait_for)
                for parameters in parameters_list
            ]
        elif task_runner := getattr(flow_run_context, "task_runner", None):
            assert isinstance(task_runner, TaskRunner)
            futures = task_runner.map(self, parameters, wait_for)
        else:
            raise RuntimeError(
                "Unable to determine task runner to use for mapped task runs. If"
                " you are mapping a task outside of a flow, please provide"
                " `deferred=True` to submit the mapped task runs for deferred"
                " execution."
            )
        if return_state:
            states: list[State[R]] = []
            for future in futures:
                future.wait()
                states.append(future.state)
            return states
        else:
            return futures

    # Background task methods

    def apply_async(
        self,
        args: Optional[tuple[Any, ...]] = None,
        kwargs: Optional[dict[str, Any]] = None,
        wait_for: Optional[Iterable[PrefectFuture[R]]] = None,
        dependencies: Optional[dict[str, set[RunInput]]] = None,
    ) -> PrefectDistributedFuture[R]:
        """
        Create a pending task run for a task worker to execute.

        Args:
            args: Arguments to run the task with
            kwargs: Keyword arguments to run the task with

        Returns:
            A PrefectDistributedFuture object representing the pending task run

        Examples:

            Define a task

            ```python
            from prefect import task
            @task
            def my_task(name: str = "world"):
                return f"hello {name}"
            ```

            Create a pending task run for the task

            ```python
            from prefect import flow
            @flow
            def my_flow():
                my_task.apply_async(("marvin",))
            ```

            Wait for a task to finish

            ```python
            @flow
            def my_flow():
                my_task.apply_async(("marvin",)).wait()
            ```

            ```python
            @flow
            def my_flow():
                print(my_task.apply_async(("marvin",)).result())

            my_flow()
            # hello marvin
            ```

            TODO: Enforce ordering between tasks that do not exchange data
            ```python
            @task
            def task_1():
                pass

            @task
            def task_2():
                pass

            @flow
            def my_flow():
                x = task_1.apply_async()

                # task 2 will wait for task_1 to complete
                y = task_2.apply_async(wait_for=[x])
            ```

        """
        from prefect.utilities.visualization import (
            VisualizationUnsupportedError,
            get_task_viz_tracker,
        )

        task_viz_tracker = get_task_viz_tracker()
        if task_viz_tracker:
            raise VisualizationUnsupportedError(
                "`task.apply_async()` is not currently supported by `flow.visualize()`"
            )
        args = args or ()
        kwargs = kwargs or {}

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        task_run: TaskRun = run_coro_as_sync(
            self.create_run(
                parameters=parameters,
                deferred=True,
                wait_for=wait_for,
                extra_task_inputs=dependencies,
            )
        )  # type: ignore

        from prefect.utilities.engine import emit_task_run_state_change_event

        # emit a `SCHEDULED` event for the task run
        emit_task_run_state_change_event(
            task_run=task_run,
            initial_state=None,
            validated_state=task_run.state,
        )

        if get_current_settings().ui_url and (task_run_url := url_for(task_run)):
            logger.info(
                f"Created task run {task_run.name!r}. View it in the UI at {task_run_url!r}"
            )

        return PrefectDistributedFuture(task_run_id=task_run.id)

    def delay(self, *args: P.args, **kwargs: P.kwargs) -> PrefectDistributedFuture[R]:
        """
        An alias for `apply_async` with simpler calling semantics.

        Avoids having to use explicit "args" and "kwargs" arguments. Arguments
        will pass through as-is to the task.

        Examples:

                Define a task

                ```python
                from prefect import task
                @task
                def my_task(name: str = "world"):
                    return f"hello {name}"
                ```

                Create a pending task run for the task

                ```python
                from prefect import flow
                @flow
                def my_flow():
                    my_task.delay("marvin")
                ```

                Wait for a task to finish

                ```python
                @flow
                def my_flow():
                    my_task.delay("marvin").wait()
                ```

                Use the result from a task in a flow

                ```python
                @flow
                def my_flow():
                    print(my_task.delay("marvin").result())

                my_flow()
                # hello marvin
                ```
        """
        return self.apply_async(args=args, kwargs=kwargs)

    @sync_compatible
    async def serve(self) -> NoReturn:
        """Serve the task using the provided task runner. This method is used to
        establish a websocket connection with the Prefect server and listen for
        submitted task runs to execute.

        Args:
            task_runner: The task runner to use for serving the task. If not provided,
                the default task runner will be used.

        Examples:
            Serve a task using the default task runner
            ```python
            @task
            def my_task():
                return 1

            my_task.serve()
            ```
        """
        from prefect.task_worker import serve

        await serve(self)


@overload
def task(__fn: Callable[P, R]) -> Task[P, R]: ...


# see https://github.com/PrefectHQ/prefect/issues/16380
@overload
def task(
    __fn: Literal[None] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    version: Optional[str] = None,
    cache_policy: Union[CachePolicy, type[NotSet]] = NotSet,
    cache_key_fn: Optional[
        Callable[["TaskRunContext", dict[str, Any]], Optional[str]]
    ] = None,
    cache_expiration: Optional[datetime.timedelta] = None,
    task_run_name: Optional[TaskRunNameValueOrCallable] = None,
    retries: int = 0,
    retry_delay_seconds: Union[
        float, int, list[float], Callable[[int], list[float]], None
    ] = None,
    retry_jitter_factor: Optional[float] = None,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_storage_key: Optional[str] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    timeout_seconds: Union[int, float, None] = None,
    log_prints: Optional[bool] = None,
    refresh_cache: Optional[bool] = None,
    on_completion: Optional[list[StateHookCallable]] = None,
    on_failure: Optional[list[StateHookCallable]] = None,
    retry_condition_fn: Optional[RetryConditionCallable] = None,
    viz_return_value: Any = None,
    asset_deps: Optional[list[Union[str, Asset]]] = None,
) -> Callable[[Callable[P, R]], Task[P, R]]: ...


# see https://github.com/PrefectHQ/prefect/issues/16380
@overload
def task(
    __fn: Literal[None] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    version: Optional[str] = None,
    cache_policy: Union[CachePolicy, type[NotSet]] = NotSet,
    cache_key_fn: Optional[
        Callable[["TaskRunContext", dict[str, Any]], Optional[str]]
    ] = None,
    cache_expiration: Optional[datetime.timedelta] = None,
    task_run_name: Optional[TaskRunNameValueOrCallable] = None,
    retries: int = 0,
    retry_delay_seconds: Union[
        float, int, list[float], Callable[[int], list[float]], None
    ] = None,
    retry_jitter_factor: Optional[float] = None,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_storage_key: Optional[str] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    timeout_seconds: Union[int, float, None] = None,
    log_prints: Optional[bool] = None,
    refresh_cache: Optional[bool] = None,
    on_completion: Optional[list[StateHookCallable]] = None,
    on_failure: Optional[list[StateHookCallable]] = None,
    retry_condition_fn: Optional[RetryConditionCallable] = None,
    viz_return_value: Any = None,
    asset_deps: Optional[list[Union[str, Asset]]] = None,
) -> Callable[[Callable[P, R]], Task[P, R]]: ...


@overload  # TODO: do we need this overload?
def task(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    version: Optional[str] = None,
    cache_policy: Union[CachePolicy, type[NotSet]] = NotSet,
    cache_key_fn: Optional[
        Callable[["TaskRunContext", dict[str, Any]], Optional[str]]
    ] = None,
    cache_expiration: Optional[datetime.timedelta] = None,
    task_run_name: Optional[TaskRunNameValueOrCallable] = None,
    retries: int = 0,
    retry_delay_seconds: Union[
        float,
        int,
        list[float],
        Callable[[int], list[float]],
    ] = 0,
    retry_jitter_factor: Optional[float] = None,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_storage_key: Optional[str] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    timeout_seconds: Union[int, float, None] = None,
    log_prints: Optional[bool] = None,
    refresh_cache: Optional[bool] = None,
    on_completion: Optional[list[StateHookCallable]] = None,
    on_failure: Optional[list[StateHookCallable]] = None,
    retry_condition_fn: Optional[RetryConditionCallable] = None,
    viz_return_value: Any = None,
    asset_deps: Optional[list[Union[str, Asset]]] = None,
) -> Callable[[Callable[P, R]], Task[P, R]]: ...


def task(
    __fn: Optional[Callable[P, R]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    version: Optional[str] = None,
    cache_policy: Union[CachePolicy, type[NotSet]] = NotSet,
    cache_key_fn: Union[
        Callable[["TaskRunContext", dict[str, Any]], Optional[str]], None
    ] = None,
    cache_expiration: Optional[datetime.timedelta] = None,
    task_run_name: Optional[TaskRunNameValueOrCallable] = None,
    retries: Optional[int] = None,
    retry_delay_seconds: Union[
        float, int, list[float], Callable[[int], list[float]], None
    ] = None,
    retry_jitter_factor: Optional[float] = None,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_storage_key: Optional[str] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    timeout_seconds: Union[int, float, None] = None,
    log_prints: Optional[bool] = None,
    refresh_cache: Optional[bool] = None,
    on_completion: Optional[list[StateHookCallable]] = None,
    on_failure: Optional[list[StateHookCallable]] = None,
    retry_condition_fn: Optional[RetryConditionCallable] = None,
    viz_return_value: Any = None,
    asset_deps: Optional[list[Union[str, Asset]]] = None,
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
        task_run_name: An optional name to distinguish runs of this task; this name can be provided
            as a string template with the task's keyword arguments as variables,
            or a function that returns a string.
        retries: An optional number of times to retry on task run failure
        retry_delay_seconds: Optionally configures how long to wait before retrying the
            task after failure. This is only applicable if `retries` is nonzero. This
            setting can either be a number of seconds, a list of retry delays, or a
            callable that, given the total number of retries, generates a list of retry
            delays. If a number of seconds, that delay will be applied to all retries.
            If a list, each retry will wait for the corresponding delay before retrying.
            When passing a callable or a list, the number of
            configured retry delays cannot exceed 50.
        retry_jitter_factor: An optional factor that defines the factor to which a
            retry can be jittered in order to avoid a "thundering herd".
        persist_result: A toggle indicating whether the result of this task
            should be persisted to result storage. Defaults to `None`, which
            indicates that the global default should be used (which is `True` by
            default).
        result_storage: An optional block to use to persist the result of this task.
            Defaults to the value set in the flow the task is called in.
        result_storage_key: An optional key to store the result in storage at when persisted.
            Defaults to a unique identifier.
        result_serializer: An optional serializer to use to serialize the result of this
            task for persistence. Defaults to the value set in the flow the task is
            called in.
        timeout_seconds: An optional number of seconds indicating a maximum runtime for
            the task. If the task exceeds this runtime, it will be marked as failed.
        log_prints: If set, `print` statements in the task will be redirected to the
            Prefect logger for the task run. Defaults to `None`, which indicates
            that the value from the flow should be used.
        refresh_cache: If set, cached results for the cache key are not used.
            Defaults to `None`, which indicates that a cached result from a previous
            execution with matching cache key is used.
        on_failure: An optional list of callables to run when the task enters a failed state.
        on_completion: An optional list of callables to run when the task enters a completed state.
        retry_condition_fn: An optional callable run when a task run returns a Failed state. Should
            return `True` if the task should continue to its retry policy (e.g. `retries=3`), and `False` if the task
            should end as failed. Defaults to `None`, indicating the task should always continue
            to its retry policy.
        viz_return_value: An optional value to return when the task dependency tree is visualized.
        asset_deps: An optional list of upstream assets that this task depends on.

    Returns:
        A callable `Task` object which, when called, will submit the task for execution.

    Examples:
        Define a simple task

        ```python
        @task
        def add(x, y):
            return x + y
        ```

        Define an async task

        ```python
        @task
        async def add(x, y):
            return x + y
        ```

        Define a task with tags and a description

        ```python
        @task(tags={"a", "b"}, description="This task is empty but its my first!")
        def my_task():
            pass
        ```

        Define a task with a custom name

        ```python
        @task(name="The Ultimate Task")
        def my_task():
            pass
        ```

        Define a task that retries 3 times with a 5 second delay between attempts

        ```python
        from random import randint

        @task(retries=3, retry_delay_seconds=5)
        def my_task():
            x = randint(0, 5)
            if x >= 3:  # Make a task that fails sometimes
                raise ValueError("Retry me please!")
            return x
        ```

        Define a task that is cached for a day based on its inputs

        ```python
        from prefect.tasks import task_input_hash
        from datetime import timedelta

        @task(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=1))
        def my_task():
            return "hello"
        ```
    """

    if __fn:
        return Task(
            fn=__fn,
            name=name,
            description=description,
            tags=tags,
            version=version,
            cache_policy=cache_policy,
            cache_key_fn=cache_key_fn,
            cache_expiration=cache_expiration,
            task_run_name=task_run_name,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            retry_jitter_factor=retry_jitter_factor,
            persist_result=persist_result,
            result_storage=result_storage,
            result_storage_key=result_storage_key,
            result_serializer=result_serializer,
            cache_result_in_memory=cache_result_in_memory,
            timeout_seconds=timeout_seconds,
            log_prints=log_prints,
            refresh_cache=refresh_cache,
            on_completion=on_completion,
            on_failure=on_failure,
            retry_condition_fn=retry_condition_fn,
            viz_return_value=viz_return_value,
            asset_deps=asset_deps,
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
                cache_policy=cache_policy,
                cache_key_fn=cache_key_fn,
                cache_expiration=cache_expiration,
                task_run_name=task_run_name,
                retries=retries,
                retry_delay_seconds=retry_delay_seconds,
                retry_jitter_factor=retry_jitter_factor,
                persist_result=persist_result,
                result_storage=result_storage,
                result_storage_key=result_storage_key,
                result_serializer=result_serializer,
                cache_result_in_memory=cache_result_in_memory,
                timeout_seconds=timeout_seconds,
                log_prints=log_prints,
                refresh_cache=refresh_cache,
                on_completion=on_completion,
                on_failure=on_failure,
                retry_condition_fn=retry_condition_fn,
                viz_return_value=viz_return_value,
                asset_deps=asset_deps,
            ),
        )


class MaterializingTask(Task[P, R]):
    """
    A task that materializes Assets.

    Args:
        assets: List of Assets that this task materializes (can be str or Asset)
        materialized_by: An optional tool that materialized the asset e.g. "dbt" or "spark"
        **task_kwargs: All other Task arguments
    """

    def __init__(
        self,
        fn: Callable[P, R],
        *,
        assets: Sequence[Union[str, Asset]],
        materialized_by: str | None = None,
        **task_kwargs: Unpack[TaskOptions],
    ):
        super().__init__(fn=fn, **task_kwargs)

        self.assets: list[Asset] = [
            Asset(key=a) if isinstance(a, str) else a for a in assets
        ]
        self.materialized_by = materialized_by

    def with_options(
        self,
        assets: Optional[Sequence[Union[str, Asset]]] = None,
        **task_kwargs: Unpack[TaskOptions],
    ) -> "MaterializingTask[P, R]":
        import inspect

        sig = inspect.signature(Task.__init__)

        # Map parameter names to attribute names where they differ
        # from parameter to attribute.
        param_to_attr = {
            "on_completion": "on_completion_hooks",
            "on_failure": "on_failure_hooks",
            "on_rollback": "on_rollback_hooks",
            "on_commit": "on_commit_hooks",
        }

        # Build kwargs for Task constructor
        init_kwargs = {}
        for param_name in sig.parameters:
            if param_name in ("self", "fn", "assets", "materialized_by"):
                continue

            attr_name = param_to_attr.get(param_name, param_name)
            init_kwargs[param_name] = task_kwargs.get(
                param_name, getattr(self, attr_name)
            )

        return MaterializingTask(
            fn=self.fn,
            assets=(
                [Asset(key=a) if isinstance(a, str) else a for a in assets]
                if assets is not None
                else self.assets
            ),
            materialized_by=self.materialized_by,
            # Now, the rest
            **init_kwargs,
        )
