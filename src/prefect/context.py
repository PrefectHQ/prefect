"""
Async and thread safe models for passing runtime context data.

These contexts should never be directly mutated by the user.

For more user-accessible information about the current run, see [`prefect.runtime`](../runtime/flow_run).
"""

import os
import sys
import warnings
import weakref
from contextlib import ExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Dict,
    Generator,
    Mapping,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

import pendulum
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import Self

import prefect.logging
import prefect.logging.configuration
import prefect.settings
from prefect._internal.compatibility.migration import getattr_migration
from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
from prefect.client.schemas import FlowRun, TaskRun
from prefect.events.worker import EventsWorker
from prefect.exceptions import MissingContextError
from prefect.results import ResultStore, get_default_persist_setting
from prefect.settings import PREFECT_HOME, Profile, Settings
from prefect.states import State
from prefect.task_runners import TaskRunner
from prefect.utilities.services import start_client_metrics_server

T = TypeVar("T")

if TYPE_CHECKING:
    from prefect.flows import Flow
    from prefect.tasks import Task

# Define the global settings context variable
# This will be populated downstream but must be null here to facilitate loading the
# default settings.
GLOBAL_SETTINGS_CONTEXT = None  # type: ignore


def serialize_context() -> Dict[str, Any]:
    """
    Serialize the current context for use in a remote execution environment.
    """

    flow_run_context = EngineContext.get()
    task_run_context = TaskRunContext.get()
    tags_context = TagsContext.get()
    settings_context = SettingsContext.get()

    return {
        "flow_run_context": flow_run_context.serialize() if flow_run_context else {},
        "task_run_context": task_run_context.serialize() if task_run_context else {},
        "tags_context": tags_context.serialize() if tags_context else {},
        "settings_context": settings_context.serialize() if settings_context else {},
    }


@contextmanager
def hydrated_context(
    serialized_context: Optional[Dict[str, Any]] = None,
    client: Union[PrefectClient, SyncPrefectClient, None] = None,
):
    with ExitStack() as stack:
        if serialized_context:
            # Set up settings context
            if settings_context := serialized_context.get("settings_context"):
                stack.enter_context(SettingsContext(**settings_context))
            # Set up parent flow run context
            client = client or get_client(sync_client=True)
            if flow_run_context := serialized_context.get("flow_run_context"):
                flow = flow_run_context["flow"]
                task_runner = stack.enter_context(flow.task_runner.duplicate())
                flow_run_context = FlowRunContext(
                    **flow_run_context,
                    client=client,
                    task_runner=task_runner,
                    detached=True,
                )
                stack.enter_context(flow_run_context)
            # Set up parent task run context
            if parent_task_run_context := serialized_context.get("task_run_context"):
                task_run_context = TaskRunContext(
                    **parent_task_run_context,
                    client=client,
                )
                stack.enter_context(task_run_context)
            # Set up tags context
            if tags_context := serialized_context.get("tags_context"):
                stack.enter_context(tags(*tags_context["current_tags"]))
        yield


class ContextModel(BaseModel):
    """
    A base model for context data that forbids mutation and extra data while providing
    a context manager
    """

    # The context variable for storing data must be defined by the child class
    __var__: ContextVar
    _token: Optional[Token] = PrivateAttr(None)
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )

    def __enter__(self) -> Self:
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
    def get(cls: Type[Self]) -> Optional[Self]:
        """Get the current context instance"""
        return cls.__var__.get(None)

    def model_copy(
        self: Self, *, update: Optional[Dict[str, Any]] = None, deep: bool = False
    ):
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
        new = super().model_copy(update=update, deep=deep)
        # Remove the token on copy to avoid re-entrance errors
        new._token = None
        return new

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the context model to a dictionary that can be pickled with cloudpickle.
        """
        return self.model_dump(exclude_unset=True)


class SyncClientContext(ContextModel):
    """
    A context for managing the sync Prefect client instances.

    Clients were formerly tracked on the TaskRunContext and FlowRunContext, but
    having two separate places and the addition of both sync and async clients
    made it difficult to manage. This context is intended to be the single
    source for sync clients.

    The client creates a sync client, which can either be read directly from
    the context object OR loaded with get_client, inject_client, or other
    Prefect utilities.

    with SyncClientContext.get_or_create() as ctx:
        c1 = get_client(sync_client=True)
        c2 = get_client(sync_client=True)
        assert c1 is c2
        assert c1 is ctx.client
    """

    __var__ = ContextVar("sync-client-context")
    client: SyncPrefectClient
    _httpx_settings: Optional[dict[str, Any]] = PrivateAttr(None)
    _context_stack: int = PrivateAttr(0)

    def __init__(self, httpx_settings: Optional[dict[str, Any]] = None):
        super().__init__(
            client=get_client(sync_client=True, httpx_settings=httpx_settings),
        )
        self._httpx_settings = httpx_settings
        self._context_stack = 0

    def __enter__(self):
        self._context_stack += 1
        if self._context_stack == 1:
            self.client.__enter__()
            self.client.raise_for_api_version_mismatch()
            return super().__enter__()
        else:
            return self

    def __exit__(self, *exc_info):
        self._context_stack -= 1
        if self._context_stack == 0:
            self.client.__exit__(*exc_info)
            return super().__exit__(*exc_info)

    @classmethod
    @contextmanager
    def get_or_create(cls) -> Generator["SyncClientContext", None, None]:
        ctx = SyncClientContext.get()
        if ctx:
            yield ctx
        else:
            with SyncClientContext() as ctx:
                yield ctx


class AsyncClientContext(ContextModel):
    """
    A context for managing the async Prefect client instances.

    Clients were formerly tracked on the TaskRunContext and FlowRunContext, but
    having two separate places and the addition of both sync and async clients
    made it difficult to manage. This context is intended to be the single
    source for async clients.

    The client creates an async client, which can either be read directly from
    the context object OR loaded with get_client, inject_client, or other
    Prefect utilities.

    with AsyncClientContext.get_or_create() as ctx:
        c1 = get_client(sync_client=False)
        c2 = get_client(sync_client=False)
        assert c1 is c2
        assert c1 is ctx.client
    """

    __var__ = ContextVar("async-client-context")
    client: PrefectClient
    _httpx_settings: Optional[dict[str, Any]] = PrivateAttr(None)
    _context_stack: int = PrivateAttr(0)

    def __init__(self, httpx_settings: Optional[dict[str, Any]] = None):
        super().__init__(
            client=get_client(sync_client=False, httpx_settings=httpx_settings),
        )
        self._httpx_settings = httpx_settings
        self._context_stack = 0

    async def __aenter__(self):
        self._context_stack += 1
        if self._context_stack == 1:
            await self.client.__aenter__()
            await self.client.raise_for_api_version_mismatch()
            return super().__enter__()
        else:
            return self

    async def __aexit__(self, *exc_info):
        self._context_stack -= 1
        if self._context_stack == 0:
            await self.client.__aexit__(*exc_info)
            return super().__exit__(*exc_info)

    @classmethod
    @asynccontextmanager
    async def get_or_create(cls) -> AsyncGenerator[Self, None]:
        ctx = cls.get()
        if ctx:
            yield ctx
        else:
            async with cls() as ctx:
                yield ctx


class RunContext(ContextModel):
    """
    The base context for a flow or task run. Data in this context will always be
    available when `get_run_context` is called.

    Attributes:
        start_time: The time the run context was entered
        client: The Prefect client instance being used for API communication
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        start_client_metrics_server()

    start_time: DateTime = Field(default_factory=lambda: pendulum.now("UTC"))
    input_keyset: Optional[Dict[str, Dict[str, str]]] = None
    client: Union[PrefectClient, SyncPrefectClient]

    def serialize(self):
        return self.model_dump(
            include={"start_time", "input_keyset"},
            exclude_unset=True,
        )


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
    """

    flow: Optional["Flow"] = None
    flow_run: Optional[FlowRun] = None
    task_runner: TaskRunner
    log_prints: bool = False
    parameters: Optional[Dict[str, Any]] = None

    # Flag signaling if the flow run context has been serialized and sent
    # to remote infrastructure.
    detached: bool = False

    # Result handling
    result_store: ResultStore
    persist_result: bool = Field(default_factory=get_default_persist_setting)

    # Counter for task calls allowing unique
    task_run_dynamic_keys: Dict[str, int] = Field(default_factory=dict)

    # Counter for flow pauses
    observed_flow_pauses: Dict[str, int] = Field(default_factory=dict)

    # Tracking for result from task runs in this flow run for dependency tracking
    # Holds the ID of the object returned by the task run and task run state
    # This is a weakref dictionary to avoid undermining garbage collection
    task_run_results: Mapping[int, State] = Field(
        default_factory=weakref.WeakValueDictionary
    )

    # Events worker to emit events
    events: Optional[EventsWorker] = None

    __var__: ContextVar = ContextVar("flow_run")

    def serialize(self):
        return self.model_dump(
            include={
                "flow_run",
                "flow",
                "parameters",
                "log_prints",
                "start_time",
                "input_keyset",
                "result_store",
                "persist_result",
            },
            exclude_unset=True,
        )


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
    result_store: ResultStore
    persist_result: bool = Field(default_factory=get_default_persist_setting)

    __var__ = ContextVar("task_run")

    def serialize(self):
        return self.model_dump(
            include={
                "task_run",
                "task",
                "parameters",
                "log_prints",
                "start_time",
                "input_keyset",
                "result_store",
                "persist_result",
            },
            exclude_unset=True,
        )


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
def tags(*new_tags: str) -> Generator[Set[str], None, None]:
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
        active_name = "ephemeral"

    with use_profile(
        profiles[active_name],
        # Override environment variables if the profile was set by the CLI
        override_environment_variables=profile_source == "by command line argument",
    ) as settings_context:
        return settings_context

    # Note the above context is exited and the global settings context is used by
    # an override in the `SettingsContext.get` method.


GLOBAL_SETTINGS_CONTEXT: SettingsContext = root_settings_context()


# 2024-07-02: This surfaces an actionable error message for removed objects
# in Prefect 3.0 upgrade.
__getattr__ = getattr_migration(__name__)
