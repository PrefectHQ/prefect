import inspect
import os
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Generic,
    Iterable,
    Optional,
    TypedDict,
    TypeVar,
    Union,
)

from pydantic import AfterValidator, BaseModel, Field, computed_field
from typing_extensions import NotRequired, ParamSpec, Self, TypeAlias, Unpack

from prefect.cache_policies import DEFAULT, NONE, CachePolicy
from prefect.results import ResultSerializer, ResultStorage
from prefect.utilities.annotations import NotSet
from prefect.utilities.hashing import hash_objects
from prefect.utilities.importtools import to_qualified_name

from .utilities import (
    evaluate_retry_delay_seconds,
    generate_task_description,
    generate_task_name,
    get_default_retries,
    get_default_retry_delay,
)

if TYPE_CHECKING:
    from prefect.client.schemas import TaskRun
    from prefect.context import TaskRunContext
    from prefect.states import State
    from prefect.transactions import Transaction

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


DelayPolicy: TypeAlias = Union[
    float,
    int,
    Annotated[list[float], Field(max_length=50)],
    Annotated[list[int], Field(max_length=50)],
    Callable[[int], list[float]],
]


class BaseTask(BaseModel, Generic[P, R]):
    fn: Callable[P, R] = Field(description="The function defining the task.")

    name: Annotated[Optional[str], AfterValidator(generate_task_name)] = Field(
        default=None,
        description="An optional name for the task; if not provided, the name will be inferred from the given function.",
        validate_default=True,
    )
    description: Annotated[
        Optional[str], AfterValidator(generate_task_description)
    ] = Field(
        default=None,
        validate_default=True,
        description="An optional string description for the task.",
    )
    tags: Annotated[
        Optional[Iterable[str] | set[str]],
        AfterValidator(lambda v: set(v) if v is not None else set()),
    ] = Field(
        default_factory=set,
        validate_default=True,
        description="An optional set of tags to be associated with runs of this task. These tags are combined with any tags defined by a `prefect.tags` context at task runtime.",
    )
    version: Optional[str] = Field(
        default=None,
        description="An optional string specifying the version of this task definition",
    )
    passed_cache_policy: Optional[Union["CachePolicy", type[NotSet]]] = Field(
        default=None,
        repr=False,
        exclude=True,
        alias="cache_policy",
        description="A cache policy that determines the level of caching for this task",
    )
    cache_key_fn: Optional[
        Callable[["TaskRunContext", dict[str, Any]], Optional[str]]
    ] = Field(
        default=None,
        description="An optional callable that, given the task run context and call parameters, generates a string key; if the key matches a previous completed state, that state result will be restored instead of running the task again.",
    )
    cache_expiration: Optional[timedelta] = Field(
        default=None,
        description="An optional amount of time indicating how long cached states for this task should be restorable; if not provided, cached states will never expire.",
    )

    cache_result_in_memory: Optional[bool] = Field(default=True)

    task_run_name: Optional[Union[Callable[[], str], str]] = Field(
        default=None,
        description="An optional name to distinguish runs of this task; this name can be provided as a string template with the task's keyword arguments as variables, or a function that returns a string.",
    )
    retries: Annotated[
        Optional[int],
        AfterValidator(lambda v: v if v is not None else get_default_retries()),
    ] = Field(
        default_factory=get_default_retries,
        description="An optional number of times to retry on task run failure.",
    )
    retry_delay_seconds: Annotated[
        Optional[DelayPolicy], AfterValidator(evaluate_retry_delay_seconds)
    ] = Field(
        default_factory=get_default_retry_delay,
        description="Optionally configures how long to wait before retrying the task after failure. This is only applicable if `retries` is nonzero. This setting can either be a number of seconds, a list of retry delays, or a callable that, given the total number of retries, generates a list of retry delays. If a number of seconds, that delay will be applied to all retries. If a list, each retry will wait for the corresponding delay before retrying. When passing a callable or a list, the number of configured retry delays cannot exceed 50.",
    )
    retry_jitter_factor: Annotated[
        Optional[float], AfterValidator(lambda v: v > 0 if v is not None else None)
    ] = Field(
        default=None,
        description="An optional factor that defines the factor to which a retry can be jittered in order to avoid a 'thundering herd'.",
    )
    passed_persist_result: Optional[bool] = Field(
        default=None,
        repr=False,
        exclude=True,
        alias="persist_result",
        description="A toggle indicating whether the result of this task should be persisted to result storage. Defaults to `None`, which indicates that the global default should be used (which is `True` by default).",
    )
    result_storage: Optional["ResultStorage"] = Field(
        default=None,
        description="An optional block to use to persist the result of this task. Defaults to the value set in the flow the task is called in.",
    )
    result_serializer: Optional["ResultSerializer"] = Field(
        default=None,
        description="An optional serializer to use to serialize the result of this task for persistence. Defaults to the value set in the flow the task is called in.",
    )
    result_storage_key: Optional[str] = Field(
        default=None,
        description="An optional key to store the result in storage at when persisted. Defaults to a unique identifier.",
    )
    timeout_seconds: Optional[float] = Field(
        default=None,
        strict=False,
        description="An optional number of seconds indicating a maximum runtime for the task. If the task exceeds this runtime, it will be marked as failed.",
    )
    log_prints: Optional[bool] = Field(
        default=None,
        description="If set, `print` statements in the task will be redirected to the Prefect logger for the task run. Defaults to `None`, which indicates that the value from the flow should be used.",
    )
    refresh_cache: Optional[bool] = Field(
        default=None,
        description="If set, cached results for the cache key are not used. Defaults to `None`, which indicates that a cached result from a previous execution with matching cache key is used.",
    )
    on_completion_hooks: Optional[
        list[Callable[["BaseTask[P,R]", "TaskRun", "State"], None]]
    ] = Field(
        default_factory=list,
        alias="on_completion",
        description="An optional list of callables to run when the task enters a completed state.",
    )
    on_failure_hooks: Optional[
        Optional[list[Callable[["BaseTask[P,R]", "TaskRun", "State"], None]]]
    ] = Field(
        default_factory=list,
        alias="on_failure",
        description="An optional list of callables to run when the task enters a failed state.",
    )
    on_rollback_hooks: Optional[list[Callable[["Transaction"], None]]] = Field(
        default_factory=list,
        alias="on_rollback",
        description="An optional list of callables to run when the task rolls back.",
    )
    on_commit_hooks: Optional[list[Callable[["Transaction"], None]]] = Field(
        default_factory=list,
        alias="on_commit",
        description="An optional list of callables to run when the task's idempotency record is committed.",
    )
    retry_condition_fn: Optional[
        Callable[["BaseTask[P,R]", "TaskRun", "State"], bool]
    ] = Field(
        default=None,
        description="An optional callable run when a task run returns a Failed state. Should return `True` if the task should continue to its retry policy (e.g. `retries=3`), and `False` if the task should end as failed. Defaults to `None`, indicating the task should always continue to its retry policy.",
    )
    viz_return_value: Optional[Any] = Field(
        default=None,
        description="An optional value to return when the task dependency tree is visualized.",
    )

    @computed_field
    @property
    def isasync(self) -> bool:
        return inspect.iscoroutinefunction(self.fn) or inspect.isasyncgenfunction(
            self.fn
        )

    @computed_field
    @property
    def isgenerator(self) -> bool:
        return inspect.isgeneratorfunction(self.fn) or inspect.isasyncgenfunction(
            self.fn
        )

    @computed_field
    @property
    def task_key(self) -> str:
        if __quaname__ := getattr(self.fn, "__qualname__", None):
            task_origin_hash = "unknown-source-file"
            try:
                if sourcefile := inspect.getsourcefile(self.fn):
                    task_origin_hash = hash_objects(
                        self.name, os.path.abspath(sourcefile)
                    )
            except TypeError:
                pass
            return f"{__quaname__}-{task_origin_hash}"
        else:
            return to_qualified_name(type(self.fn))

    @computed_field
    @property
    def persist_result(self) -> bool:
        if self.passed_persist_result is not None:
            return self.passed_persist_result
        return any(
            [
                self.passed_cache_policy not in (NONE, NotSet),
                self.cache_key_fn is not None,
                self.result_storage_key is not None,
                self.result_storage is not None,
                self.result_serializer is not None,
                self.passed_persist_result,
            ]
        )

    @persist_result.setter
    def persist_result(self, value: bool) -> None:
        self.passed_persist_result = value

    @computed_field
    @property
    def cache_policy(self) -> Optional[Union["CachePolicy", type[NotSet]]]:
        declared_cache_policy = self.passed_cache_policy not in (NONE, NotSet)

        if self.cache_key_fn:
            # If a cache_key_fn is passed, then the cache_policy is determined by the cache_key_fn
            # and the passed cache_policy is ignored.
            if declared_cache_policy:
                # issue warning that the cache_policy is being ignored
                pass
            return CachePolicy.from_cache_key_fn(self.cache_key_fn)

        if self.persist_result:
            # If persist_result is True, then

            if self.result_storage_key:
                # TODO: handle this situation with double storage
                return None
            elif not declared_cache_policy:
                return DEFAULT
            return self.passed_cache_policy
        else:
            if declared_cache_policy:
                # issue warning that the cache_policy is being ignored
                pass
            return NONE

    def on_completion(
        self, fn: Callable[["BaseTask[P,R]", "TaskRun", "State"], None]
    ) -> Callable[["BaseTask[P,R]", "TaskRun", "State"], None]:
        if self.on_completion_hooks is None:
            self.on_completion_hooks = [fn]
        else:
            self.on_completion_hooks.append(fn)
        return fn

    def on_failure(
        self, fn: Callable[["BaseTask[P,R]", "TaskRun", "State"], None]
    ) -> Callable[["BaseTask[P,R]", "TaskRun", "State"], None]:
        if self.on_failure_hooks is None:
            self.on_failure_hooks = [fn]
        else:
            self.on_failure_hooks.append(fn)
        return fn

    def on_commit(
        self, fn: Callable[["Transaction"], None]
    ) -> Callable[["Transaction"], None]:
        if self.on_commit_hooks is None:
            self.on_commit_hooks = [fn]
        else:
            self.on_commit_hooks.append(fn)
        return fn

    def on_rollback(
        self, fn: Callable[["Transaction"], None]
    ) -> Callable[["Transaction"], None]:
        if self.on_rollback_hooks is None:
            self.on_rollback_hooks = [fn]
        else:
            self.on_rollback_hooks.append(fn)
        return fn

    def with_options(
        self: Self,
        fn: Optional[Callable[P, R]] = None,
        **kwargs: Unpack["BaseTaskConfig[P, R]"],
    ) -> Self:
        """
        Returns a new task with the provided options.

        Args:
            **kwargs: The options to set on the new task.

        Returns:
            Task: A new task with the provided options.
        """
        return self.model_validate({"fn": fn} | self.model_dump() | kwargs)


class BaseTaskConfig(TypedDict, Generic[P, R]):
    name: NotRequired[str]
    description: NotRequired[str]
    tags: NotRequired[Iterable[str] | set[str]]
    version: NotRequired[str]
    cache_policy: NotRequired[Union[CachePolicy, type[NotSet]]]
    cache_key_fn: NotRequired[
        Callable[["TaskRunContext", dict[str, Any]], NotRequired[str]]
    ]
    cache_expiration: NotRequired[timedelta]
    task_run_name: NotRequired[Union[Callable[[], str], str]]
    retries: NotRequired[int]
    retry_delay_seconds: NotRequired[DelayPolicy]
    retry_jitter_factor: NotRequired[float]
    persist_result: NotRequired[bool]
    result_storage: NotRequired[ResultStorage]
    result_serializer: NotRequired[ResultSerializer]
    result_storage_key: NotRequired[str]
    timeout_seconds: NotRequired[float]
    log_prints: NotRequired[bool]
    refresh_cache: NotRequired[bool]
    on_completion: NotRequired[Callable[[BaseTask[P, R], "TaskRun", "State"], None]]
    on_failure: NotRequired[Callable[[BaseTask[P, R], "TaskRun", "State"], None]]
    on_rollback: NotRequired[list[Callable[["Transaction"], None]]]
    on_commit: NotRequired[list[Callable[["Transaction"], None]]]
    retry_condition_fn: NotRequired[
        Callable[[BaseTask[P, R], "TaskRun", "State"], bool]
    ]
    viz_return_value: NotRequired[Any]
