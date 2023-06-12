import datetime
import json
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
    overload,
)
from typing_extensions import Literal
from uuid import UUID

import pendulum
from pydantic import Field, HttpUrl, conint, root_validator, validator

from prefect._internal.schemas.bases import ObjectBaseModel, PrefectBaseModel
from prefect._internal.schemas.fields import CreatedBy, DateTimeTZ, UpdatedBy
from prefect._internal.schemas.validators import raise_on_name_with_banned_characters
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.settings import PREFECT_CLOUD_API_URL
from prefect.utilities.collections import AutoEnum, listrepr
from prefect.utilities.names import generate_slug
from prefect.utilities.templating import find_placeholders

if TYPE_CHECKING:
    from prefect.deprecated.data_documents import DataDocument
    from prefect.results import BaseResult

R = TypeVar("R")


DEFAULT_BLOCK_SCHEMA_VERSION = "non-versioned"
DEFAULT_AGENT_WORK_POOL_NAME = "default-agent-pool"
FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS = [
    "flow_run_notification_policy_id",
    "flow_id",
    "flow_name",
    "flow_run_url",
    "flow_run_id",
    "flow_run_name",
    "flow_run_parameters",
    "flow_run_state_type",
    "flow_run_state_name",
    "flow_run_state_timestamp",
    "flow_run_state_message",
]
MAX_VARIABLE_NAME_LENGTH = 255
MAX_VARIABLE_VALUE_LENGTH = 5000


class StateType(AutoEnum):
    """Enumeration of state types."""

    SCHEDULED = AutoEnum.auto()
    PENDING = AutoEnum.auto()
    RUNNING = AutoEnum.auto()
    COMPLETED = AutoEnum.auto()
    FAILED = AutoEnum.auto()
    CANCELLED = AutoEnum.auto()
    CRASHED = AutoEnum.auto()
    PAUSED = AutoEnum.auto()
    CANCELLING = AutoEnum.auto()


class StateDetails(PrefectBaseModel):
    flow_run_id: UUID = None
    task_run_id: UUID = None
    # for task runs that represent subflows, the subflow's run ID
    child_flow_run_id: UUID = None
    scheduled_time: DateTimeTZ = None
    cache_key: str = None
    cache_expiration: DateTimeTZ = None
    untrackable_result: bool = False
    pause_timeout: DateTimeTZ = None
    pause_reschedule: bool = False
    pause_key: str = None
    refresh_cache: bool = None


class State(ObjectBaseModel, Generic[R]):
    """
    The state of a run.
    """

    type: StateType
    name: Optional[str] = Field(default=None)
    timestamp: DateTimeTZ = Field(default_factory=lambda: pendulum.now("UTC"))
    message: Optional[str] = Field(default=None, example="Run started")
    state_details: StateDetails = Field(default_factory=StateDetails)
    data: Union["BaseResult[R]", "DataDocument[R]", Any] = Field(
        default=None,
    )

    @overload
    def result(self: "State[R]", raise_on_failure: bool = True) -> R:
        ...

    @overload
    def result(self: "State[R]", raise_on_failure: bool = False) -> Union[R, Exception]:
        ...

    def result(self, raise_on_failure: bool = True, fetch: Optional[bool] = None):
        """
        Retrieve the result attached to this state.

        Args:
            raise_on_failure: a boolean specifying whether to raise an exception
                if the state is of type `FAILED` and the underlying data is an exception
            fetch: a boolean specifying whether to resolve references to persisted
                results into data. For synchronous users, this defaults to `True`.
                For asynchronous users, this defaults to `False` for backwards
                compatibility.

        Raises:
            TypeError: If the state is failed but the result is not an exception.

        Returns:
            The result of the run

        Examples:
            >>> from prefect import flow, task
            >>> @task
            >>> def my_task(x):
            >>>     return x

            Get the result from a task future in a flow

            >>> @flow
            >>> def my_flow():
            >>>     future = my_task("hello")
            >>>     state = future.wait()
            >>>     result = state.result()
            >>>     print(result)
            >>> my_flow()
            hello

            Get the result from a flow state

            >>> @flow
            >>> def my_flow():
            >>>     return "hello"
            >>> my_flow(return_state=True).result()
            hello

            Get the result from a failed state

            >>> @flow
            >>> def my_flow():
            >>>     raise ValueError("oh no!")
            >>> state = my_flow(return_state=True)  # Error is wrapped in FAILED state
            >>> state.result()  # Raises `ValueError`

            Get the result from a failed state without erroring

            >>> @flow
            >>> def my_flow():
            >>>     raise ValueError("oh no!")
            >>> state = my_flow(return_state=True)
            >>> result = state.result(raise_on_failure=False)
            >>> print(result)
            ValueError("oh no!")


            Get the result from a flow state in an async context

            >>> @flow
            >>> async def my_flow():
            >>>     return "hello"
            >>> state = await my_flow(return_state=True)
            >>> await state.result()
            hello
        """
        from prefect.states import get_state_result

        return get_state_result(self, raise_on_failure=raise_on_failure, fetch=fetch)

    def to_state_create(self):
        """
        Convert this state to a `StateCreate` type which can be used to set the state of
        a run in the API.

        This method will drop this state's `data` if it is not a result type. Only
        results should be sent to the API. Other data is only available locally.
        """
        from prefect.client.schemas.actions import StateCreate
        from prefect.results import BaseResult

        return StateCreate(
            type=self.type,
            name=self.name,
            message=self.message,
            data=self.data if isinstance(self.data, BaseResult) else None,
            state_details=self.state_details,
        )

    @validator("name", always=True)
    def default_name_from_type(cls, v, *, values, **kwargs):
        """If a name is not provided, use the type"""

        # if `type` is not in `values` it means the `type` didn't pass its own
        # validation check and an error will be raised after this function is called
        if v is None and values.get("type"):
            v = " ".join([v.capitalize() for v in values.get("type").value.split("_")])
        return v

    @root_validator
    def default_scheduled_start_time(cls, values):
        """
        TODO: This should throw an error instead of setting a default but is out of
              scope for https://github.com/PrefectHQ/orion/pull/174/ and can be rolled
              into work refactoring state initialization
        """
        if values.get("type") == StateType.SCHEDULED:
            state_details = values.setdefault(
                "state_details", cls.__fields__["state_details"].get_default()
            )
            if not state_details.scheduled_time:
                state_details.scheduled_time = pendulum.now("utc")
        return values

    def is_scheduled(self) -> bool:
        return self.type == StateType.SCHEDULED

    def is_pending(self) -> bool:
        return self.type == StateType.PENDING

    def is_running(self) -> bool:
        return self.type == StateType.RUNNING

    def is_completed(self) -> bool:
        return self.type == StateType.COMPLETED

    def is_failed(self) -> bool:
        return self.type == StateType.FAILED

    def is_crashed(self) -> bool:
        return self.type == StateType.CRASHED

    def is_cancelled(self) -> bool:
        return self.type == StateType.CANCELLED

    def is_cancelling(self) -> bool:
        return self.type == StateType.CANCELLING

    def is_final(self) -> bool:
        return self.type in {
            StateType.CANCELLED,
            StateType.FAILED,
            StateType.COMPLETED,
            StateType.CRASHED,
        }

    def is_paused(self) -> bool:
        return self.type == StateType.PAUSED

    def copy(self, *, update: dict = None, reset_fields: bool = False, **kwargs):
        """
        Copying API models should return an object that could be inserted into the
        database again. The 'timestamp' is reset using the default factory.
        """
        update = update or {}
        update.setdefault("timestamp", self.__fields__["timestamp"].get_default())
        return super().copy(reset_fields=reset_fields, update=update, **kwargs)

    def __repr__(self) -> str:
        """
        Generates a complete state representation appropriate for introspection
        and debugging, including the result:

        `MyCompletedState(message="my message", type=COMPLETED, result=...)`
        """
        from prefect.deprecated.data_documents import DataDocument

        if isinstance(self.data, DataDocument):
            result = self.data.decode()
        else:
            result = self.data

        display = dict(
            message=repr(self.message),
            type=str(self.type.value),
            result=repr(result),
        )

        return f"{self.name}({', '.join(f'{k}={v}' for k, v in display.items())})"

    def __str__(self) -> str:
        """
        Generates a simple state representation appropriate for logging:

        `MyCompletedState("my message", type=COMPLETED)`
        """

        display = []

        if self.message:
            display.append(repr(self.message))

        if self.type.value.lower() != self.name.lower():
            display.append(f"type={self.type.value}")

        return f"{self.name}({', '.join(display)})"

    def __hash__(self) -> int:
        return hash(
            (
                getattr(self.state_details, "flow_run_id", None),
                getattr(self.state_details, "task_run_id", None),
                self.timestamp,
                self.type,
            )
        )


class FlowRunPolicy(PrefectBaseModel):
    """Defines of how a flow run should be orchestrated."""

    max_retries: int = Field(
        default=0,
        description=(
            "The maximum number of retries. Field is not used. Please use `retries`"
            " instead."
        ),
        deprecated=True,
    )
    retry_delay_seconds: float = Field(
        default=0,
        description=(
            "The delay between retries. Field is not used. Please use `retry_delay`"
            " instead."
        ),
        deprecated=True,
    )
    retries: Optional[int] = Field(default=None, description="The number of retries.")
    retry_delay: Optional[int] = Field(
        default=None, description="The delay time between retries, in seconds."
    )
    pause_keys: Optional[set] = Field(
        default_factory=set, description="Tracks pauses this run has observed."
    )
    resuming: Optional[bool] = Field(
        default=False, description="Indicates if this run is resuming from a pause."
    )

    @root_validator
    def populate_deprecated_fields(cls, values):
        """
        If deprecated fields are provided, populate the corresponding new fields
        to preserve orchestration behavior.
        """
        if not values.get("retries", None) and values.get("max_retries", 0) != 0:
            values["retries"] = values["max_retries"]
        if (
            not values.get("retry_delay", None)
            and values.get("retry_delay_seconds", 0) != 0
        ):
            values["retry_delay"] = values["retry_delay_seconds"]
        return values


class FlowRun(ObjectBaseModel):
    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description=(
            "The name of the flow run. Defaults to a random slug if not specified."
        ),
        example="my-flow-run",
    )
    flow_id: UUID = Field(default=..., description="The id of the flow being run.")
    state_id: Optional[UUID] = Field(
        default=None, description="The id of the flow run's current state."
    )
    deployment_id: Optional[UUID] = Field(
        default=None,
        description=(
            "The id of the deployment associated with this flow run, if available."
        ),
    )
    work_queue_name: Optional[str] = Field(
        default=None, description="The work queue that handled this flow run."
    )
    flow_version: Optional[str] = Field(
        default=None,
        description="The version of the flow executed in this flow run.",
        example="1.0",
    )
    parameters: dict = Field(
        default_factory=dict, description="Parameters for the flow run."
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        description=(
            "An optional idempotency key for the flow run. Used to ensure the same flow"
            " run is not created multiple times."
        ),
    )
    context: dict = Field(
        default_factory=dict,
        description="Additional context for the flow run.",
        example={"my_var": "my_val"},
    )
    empirical_policy: FlowRunPolicy = Field(
        default_factory=FlowRunPolicy,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags on the flow run",
        example=["tag-1", "tag-2"],
    )
    parent_task_run_id: Optional[UUID] = Field(
        default=None,
        description=(
            "If the flow run is a subflow, the id of the 'dummy' task in the parent"
            " flow used to track subflow state."
        ),
    )
    run_count: int = Field(
        default=0, description="The number of times the flow run was executed."
    )
    expected_start_time: Optional[DateTimeTZ] = Field(
        default=None,
        description="The flow run's expected start time.",
    )
    next_scheduled_start_time: Optional[DateTimeTZ] = Field(
        default=None,
        description="The next time the flow run is scheduled to start.",
    )
    start_time: Optional[DateTimeTZ] = Field(
        default=None, description="The actual start time."
    )
    end_time: Optional[DateTimeTZ] = Field(
        default=None, description="The actual end time."
    )
    total_run_time: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description=(
            "Total run time. If the flow run was executed multiple times, the time of"
            " each run will be summed."
        ),
    )
    estimated_run_time: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description="A real-time estimate of the total run time.",
    )
    estimated_start_time_delta: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description="The difference between actual and expected start time.",
    )
    auto_scheduled: bool = Field(
        default=False,
        description="Whether or not the flow run was automatically scheduled.",
    )
    infrastructure_document_id: Optional[UUID] = Field(
        default=None,
        description="The block document defining infrastructure to use this flow run.",
    )
    infrastructure_pid: Optional[str] = Field(
        default=None,
        description="The id of the flow run as returned by an infrastructure block.",
    )
    created_by: Optional[CreatedBy] = Field(
        default=None,
        description="Optional information about the creator of this flow run.",
    )
    work_queue_id: Optional[UUID] = Field(
        default=None, description="The id of the run's work pool queue."
    )

    work_pool_id: Optional[UUID] = Field(
        description="The work pool with which the queue is associated."
    )
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the flow run's work pool.",
        example="my-work-pool",
    )
    state: Optional[State] = Field(
        default=None,
        description="The state of the flow run.",
        example=State(type=StateType.COMPLETED),
    )

    def __eq__(self, other: Any) -> bool:
        """
        Check for "equality" to another flow run schema

        Estimates times are rolling and will always change with repeated queries for
        a flow run so we ignore them during equality checks.
        """
        if isinstance(other, FlowRun):
            exclude_fields = {"estimated_run_time", "estimated_start_time_delta"}
            return self.dict(exclude=exclude_fields) == other.dict(
                exclude=exclude_fields
            )
        return super().__eq__(other)

    @validator("name", pre=True)
    def set_default_name(cls, name):
        return name or generate_slug(2)

    # These are server-side optimizations and should not be present on client models
    # TODO: Deprecate these fields

    state_type: Optional[StateType] = Field(
        default=None, description="The type of the current flow run state."
    )
    state_name: Optional[str] = Field(
        default=None, description="The name of the current flow run state."
    )


class TaskRunPolicy(PrefectBaseModel):
    """Defines of how a task run should retry."""

    max_retries: int = Field(
        default=0,
        description=(
            "The maximum number of retries. Field is not used. Please use `retries`"
            " instead."
        ),
        deprecated=True,
    )
    retry_delay_seconds: float = Field(
        default=0,
        description=(
            "The delay between retries. Field is not used. Please use `retry_delay`"
            " instead."
        ),
        deprecated=True,
    )
    retries: Optional[int] = Field(default=None, description="The number of retries.")
    retry_delay: Union[None, int, List[int]] = Field(
        default=None,
        description="A delay time or list of delay times between retries, in seconds.",
    )
    retry_jitter_factor: Optional[float] = Field(
        default=None, description="Determines the amount a retry should jitter"
    )

    @root_validator
    def populate_deprecated_fields(cls, values):
        """
        If deprecated fields are provided, populate the corresponding new fields
        to preserve orchestration behavior.
        """
        if not values.get("retries", None) and values.get("max_retries", 0) != 0:
            values["retries"] = values["max_retries"]

        if (
            not values.get("retry_delay", None)
            and values.get("retry_delay_seconds", 0) != 0
        ):
            values["retry_delay"] = values["retry_delay_seconds"]

        return values

    @validator("retry_delay")
    def validate_configured_retry_delays(cls, v):
        if isinstance(v, list) and (len(v) > 50):
            raise ValueError("Can not configure more than 50 retry delays per task.")
        return v

    @validator("retry_jitter_factor")
    def validate_jitter_factor(cls, v):
        if v is not None and v < 0:
            raise ValueError("`retry_jitter_factor` must be >= 0.")
        return v


class TaskRunInput(PrefectBaseModel):
    """
    Base class for classes that represent inputs to task runs, which
    could include, constants, parameters, or other task runs.
    """

    # freeze TaskRunInputs to allow them to be placed in sets
    class Config:
        frozen = True

    input_type: str


class TaskRunResult(TaskRunInput):
    """Represents a task run result input to another task run."""

    input_type: Literal["task_run"] = "task_run"
    id: UUID


class Parameter(TaskRunInput):
    """Represents a parameter input to a task run."""

    input_type: Literal["parameter"] = "parameter"
    name: str


class Constant(TaskRunInput):
    """Represents constant input value to a task run."""

    input_type: Literal["constant"] = "constant"
    type: str


class TaskRun(ObjectBaseModel):
    name: str = Field(default_factory=lambda: generate_slug(2), example="my-task-run")
    flow_run_id: UUID = Field(
        default=..., description="The flow run id of the task run."
    )
    task_key: str = Field(
        default=..., description="A unique identifier for the task being run."
    )
    dynamic_key: str = Field(
        default=...,
        description=(
            "A dynamic key used to differentiate between multiple runs of the same task"
            " within the same flow run."
        ),
    )
    cache_key: Optional[str] = Field(
        default=None,
        description=(
            "An optional cache key. If a COMPLETED state associated with this cache key"
            " is found, the cached COMPLETED state will be used instead of executing"
            " the task run."
        ),
    )
    cache_expiration: Optional[DateTimeTZ] = Field(
        default=None, description="Specifies when the cached state should expire."
    )
    task_version: Optional[str] = Field(
        default=None, description="The version of the task being run."
    )
    empirical_policy: TaskRunPolicy = Field(
        default_factory=TaskRunPolicy,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the task run.",
        example=["tag-1", "tag-2"],
    )
    state_id: Optional[UUID] = Field(
        default=None, description="The id of the current task run state."
    )
    task_inputs: Dict[str, List[Union[TaskRunResult, Parameter, Constant]]] = Field(
        default_factory=dict,
        description=(
            "Tracks the source of inputs to a task run. Used for internal bookkeeping."
        ),
    )
    state_type: Optional[StateType] = Field(
        default=None, description="The type of the current task run state."
    )
    state_name: Optional[str] = Field(
        default=None, description="The name of the current task run state."
    )
    run_count: int = Field(
        default=0, description="The number of times the task run has been executed."
    )
    flow_run_run_count: int = Field(
        default=0,
        description=(
            "If the parent flow has retried, this indicates the flow retry this run is"
            " associated with."
        ),
    )
    expected_start_time: Optional[DateTimeTZ] = Field(
        default=None,
        description="The task run's expected start time.",
    )

    # the next scheduled start time will be populated
    # whenever the run is in a scheduled state
    next_scheduled_start_time: Optional[DateTimeTZ] = Field(
        default=None,
        description="The next time the task run is scheduled to start.",
    )
    start_time: Optional[DateTimeTZ] = Field(
        default=None, description="The actual start time."
    )
    end_time: Optional[DateTimeTZ] = Field(
        default=None, description="The actual end time."
    )
    total_run_time: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description=(
            "Total run time. If the task run was executed multiple times, the time of"
            " each run will be summed."
        ),
    )
    estimated_run_time: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description="A real-time estimate of total run time.",
    )
    estimated_start_time_delta: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description="The difference between actual and expected start time.",
    )

    state: Optional[State] = Field(
        default=None,
        description="The state of the flow run.",
        example=State(type=StateType.COMPLETED),
    )

    @validator("name", pre=True)
    def set_default_name(cls, name):
        return name or generate_slug(2)


class Workspace(PrefectBaseModel):
    """
    A Prefect Cloud workspace.

    Expected payload for each workspace returned by the `me/workspaces` route.
    """

    account_id: UUID = Field(..., description="The account id of the workspace.")
    account_name: str = Field(..., description="The account name.")
    account_handle: str = Field(..., description="The account's unique handle.")
    workspace_id: UUID = Field(..., description="The workspace id.")
    workspace_name: str = Field(..., description="The workspace name.")
    workspace_description: str = Field(..., description="Description of the workspace.")
    workspace_handle: str = Field(..., description="The workspace's unique handle.")

    class Config:
        extra = "ignore"

    @property
    def handle(self) -> str:
        """
        The full handle of the workspace as `account_handle` / `workspace_handle`
        """
        return self.account_handle + "/" + self.workspace_handle

    def api_url(self) -> str:
        """
        Generate the API URL for accessing this workspace
        """
        return (
            f"{PREFECT_CLOUD_API_URL.value()}"
            f"/accounts/{self.account_id}"
            f"/workspaces/{self.workspace_id}"
        )

    def __hash__(self):
        return hash(self.handle)


class BlockType(ObjectBaseModel):
    """An ORM representation of a block type"""

    name: str = Field(default=..., description="A block type's name")
    slug: str = Field(default=..., description="A block type's slug")
    logo_url: Optional[HttpUrl] = Field(
        default=None, description="Web URL for the block type's logo"
    )
    documentation_url: Optional[HttpUrl] = Field(
        default=None, description="Web URL for the block type's documentation"
    )
    description: Optional[str] = Field(
        default=None,
        description="A short blurb about the corresponding block's intended use",
    )
    code_example: Optional[str] = Field(
        default=None,
        description="A code snippet demonstrating use of the corresponding block",
    )
    is_protected: bool = Field(
        default=False, description="Protected block types cannot be modified via API."
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_name_with_banned_characters(v)
        return v


class BlockSchema(ObjectBaseModel):
    """A representation of a block schema."""

    checksum: str = Field(default=..., description="The block schema's unique checksum")
    fields: dict = Field(
        default_factory=dict, description="The block schema's field schema"
    )
    block_type_id: Optional[UUID] = Field(default=..., description="A block type ID")
    block_type: Optional[BlockType] = Field(
        default=None, description="The associated block type"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="A list of Block capabilities",
    )
    version: str = Field(
        default=DEFAULT_BLOCK_SCHEMA_VERSION,
        description="Human readable identifier for the block schema",
    )


class BlockDocument(ObjectBaseModel):
    """An ORM representation of a block document."""

    name: Optional[str] = Field(
        default=None,
        description=(
            "The block document's name. Not required for anonymous block documents."
        ),
    )
    data: dict = Field(default_factory=dict, description="The block document's data")
    block_schema_id: UUID = Field(default=..., description="A block schema ID")
    block_schema: Optional[BlockSchema] = Field(
        default=None, description="The associated block schema"
    )
    block_type_id: UUID = Field(default=..., description="A block type ID")
    block_type: Optional[BlockType] = Field(
        default=None, description="The associated block type"
    )
    block_document_references: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Record of the block document's references"
    )
    is_anonymous: bool = Field(
        default=False,
        description=(
            "Whether the block is anonymous (anonymous blocks are usually created by"
            " Prefect automatically)"
        ),
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        # the BlockDocumentCreate subclass allows name=None
        # and will inherit this validator
        if v is not None:
            raise_on_name_with_banned_characters(v)
        return v

    @root_validator
    def validate_name_is_present_if_not_anonymous(cls, values):
        # anonymous blocks may have no name prior to actually being
        # stored in the database
        if not values.get("is_anonymous") and not values.get("name"):
            raise ValueError("Names must be provided for block documents.")
        return values


class Flow(ObjectBaseModel):
    """An ORM representation of flow data."""

    name: str = Field(
        default=..., description="The name of the flow", example="my-flow"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        example=["tag-1", "tag-2"],
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_name_with_banned_characters(v)
        return v


class FlowRunnerSettings(PrefectBaseModel):
    """
    An API schema for passing details about the flow runner.

    This schema is agnostic to the types and configuration provided by clients
    """

    type: Optional[str] = Field(
        default=None,
        description=(
            "The type of the flow runner which can be used by the client for"
            " dispatching."
        ),
    )
    config: Optional[dict] = Field(
        default=None, description="The configuration for the given flow runner type."
    )

    # The following is required for composite compatibility in the ORM

    def __init__(self, type: str = None, config: dict = None, **kwargs) -> None:
        # Pydantic does not support positional arguments so they must be converted to
        # keyword arguments
        super().__init__(type=type, config=config, **kwargs)

    def __composite_values__(self):
        return self.type, self.config


class Deployment(ObjectBaseModel):
    """An ORM representation of deployment data."""

    name: str = Field(default=..., description="The name of the deployment.")
    version: Optional[str] = Field(
        default=None, description="An optional version for the deployment."
    )
    description: Optional[str] = Field(
        default=None, description="A description for the deployment."
    )
    flow_id: UUID = Field(
        default=..., description="The flow id associated with the deployment."
    )
    schedule: Optional[SCHEDULE_TYPES] = Field(
        default=None, description="A schedule for the deployment."
    )
    is_schedule_active: bool = Field(
        default=True, description="Whether or not the deployment schedule is active."
    )
    infra_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to the base infrastructure block at runtime.",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    pull_steps: Optional[List[dict]] = Field(
        default=None,
        description="Pull steps for cloning and running this deployment.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the deployment",
        example=["tag-1", "tag-2"],
    )
    work_queue_name: Optional[str] = Field(
        default=None,
        description=(
            "The work queue for the deployment. If no work queue is set, work will not"
            " be scheduled."
        ),
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The parameter schema of the flow, including defaults.",
    )
    path: Optional[str] = Field(
        default=None,
        description=(
            "The path to the working directory for the workflow, relative to remote"
            " storage or an absolute path."
        ),
    )
    entrypoint: Optional[str] = Field(
        default=None,
        description=(
            "The path to the entrypoint for the workflow, relative to the `path`."
        ),
    )
    manifest_path: Optional[str] = Field(
        default=None,
        description=(
            "The path to the flow's manifest file, relative to the chosen storage."
        ),
    )
    storage_document_id: Optional[UUID] = Field(
        default=None,
        description="The block document defining storage used for this flow.",
    )
    infrastructure_document_id: Optional[UUID] = Field(
        default=None,
        description="The block document defining infrastructure to use for flow runs.",
    )
    created_by: Optional[CreatedBy] = Field(
        default=None,
        description="Optional information about the creator of this deployment.",
    )
    updated_by: Optional[UpdatedBy] = Field(
        default=None,
        description="Optional information about the updater of this deployment.",
    )
    work_queue_id: UUID = Field(
        default=None,
        description=(
            "The id of the work pool queue to which this deployment is assigned."
        ),
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_name_with_banned_characters(v)
        return v


class ConcurrencyLimit(ObjectBaseModel):
    """An ORM representation of a concurrency limit."""

    tag: str = Field(
        default=..., description="A tag the concurrency limit is applied to."
    )
    concurrency_limit: int = Field(default=..., description="The concurrency limit.")
    active_slots: List[UUID] = Field(
        default_factory=list,
        description="A list of active run ids using a concurrency slot",
    )


class BlockSchema(ObjectBaseModel):
    """An ORM representation of a block schema."""

    checksum: str = Field(default=..., description="The block schema's unique checksum")
    fields: dict = Field(
        default_factory=dict, description="The block schema's field schema"
    )
    block_type_id: Optional[UUID] = Field(default=..., description="A block type ID")
    block_type: Optional[BlockType] = Field(
        default=None, description="The associated block type"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="A list of Block capabilities",
    )
    version: str = Field(
        default=DEFAULT_BLOCK_SCHEMA_VERSION,
        description="Human readable identifier for the block schema",
    )


class BlockSchemaReference(ObjectBaseModel):
    """An ORM representation of a block schema reference."""

    parent_block_schema_id: UUID = Field(
        default=..., description="ID of block schema the reference is nested within"
    )
    parent_block_schema: Optional[BlockSchema] = Field(
        default=None, description="The block schema the reference is nested within"
    )
    reference_block_schema_id: UUID = Field(
        default=..., description="ID of the nested block schema"
    )
    reference_block_schema: Optional[BlockSchema] = Field(
        default=None, description="The nested block schema"
    )
    name: str = Field(
        default=..., description="The name that the reference is nested under"
    )


class BlockDocumentReference(ObjectBaseModel):
    """An ORM representation of a block document reference."""

    parent_block_document_id: UUID = Field(
        default=..., description="ID of block document the reference is nested within"
    )
    parent_block_document: Optional[BlockDocument] = Field(
        default=None, description="The block document the reference is nested within"
    )
    reference_block_document_id: UUID = Field(
        default=..., description="ID of the nested block document"
    )
    reference_block_document: Optional[BlockDocument] = Field(
        default=None, description="The nested block document"
    )
    name: str = Field(
        default=..., description="The name that the reference is nested under"
    )

    @root_validator
    def validate_parent_and_ref_are_different(cls, values):
        parent_id = values.get("parent_block_document_id")
        ref_id = values.get("reference_block_document_id")
        if parent_id and ref_id and parent_id == ref_id:
            raise ValueError(
                "`parent_block_document_id` and `reference_block_document_id` cannot be"
                " the same"
            )
        return values


class Configuration(ObjectBaseModel):
    """An ORM representation of account info."""

    key: str = Field(default=..., description="Account info key")
    value: dict = Field(default=..., description="Account info")


class SavedSearchFilter(PrefectBaseModel):
    """A filter for a saved search model. Intended for use by the Prefect UI."""

    object: str = Field(default=..., description="The object over which to filter.")
    property: str = Field(
        default=..., description="The property of the object on which to filter."
    )
    type: str = Field(default=..., description="The type of the property.")
    operation: str = Field(
        default=...,
        description="The operator to apply to the object. For example, `equals`.",
    )
    value: Any = Field(
        default=..., description="A JSON-compatible value for the filter."
    )


class SavedSearch(ObjectBaseModel):
    """An ORM representation of saved search data. Represents a set of filter criteria."""

    name: str = Field(default=..., description="The name of the saved search.")
    filters: List[SavedSearchFilter] = Field(
        default_factory=list, description="The filter set for the saved search."
    )


class Log(ObjectBaseModel):
    """An ORM representation of log data."""

    name: str = Field(default=..., description="The logger name.")
    level: int = Field(default=..., description="The log level.")
    message: str = Field(default=..., description="The log message.")
    timestamp: DateTimeTZ = Field(default=..., description="The log timestamp.")
    flow_run_id: UUID = Field(
        default=..., description="The flow run ID associated with the log."
    )
    task_run_id: Optional[UUID] = Field(
        default=None, description="The task run ID associated with the log."
    )


class QueueFilter(PrefectBaseModel):
    """Filter criteria definition for a work queue."""

    tags: Optional[List[str]] = Field(
        default=None,
        description="Only include flow runs with these tags in the work queue.",
    )
    deployment_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Only include flow runs from these deployments in the work queue.",
    )


class WorkQueue(ObjectBaseModel):
    """An ORM representation of a work queue"""

    name: str = Field(default=..., description="The name of the work queue.")
    description: Optional[str] = Field(
        default="", description="An optional description for the work queue."
    )
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[conint(ge=0)] = Field(
        default=None, description="An optional concurrency limit for the work queue."
    )
    priority: conint(ge=1) = Field(
        default=1,
        description=(
            "The queue's priority. Lower values are higher priority (1 is the highest)."
        ),
    )
    work_pool_name: Optional[str] = Field(default=None)
    # Will be required after a future migration
    work_pool_id: Optional[UUID] = Field(
        description="The work pool with which the queue is associated."
    )
    filter: Optional[QueueFilter] = Field(
        default=None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )
    last_polled: Optional[DateTimeTZ] = Field(
        default=None, description="The last time an agent polled this queue for work."
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_name_with_banned_characters(v)
        return v


class WorkQueueHealthPolicy(PrefectBaseModel):
    maximum_late_runs: Optional[int] = Field(
        default=0,
        description=(
            "The maximum number of late runs in the work queue before it is deemed"
            " unhealthy. Defaults to `0`."
        ),
    )
    maximum_seconds_since_last_polled: Optional[int] = Field(
        default=60,
        description=(
            "The maximum number of time in seconds elapsed since work queue has been"
            " polled before it is deemed unhealthy. Defaults to `60`."
        ),
    )

    def evaluate_health_status(
        self, late_runs_count: int, last_polled: Optional[DateTimeTZ] = None
    ) -> bool:
        """
        Given empirical information about the state of the work queue, evaulate its health status.

        Args:
            late_runs: the count of late runs for the work queue.
            last_polled: the last time the work queue was polled, if available.

        Returns:
            bool: whether or not the work queue is healthy.
        """
        healthy = True
        if (
            self.maximum_late_runs is not None
            and late_runs_count > self.maximum_late_runs
        ):
            healthy = False

        if self.maximum_seconds_since_last_polled is not None:
            if (
                last_polled is None
                or pendulum.now("UTC").diff(last_polled).in_seconds()
                > self.maximum_seconds_since_last_polled
            ):
                healthy = False

        return healthy


class WorkQueueStatusDetail(PrefectBaseModel):
    healthy: bool = Field(..., description="Whether or not the work queue is healthy.")
    late_runs_count: int = Field(
        default=0, description="The number of late flow runs in the work queue."
    )
    last_polled: Optional[DateTimeTZ] = Field(
        default=None, description="The last time an agent polled this queue for work."
    )
    health_check_policy: WorkQueueHealthPolicy = Field(
        ...,
        description=(
            "The policy used to determine whether or not the work queue is healthy."
        ),
    )


class FlowRunNotificationPolicy(ObjectBaseModel):
    """An ORM representation of a flow run notification."""

    is_active: bool = Field(
        default=True, description="Whether the policy is currently active"
    )
    state_names: List[str] = Field(
        default=..., description="The flow run states that trigger notifications"
    )
    tags: List[str] = Field(
        default=...,
        description="The flow run tags that trigger notifications (set [] to disable)",
    )
    block_document_id: UUID = Field(
        default=..., description="The block document ID used for sending notifications"
    )
    message_template: Optional[str] = Field(
        default=None,
        description=(
            "A templatable notification message. Use {braces} to add variables."
            " Valid variables include:"
            f" {listrepr(sorted(FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS), sep=', ')}"
        ),
        example=(
            "Flow run {flow_run_name} with id {flow_run_id} entered state"
            " {flow_run_state_name}."
        ),
    )

    @validator("message_template")
    def validate_message_template_variables(cls, v):
        if v is not None:
            try:
                v.format(**{k: "test" for k in FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS})
            except KeyError as exc:
                raise ValueError(f"Invalid template variable provided: '{exc.args[0]}'")
        return v


class Agent(ObjectBaseModel):
    """An ORM representation of an agent"""

    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description=(
            "The name of the agent. If a name is not provided, it will be"
            " auto-generated."
        ),
    )
    work_queue_id: UUID = Field(
        default=..., description="The work queue with which the agent is associated."
    )
    last_activity_time: Optional[DateTimeTZ] = Field(
        default=None, description="The last time this agent polled for work."
    )


class WorkPool(ObjectBaseModel):
    """An ORM representation of a work pool"""

    name: str = Field(
        description="The name of the work pool.",
    )
    description: Optional[str] = Field(
        default=None, description="A description of the work pool."
    )
    type: str = Field(description="The work pool type.")
    base_job_template: Dict[str, Any] = Field(
        default_factory=dict, description="The work pool's base job template."
    )
    is_paused: bool = Field(
        default=False,
        description="Pausing the work pool stops the delivery of all work.",
    )
    concurrency_limit: Optional[conint(ge=0)] = Field(
        default=None, description="A concurrency limit for the work pool."
    )

    # this required field has a default of None so that the custom validator
    # below will be called and produce a more helpful error message
    default_queue_id: UUID = Field(
        None, description="The id of the pool's default queue."
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_name_with_banned_characters(v)
        return v

    @validator("default_queue_id", always=True)
    def helpful_error_for_missing_default_queue_id(cls, v):
        """
        Default queue ID is required because all pools must have a default queue
        ID, but it represents a circular foreign key relationship to a
        WorkQueue (which can't be created until the work pool exists).
        Therefore, while this field can *technically* be null, it shouldn't be.
        This should only be an issue when creating new pools, as reading
        existing ones will always have this field populated. This custom error
        message will help users understand that they should use the
        `actions.WorkPoolCreate` model in that case.
        """
        if v is None:
            raise ValueError(
                "`default_queue_id` is a required field. If you are "
                "creating a new WorkPool and don't have a queue "
                "ID yet, use the `actions.WorkPoolCreate` model instead."
            )
        return v

    @validator("base_job_template")
    def validate_base_job_template(cls, v):
        if v == dict():
            return v

        job_config = v.get("job_configuration")
        variables = v.get("variables")
        if not (job_config and variables):
            raise ValueError(
                "The `base_job_template` must contain both a `job_configuration` key"
                " and a `variables` key."
            )
        template_variables = set()
        for template in job_config.values():
            # find any variables inside of double curly braces, minus any whitespace
            # e.g. "{{ var1 }}.{{var2}}" -> ["var1", "var2"]
            # convert to json string to handle nested objects and lists
            found_variables = find_placeholders(json.dumps(template))
            template_variables = {placeholder.name for placeholder in found_variables}

        provided_variables = set(variables["properties"].keys())
        if not template_variables.issubset(provided_variables):
            missing_variables = template_variables - provided_variables
            raise ValueError(
                "The variables specified in the job configuration template must be "
                "present as properties in the variables schema. "
                "Your job configuration uses the following undeclared "
                f"variable(s): {' ,'.join(missing_variables)}."
            )
        return v


class Worker(ObjectBaseModel):
    """An ORM representation of a worker"""

    name: str = Field(description="The name of the worker.")
    work_pool_id: UUID = Field(
        description="The work pool with which the queue is associated."
    )
    last_heartbeat_time: datetime.datetime = Field(
        None, description="The last time the worker process sent a heartbeat."
    )


Flow.update_forward_refs()
FlowRun.update_forward_refs()


class Artifact(ObjectBaseModel):
    key: Optional[str] = Field(
        default=None, description="An optional unique reference key for this artifact."
    )
    type: Optional[str] = Field(
        default=None,
        description=(
            "An identifier that describes the shape of the data field. e.g. 'result',"
            " 'table', 'markdown'"
        ),
    )
    description: Optional[str] = Field(
        default=None, description="A markdown-enabled description of the artifact."
    )
    # data will eventually be typed as `Optional[Union[Result, Any]]`
    data: Optional[Union[Dict[str, Any], Any]] = Field(
        default=None,
        description=(
            "Data associated with the artifact, e.g. a result.; structure depends on"
            " the artifact type."
        ),
    )
    metadata_: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "User-defined artifact metadata. Content must be string key and value"
            " pairs."
        ),
    )
    flow_run_id: Optional[UUID] = Field(
        default=None, description="The flow run associated with the artifact."
    )
    task_run_id: Optional[UUID] = Field(
        default=None, description="The task run associated with the artifact."
    )

    @validator("metadata_")
    def validate_metadata_length(cls, v):
        max_metadata_length = 500
        if not isinstance(v, dict):
            return v
        for key in v.keys():
            if len(str(v[key])) > max_metadata_length:
                v[key] = str(v[key])[:max_metadata_length] + "..."
        return v


class ArtifactCollection(ObjectBaseModel):
    key: str = Field(description="An optional unique reference key for this artifact.")
    latest_id: UUID = Field(
        description="The latest artifact ID associated with the key."
    )
    type: Optional[str] = Field(
        default=None,
        description=(
            "An identifier that describes the shape of the data field. e.g. 'result',"
            " 'table', 'markdown'"
        ),
    )
    description: Optional[str] = Field(
        default=None, description="A markdown-enabled description of the artifact."
    )
    data: Optional[Union[Dict[str, Any], Any]] = Field(
        default=None,
        description=(
            "Data associated with the artifact, e.g. a result.; structure depends on"
            " the artifact type."
        ),
    )
    metadata_: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "User-defined artifact metadata. Content must be string key and value"
            " pairs."
        ),
    )
    flow_run_id: Optional[UUID] = Field(
        default=None, description="The flow run associated with the artifact."
    )
    task_run_id: Optional[UUID] = Field(
        default=None, description="The task run associated with the artifact."
    )


class Variable(ObjectBaseModel):
    name: str = Field(
        default=...,
        description="The name of the variable",
        example="my_variable",
        max_length=MAX_VARIABLE_NAME_LENGTH,
    )
    value: str = Field(
        default=...,
        description="The value of the variable",
        example="my-value",
        max_length=MAX_VARIABLE_VALUE_LENGTH,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of variable tags",
        example=["tag-1", "tag-2"],
    )
