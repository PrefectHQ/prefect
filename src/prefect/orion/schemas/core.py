"""
Full schemas of Orion API objects.
"""
import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import Field, HttpUrl, root_validator, validator
from typing_extensions import Literal

import prefect.orion.database
import prefect.orion.schemas as schemas
from prefect.exceptions import InvalidNameError
from prefect.orion.utilities.names import generate_slug, obfuscate_string
from prefect.orion.utilities.schemas import DateTimeTZ, ORMBaseModel, PrefectBaseModel
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict, listrepr

INVALID_CHARACTERS = ["/", "%", "&", ">", "<"]

FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS = [
    "flow_run_notification_policy_id",
    "flow_id",
    "flow_name",
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


class Flow(ORMBaseModel):
    """An ORM representation of flow data."""

    name: str = Field(..., description="The name of the flow", example="my-flow")
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

    type: str = Field(
        None,
        description="The type of the flow runner which can be used by the client for dispatching.",
    )
    config: dict = Field(
        None, description="The configuration for the given flow runner type."
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
        0,
        description="The maximum number of retries. Field is not used. Please use `retries` instead.",
        deprecated=True,
    )
    retry_delay_seconds: float = Field(
        0,
        description="The delay between retries. Field is not used. Please use `retry_delay` instead.",
        deprecated=True,
    )

    retries: Optional[int] = Field(None, description="The number of retries.")
    retry_delay: Optional[int] = Field(
        None, description="The delay time between retries, in seconds."
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
    flow_id: UUID = Field(..., description="The id of the flow being run.")
    state_id: UUID = Field(None, description="The id of the flow run's current state.")
    deployment_id: UUID = Field(
        None,
        description="The id of the deployment associated with this flow run, if available.",
    )
    work_queue_name: str = Field(
        None, description="The work queue that handled this flow run."
    )
    flow_version: str = Field(
        None,
        description="The version of the flow executed in this flow run.",
        example="1.0",
    )
    parameters: dict = Field(
        default_factory=dict, description="Parameters for the flow run."
    )
    idempotency_key: str = Field(
        None,
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
    parent_task_run_id: UUID = Field(
        None,
        description="If the flow run is a subflow, the id of the 'dummy' task in the parent flow used to track subflow state.",
    )

    state_type: schemas.states.StateType = Field(
        None, description="The type of the current flow run state."
    )
    state_name: str = Field(None, description="The name of the current flow run state.")

    run_count: int = Field(
        0, description="The number of times the flow run was executed."
    )

    expected_start_time: DateTimeTZ = Field(
        None,
        description="The flow run's expected start time.",
    )

    next_scheduled_start_time: DateTimeTZ = Field(
        None,
        description="The next time the flow run is scheduled to start.",
    )
    start_time: DateTimeTZ = Field(None, description="The actual start time.")
    end_time: DateTimeTZ = Field(None, description="The actual end time.")
    total_run_time: datetime.timedelta = Field(
        datetime.timedelta(0),
        description="Total run time. If the flow run was executed multiple times, the time of each run will be summed.",
    )
    estimated_run_time: datetime.timedelta = Field(
        datetime.timedelta(0), description="A real-time estimate of the total run time."
    )
    estimated_start_time_delta: datetime.timedelta = Field(
        datetime.timedelta(0),
        description="The difference between actual and expected start time.",
    )
    auto_scheduled: bool = Field(
        False, description="Whether or not the flow run was automatically scheduled."
    )
    infrastructure_document_id: Optional[UUID] = Field(
        None,
        description="The block document defining infrastructure to use this flow run.",
    )

    # relationships
    # flow: Flow = None
    # task_runs: List["TaskRun"] = Field(default_factory=list)
    state: schemas.states.State = Field(
        None, description="The current state of the flow run."
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
        0,
        description="The maximum number of retries. Field is not used. Please use `retries` instead.",
        deprecated=True,
    )
    retry_delay_seconds: float = Field(
        0,
        description="The delay between retries. Field is not used. Please use `retry_delay` instead.",
        deprecated=True,
    )

    retries: Optional[int] = Field(None, description="The number of retries.")
    retry_delay: Optional[int] = Field(
        None, description="The delay time between retries, in seconds."
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
    flow_run_id: UUID = Field(..., description="The flow run id of the task run.")
    task_key: str = Field(
        ..., description="A unique identifier for the task being run."
    )
    dynamic_key: str = Field(
        ...,
        description="A dynamic key used to differentiate between multiple runs of the same task within the same flow run.",
    )
    cache_key: str = Field(
        None,
        description="An optional cache key. If a COMPLETED state associated with this cache key is found, the cached COMPLETED state will be used instead of executing the task run.",
    )
    cache_expiration: DateTimeTZ = Field(
        None, description="Specifies when the cached state should expire."
    )
    task_version: str = Field(None, description="The version of the task being run.")
    empirical_policy: TaskRunPolicy = Field(
        default_factory=TaskRunPolicy,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the task run.",
        example=["tag-1", "tag-2"],
    )
    state_id: UUID = Field(None, description="The id of the current task run state.")
    task_inputs: Dict[str, List[Union[TaskRunResult, Parameter, Constant]]] = Field(
        default_factory=dict,
        description="Tracks the source of inputs to a task run. Used for internal bookkeeping.",
    )

    state_type: schemas.states.StateType = Field(
        None, description="The type of the current task run state."
    )
    state_name: str = Field(None, description="The name of the current task run state.")
    run_count: int = Field(
        0, description="The number of times the task run has been executed."
    )

    expected_start_time: DateTimeTZ = Field(
        None,
        description="The task run's expected start time.",
    )

    # the next scheduled start time will be populated
    # whenever the run is in a scheduled state
    next_scheduled_start_time: DateTimeTZ = Field(
        None,
        description="The next time the task run is scheduled to start.",
    )
    start_time: DateTimeTZ = Field(None, description="The actual start time.")
    end_time: DateTimeTZ = Field(None, description="The actual end time.")
    total_run_time: datetime.timedelta = Field(
        datetime.timedelta(0),
        description="Total run time. If the task run was executed multiple times, the time of each run will be summed.",
    )
    estimated_run_time: datetime.timedelta = Field(
        datetime.timedelta(0), description="A real-time estimate of total run time."
    )
    estimated_start_time_delta: datetime.timedelta = Field(
        datetime.timedelta(0),
        description="The difference between actual and expected start time.",
    )

    # relationships
    # flow_run: FlowRun = None
    # subflow_runs: List[FlowRun] = Field(default_factory=list)
    state: schemas.states.State = Field(None, description="The current task run state.")

    @validator("name", pre=True)
    def set_name(cls, name):
        return name or generate_slug(2)


class Deployment(ORMBaseModel):
    """An ORM representation of deployment data."""

    name: str = Field(..., description="The name of the deployment.")
    version: Optional[str] = Field(
        None, description="An optional version for the deployment."
    )
    description: str = Field(None, description="A description for the deployment.")
    flow_id: UUID = Field(
        ..., description="The flow id associated with the deployment."
    )
    schedule: schemas.schedules.SCHEDULE_TYPES = Field(
        None, description="A schedule for the deployment."
    )
    is_schedule_active: bool = Field(
        True, description="Whether or not the deployment schedule is active."
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
        None,
        description="The work queue for the deployment. If no work queue is set, work will not be scheduled.",
    )
    parameter_openapi_schema: Dict[str, Any] = Field(
        None,
        description="The parameter schema of the flow, including defaults.",
    )
    path: str = Field(
        None,
        description="The path to the working directory for the workflow, relative to remote storage or an absolute path.",
    )
    entrypoint: str = Field(
        None,
        description="The path to the entrypoint for the workflow, relative to the `path`.",
    )
    manifest_path: str = Field(
        None,
        description="The path to the flow's manifest file, relative to the chosen storage.",
    )
    storage_document_id: Optional[UUID] = Field(
        None,
        description="The block document defining storage used for this flow.",
    )
    infrastructure_document_id: Optional[UUID] = Field(
        None,
        description="The block document defining infrastructure to use for flow runs.",
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_invalid_name(v)
        return v


class ConcurrencyLimit(ORMBaseModel):
    """An ORM representation of a concurrency limit."""

    tag: str = Field(..., description="A tag the concurrency limit is applied to.")
    concurrency_limit: int = Field(..., description="The concurrency limit.")
    active_slots: List[UUID] = Field(
        default_factory=list,
        description="A list of active run ids using a concurrency slot",
    )


class BlockType(ORMBaseModel):
    """An ORM representation of a block type"""

    name: str = Field(..., description="A block type's name")
    slug: str = Field(..., description="A block type's slug")
    logo_url: Optional[HttpUrl] = Field(
        None, description="Web URL for the block type's logo"
    )
    documentation_url: Optional[HttpUrl] = Field(
        None, description="Web URL for the block type's documentation"
    )
    description: Optional[str] = Field(
        None, description="A short blurb about the corresponding block's intended use"
    )
    code_example: Optional[str] = Field(
        None, description="A code snippet demonstrating use of the corresponding block"
    )
    is_protected: bool = Field(
        False, description="Protected block types cannot be modified via API."
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_invalid_name(v)
        return v


class BlockSchema(ORMBaseModel):
    """An ORM representation of a block schema."""

    checksum: str = Field(..., description="The block schema's unique checksum")
    fields: dict = Field(
        default_factory=dict, description="The block schema's field schema"
    )
    block_type_id: Optional[UUID] = Field(..., description="A block type ID")
    block_type: Optional[BlockType] = Field(
        None, description="The associated block type"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="A list of Block capabilities",
    )
    version: str = Field(
        DEFAULT_BLOCK_SCHEMA_VERSION,
        description="Human readable identifier for the block schema",
    )


class BlockSchemaReference(ORMBaseModel):
    """An ORM representation of a block schema reference."""

    parent_block_schema_id: UUID = Field(
        ..., description="ID of block schema the reference is nested within"
    )
    parent_block_schema: Optional[BlockSchema] = Field(
        None, description="The block schema the reference is nested within"
    )
    reference_block_schema_id: UUID = Field(
        ..., description="ID of the nested block schema"
    )
    reference_block_schema: Optional[BlockSchema] = Field(
        None, description="The nested block schema"
    )
    name: str = Field(..., description="The name that the reference is nested under")


class BlockDocument(ORMBaseModel):
    """An ORM representation of a block document."""

    name: Optional[str] = Field(
        None,
        description="The block document's name. Not required for anonymous block documents.",
    )
    data: dict = Field(default_factory=dict, description="The block document's data")
    block_schema_id: UUID = Field(..., description="A block schema ID")
    block_schema: Optional[BlockSchema] = Field(
        None, description="The associated block schema"
    )
    block_type_id: UUID = Field(..., description="A block type ID")
    block_type: Optional[BlockType] = Field(
        None, description="The associated block type"
    )
    block_document_references: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Record of the block document's references"
    )
    is_anonymous: bool = Field(
        False,
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
            for field in orm_block_document.block_schema.fields.get(
                "secret_fields", []
            ):
                key = tuple(field.split("."))
                if flat_data.get(key) is not None:
                    flat_data[key] = obfuscate_string(flat_data[key])
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
        ..., description="ID of block document the reference is nested within"
    )
    parent_block_document: Optional[BlockDocument] = Field(
        None, description="The block document the reference is nested within"
    )
    reference_block_document_id: UUID = Field(
        ..., description="ID of the nested block document"
    )
    reference_block_document: Optional[BlockDocument] = Field(
        None, description="The nested block document"
    )
    name: str = Field(..., description="The name that the reference is nested under")


class Configuration(ORMBaseModel):
    """An ORM representation of account info."""

    key: str = Field(..., description="Account info key")
    value: dict = Field(..., description="Account info")


class SavedSearchFilter(PrefectBaseModel):
    """A filter for a saved search model. Intended for use by the Prefect UI."""

    object: str = Field(..., description="The object over which to filter.")
    property: str = Field(
        ..., description="The property of the object on which to filter."
    )
    type: str = Field(..., description="The type of the property.")
    operation: str = Field(
        ..., description="The operator to apply to the object. For example, `equals`."
    )
    value: Any = Field(..., description="A JSON-compatible value for the filter.")


class SavedSearch(ORMBaseModel):
    """An ORM representation of saved search data. Represents a set of filter criteria."""

    name: str = Field(..., description="The name of the saved search.")
    filters: List[SavedSearchFilter] = Field(
        default_factory=list, description="The filter set for the saved search."
    )


class Log(ORMBaseModel):
    """An ORM representation of log data."""

    name: str = Field(..., description="The logger name.")
    level: int = Field(..., description="The log level.")
    message: str = Field(..., description="The log message.")
    timestamp: DateTimeTZ = Field(..., description="The log timestamp.")
    flow_run_id: UUID = Field(
        ..., description="The flow run ID associated with the log."
    )
    task_run_id: Optional[UUID] = Field(
        None, description="The task run ID associated with the log."
    )


class QueueFilter(PrefectBaseModel):
    """Filter criteria definition for a work queue."""

    tags: Optional[List[str]] = Field(
        None,
        description="Only include flow runs with these tags in the work queue.",
    )
    deployment_ids: Optional[List[UUID]] = Field(
        None,
        description="Only include flow runs from these deployments in the work queue.",
    )


class WorkQueue(ORMBaseModel):
    """An ORM representation of a work queue"""

    name: str = Field(..., description="The name of the work queue.")
    description: Optional[str] = Field(
        "", description="An optional description for the work queue."
    )
    is_paused: bool = Field(
        False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[int] = Field(
        None, description="An optional concurrency limit for the work queue."
    )
    filter: Optional[QueueFilter] = Field(
        None,
        description="Deprecated field: Filter criteria for the work queue.",
        deprecated=True,
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        raise_on_invalid_name(v)
        return v


class FlowRunNotificationPolicy(ORMBaseModel):
    """An ORM representation of a flow run notification."""

    is_active: bool = Field(True, description="Whether the policy is currently active")
    state_names: List[str] = Field(
        ..., description="The flow run states that trigger notifications"
    )
    tags: List[str] = Field(
        ...,
        description="The flow run tags that trigger notifications (set [] to disable)",
    )
    block_document_id: UUID = Field(
        ..., description="The block document ID used for sending notifications"
    )
    message_template: str = Field(
        None,
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
        ..., description="The work queue with which the agent is associated."
    )
    last_activity_time: Optional[DateTimeTZ] = Field(
        None, description="The last time this agent polled for work."
    )


Flow.update_forward_refs()
FlowRun.update_forward_refs()
