"""
Full schemas of Prefect REST API objects.
"""

import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union
from uuid import UUID

import pendulum
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import Literal, Self

from prefect._internal.schemas.validators import (
    get_or_create_run_name,
    list_length_50_or_less,
    raise_on_name_alphanumeric_dashes_only,
    set_run_policy_deprecated_fields,
    validate_cache_key_length,
    validate_default_queue_id_not_none,
    validate_max_metadata_length,
    validate_message_template_variables,
    validate_name_present_on_nonanonymous_blocks,
    validate_not_negative,
    validate_parent_and_ref_diff,
    validate_schedule_max_scheduled_runs,
)
from prefect.server.schemas import schedules, states
from prefect.server.schemas.statuses import WorkPoolStatus
from prefect.server.utilities.schemas.bases import (
    ORMBaseModel,
    PrefectBaseModel,
)
from prefect.settings import PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS
from prefect.types import (
    MAX_VARIABLE_NAME_LENGTH,
    LaxUrl,
    Name,
    NameOrEmpty,
    NonEmptyishName,
    NonNegativeInteger,
    PositiveInteger,
    StrictVariableValue,
)
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict, listrepr
from prefect.utilities.names import generate_slug, obfuscate

if TYPE_CHECKING:
    from prefect.server.database import orm_models


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

DEFAULT_BLOCK_SCHEMA_VERSION = "non-versioned"


class Flow(ORMBaseModel):
    """An ORM representation of flow data."""

    name: Name = Field(
        default=..., description="The name of the flow", examples=["my-flow"]
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )


class FlowRunPolicy(PrefectBaseModel):
    """Defines of how a flow run should retry."""

    # TODO: Determine how to separate between infrastructure and within-process level
    #       retries
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

    @model_validator(mode="before")
    def populate_deprecated_fields(cls, values):
        return set_run_policy_deprecated_fields(values)


class CreatedBy(BaseModel):
    id: Optional[UUID] = Field(
        default=None, description="The id of the creator of the object."
    )
    type: Optional[str] = Field(
        default=None, description="The type of the creator of the object."
    )
    display_value: Optional[str] = Field(
        default=None, description="The display value for the creator."
    )


class UpdatedBy(BaseModel):
    id: Optional[UUID] = Field(
        default=None, description="The id of the updater of the object."
    )
    type: Optional[str] = Field(
        default=None, description="The type of the updater of the object."
    )
    display_value: Optional[str] = Field(
        default=None, description="The display value for the updater."
    )


class FlowRun(ORMBaseModel):
    """An ORM representation of flow run data."""

    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description=(
            "The name of the flow run. Defaults to a random slug if not specified."
        ),
        examples=["my-flow-run"],
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
    deployment_version: Optional[str] = Field(
        default=None,
        description="The version of the deployment associated with this flow run.",
        examples=["1.0"],
    )
    work_queue_name: Optional[str] = Field(
        default=None, description="The work queue that handled this flow run."
    )
    flow_version: Optional[str] = Field(
        default=None,
        description="The version of the flow executed in this flow run.",
        examples=["1.0"],
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the flow run."
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        description=(
            "An optional idempotency key for the flow run. Used to ensure the same flow"
            " run is not created multiple times."
        ),
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the flow run.",
        examples=[{"my_var": "my_value"}],
    )
    empirical_policy: FlowRunPolicy = Field(
        default_factory=FlowRunPolicy,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags on the flow run",
        examples=[["tag-1", "tag-2"]],
    )
    parent_task_run_id: Optional[UUID] = Field(
        default=None,
        description=(
            "If the flow run is a subflow, the id of the 'dummy' task in the parent"
            " flow used to track subflow state."
        ),
    )

    state_type: Optional[states.StateType] = Field(
        default=None, description="The type of the current flow run state."
    )
    state_name: Optional[str] = Field(
        default=None, description="The name of the current flow run state."
    )
    run_count: int = Field(
        default=0, description="The number of times the flow run was executed."
    )
    expected_start_time: Optional[DateTime] = Field(
        default=None,
        description="The flow run's expected start time.",
    )
    next_scheduled_start_time: Optional[DateTime] = Field(
        default=None,
        description="The next time the flow run is scheduled to start.",
    )
    start_time: Optional[DateTime] = Field(
        default=None, description="The actual start time."
    )
    end_time: Optional[DateTime] = Field(
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

    # relationships
    # flow: Flow = None
    # task_runs: List["TaskRun"] = Field(default_factory=list)
    state: Optional[states.State] = Field(
        default=None, description="The current state of the flow run."
    )
    # parent_task_run: "TaskRun" = None

    job_variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Variables used as overrides in the base job template",
    )

    @field_validator("name", mode="before")
    @classmethod
    def set_name(cls, name):
        return get_or_create_run_name(name)

    def __eq__(self, other: Any) -> bool:
        """
        Check for "equality" to another flow run schema

        Estimates times are rolling and will always change with repeated queries for
        a flow run so we ignore them during equality checks.
        """
        if isinstance(other, FlowRun):
            exclude_fields = {"estimated_run_time", "estimated_start_time_delta"}
            return self.model_dump(exclude=exclude_fields) == other.model_dump(
                exclude=exclude_fields
            )
        return super().__eq__(other)


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

    @model_validator(mode="before")
    def populate_deprecated_fields(cls, values):
        return set_run_policy_deprecated_fields(values)

    @field_validator("retry_delay")
    @classmethod
    def validate_configured_retry_delays(cls, v):
        return list_length_50_or_less(v)

    @field_validator("retry_jitter_factor")
    @classmethod
    def validate_jitter_factor(cls, v):
        return validate_not_negative(v)


class TaskRunInput(PrefectBaseModel):
    """
    Base class for classes that represent inputs to task runs, which
    could include, constants, parameters, or other task runs.
    """

    model_config = ConfigDict(frozen=True)

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


class TaskRun(ORMBaseModel):
    """An ORM representation of task run data."""

    name: str = Field(
        default_factory=lambda: generate_slug(2), examples=["my-task-run"]
    )
    flow_run_id: Optional[UUID] = Field(
        default=None, description="The flow run id of the task run."
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
    cache_expiration: Optional[DateTime] = Field(
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
        examples=[["tag-1", "tag-2"]],
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
    state_type: Optional[states.StateType] = Field(
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
    expected_start_time: Optional[DateTime] = Field(
        default=None,
        description="The task run's expected start time.",
    )

    # the next scheduled start time will be populated
    # whenever the run is in a scheduled state
    next_scheduled_start_time: Optional[DateTime] = Field(
        default=None,
        description="The next time the task run is scheduled to start.",
    )
    start_time: Optional[DateTime] = Field(
        default=None, description="The actual start time."
    )
    end_time: Optional[DateTime] = Field(
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

    # relationships
    # flow_run: FlowRun = None
    # subflow_runs: List[FlowRun] = Field(default_factory=list)
    state: Optional[states.State] = Field(
        default=None, description="The current task run state."
    )

    @field_validator("name", mode="before")
    @classmethod
    def set_name(cls, name):
        return get_or_create_run_name(name)

    @field_validator("cache_key")
    @classmethod
    def validate_cache_key(cls, cache_key):
        return validate_cache_key_length(cache_key)


class DeploymentSchedule(ORMBaseModel):
    deployment_id: Optional[UUID] = Field(
        default=None,
        description="The deployment id associated with this schedule.",
    )
    schedule: schedules.SCHEDULE_TYPES = Field(
        default=..., description="The schedule for the deployment."
    )
    active: bool = Field(
        default=True, description="Whether or not the schedule is active."
    )
    max_active_runs: Optional[PositiveInteger] = Field(
        default=None,
        description="The maximum number of active runs for the schedule.",
    )
    max_scheduled_runs: Optional[PositiveInteger] = Field(
        default=None,
        description="The maximum number of scheduled runs for the schedule.",
    )
    catchup: bool = Field(
        default=False,
        description="Whether or not a worker should catch up on Late runs for the schedule.",
    )

    @field_validator("max_scheduled_runs")
    @classmethod
    def validate_max_scheduled_runs(cls, v):
        return validate_schedule_max_scheduled_runs(
            v, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()
        )


class Deployment(ORMBaseModel):
    """An ORM representation of deployment data."""

    model_config = ConfigDict(populate_by_name=True)

    name: NameOrEmpty = Field(default=..., description="The name of the deployment.")
    version: Optional[str] = Field(
        default=None, description="An optional version for the deployment."
    )
    description: Optional[str] = Field(
        default=None, description="A description for the deployment."
    )
    flow_id: UUID = Field(
        default=..., description="The flow id associated with the deployment."
    )
    paused: bool = Field(
        default=False, description="Whether or not the deployment is paused."
    )
    schedules: List[DeploymentSchedule] = Field(
        default_factory=list, description="A list of schedules for the deployment."
    )
    concurrency_limit: Optional[PositiveInteger] = Field(
        default=None, description="The concurrency limit for the deployment."
    )
    job_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to flow run infrastructure at runtime.",
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
        examples=[["tag-1", "tag-2"]],
    )
    work_queue_name: Optional[str] = Field(
        default=None,
        description=(
            "The work queue for the deployment. If no work queue is set, work will not"
            " be scheduled."
        ),
    )
    last_polled: Optional[DateTime] = Field(
        default=None,
        description="The last time the deployment was polled for status updates.",
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
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
    work_queue_id: Optional[UUID] = Field(
        default=None,
        description=(
            "The id of the work pool queue to which this deployment is assigned."
        ),
    )
    enforce_parameter_schema: bool = Field(
        default=True,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )


class ConcurrencyLimit(ORMBaseModel):
    """An ORM representation of a concurrency limit."""

    tag: str = Field(
        default=..., description="A tag the concurrency limit is applied to."
    )
    concurrency_limit: int = Field(default=..., description="The concurrency limit.")
    active_slots: List[UUID] = Field(
        default_factory=list,
        description="A list of active run ids using a concurrency slot",
    )


class ConcurrencyLimitV2(ORMBaseModel):
    """An ORM representation of a v2 concurrency limit."""

    active: bool = Field(
        default=True, description="Whether the concurrency limit is active."
    )
    name: Name = Field(default=..., description="The name of the concurrency limit.")
    limit: int = Field(default=..., description="The concurrency limit.")
    active_slots: int = Field(default=0, description="The number of active slots.")
    denied_slots: int = Field(default=0, description="The number of denied slots.")
    slot_decay_per_second: float = Field(
        default=0,
        description="The decay rate for active slots when used as a rate limit.",
    )
    avg_slot_occupancy_seconds: float = Field(
        default=2.0, description="The average amount of time a slot is occupied."
    )


class BlockType(ORMBaseModel):
    """An ORM representation of a block type"""

    name: Name = Field(default=..., description="A block type's name")
    slug: str = Field(default=..., description="A block type's slug")
    logo_url: Optional[LaxUrl] = Field(  # TODO: make it HttpUrl
        default=None, description="Web URL for the block type's logo"
    )
    documentation_url: Optional[LaxUrl] = Field(  # TODO: make it HttpUrl
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


class BlockSchema(ORMBaseModel):
    """An ORM representation of a block schema."""

    checksum: str = Field(default=..., description="The block schema's unique checksum")
    fields: Dict[str, Any] = Field(
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


class BlockSchemaReference(ORMBaseModel):
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


class BlockDocument(ORMBaseModel):
    """An ORM representation of a block document."""

    name: Optional[Name] = Field(
        default=None,
        description=(
            "The block document's name. Not required for anonymous block documents."
        ),
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="The block document's data"
    )
    block_schema_id: UUID = Field(default=..., description="A block schema ID")
    block_schema: Optional[BlockSchema] = Field(
        default=None, description="The associated block schema"
    )
    block_type_id: UUID = Field(default=..., description="A block type ID")
    block_type_name: Optional[str] = Field(
        default=None, description="The associated block type's name"
    )
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

    @model_validator(mode="before")
    def validate_name_is_present_if_not_anonymous(cls, values):
        return validate_name_present_on_nonanonymous_blocks(values)

    @classmethod
    async def from_orm_model(
        cls: type[Self],
        session,
        orm_block_document: "orm_models.ORMBlockDocument",
        include_secrets: bool = False,
    ) -> Self:
        data = await orm_block_document.decrypt_data(session=session)
        # if secrets are not included, obfuscate them based on the schema's
        # `secret_fields`. Note this walks any nested blocks as well. If the
        # nested blocks were recovered from named blocks, they will already
        # be obfuscated, but if nested fields were hardcoded into the parent
        # blocks data, this is the only opportunity to obfuscate them.
        if not include_secrets:
            flat_data = dict_to_flatdict(data)
            # iterate over the (possibly nested) secret fields
            # and obfuscate their data
            for secret_field in orm_block_document.block_schema.fields.get(
                "secret_fields", []
            ):
                secret_key = tuple(secret_field.split("."))
                if flat_data.get(secret_key) is not None:
                    flat_data[secret_key] = obfuscate(flat_data[secret_key])
                # If a wildcard (*) is in the current secret key path, we take the portion
                # of the path before the wildcard and compare it to the same level of each
                # key. A match means that the field is nested under the secret key and should
                # be obfuscated.
                elif "*" in secret_key:
                    wildcard_index = secret_key.index("*")
                    for data_key in flat_data.keys():
                        if secret_key[0:wildcard_index] == data_key[0:wildcard_index]:
                            flat_data[data_key] = obfuscate(flat_data[data_key])
            data = flatdict_to_dict(flat_data)
        return cls(
            id=orm_block_document.id,
            created=orm_block_document.created,
            updated=orm_block_document.updated,
            name=orm_block_document.name,
            data=data,
            block_schema_id=orm_block_document.block_schema_id,
            block_schema=orm_block_document.block_schema,
            block_type_id=orm_block_document.block_type_id,
            block_type_name=orm_block_document.block_type_name,
            block_type=orm_block_document.block_type,
            is_anonymous=orm_block_document.is_anonymous,
        )


class BlockDocumentReference(ORMBaseModel):
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

    @model_validator(mode="before")
    def validate_parent_and_ref_are_different(cls, values):
        return validate_parent_and_ref_diff(values)


class Configuration(ORMBaseModel):
    """An ORM representation of account info."""

    key: str = Field(default=..., description="Account info key")
    value: Dict[str, Any] = Field(default=..., description="Account info")


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


class SavedSearch(ORMBaseModel):
    """An ORM representation of saved search data. Represents a set of filter criteria."""

    name: str = Field(default=..., description="The name of the saved search.")
    filters: List[SavedSearchFilter] = Field(
        default_factory=list, description="The filter set for the saved search."
    )


class Log(ORMBaseModel):
    """An ORM representation of log data."""

    name: str = Field(default=..., description="The logger name.")
    level: int = Field(default=..., description="The log level.")
    message: str = Field(default=..., description="The log message.")
    timestamp: DateTime = Field(default=..., description="The log timestamp.")
    flow_run_id: Optional[UUID] = Field(
        default=None, description="The flow run ID associated with the log."
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


class WorkQueue(ORMBaseModel):
    """An ORM representation of a work queue"""

    name: Name = Field(default=..., description="The name of the work queue.")
    description: Optional[str] = Field(
        default="", description="An optional description for the work queue."
    )
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(
        default=None, description="An optional concurrency limit for the work queue."
    )
    priority: PositiveInteger = Field(
        default=1,
        description=(
            "The queue's priority. Lower values are higher priority (1 is the highest)."
        ),
    )
    # Will be required after a future migration
    work_pool_id: Optional[UUID] = Field(
        default=None, description="The work pool with which the queue is associated."
    )
    filter: Optional[QueueFilter] = Field(
        default=None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )
    last_polled: Optional[DateTime] = Field(
        default=None, description="The last time an agent polled this queue for work."
    )


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
        self, late_runs_count: int, last_polled: Optional[DateTime] = None
    ) -> bool:
        """
        Given empirical information about the state of the work queue, evaluate its health status.

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
    last_polled: Optional[DateTime] = Field(
        default=None, description="The last time an agent polled this queue for work."
    )
    health_check_policy: WorkQueueHealthPolicy = Field(
        ...,
        description=(
            "The policy used to determine whether or not the work queue is healthy."
        ),
    )


class FlowRunNotificationPolicy(ORMBaseModel):
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
        examples=[
            "Flow run {flow_run_name} with id {flow_run_id} entered state"
            " {flow_run_state_name}."
        ],
    )

    @field_validator("message_template")
    @classmethod
    def validate_message_template_variables(cls, v):
        return validate_message_template_variables(v)


class Agent(ORMBaseModel):
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
    last_activity_time: Optional[DateTime] = Field(
        default=None, description="The last time this agent polled for work."
    )


class WorkPool(ORMBaseModel):
    """An ORM representation of a work pool"""

    name: NonEmptyishName = Field(
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
    concurrency_limit: Optional[NonNegativeInteger] = Field(
        default=None, description="A concurrency limit for the work pool."
    )
    status: Optional[WorkPoolStatus] = Field(
        default=None, description="The current status of the work pool."
    )

    # this required field has a default of None so that the custom validator
    # below will be called and produce a more helpful error message
    default_queue_id: Optional[UUID] = Field(
        None, description="The id of the pool's default queue."
    )

    @field_validator("default_queue_id")
    def helpful_error_for_missing_default_queue_id(cls, v):
        return validate_default_queue_id_not_none(v)

    @classmethod
    def model_validate(
        cls: Type[Self],
        obj: Any,
        *,
        strict: Optional[bool] = None,
        from_attributes: Optional[bool] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> Self:
        parsed: WorkPool = super().model_validate(
            obj, strict=strict, from_attributes=from_attributes, context=context
        )
        if from_attributes:
            if obj.type == "prefect-agent":
                parsed.status = None
        return parsed


class Worker(ORMBaseModel):
    """An ORM representation of a worker"""

    name: str = Field(description="The name of the worker.")
    work_pool_id: UUID = Field(
        description="The work pool with which the queue is associated."
    )
    last_heartbeat_time: datetime.datetime = Field(
        None, description="The last time the worker process sent a heartbeat."
    )
    heartbeat_interval_seconds: Optional[int] = Field(
        default=None,
        description=(
            "The number of seconds to expect between heartbeats sent by the worker."
        ),
    )


Flow.model_rebuild()
FlowRun.model_rebuild()


class Artifact(ORMBaseModel):
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

    @classmethod
    def from_result(cls, data: Any):
        artifact_info = dict()
        if isinstance(data, dict):
            artifact_key = data.pop("artifact_key", None)
            if artifact_key:
                artifact_info["key"] = artifact_key

            artifact_type = data.pop("artifact_type", None)
            if artifact_type:
                artifact_info["type"] = artifact_type

            description = data.pop("artifact_description", None)
            if description:
                artifact_info["description"] = description

        return cls(data=data, **artifact_info)

    @field_validator("metadata_")
    @classmethod
    def validate_metadata_length(cls, v):
        return validate_max_metadata_length(v)


class ArtifactCollection(ORMBaseModel):
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


class Variable(ORMBaseModel):
    name: str = Field(
        default=...,
        description="The name of the variable",
        examples=["my-variable"],
        max_length=MAX_VARIABLE_NAME_LENGTH,
    )
    value: StrictVariableValue = Field(
        default=...,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of variable tags",
        examples=[["tag-1", "tag-2"]],
    )


class FlowRunInput(ORMBaseModel):
    flow_run_id: UUID = Field(description="The flow run ID associated with the input.")
    key: str = Field(description="The key of the input.")
    value: str = Field(description="The value of the input.")
    sender: Optional[str] = Field(default=None, description="The sender of the input.")

    @field_validator("key", check_fields=False)
    @classmethod
    def validate_name_characters(cls, v):
        raise_on_name_alphanumeric_dashes_only(v)
        return v


class CsrfToken(ORMBaseModel):
    token: str = Field(
        default=...,
        description="The CSRF token",
    )
    client: str = Field(
        default=..., description="The client id associated with the CSRF token"
    )
    expiration: DateTime = Field(
        default=..., description="The expiration time of the CSRF token"
    )
