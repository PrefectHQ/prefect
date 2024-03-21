r"""
Async and thread safe models for passing runtime context data.

These contexts should never be directly mutated by the user.

For more user-accessible information about the current run, see [`prefect.runtime`](../runtime/flow_run).
"""
import json
import os
import sys
import warnings
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar, Token
from functools import update_wrapper
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    ContextManager,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID

import anyio.abc
import pendulum

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field, PrivateAttr
else:
    from pydantic import BaseModel, Field, PrivateAttr

import prefect.logging
import prefect.logging.configuration
import prefect.settings
from prefect._internal.schemas.fields import DateTimeTZ
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import FlowRun, TaskRun
from prefect.events.worker import EventsWorker
from prefect.exceptions import MissingContextError
from prefect.futures import PrefectFuture
from prefect.results import ResultFactory
from prefect.settings import PREFECT_HOME, Profile, Settings
from prefect.states import State
from prefect.task_runners import BaseTaskRunner
from prefect.utilities.importtools import load_script_as_module

if TYPE_CHECKING:
    from prefect.tasks import Task as TaskObject
from prefect.client.schemas import (
    OrchestrationResult,
    SetStateStatus,
    StateAcceptDetails,
)
from prefect.client.schemas.objects import (
    Constant,
    Flow,
    Parameter,
    TaskRunPolicy,
    TaskRunResult,
)

T = TypeVar("T")

if TYPE_CHECKING:
    from prefect.flows import Flow
    from prefect.tasks import Task

# Define the global settings context variable
# This will be populated downstream but must be null here to facilitate loading the
# default settings.
GLOBAL_SETTINGS_CONTEXT = None


class ContextModel(BaseModel):
    """
    A base model for context data that forbids mutation and extra data while providing
    a context manager
    """

    # The context variable for storing data must be defined by the child class
    __var__: ContextVar
    _token: Token = PrivateAttr(None)

    class Config:
        allow_mutation = False
        arbitrary_types_allowed = True
        extra = "forbid"

    def __enter__(self):
        if self._token is not None:
            raise RuntimeError(
                "Context already entered. Context enter calls cannot be nested."
            )
        self._token = self.__var__.set(self)
        return self

    def __exit__(self, *_):
        if not self._token:
            raise RuntimeError(
                "Asymmetric use of context. Context exit called without an enter."
            )
        self.__var__.reset(self._token)
        self._token = None

    @classmethod
    def get(cls: Type[T]) -> Optional[T]:
        return cls.__var__.get(None)

    def copy(self, **kwargs):
        """
        Duplicate the context model, optionally choosing which fields to include, exclude, or change.

        Attributes:
            include: Fields to include in new model.
            exclude: Fields to exclude from new model, as with values this takes precedence over include.
            update: Values to change/add in the new model. Note: the data is not validated before creating
                the new model - you should trust this data.
            deep: Set to `True` to make a deep copy of the model.

        Returns:
            A new model instance.
        """
        # Remove the token on copy to avoid re-entrance errors
        new = super().copy(**kwargs)
        new._token = None
        return new


class PrefectObjectRegistry(ContextModel):
    """
    A context that acts as a registry for all Prefect objects that are
    registered during load and execution.

    Attributes:
        start_time: The time the object registry was created.
        block_code_execution: If set, flow calls will be ignored.
        capture_failures: If set, failures during __init__ will be silenced and tracked.
    """

    start_time: DateTimeTZ = Field(default_factory=lambda: pendulum.now("UTC"))

    _instance_registry: Dict[Type[T], List[T]] = PrivateAttr(
        default_factory=lambda: defaultdict(list)
    )

    # Failures will be a tuple of (exception, instance, args, kwargs)
    _instance_init_failures: Dict[
        Type[T], List[Tuple[Exception, T, Tuple, Dict]]
    ] = PrivateAttr(default_factory=lambda: defaultdict(list))

    block_code_execution: bool = False
    capture_failures: bool = False

    __var__ = ContextVar("object_registry")

    def get_instances(self, type_: Type[T]) -> List[T]:
        instances = []
        for registered_type, type_instances in self._instance_registry.items():
            if type_ in registered_type.mro():
                instances.extend(type_instances)
        return instances

    def get_instance_failures(
        self, type_: Type[T]
    ) -> List[Tuple[Exception, T, Tuple, Dict]]:
        failures = []
        for type__ in type_.mro():
            failures.extend(self._instance_init_failures[type__])
        return failures

    def register_instance(self, object):
        # TODO: Consider using a 'Set' to avoid duplicate entries
        self._instance_registry[type(object)].append(object)

    def register_init_failure(
        self, exc: Exception, object: Any, init_args: Tuple, init_kwargs: Dict
    ):
        self._instance_init_failures[type(object)].append(
            (exc, object, init_args, init_kwargs)
        )

    @classmethod
    def register_instances(cls, type_: Type[T]) -> Type[T]:
        """
        Decorator for a class that adds registration to the `PrefectObjectRegistry`
        on initialization of instances.
        """
        original_init = type_.__init__

        def __register_init__(__self__: T, *args: Any, **kwargs: Any) -> None:
            registry = cls.get()
            try:
                original_init(__self__, *args, **kwargs)
            except Exception as exc:
                if not registry or not registry.capture_failures:
                    raise
                else:
                    registry.register_init_failure(exc, __self__, args, kwargs)
            else:
                if registry:
                    registry.register_instance(__self__)

        update_wrapper(__register_init__, original_init)

        type_.__init__ = __register_init__
        return type_


class RunContext(ContextModel):
    """
    The base context for a flow or task run. Data in this context will always be
    available when `get_run_context` is called.

    Attributes:
        start_time: The time the run context was entered
        client: The Prefect client instance being used for API communication
    """

    start_time: DateTimeTZ = Field(default_factory=lambda: pendulum.now("UTC"))
    input_keyset: Optional[Dict[str, Dict[str, str]]] = None
    client: PrefectClient


class EngineContext(RunContext):
    """
    The context for a flow run. Data in this context is only available from within a
    flow run function.

    Attributes:
        flow: The flow instance associated with the run
        flow_run: The API metadata for the flow run
        task_runner: The task runner instance being used for the flow run
        task_run_futures: A list of futures for task runs submitted within this flow run
        task_run_states: A list of states for task runs created within this flow run
        task_run_results: A mapping of result ids to task run states for this flow run
        flow_run_states: A list of states for flow runs created within this flow run
        sync_portal: A blocking portal for sync task/flow runs in an async flow
        timeout_scope: The cancellation scope for flow level timeouts
    """

    flow: Optional["Flow"] = None
    flow_run: Optional[FlowRun] = None
    autonomous_task_run: Optional[TaskRun] = None
    task_runner: BaseTaskRunner
    log_prints: bool = False
    parameters: Optional[Dict[str, Any]] = None

    # Result handling
    result_factory: ResultFactory

    # Counter for task calls allowing unique
    task_run_dynamic_keys: Dict[str, int] = Field(default_factory=dict)

    # Counter for flow pauses
    observed_flow_pauses: Dict[str, int] = Field(default_factory=dict)

    # Tracking for objects created by this flow run
    task_run_futures: List[PrefectFuture] = Field(default_factory=list)
    task_run_states: List[State] = Field(default_factory=list)
    task_run_results: Dict[int, State] = Field(default_factory=dict)
    flow_run_states: List[State] = Field(default_factory=list)

    # The synchronous portal is only created for async flows for creating engine calls
    # from synchronous task and subflow calls
    sync_portal: Optional[anyio.abc.BlockingPortal] = None
    timeout_scope: Optional[anyio.abc.CancelScope] = None

    # Task group that can be used for background tasks during the flow run
    background_tasks: anyio.abc.TaskGroup

    # Events worker to emit events to Prefect Cloud
    events: Optional[EventsWorker] = None

    # Storage for client side orchestration
    task_run_file_directory: str | None = None

    def get_file_path_for_task_run(self, task_run_id: UUID) -> str:
        return f"{self.task_run_file_directory}/task-run-{task_run_id}.json"

    def get_file_path_for_task_run_state(self, task_run_state_id: UUID) -> str:
        return f"{self.task_run_file_directory}/task-run-state-{task_run_state_id}.json"

    def write_task_run_data(self, task_run: TaskRun) -> None:
        # Write data to file instead
        file_path = self.get_file_path_for_task_run(task_run_id=task_run.id)
        with open(file_path, "w") as f:
            import json

            f.write(json.dumps(task_run.dict(json_compatible=True)))

        # print(f"Created or updated task run {task_run.id} and wrote to {file_path} ...")

    def write_task_run_state_data(self, task_run_state: State) -> None:
        # Write data to file instead
        file_path = self.get_file_path_for_task_run_state(
            task_run_state_id=task_run_state.id
        )
        with open(file_path, "w") as f:
            import json

            f.write(json.dumps(task_run_state.dict(json_compatible=True)))

        # print(f"Created task run state {task_run_state.id} and wrote to {file_path} ...")

    async def read_task_run_state(self, task_run_state_id: UUID) -> State:
        with open(
            self.get_file_path_for_task_run_state(task_run_state_id=task_run_state_id)
        ) as f:
            contents = json.load(f)

        state = State(**contents)
        return state

    async def read_task_run(self, task_run_id: UUID) -> TaskRun:
        with open(self.get_file_path_for_task_run(task_run_id=task_run_id)) as f:
            contents = json.load(f)

        task_run = TaskRun(**contents)
        if task_run.state_id is not None:
            task_run.state = await self.read_task_run_state(
                task_run_state_id=task_run.state_id
            )

        return task_run

    async def create_task_run(
        self,
        task: "TaskObject",
        flow_run_id: Optional[UUID],
        dynamic_key: str,
        name: str = None,
        extra_tags: Iterable[str] = None,
        state: prefect.states.State = None,
        task_inputs: Dict[
            str,
            List[
                Union[
                    TaskRunResult,
                    Parameter,
                    Constant,
                ]
            ],
        ] = None,
    ) -> TaskRun:
        """
        Create a task run

        Args:
            task: The Task to run
            flow_run_id: The flow run id with which to associate the task run
            dynamic_key: A key unique to this particular run of a Task within the flow
            name: An optional name for the task run
            extra_tags: an optional list of extra tags to apply to the task run in
                addition to `task.tags`
            state: The initial state for the run. If not provided, defaults to
                `Pending` for now. Should always be a `Scheduled` type.
            task_inputs: the set of inputs passed to the task

        Returns:
            The created task run.
        """
        tags = set(task.tags).union(extra_tags or [])

        if state is None:
            state = prefect.states.Pending()

        def generate_stable_uuid(input_uuid, input_string, input_integer):
            import uuid

            # Concatenate your inputs into a single string. Ensure the integer is converted to string
            name = f"{input_string}-{str(input_integer)}"
            # Generate a stable UUID based on the SHA-1 hash of the namespace and name
            stable_uuid = uuid.uuid5(input_uuid, name)
            return stable_uuid

        task_run_id = generate_stable_uuid(
            input_uuid=flow_run_id,
            input_string=task.task_key,
            input_integer=dynamic_key,
        )
        task_run_data = TaskRun(
            id=task_run_id,
            created=pendulum.now("UTC"),
            updated=pendulum.now("UTC"),
            name=name,
            flow_run_id=flow_run_id,
            task_key=task.task_key,
            dynamic_key=dynamic_key,
            tags=list(tags),
            task_version=task.version,
            expected_start_time=pendulum.now("UTC"),
            empirical_policy=TaskRunPolicy(
                retries=task.retries,
                retry_delay=task.retry_delay_seconds,
                retry_jitter_factor=task.retry_jitter_factor,
            ),
            # state=state.to_state_create(),
            task_inputs=task_inputs or {},
        )

        # Write data to file instead
        self.write_task_run_data(task_run=task_run_data)

        # Set the task runs state
        await self.set_task_run_state(task_run_id=task_run_id, state=state)

        # Read the updated task run and return
        return await self.read_task_run(task_run_id=task_run_id)

    async def set_task_run_state(
        self,
        task_run_id: UUID,
        state: State,
        force: bool = False,
    ) -> OrchestrationResult:
        """
        Set the state of a task run.

        Args:
            task_run_id: the id of the task run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Prefect API to accept the state

        Returns:
            an OrchestrationResult model representation of state orchestration output
        """
        # print(f"Setting state for task run {task_run_id} to {state.name} ...")

        # TODO - handle the `data` associated with a state
        state.data = None

        # Mock orchestration rules for task runs
        # This needs to match prefect.server.orchestration.global_policy.GlobalTaskPolicy
        # and prefect.server.orchestration.core_policy.CorePolicy
        # TODO - only minimum tracking rules are implemented so far and we should
        # handle exception cases similar to server side
        task_run = await self.read_task_run(task_run_id=task_run_id)
        if not task_run:
            raise Exception(f"Could not find task run {task_run_id}")

        # Implements the following
        # def COMMON_GLOBAL_TRANSFORMS():
        #     return [
        #         SetRunStateType,
        #         SetRunStateName,
        #         SetRunStateTimestamp,
        #         SetStartTime,
        #         SetEndTime,
        #         IncrementRunTime, (not implemented)
        #         SetExpectedStartTime, (not implemented)
        #         SetNextScheduledStartTime, (not implemented)
        #         UpdateStateDetails,
        #     ]
        task_run.state_type = state.type
        task_run.state_name = state.name
        if state.is_running() and task_run.start_time is None:
            task_run.start_time = state.timestamp

        if state.is_final():
            task_run.end_time = state.timestamp

        state.state_details.flow_run_id = task_run.flow_run_id
        state.state_details.task_run_id = task_run.id

        # This is effectively the "COMMIT" of the transaction
        state.task_run_id = state.id
        task_run.state_id = state.id

        # Write the new task run state
        self.write_task_run_state_data(task_run_state=state)

        # Write the updated task run
        self.write_task_run_data(task_run=task_run)

        # Return orchestration result
        # TODO - handle abort / wait
        return OrchestrationResult(
            state=state,
            status=SetStateStatus.ACCEPT,
            details=StateAcceptDetails(),
        )

    async def set_task_run_name(self, task_run_id: UUID, task_run_name: str) -> None:
        task_run = await self.read_task_run(task_run_id=task_run_id)
        task_run.name = task_run_name
        self.write_task_run_data(task_run=task_run)

    __var__ = ContextVar("flow_run")


FlowRunContext = EngineContext  # for backwards compatibility


class TaskRunContext(RunContext):
    """
    The context for a task run. Data in this context is only available from within a
    task run function.

    Attributes:
        task: The task instance associated with the task run
        task_run: The API metadata for this task run
    """

    task: "Task"
    task_run: TaskRun
    log_prints: bool = False
    parameters: Dict[str, Any]

    # Result handling
    result_factory: ResultFactory

    __var__ = ContextVar("task_run")


class TagsContext(ContextModel):
    """
    The context for `prefect.tags` management.

    Attributes:
        current_tags: A set of current tags in the context
    """

    current_tags: Set[str] = Field(default_factory=set)

    @classmethod
    def get(cls) -> "TagsContext":
        # Return an empty `TagsContext` instead of `None` if no context exists
        return cls.__var__.get(TagsContext())

    __var__ = ContextVar("tags")


class SettingsContext(ContextModel):
    """
    The context for a Prefect settings.

    This allows for safe concurrent access and modification of settings.

    Attributes:
        profile: The profile that is in use.
        settings: The complete settings model.
    """

    profile: Profile
    settings: Settings

    __var__ = ContextVar("settings")

    def __hash__(self) -> int:
        return hash(self.settings)

    def __enter__(self):
        """
        Upon entrance, we ensure the home directory for the profile exists.
        """
        return_value = super().__enter__()

        try:
            prefect_home = Path(self.settings.value_of(PREFECT_HOME))
            prefect_home.mkdir(mode=0o0700, exist_ok=True)
        except OSError:
            warnings.warn(
                (
                    "Failed to create the Prefect home directory at "
                    f"{self.settings.value_of(PREFECT_HOME)}"
                ),
                stacklevel=2,
            )

        return return_value

    @classmethod
    def get(cls) -> "SettingsContext":
        # Return the global context instead of `None` if no context exists
        return super().get() or GLOBAL_SETTINGS_CONTEXT


def get_run_context() -> Union[FlowRunContext, TaskRunContext]:
    """
    Get the current run context from within a task or flow function.

    Returns:
        A `FlowRunContext` or `TaskRunContext` depending on the function type.

    Raises
        RuntimeError: If called outside of a flow or task run.
    """
    task_run_ctx = TaskRunContext.get()
    if task_run_ctx:
        return task_run_ctx

    flow_run_ctx = FlowRunContext.get()
    if flow_run_ctx:
        return flow_run_ctx

    raise MissingContextError(
        "No run context available. You are not in a flow or task run context."
    )


def get_settings_context() -> SettingsContext:
    """
    Get the current settings context which contains profile information and the
    settings that are being used.

    Generally, the settings that are being used are a combination of values from the
    profile and environment. See `prefect.context.use_profile` for more details.
    """
    settings_ctx = SettingsContext.get()

    if not settings_ctx:
        raise MissingContextError("No settings context found.")

    return settings_ctx


@contextmanager
def tags(*new_tags: str) -> Set[str]:
    """
    Context manager to add tags to flow and task run calls.

    Tags are always combined with any existing tags.

    Yields:
        The current set of tags

    Examples:
        >>> from prefect import tags, task, flow
        >>> @task
        >>> def my_task():
        >>>     pass

        Run a task with tags

        >>> @flow
        >>> def my_flow():
        >>>     with tags("a", "b"):
        >>>         my_task()  # has tags: a, b

        Run a flow with tags

        >>> @flow
        >>> def my_flow():
        >>>     pass
        >>> with tags("a", "b"):
        >>>     my_flow()  # has tags: a, b

        Run a task with nested tag contexts

        >>> @flow
        >>> def my_flow():
        >>>     with tags("a", "b"):
        >>>         with tags("c", "d"):
        >>>             my_task()  # has tags: a, b, c, d
        >>>         my_task()  # has tags: a, b

        Inspect the current tags

        >>> @flow
        >>> def my_flow():
        >>>     with tags("c", "d"):
        >>>         with tags("e", "f") as current_tags:
        >>>              print(current_tags)
        >>> with tags("a", "b"):
        >>>     my_flow()
        {"a", "b", "c", "d", "e", "f"}
    """
    current_tags = TagsContext.get().current_tags
    new_tags = current_tags.union(new_tags)
    with TagsContext(current_tags=new_tags):
        yield new_tags


def registry_from_script(
    path: str,
    block_code_execution: bool = True,
    capture_failures: bool = True,
) -> PrefectObjectRegistry:
    """
    Return a fresh registry with instances populated from execution of a script.
    """
    with PrefectObjectRegistry(
        block_code_execution=block_code_execution,
        capture_failures=capture_failures,
    ) as registry:
        load_script_as_module(path)

    return registry


@contextmanager
def use_profile(
    profile: Union[Profile, str],
    override_environment_variables: bool = False,
    include_current_context: bool = True,
):
    """
    Switch to a profile for the duration of this context.

    Profile contexts are confined to an async context in a single thread.

    Args:
        profile: The name of the profile to load or an instance of a Profile.
        override_environment_variable: If set, variables in the profile will take
            precedence over current environment variables. By default, environment
            variables will override profile settings.
        include_current_context: If set, the new settings will be constructed
            with the current settings context as a base. If not set, the use_base settings
            will be loaded from the environment and defaults.

    Yields:
        The created `SettingsContext` object
    """
    if isinstance(profile, str):
        profiles = prefect.settings.load_profiles()
        profile = profiles[profile]

    if not isinstance(profile, Profile):
        raise TypeError(
            f"Unexpected type {type(profile).__name__!r} for `profile`. "
            "Expected 'str' or 'Profile'."
        )

    # Create a copy of the profiles settings as we will mutate it
    profile_settings = profile.settings.copy()

    existing_context = SettingsContext.get()
    if existing_context and include_current_context:
        settings = existing_context.settings
    else:
        settings = prefect.settings.get_settings_from_env()

    if not override_environment_variables:
        for key in os.environ:
            if key in prefect.settings.SETTING_VARIABLES:
                profile_settings.pop(prefect.settings.SETTING_VARIABLES[key], None)

    new_settings = settings.copy_with_update(updates=profile_settings)

    with SettingsContext(profile=profile, settings=new_settings) as ctx:
        yield ctx


def root_settings_context():
    """
    Return the settings context that will exist as the root context for the module.

    The profile to use is determined with the following precedence
    - Command line via 'prefect --profile <name>'
    - Environment variable via 'PREFECT_PROFILE'
    - Profiles file via the 'active' key
    """
    profiles = prefect.settings.load_profiles()
    active_name = profiles.active_name
    profile_source = "in the profiles file"

    if "PREFECT_PROFILE" in os.environ:
        active_name = os.environ["PREFECT_PROFILE"]
        profile_source = "by environment variable"

    if (
        sys.argv[0].endswith("/prefect")
        and len(sys.argv) >= 3
        and sys.argv[1] == "--profile"
    ):
        active_name = sys.argv[2]
        profile_source = "by command line argument"

    if active_name not in profiles.names:
        print(
            (
                f"WARNING: Active profile {active_name!r} set {profile_source} not "
                "found. The default profile will be used instead. "
            ),
            file=sys.stderr,
        )
        active_name = "default"

    with use_profile(
        profiles[active_name],
        # Override environment variables if the profile was set by the CLI
        override_environment_variables=profile_source == "by command line argument",
    ) as settings_context:
        return settings_context

    # Note the above context is exited and the global settings context is used by
    # an override in the `SettingsContext.get` method.


GLOBAL_SETTINGS_CONTEXT: SettingsContext = root_settings_context()
GLOBAL_OBJECT_REGISTRY: ContextManager[PrefectObjectRegistry] = None


def initialize_object_registry():
    global GLOBAL_OBJECT_REGISTRY

    if GLOBAL_OBJECT_REGISTRY:
        return

    GLOBAL_OBJECT_REGISTRY = PrefectObjectRegistry()
    GLOBAL_OBJECT_REGISTRY.__enter__()
