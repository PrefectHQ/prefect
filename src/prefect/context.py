"""
Async and thread safe models for passing runtime context data.

These contexts should never be directly mutated by the user.

For more user-accessible information about the current run, see [`prefect.runtime`](../runtime/flow_run).
"""

import asyncio
import json
import os
import sys
import warnings
from collections.abc import AsyncGenerator, Generator, Mapping
from contextlib import ExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Optional,
    TypeVar,
    Union,
)
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from typing_extensions import Self

import prefect.settings
import prefect.types._datetime
from prefect._internal.compatibility.migration import getattr_migration
from prefect.assets import Asset
from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.objects import RunType
from prefect.events.worker import EventsWorker
from prefect.exceptions import MissingContextError
from prefect.results import (
    ResultStore,
    get_default_persist_setting,
    get_default_persist_setting_for_tasks,
)
from prefect.settings import Profile, Settings
from prefect.settings.legacy import (
    _get_settings_fields,  # type: ignore[reportPrivateUsage]
)
from prefect.states import State
from prefect.task_runners import TaskRunner
from prefect.types import DateTime
from prefect.utilities.services import start_client_metrics_server

T = TypeVar("T")
P = TypeVar("P")
R = TypeVar("R")

if TYPE_CHECKING:
    from prefect.flows import Flow
    from prefect.tasks import Task


def serialize_context(
    asset_ctx_kwargs: Union[dict[str, Any], None] = None,
) -> dict[str, Any]:
    """
    Serialize the current context for use in a remote execution environment.

    Optionally provide asset_ctx_kwargs to create new AssetContext, that will be used
    in the remote execution environment. This is useful for TaskRunners, who rely on creating the
    task run in the remote environment.
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
        "asset_context": AssetContext.from_task_and_inputs(
            **asset_ctx_kwargs
        ).serialize()
        if asset_ctx_kwargs
        else {},
    }


@contextmanager
def hydrated_context(
    serialized_context: Optional[dict[str, Any]] = None,
    client: Union[PrefectClient, SyncPrefectClient, None] = None,
) -> Generator[None, Any, None]:
    # We need to rebuild the models because we might be hydrating in a remote
    # environment where the models are not available.
    # TODO: Remove this once we have fixed our circular imports and we don't need to rebuild models any more.
    from prefect._result_records import ResultRecordMetadata
    from prefect.flows import Flow
    from prefect.tasks import Task

    _types: dict[str, Any] = dict(
        Flow=Flow,
        Task=Task,
        ResultRecordMetadata=ResultRecordMetadata,
    )
    FlowRunContext.model_rebuild(_types_namespace=_types)
    TaskRunContext.model_rebuild(_types_namespace=_types)

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
            # Set up asset context
            if asset_context := serialized_context.get("asset_context"):
                stack.enter_context(AssetContext(**asset_context))
        yield


class ContextModel(BaseModel):
    """
    A base model for context data that forbids mutation and extra data while providing
    a context manager
    """

    if TYPE_CHECKING:
        # subclasses can pass through keyword arguments to the pydantic base model
        def __init__(self, **kwargs: Any) -> None: ...

    # The context variable for storing data must be defined by the child class
    __var__: ClassVar[ContextVar[Any]]
    _token: Optional[Token[Self]] = PrivateAttr(None)
    model_config: ClassVar[ConfigDict] = ConfigDict(
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

    def __exit__(self, *_: Any) -> None:
        if not self._token:
            raise RuntimeError(
                "Asymmetric use of context. Context exit called without an enter."
            )
        self.__var__.reset(self._token)
        self._token = None

    @classmethod
    def get(cls: type[Self]) -> Optional[Self]:
        """Get the current context instance"""
        return cls.__var__.get(None)

    def model_copy(
        self: Self, *, update: Optional[Mapping[str, Any]] = None, deep: bool = False
    ) -> Self:
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

    def serialize(self, include_secrets: bool = True) -> dict[str, Any]:
        """
        Serialize the context model to a dictionary that can be pickled with cloudpickle.
        """
        return self.model_dump(
            exclude_unset=True, context={"include_secrets": include_secrets}
        )


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

    __var__: ClassVar[ContextVar[Self]] = ContextVar("sync-client-context")
    client: SyncPrefectClient
    _httpx_settings: Optional[dict[str, Any]] = PrivateAttr(None)
    _context_stack: int = PrivateAttr(0)

    def __init__(self, httpx_settings: Optional[dict[str, Any]] = None) -> None:
        super().__init__(
            client=get_client(sync_client=True, httpx_settings=httpx_settings),
        )
        self._httpx_settings = httpx_settings
        self._context_stack = 0

    def __enter__(self) -> Self:
        self._context_stack += 1
        if self._context_stack == 1:
            self.client.__enter__()
            self.client.raise_for_api_version_mismatch()
            return super().__enter__()
        else:
            return self

    def __exit__(self, *exc_info: Any) -> None:
        self._context_stack -= 1
        if self._context_stack == 0:
            self.client.__exit__(*exc_info)
            return super().__exit__(*exc_info)

    @classmethod
    @contextmanager
    def get_or_create(cls) -> Generator[Self, None, None]:
        ctx = cls.get()
        if ctx:
            yield ctx
        else:
            with cls() as ctx:
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

    __var__: ClassVar[ContextVar[Self]] = ContextVar("async-client-context")
    client: PrefectClient
    _httpx_settings: Optional[dict[str, Any]] = PrivateAttr(None)
    _context_stack: int = PrivateAttr(0)

    def __init__(self, httpx_settings: Optional[dict[str, Any]] = None):
        super().__init__(
            client=get_client(sync_client=False, httpx_settings=httpx_settings)
        )
        self._httpx_settings = httpx_settings
        self._context_stack = 0

    async def __aenter__(self: Self) -> Self:
        self._context_stack += 1
        if self._context_stack == 1:
            await self.client.__aenter__()
            await self.client.raise_for_api_version_mismatch()
            return super().__enter__()
        else:
            return self

    async def __aexit__(self: Self, *exc_info: Any) -> None:
        self._context_stack -= 1
        if self._context_stack == 0:
            await self.client.__aexit__(*exc_info)
            return super().__exit__(*exc_info)

    @classmethod
    @asynccontextmanager
    async def get_or_create(cls) -> AsyncGenerator[Self, None]:
        ctx = cls.get()
        if ctx and asyncio.get_running_loop() is ctx.client.loop:
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        start_client_metrics_server()

    start_time: DateTime = Field(
        default_factory=lambda: prefect.types._datetime.now("UTC")
    )
    input_keyset: Optional[dict[str, dict[str, str]]] = None
    client: Union[PrefectClient, SyncPrefectClient]

    def serialize(self: Self, include_secrets: bool = True) -> dict[str, Any]:
        return self.model_dump(
            include={"start_time", "input_keyset"},
            exclude_unset=True,
            context={"include_secrets": include_secrets},
        )


class EngineContext(RunContext):
    """
    The context for a flow run. Data in this context is only available from within a
    flow run function.

    Attributes:
        flow: The flow instance associated with the run
        flow_run: The API metadata for the flow run
        task_runner: The task runner instance being used for the flow run
        run_results: A mapping of result ids to run states for this flow run
        log_prints: Whether to log print statements from the flow run
        parameters: The parameters passed to the flow run
        detached: Flag indicating if context has been serialized and sent to remote infrastructure
        result_store: The result store used to persist results
        persist_result: Whether to persist the flow run result
        task_run_dynamic_keys: Counter for task calls allowing unique keys
        observed_flow_pauses: Counter for flow pauses
        events: Events worker to emit events
    """

    flow: Optional["Flow[Any, Any]"] = None
    flow_run: Optional[FlowRun] = None
    task_runner: TaskRunner[Any]
    log_prints: bool = False
    parameters: Optional[dict[str, Any]] = None

    # Flag signaling if the flow run context has been serialized and sent
    # to remote infrastructure.
    detached: bool = False

    # Result handling
    result_store: ResultStore
    persist_result: bool = Field(default_factory=get_default_persist_setting)

    # Counter for task calls allowing unique
    task_run_dynamic_keys: dict[str, Union[str, int]] = Field(default_factory=dict)

    # Counter for flow pauses
    observed_flow_pauses: dict[str, int] = Field(default_factory=dict)

    # Tracking for result from task runs and sub flows in this flow run for
    # dependency tracking. Holds the ID of the object returned by
    # the run and state
    run_results: dict[int, tuple[State, RunType]] = Field(default_factory=dict)

    # Tracking information needed to track asset linage between
    # tasks and materialization
    task_run_assets: dict[UUID, set[Asset]] = Field(default_factory=dict)

    # Events worker to emit events
    events: Optional[EventsWorker] = None

    __var__: ClassVar[ContextVar[Self]] = ContextVar("flow_run")

    def serialize(self: Self, include_secrets: bool = True) -> dict[str, Any]:
        serialized = self.model_dump(
            include={
                "flow_run",
                "flow",
                "parameters",
                "log_prints",
                "start_time",
                "input_keyset",
                "persist_result",
            },
            exclude_unset=True,
            context={"include_secrets": include_secrets},
        )
        if self.result_store:
            serialized["result_store"] = self.result_store.model_dump(
                serialize_as_any=True,
                exclude_unset=True,
                context={"include_secrets": include_secrets},
            )
        return serialized


FlowRunContext = EngineContext  # for backwards compatibility


class TaskRunContext(RunContext):
    """
    The context for a task run. Data in this context is only available from within a
    task run function.

    Attributes:
        task: The task instance associated with the task run
        task_run: The API metadata for this task run
    """

    task: "Task[Any, Any]"
    task_run: TaskRun
    log_prints: bool = False
    parameters: dict[str, Any]

    # Result handling
    result_store: ResultStore
    persist_result: bool = Field(default_factory=get_default_persist_setting_for_tasks)

    __var__: ClassVar[ContextVar[Self]] = ContextVar("task_run")

    def serialize(self: Self, include_secrets: bool = True) -> dict[str, Any]:
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
            serialize_as_any=True,
            context={"include_secrets": include_secrets},
        )


class AssetContext(ContextModel):
    """
    The asset context for a materializing task run. Contains all asset-related information needed
    for asset event emission and downstream asset dependency propagation.

    Attributes:
        direct_asset_dependencies: Assets that this task directly depends on (from task.asset_deps)
        downstream_assets: Assets that this task will create/materialize (from MaterializingTask.assets)
        upstream_assets: Assets from upstream task dependencies
        materialized_by: Tool that materialized the assets (from MaterializingTask.materialized_by)
        task_run_id: ID of the associated task run
        materialization_metadata: Metadata for materialized assets
    """

    direct_asset_dependencies: set[Asset] = Field(default_factory=set)
    downstream_assets: set[Asset] = Field(default_factory=set)
    upstream_assets: set[Asset] = Field(default_factory=set)
    materialized_by: Optional[str] = None
    task_run_id: Optional[UUID] = None
    materialization_metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)
    copy_to_child_ctx: bool = False

    __var__: ClassVar[ContextVar[Self]] = ContextVar("asset_context")

    @classmethod
    def from_task_and_inputs(
        cls,
        task: "Task[Any, Any]",
        task_run_id: UUID,
        task_inputs: Optional[dict[str, set[Any]]] = None,
        copy_to_child_ctx: bool = False,
    ) -> "AssetContext":
        """
        Create an AssetContext from a task and its resolved inputs.

        Args:
            task: The task instance
            task_run_id: The task run ID
            task_inputs: The resolved task inputs (TaskRunResult objects)
            copy_to_child_ctx: Whether this context should be copied on a child AssetContext

        Returns:
            Configured AssetContext
        """
        from prefect.client.schemas import TaskRunResult
        from prefect.tasks import MaterializingTask

        upstream_assets: set[Asset] = set()

        flow_ctx = FlowRunContext.get()
        if task_inputs and flow_ctx:
            for name, inputs in task_inputs.items():
                # Parent task runs are not dependencies
                # that we want to track
                if name == "__parents__":
                    continue

                for task_input in inputs:
                    if isinstance(task_input, TaskRunResult):
                        task_assets = flow_ctx.task_run_assets.get(task_input.id)
                        if task_assets:
                            upstream_assets.update(task_assets)

        ctx = cls(
            direct_asset_dependencies=set(task.asset_deps)
            if task.asset_deps
            else set(),
            downstream_assets=set(task.assets)
            if isinstance(task, MaterializingTask) and task.assets
            else set(),
            upstream_assets=upstream_assets,
            materialized_by=task.materialized_by
            if isinstance(task, MaterializingTask)
            else None,
            task_run_id=task_run_id,
            copy_to_child_ctx=copy_to_child_ctx,
        )
        ctx.update_tracked_assets()

        return ctx

    def add_asset_metadata(self, asset_key: str, metadata: dict[str, Any]) -> None:
        """
        Add metadata for a materialized asset.

        Args:
            asset_key: The asset key
            metadata: Metadata dictionary to add

        Raises:
            ValueError: If asset_key is not in downstream_assets
        """
        downstream_keys = {asset.key for asset in self.downstream_assets}
        if asset_key not in downstream_keys:
            raise ValueError(
                "Can only add metadata to assets that are arguments to @materialize"
            )

        existing = self.materialization_metadata.get(asset_key, {})
        self.materialization_metadata[asset_key] = existing | metadata

    @staticmethod
    def asset_as_resource(asset: Asset) -> dict[str, str]:
        """Convert Asset to event resource format."""
        resource = {"prefect.resource.id": asset.key}

        if asset.properties:
            properties_dict = asset.properties.model_dump(exclude_unset=True)

            if "name" in properties_dict:
                resource["prefect.resource.name"] = properties_dict["name"]

            if "description" in properties_dict:
                resource["prefect.asset.description"] = properties_dict["description"]

            if "url" in properties_dict:
                resource["prefect.asset.url"] = properties_dict["url"]

            if "owners" in properties_dict:
                resource["prefect.asset.owners"] = json.dumps(properties_dict["owners"])

        return resource

    @staticmethod
    def asset_as_related(asset: Asset) -> dict[str, str]:
        """Convert Asset to event related format."""
        return {
            "prefect.resource.id": asset.key,
            "prefect.resource.role": "asset",
        }

    @staticmethod
    def related_materialized_by(by: str) -> dict[str, str]:
        """Create a related resource for the tool that performed the materialization"""
        return {
            "prefect.resource.id": by,
            "prefect.resource.role": "asset-materialized-by",
        }

    def emit_events(self, state: State) -> None:
        """
        Emit asset events
        """

        from prefect.events import emit_event

        if state.name == "Cached":
            return
        elif state.is_failed():
            event_status = "failed"
        elif state.is_completed():
            event_status = "succeeded"
        else:
            return

        # If we have no downstream assets, this not a materialization
        if not self.downstream_assets:
            return

        # Emit reference events for all upstream assets (direct + inherited)
        all_upstream_assets = self.upstream_assets | self.direct_asset_dependencies
        for asset in all_upstream_assets:
            emit_event(
                event="prefect.asset.referenced",
                resource=self.asset_as_resource(asset),
                related=[],
            )

        # Emit materialization events for downstream assets
        upstream_related = [self.asset_as_related(a) for a in all_upstream_assets]

        if self.materialized_by:
            upstream_related.append(self.related_materialized_by(self.materialized_by))

        for asset in self.downstream_assets:
            emit_event(
                event=f"prefect.asset.materialization.{event_status}",
                resource=self.asset_as_resource(asset),
                related=upstream_related,
                payload=self.materialization_metadata.get(asset.key),
            )

    def update_tracked_assets(self) -> None:
        """
        Update the flow run context with assets that should be propagated downstream.
        """
        if not (flow_run_context := FlowRunContext.get()):
            return

        if not self.task_run_id:
            return

        if self.downstream_assets:
            # MaterializingTask: propagate the downstream assets (what we create)
            assets_for_downstream = set(self.downstream_assets)
        else:
            # Regular task: propagate upstream assets + direct dependencies
            assets_for_downstream = set(
                self.upstream_assets | self.direct_asset_dependencies
            )

        flow_run_context.task_run_assets[self.task_run_id] = assets_for_downstream

    def serialize(self: Self, include_secrets: bool = True) -> dict[str, Any]:
        """Serialize the AssetContext for distributed execution."""
        return self.model_dump(
            # use json serialization so fields that are
            # sets of pydantic models are serialized
            mode="json",
            exclude_unset=True,
            serialize_as_any=True,
            context={"include_secrets": include_secrets},
        )


class TagsContext(ContextModel):
    """
    The context for `prefect.tags` management.

    Attributes:
        current_tags: A set of current tags in the context
    """

    current_tags: set[str] = Field(default_factory=set)

    @classmethod
    def get(cls) -> Self:
        # Return an empty `TagsContext` instead of `None` if no context exists
        return cls.__var__.get(cls())

    __var__: ClassVar[ContextVar[Self]] = ContextVar("tags")


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

    __var__: ClassVar[ContextVar[Self]] = ContextVar("settings")

    def __hash__(self: Self) -> int:
        return hash(self.settings)

    @classmethod
    def get(cls) -> Optional["SettingsContext"]:
        # Return the global context instead of `None` if no context exists
        try:
            return super().get() or GLOBAL_SETTINGS_CONTEXT
        except NameError:
            # GLOBAL_SETTINGS_CONTEXT has not yet been set; in order to create
            # it profiles need to be loaded, and that process calls
            # SettingsContext.get().
            return None


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
def tags(*new_tags: str) -> Generator[set[str], None, None]:
    """
    Context manager to add tags to flow and task run calls.

    Tags are always combined with any existing tags.

    Yields:
        The current set of tags

    Examples:
        ```python
        from prefect import tags, task, flow
        @task
        def my_task():
            pass
        ```

        Run a task with tags

        ```python
        @flow
        def my_flow():
            with tags("a", "b"):
                my_task()  # has tags: a, b
        ```

        Run a flow with tags

        ```python
        @flow
        def my_flow():
            pass
        with tags("a", "b"):
            my_flow()  # has tags: a, b
        ```

        Run a task with nested tag contexts

        ```python
        @flow
        def my_flow():
            with tags("a", "b"):
                with tags("c", "d"):
                    my_task()  # has tags: a, b, c, d
                my_task()  # has tags: a, b
        ```

        Inspect the current tags

        ```python
        @flow
        def my_flow():
            with tags("c", "d"):
                with tags("e", "f") as current_tags:
                     print(current_tags)
        with tags("a", "b"):
            my_flow()
        # {"a", "b", "c", "d", "e", "f"}
        ```
    """
    current_tags = TagsContext.get().current_tags
    _new_tags = current_tags.union(new_tags)
    with TagsContext(current_tags=_new_tags):
        yield _new_tags


@contextmanager
def use_profile(
    profile: Union[Profile, str],
    override_environment_variables: bool = False,
    include_current_context: bool = True,
) -> Generator[SettingsContext, Any, None]:
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

    if not TYPE_CHECKING:
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
        settings = Settings()

    if not override_environment_variables:
        for key in os.environ:
            if key in _get_settings_fields(Settings):
                profile_settings.pop(_get_settings_fields(Settings)[key], None)

    new_settings = settings.copy_with_update(updates=profile_settings)

    with SettingsContext(profile=profile, settings=new_settings) as ctx:
        yield ctx


def root_settings_context() -> SettingsContext:
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

    if not (settings := Settings()).home.exists():
        try:
            settings.home.mkdir(mode=0o0700, exist_ok=True)
        except OSError:
            warnings.warn(
                (f"Failed to create the Prefect home directory at {settings.home}"),
                stacklevel=2,
            )

    return SettingsContext(profile=profiles[active_name], settings=settings)

    # Note the above context is exited and the global settings context is used by
    # an override in the `SettingsContext.get` method.


GLOBAL_SETTINGS_CONTEXT: SettingsContext = root_settings_context()


# 2024-07-02: This surfaces an actionable error message for removed objects
# in Prefect 3.0 upgrade.
__getattr__: Callable[[str], Any] = getattr_migration(__name__)
