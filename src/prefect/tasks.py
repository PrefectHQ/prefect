"""
Module containing the base workflow task class and decorator - for most use cases, using the [`@task` decorator][prefect.tasks.task] is preferred.
"""
# This file requires type-checking with pyright because mypy does not yet support PEP612
# See https://github.com/python/mypy/issues/8645

import datetime
import inspect
import os
from copy import copy
from functools import partial, update_wrapper
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    NoReturn,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID, uuid4

from typing_extensions import Literal, ParamSpec

from prefect.client.orchestration import get_client
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import TaskRunInput, TaskRunResult
from prefect.context import (
    FlowRunContext,
    PrefectObjectRegistry,
    TagsContext,
    TaskRunContext,
    serialize_context,
)
from prefect.futures import PrefectDistributedFuture, PrefectFuture
from prefect.logging.loggers import get_logger
from prefect.records.cache_policies import DEFAULT, CachePolicy
from prefect.results import ResultFactory, ResultSerializer, ResultStorage
from prefect.settings import (
    PREFECT_TASK_DEFAULT_RETRIES,
    PREFECT_TASK_DEFAULT_RETRY_DELAY_SECONDS,
)
from prefect.states import Pending, Scheduled, State
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.callables import (
    expand_mapping_parameters,
    get_call_parameters,
    raise_for_reserved_arguments,
)
from prefect.utilities.hashing import hash_objects
from prefect.utilities.importtools import to_qualified_name

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.context import TaskRunContext
    from prefect.transactions import Transaction

T = TypeVar("T")  # Generic type var for capturing the inner return type of async funcs
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the task

NUM_CHARS_DYNAMIC_KEY = 8

logger = get_logger("tasks")


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
        persist_result: An optional toggle indicating whether the result of this task
            should be persisted to result storage. Defaults to `None`, which indicates
            that Prefect should choose whether the result should be persisted depending on
            the features being used.
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
    """

    # NOTE: These parameters (types, defaults, and docstrings) should be duplicated
    #       exactly in the @task decorator
    def __init__(
        self,
        fn: Callable[P, R],
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        version: Optional[str] = None,
        cache_policy: Optional[CachePolicy] = NotSet,
        cache_key_fn: Optional[
            Callable[["TaskRunContext", Dict[str, Any]], Optional[str]]
        ] = None,
        cache_expiration: Optional[datetime.timedelta] = None,
        task_run_name: Optional[Union[Callable[[], str], str]] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[
            Union[
                float,
                int,
                List[float],
                Callable[[int], List[float]],
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
        on_completion: Optional[List[Callable[["Task", TaskRun, State], None]]] = None,
        on_failure: Optional[List[Callable[["Task", TaskRun, State], None]]] = None,
        on_rollback: Optional[List[Callable[["Transaction"], None]]] = None,
        on_commit: Optional[List[Callable[["Transaction"], None]]] = None,
        retry_condition_fn: Optional[Callable[["Task", TaskRun, State], bool]] = None,
        viz_return_value: Optional[Any] = None,
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

        self.tags = set(tags if tags else [])

        if not hasattr(self.fn, "__qualname__"):
            self.task_key = to_qualified_name(type(self.fn))
        else:
            try:
                task_origin_hash = hash_objects(
                    self.name, os.path.abspath(inspect.getsourcefile(self.fn))
                )
            except TypeError:
                task_origin_hash = "unknown-source-file"

            self.task_key = f"{self.fn.__qualname__}-{task_origin_hash}"

        # TODO: warn of precedence of cache policies and cache key fn if both provided?
        if cache_key_fn:
            cache_policy = CachePolicy.from_cache_key_fn(cache_key_fn)

        # TODO: manage expiration and cache refresh
        self.cache_key_fn = cache_key_fn
        self.cache_expiration = cache_expiration
        self.refresh_cache = refresh_cache

        if cache_policy is NotSet and result_storage_key is None:
            self.cache_policy = DEFAULT
        elif result_storage_key:
            # TODO: handle this situation with double storage
            self.cache_policy = None
        else:
            self.cache_policy = cache_policy

        # TaskRunPolicy settings
        # TODO: We can instantiate a `TaskRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here

        self.retries = (
            retries if retries is not None else PREFECT_TASK_DEFAULT_RETRIES.value()
        )
        if retry_delay_seconds is None:
            retry_delay_seconds = PREFECT_TASK_DEFAULT_RETRY_DELAY_SECONDS.value()

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
        self.result_storage_key = result_storage_key
        self.cache_result_in_memory = cache_result_in_memory
        self.timeout_seconds = float(timeout_seconds) if timeout_seconds else None
        self.on_rollback_hooks = on_rollback or []
        self.on_commit_hooks = on_commit or []
        self.on_completion_hooks = on_completion or []
        self.on_failure_hooks = on_failure or []

        # retry_condition_fn must be a callable or None. If it is neither, raise a TypeError
        if retry_condition_fn is not None and not (callable(retry_condition_fn)):
            raise TypeError(
                "Expected `retry_condition_fn` to be callable, got"
                f" {type(retry_condition_fn).__name__} instead."
            )

        self.retry_condition_fn = retry_condition_fn
        self.viz_return_value = viz_return_value

    def with_options(
        self,
        *,
        name: str = None,
        description: str = None,
        tags: Iterable[str] = None,
        cache_policy: CachePolicy = NotSet,
        cache_key_fn: Callable[
            ["TaskRunContext", Dict[str, Any]], Optional[str]
        ] = None,
        task_run_name: Optional[Union[Callable[[], str], str]] = None,
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
        result_storage_key: Optional[str] = NotSet,
        cache_result_in_memory: Optional[bool] = None,
        timeout_seconds: Union[int, float] = None,
        log_prints: Optional[bool] = NotSet,
        refresh_cache: Optional[bool] = NotSet,
        on_completion: Optional[
            List[Callable[["Task", TaskRun, State], Union[Awaitable[None], None]]]
        ] = None,
        on_failure: Optional[
            List[Callable[["Task", TaskRun, State], Union[Awaitable[None], None]]]
        ] = None,
        retry_condition_fn: Optional[Callable[["Task", TaskRun, State], bool]] = None,
        viz_return_value: Optional[Any] = None,
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
            cache_policy=cache_policy
            if cache_policy is not NotSet
            else self.cache_policy,
            cache_key_fn=cache_key_fn or self.cache_key_fn,
            cache_expiration=cache_expiration or self.cache_expiration,
            task_run_name=task_run_name,
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
        )

    def on_completion(
        self, fn: Callable[["Task", TaskRun, State], None]
    ) -> Callable[["Task", TaskRun, State], None]:
        self.on_completion_hooks.append(fn)
        return fn

    def on_failure(
        self, fn: Callable[["Task", TaskRun, State], None]
    ) -> Callable[["Task", TaskRun, State], None]:
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
        parameters: Optional[Dict[str, Any]] = None,
        flow_run_context: Optional[FlowRunContext] = None,
        parent_task_run_context: Optional[TaskRunContext] = None,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        extra_task_inputs: Optional[Dict[str, Set[TaskRunInput]]] = None,
        deferred: bool = False,
    ) -> TaskRun:
        from prefect.utilities.engine import (
            _dynamic_key_for_task_run,
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
                task_run_name = f"{self.name}-{dynamic_key[:NUM_CHARS_DYNAMIC_KEY]}"
            else:
                dynamic_key = _dynamic_key_for_task_run(
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
                parameters_id = uuid4()
                state.state_details.task_parameters_id = parameters_id

                # TODO: Improve use of result storage for parameter storage / reference
                self.persist_result = True

                factory = await ResultFactory.from_autonomous_task(self, client=client)
                context = serialize_context()
                data: Dict[str, Any] = {"context": context}
                if parameters:
                    data["parameters"] = parameters
                if wait_for:
                    data["wait_for"] = wait_for
                await factory.store_parameters(parameters_id, data)

            # collect task inputs
            task_inputs = {
                k: collect_task_run_inputs_sync(v) for k, v in parameters.items()
            }

            # check if this task has a parent task run based on running in another
            # task run's existing context. A task run is only considered a parent if
            # it is in the same flow run (because otherwise presumably the child is
            # in a subflow, so the subflow serves as the parent) or if there is no
            # flow run
            if parent_task_run_context:
                # there is no flow run
                if not flow_run_context:
                    task_inputs["__parents__"] = [
                        TaskRunResult(id=parent_task_run_context.task_run.id)
                    ]
                # there is a flow run and the task run is in the same flow run
                elif (
                    flow_run_context
                    and parent_task_run_context.task_run.flow_run_id
                    == getattr(flow_run_context.flow_run, "id", None)
                ):
                    task_inputs["__parents__"] = [
                        TaskRunResult(id=parent_task_run_context.task_run.id)
                    ]

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
        self: "Task[P, NoReturn]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> PrefectFuture:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def submit(
        self: "Task[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> PrefectFuture:
        ...

    @overload
    def submit(
        self: "Task[P, T]",
        return_state: Literal[True],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> State[T]:
        ...

    def submit(
        self,
        *args: Any,
        return_state: bool = False,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        **kwargs: Any,
    ):
        """
        Submit a run of the task to the engine.

        Will create a new task run in the backing API and submit the task to the flow's
        task runner. This call only blocks execution while the task is being submitted,
        once it is submitted, the flow function will continue executing.

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
        self: "Task[P, NoReturn]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> List[PrefectFuture]:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def map(
        self: "Task[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> List[PrefectFuture]:
        ...

    @overload
    def map(
        self: "Task[P, T]",
        return_state: Literal[True],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> List[State[T]]:
        ...

    def map(
        self,
        *args: Any,
        return_state: bool = False,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        deferred: bool = False,
        **kwargs: Any,
    ):
        """
        Submit a mapped run of the task to a worker.

        Must be called within a flow function. If writing an async task, this
        call must be awaited.

        Must be called with at least one iterable and all iterables must be
        the same length. Any arguments that are not iterable will be treated as
        a static value and each task run will receive the same value.

        Will create as many task runs as the length of the iterable(s) in the
        backing API and submit the task runs to the flow's task runner. This
        call blocks if given a future as input while the future is resolved. It
        also blocks while the tasks are being submitted, once they are
        submitted, the flow function will continue executing.

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
            states = []
            for future in futures:
                future.wait()
                states.append(future.state)
            return states
        else:
            return futures

    def apply_async(
        self,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> PrefectDistributedFuture:
        """
        Create a pending task run for a task worker to execute.

        Args:
            args: Arguments to run the task with
            kwargs: Keyword arguments to run the task with

        Returns:
            A PrefectDistributedFuture object representing the pending task run

        Examples:

            Define a task

            >>> from prefect import task
            >>> @task
            >>> def my_task(name: str = "world"):
            >>>     return f"hello {name}"

            Create a pending task run for the task

            >>> from prefect import flow
            >>> @flow
            >>> def my_flow():
            >>>     my_task.apply_async(("marvin",))

            Wait for a task to finish

            >>> @flow
            >>> def my_flow():
            >>>     my_task.apply_async(("marvin",)).wait()


            >>> @flow
            >>> def my_flow():
            >>>     print(my_task.apply_async(("marvin",)).result())
            >>>
            >>> my_flow()
            hello marvin

            TODO: Enforce ordering between tasks that do not exchange data
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
            >>>     x = task_1.apply_async()
            >>>
            >>>     # task 2 will wait for task_1 to complete
            >>>     y = task_2.apply_async(wait_for=[x])

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

        task_run = run_coro_as_sync(
            self.create_run(
                parameters=parameters,
                deferred=True,
                wait_for=wait_for,
                extra_task_inputs=dependencies,
            )
        )
        return PrefectDistributedFuture(task_run_id=task_run.id)

    def delay(self, *args: P.args, **kwargs: P.kwargs) -> PrefectDistributedFuture:
        """
        An alias for `apply_async` with simpler calling semantics.

        Avoids having to use explicit "args" and "kwargs" arguments. Arguments
        will pass through as-is to the task.

        Examples:

                Define a task

                >>> from prefect import task
                >>> @task
                >>> def my_task(name: str = "world"):
                >>>     return f"hello {name}"

                Create a pending task run for the task

                >>> from prefect import flow
                >>> @flow
                >>> def my_flow():
                >>>     my_task.delay("marvin")

                Wait for a task to finish

                >>> @flow
                >>> def my_flow():
                >>>     my_task.delay("marvin").wait()

                Use the result from a task in a flow

                >>> @flow
                >>> def my_flow():
                >>>     print(my_task.delay("marvin").result())
                >>>
                >>> my_flow()
                hello marvin
        """
        return self.apply_async(args=args, kwargs=kwargs)

    def serve(self) -> "Task":
        """Serve the task using the provided task runner. This method is used to
        establish a websocket connection with the Prefect server and listen for
        submitted task runs to execute.

        Args:
            task_runner: The task runner to use for serving the task. If not provided,
                the default ConcurrentTaskRunner will be used.

        Examples:
            Serve a task using the default task runner
            >>> @task
            >>> def my_task():
            >>>     return 1

            >>> my_task.serve()
        """
        from prefect.task_worker import serve

        serve(self)


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
    cache_policy: CachePolicy = NotSet,
    cache_key_fn: Callable[["TaskRunContext", Dict[str, Any]], Optional[str]] = None,
    cache_expiration: datetime.timedelta = None,
    task_run_name: Optional[Union[Callable[[], str], str]] = None,
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
    result_storage_key: Optional[str] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    timeout_seconds: Union[int, float] = None,
    log_prints: Optional[bool] = None,
    refresh_cache: Optional[bool] = None,
    on_completion: Optional[List[Callable[["Task", TaskRun, State], None]]] = None,
    on_failure: Optional[List[Callable[["Task", TaskRun, State], None]]] = None,
    retry_condition_fn: Optional[Callable[["Task", TaskRun, State], bool]] = None,
    viz_return_value: Any = None,
) -> Callable[[Callable[P, R]], Task[P, R]]:
    ...


def task(
    __fn=None,
    *,
    name: str = None,
    description: str = None,
    tags: Iterable[str] = None,
    version: str = None,
    cache_policy: CachePolicy = NotSet,
    cache_key_fn: Callable[["TaskRunContext", Dict[str, Any]], Optional[str]] = None,
    cache_expiration: datetime.timedelta = None,
    task_run_name: Optional[Union[Callable[[], str], str]] = None,
    retries: int = None,
    retry_delay_seconds: Union[
        float,
        int,
        List[float],
        Callable[[int], List[float]],
    ] = None,
    retry_jitter_factor: Optional[float] = None,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_storage_key: Optional[str] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    timeout_seconds: Union[int, float] = None,
    log_prints: Optional[bool] = None,
    refresh_cache: Optional[bool] = None,
    on_completion: Optional[List[Callable[["Task", TaskRun, State], None]]] = None,
    on_failure: Optional[List[Callable[["Task", TaskRun, State], None]]] = None,
    retry_condition_fn: Optional[Callable[["Task", TaskRun, State], bool]] = None,
    viz_return_value: Any = None,
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
            ),
        )
