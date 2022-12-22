"""
Full schemas of Orion API objects.
"""
import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import pendulum
from pydantic import Field, HttpUrl, conint, root_validator, validator
from typing_extensions import Literal

import prefect.orion.database
import prefect.orion.schemas as schemas
from prefect.exceptions import InvalidNameError
from prefect.orion.utilities.schemas import DateTimeTZ, ORMBaseModel, PrefectBaseModel
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict, listrepr
from prefect.utilities.names import generate_slug, obfuscate, obfuscate_string

INVALID_CHARACTERS = ["/", "%", "&", ">", "<"]

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


def raise_on_invalid_name(name: str) -> None:
    """
    Raise an InvalidNameError if the given name contains any invalid
    characters.
    """
    if any(c in name for c in INVALID_CHARACTERS):
        raise InvalidNameError(
            f"Name {name!r} contains an invalid character. "
            f"Must not contain any of: {INVALID_CHARACTERS}."
        )


class CreatedBy(PrefectBaseModel):
    id: Optional[UUID] = Field(
        default=None, description="The id of the creator of the object."
    )
    type: Optional[str] = Field(
        default=None, description="The type of the creator of the object."
    )
    display_value: Optional[str] = Field(
        default=None, description="The display value for the creator."
    )


class UpdatedBy(PrefectBaseModel):
    id: Optional[UUID] = Field(
        default=None, description="The id of the updater of the object."
    )
    type: Optional[str] = Field(
        default=None, description="The type of the updater of the object."
    )
    display_value: Optional[str] = Field(
        default=None, description="The display value for the updater."
    )


class Flow(ORMBaseModel):
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
        raise_on_invalid_name(v)
        return v


class FlowRunnerSettings(PrefectBaseModel):
    """
    An API schema for passing details about the flow runner.

    This schema is agnostic to the types and configuration provided by clients
    """

    type: Optional[str] = Field(
        default=None,
        description="The type of the flow runner which can be used by the client for dispatching.",
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


class FlowRunPolicy(PrefectBaseModel):
    """Defines of how a flow run should retry."""

    # TODO: Determine how to separate between infrastructure and within-process level
    #       retries
    max_retries: int = Field(
        default=0,
        description="The maximum number of retries. Field is not used. Please use `retries` instead.",
        deprecated=True,
    )
    retry_delay_seconds: float = Field(
        default=0,
        description="The delay between retries. Field is not used. Please use `retry_delay` instead.",
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


class FlowRun(ORMBaseModel):
    """An ORM representation of flow run data."""

    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description="The name of the flow run. Defaults to a random slug if not specified.",
        example="my-flow-run",
    )
    flow_id: UUID = Field(default=..., description="The id of the flow being run.")
    state_id: Optional[UUID] = Field(
        default=None, description="The id of the flow run's current state."
    )
    deployment_id: Optional[UUID] = Field(
        default=None,
        description="The id of the deployment associated with this flow run, if available.",
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
        description="An optional idempotency key for the flow run. Used to ensure the same flow run is not created multiple times.",
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
        description="If the flow run is a subflow, the id of the 'dummy' task in the parent flow used to track subflow state.",
    )

    state_type: Optional[schemas.states.StateType] = Field(
        default=None, description="The type of the current flow run state."
    )
    state_name: Optional[str] = Field(
        default=None, description="The name of the current flow run state."
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
        description="Total run time. If the flow run was executed multiple times, the time of each run will be summed.",
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
    worker_pool_queue_id: Optional[UUID] = Field(
        default=None, description="The id of the run's worker pool queue."
    )

    # relationships
    # flow: Flow = None
    # task_runs: List["TaskRun"] = Field(default_factory=list)
    state: Optional[schemas.states.State] = Field(
        default=None, description="The current state of the flow run."
    )
    # parent_task_run: "TaskRun" = None

    @validator("name", pre=True)
    def set_name(cls, name):
        return name or generate_slug(2)

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


class TaskRunPolicy(PrefectBaseModel):
    """Defines of how a task run should retry."""

    max_retries: int = Field(
        default=0,
        description="The maximum number of retries. Field is not used. Please use `retries` instead.",
        deprecated=True,
    )
    retry_delay_seconds: float = Field(
        default=0,
        description="The delay between retries. Field is not used. Please use `retry_delay` instead.",
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


class TaskRun(ORMBaseModel):
    """An ORM representation of task run data."""

    name: str = Field(default_factory=lambda: generate_slug(2), example="my-task-run")
    flow_run_id: UUID = Field(
        default=..., description="The flow run id of the task run."
    )
    task_key: str = Field(
        default=..., description="A unique identifier for the task being run."
    )
    dynamic_key: str = Field(
        default=...,
        description="A dynamic key used to differentiate between multiple runs of the same task within the same flow run.",
    )
    cache_key: Optional[str] = Field(
        default=None,
        description="An optional cache key. If a COMPLETED state associated with this cache key is found, the cached COMPLETED state will be used instead of executing the task run.",
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
        description="Tracks the source of inputs to a task run. Used for internal bookkeeping.",
    )
    state_type: Optional[schemas.states.StateType] = Field(
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
        description="If the parent flow has retried, this indicates the flow retry this run is associated with.",
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
        description="Total run time. If the task run was executed multiple times, the time of each run will be summed.",
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
    state: Optional[schemas.states.State] = Field(
        default=None, description="The current task run state."
    )

    @validator("name", pre=True)
    def set_name(cls, name):
        return name or generate_slug(2)


class Deployment(ORMBaseModel):
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
    schedule: Optional[schemas.schedules.SCHEDULE_TYPES] = Field(
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
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the deployment",
        example=["tag-1", "tag-2"],
    )
    work_queue_name: Optional[str] = Field(
        default=None,
        description="The work queue for the deployment. If no work queue is set, work will not be scheduled.",
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The parameter schema of the flow, including defaults.",
    )
    path: Optional[str] = Field(
        default=None,
        description="The path to the working directory for the workflow, relative to remote storage or an absolute path.",
    )
    entrypoint: Optional[str] = Field(
        default=None,
        description="The path to the entrypoint for the workflow, relative to the `path`.",
    )
    manifest_path: Optional[str] = Field(
        default=None,
        description="The path to the flow's manifest file, relative to the chosen storage.",
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
    worker_pool_queue_id: UUID = Field(
        default=None,
        description="The id of the worker pool queue to which this deployment is assigned.",
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_invalid_name(v)
        return v


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


class BlockType(ORMBaseModel):
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
        raise_on_invalid_name(v)
        return v


class BlockSchema(ORMBaseModel):
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

    name: Optional[str] = Field(
        default=None,
        description="The block document's name. Not required for anonymous block documents.",
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
        description="Whether the block is anonymous (anonymous blocks are usually created by Prefect automatically)",
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        # the BlockDocumentCreate subclass allows name=None
        # and will inherit this validator
        if v is not None:
            raise_on_invalid_name(v)
        return v

    @root_validator
    def validate_name_is_present_if_not_anonymous(cls, values):
        # anonymous blocks may have no name prior to actually being
        # stored in the database
        if not values.get("is_anonymous") and not values.get("name"):
            raise ValueError("Names must be provided for block documents.")
        return values

    @classmethod
    async def from_orm_model(
        cls,
        session,
        orm_block_document: "prefect.orion.database.orm_models.ORMBlockDocument",
        include_secrets: bool = False,
    ):
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
                    flat_data[secret_key] = obfuscate_string(flat_data[secret_key])
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


class Configuration(ORMBaseModel):
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


class WorkQueue(ORMBaseModel):
    """An ORM representation of a work queue"""

    name: str = Field(default=..., description="The name of the work queue.")
    description: Optional[str] = Field(
        default="", description="An optional description for the work queue."
    )
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[int] = Field(
        default=None, description="An optional concurrency limit for the work queue."
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
        raise_on_invalid_name(v)
        return v


class WorkQueueHealthPolicy(PrefectBaseModel):
    maximum_late_runs: Optional[int] = Field(
        default=0,
        description="The maximum number of late runs in the work queue before it is deemed unhealthy. Defaults to `0`.",
    )
    maximum_seconds_since_last_polled: Optional[int] = Field(
        default=60,
        description="The maximum number of time in seconds elapsed since work queue has been polled before it is deemed unhealthy. Defaults to `60`.",
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
        description="The policy used to determine whether or not the work queue is healthy.",
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
            "A templatable notification message. Use {braces} to add variables. "
            f'Valid variables include: {listrepr(sorted(FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS), sep=", ")}'
        ),
        example="Flow run {flow_run_name} with id {flow_run_id} entered state {flow_run_state_name}.",
    )

    @validator("message_template")
    def validate_message_template_variables(cls, v):
        if v is not None:
            try:
                v.format(**{k: "test" for k in FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS})
            except KeyError as exc:
                raise ValueError(f"Invalid template variable provided: '{exc.args[0]}'")
        return v


class Agent(ORMBaseModel):
    """An ORM representation of an agent"""

    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description="The name of the agent. If a name is not provided, it will be auto-generated.",
    )
    work_queue_id: UUID = Field(
        default=..., description="The work queue with which the agent is associated."
    )
    last_activity_time: Optional[DateTimeTZ] = Field(
        default=None, description="The last time this agent polled for work."
    )


class WorkerPool(ORMBaseModel):
    """An ORM representation of a worker pool"""

    name: str = Field(
        description="The name of the worker pool.",
    )
    description: Optional[str] = Field(
        default=None, description="A description of the worker pool."
    )
    type: Optional[str] = Field(None, description="The worker pool type.")
    base_job_template: Dict[str, Any] = Field(
        default_factory=dict, description="The worker pool's base job template."
    )
    is_paused: bool = Field(
        default=False,
        description="Pausing the worker pool stops the delivery of all work.",
    )
    concurrency_limit: Optional[conint(ge=0)] = Field(
        default=None, description="A concurrency limit for the worker pool."
    )

    # this required field has a default of None so that the custom validator
    # below will be called and produce a more helpful error message
    default_queue_id: UUID = Field(
        None, description="The id of the pool's default queue."
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_invalid_name(v)
        return v

    @validator("default_queue_id", always=True)
    def helpful_error_for_missing_default_queue_id(cls, v):
        """
        Default queue ID is required because all pools must have a default queue
        ID, but it represents a circular foreign key relationship to a
        WorkerPoolQueue (which can't be created until the worker pool exists).
        Therefore, while this field can *technically* be null, it shouldn't be.
        This should only be an issue when creating new pools, as reading
        existing ones will always have this field populated. This custom error
        message will help users understand that they should use the
        `actions.WorkerPoolCreate` model in that case.
        """
        if v is None:
            raise ValueError(
                "`default_queue_id` is a required field. If you are "
                "creating a new WorkerPool and don't have a queue "
                "ID yet, use the `actions.WorkerPoolCreate` model instead."
            )
        return v


class Worker(ORMBaseModel):
    """An ORM representation of a worker"""

    name: str = Field(description="The name of the worker.")
    worker_pool_id: UUID = Field(
        description="The worker pool with which the queue is associated."
    )
    last_heartbeat_time: datetime.datetime = Field(
        None, description="The last time the worker process sent a heartbeat."
    )


class WorkerPoolQueue(ORMBaseModel):
    """An ORM representation of a worker pool queue"""

    worker_pool_id: UUID = Field(
        description="The worker pool with which the queue is associated."
    )
    name: str = Field(
        description="The name of the queue.",
    )
    description: Optional[str] = Field(
        default=None, description="A description of the queue."
    )
    is_paused: bool = Field(
        default=False, description="Pausing the queue stops the delivery of all work."
    )
    concurrency_limit: Optional[conint(ge=0)] = Field(
        default=None, description="A concurrency limit for the queue."
    )
    priority: conint(ge=1) = Field(
        ...,
        description="The queue's priority. Lower values are higher priority (1 is the highest).",
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_invalid_name(v)
        return v


Flow.update_forward_refs()
FlowRun.update_forward_refs()
