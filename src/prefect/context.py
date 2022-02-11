"""
Async and thread safe models for passing runtime context data.

These contexts should never be directly mutated by the user.
"""
import atexit
import os
import threading
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, List, Optional, Set, Type, TypeVar, Union

import pendulum
import toml
from anyio.abc import BlockingPortal, CancelScope
from pendulum.datetime import DateTime
from pydantic import BaseModel, Field

import prefect.logging.configuration
import prefect.settings
from prefect.client import OrionClient
from prefect.exceptions import MissingContextError
from prefect.flows import Flow
from prefect.futures import PrefectFuture
from prefect.orion.schemas.core import FlowRun, TaskRun
from prefect.orion.schemas.states import State
from prefect.settings import Settings
from prefect.task_runners import BaseTaskRunner
from prefect.tasks import Task

T = TypeVar("T")


class ContextModel(BaseModel):
    """
    A base model for context data that forbids mutation and extra data while providing
    a context manager
    """

    # The context variable for storing data must be defined by the child class
    __var__: ContextVar

    class Config:
        allow_mutation = False
        arbitrary_types_allowed = True
        extra = "forbid"

    def __enter__(self):
        # We've frozen the rest of the data on the class but we'd like to still store
        # this token for resetting on context exit
        object.__setattr__(self, "__token", self.__var__.set(self))
        return self

    def __exit__(self, *_):
        self.__var__.reset(getattr(self, "__token"))

    @classmethod
    def get(cls: Type[T]) -> Optional[T]:
        return cls.__var__.get(None)


class RunContext(ContextModel):
    """
    The base context for a flow or task run. Data in this context will always be
    available when `get_run_context` is called.

    Attributes:
        start_time: The time the run context was entered
        client: The Orion client instance being used for API communication
    """

    start_time: DateTime = Field(default_factory=lambda: pendulum.now("UTC"))
    client: OrionClient


class FlowRunContext(RunContext):
    """
    The context for a flow run. Data in this context is only available from within a
    flow run function.

    Attributes:
        flow: The flow instance associated with the run
        flow_run: The API metadata for the flow run
        task_runner: The task_runner instance being used for the flow run
        task_run_futures: A list of futures for task runs created within this flow run
        subflow_states: A list of states for flow runs created within this flow run
        sync_portal: A blocking portal for sync task/flow runs in an async flow
        timeout_scope: The cancellation scope for flow level timeouts
    """

    flow: Flow
    flow_run: FlowRun
    task_runner: BaseTaskRunner

    # Tracking created objects
    task_run_futures: List[PrefectFuture] = Field(default_factory=list)
    subflow_states: List[State] = Field(default_factory=list)

    # The synchronous portal is only created for async flows for creating engine calls
    # from synchronous task and subflow calls
    sync_portal: Optional[BlockingPortal] = None
    timeout_scope: Optional[CancelScope] = None

    __var__ = ContextVar("flow_run")


class TaskRunContext(RunContext):
    """
    The context for a task run. Data in this context is only available from within a
    task run function.

    Attributes:
        task: The task instance associated with the task run
        task_run: The API metadata for this task run
    """

    task: Task
    task_run: TaskRun

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
        >>> with tags("a", b"):
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
        >>> with tags("a", b"):
        >>>     my_flow()
        {"a", "b", "c", "d", "e", "f"}
    """
    current_tags = TagsContext.get().current_tags
    new_tags = current_tags.union(new_tags)
    with TagsContext(current_tags=new_tags):
        yield new_tags


@contextmanager
def temporary_environ(
    variables, override_existing: bool = True, warn_on_override: bool = False
):
    """
    Temporarily override default values in os.environ.

    Yields a dictionary of the key/value pairs matching the provided keys.
    """
    old_env = os.environ.copy()

    if override_existing:
        overrides = set(old_env.keys()).intersection(variables.keys())
        if overrides and warn_on_override:
            warnings.warn(
                f"Temporary environment is overriding key(s): {', '.join(overrides)}",
                stacklevel=3,
            )

    try:
        for var, value in variables.items():
            if value is None and var in os.environ and override_existing:
                # Allow setting `None` to remove items
                os.environ.pop(var)
                continue

            value = str(value)

            if var not in old_env or override_existing:
                os.environ[var] = value
            else:
                os.environ.setdefault(var, value)

        yield {var: os.environ.get(var) for var in variables}

    finally:
        for var in variables:
            if old_env.get(var):
                os.environ[var] = old_env[var]
            else:
                os.environ.pop(var, None)


class ProfileContext(ContextModel):
    """
    The context for a Prefect settings profile.

    Attributes:
        name: The name of the profile
        settings: The complete settings model
        env: The environment variables set in this profile configuration and their
            current values. These may differ from the profile configuration if the
            use has overridden them explicitly.
    """

    name: str
    settings: Settings
    env: Dict[str, str]

    __var__ = ContextVar("profile")


DEFAULT_PROFILES = {"default": {}}


def load_profiles() -> Dict[str, Dict[str, str]]:
    path = prefect.settings.from_env().profiles_path
    if not path.exists():
        profiles = DEFAULT_PROFILES
    else:
        profiles = {**DEFAULT_PROFILES, **toml.loads(path.read_text())}

    return profiles


def write_profiles(profiles: dict):
    path = prefect.settings.from_env().profiles_path
    profiles = {**DEFAULT_PROFILES, **profiles}
    return path.write_text(toml.dumps(profiles))


def load_profile(name: str) -> Dict[str, str]:
    """
    Loads a profile from the TOML file.

    Asserts that all variables are valid string key/value pairs.
    """
    profiles = load_profiles()

    if name not in profiles:
        raise ValueError(f"Profile {name!r} not found.")

    variables = profiles[name]
    for var, value in variables.items():
        try:
            variables[var] = str(value)
        except Exception as exc:
            raise TypeError(
                f"Invalid value {value!r} for variable {var!r}: Cannot be coerced to string."
            ) from exc

    return variables


_PROFILE_LOCK = threading.Lock()


@contextmanager
def profile(
    name: str,
    create_home: bool = False,
    setup_logging: bool = False,
    override_existing_variables: bool = False,
):
    """
    Switch to a new profile for the duration of this context.

    Upon initialization, we can create the home directory contained in the settings and
    set up logging. These steps are optional. Logging can only be set up once per
    process and later attempts to configure logging will fail.

    Profile contexts are confined to an async context in a single thread.

    Args:
        name: The name of the profile to load. Must exist.
        create_home: Create the PREFECT_HOME directory.
        setup_logging: Configure logging for the current process.
        override_existing_variables: If set, variables in the profile will take
            precedence over current environment variables. By default, environment
            variables will override profile settings.

    Yields:
        The created `ProfileContext` object
    """
    env = load_profile(name)

    # Prevent multiple threads from mutating the environment concurrently
    with _PROFILE_LOCK:
        with temporary_environ(
            env, override_existing=override_existing_variables, warn_on_override=True
        ):
            settings = prefect.settings.from_env()

    if create_home and not os.path.exists(settings.home):
        os.makedirs(settings.home, exist_ok=True)

    if setup_logging:
        prefect.logging.configuration.setup_logging(settings)

    with ProfileContext(name=name, settings=settings, env=env) as ctx:
        yield ctx


def initialize_module_profile():
    """
    Initialize the profle that will exist as the root context for the module.

    This should only be called _once_ at Prefect module initialization.
    """
    name = os.environ.get("PREFECT_PROFILE", "default")
    context = profile(name=name, create_home=True, setup_logging=True)
    context.__enter__()
    atexit.register(lambda: context.__exit__(None, None, None))


def get_profile_context() -> ProfileContext:
    profile_ctx = ProfileContext.get()

    if not profile_ctx:
        raise MissingContextError("No profile is being used.")

    return profile_ctx
