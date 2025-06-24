from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar, Union
from uuid import UUID, uuid4

import jsonschema
from pydantic import BaseModel, Field, field_validator, model_validator

import prefect.client.schemas.objects as objects
from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    convert_to_strings,
    remove_old_deployment_fields,
    validate_name_present_on_nonanonymous_blocks,
    validate_schedule_max_scheduled_runs,
)
from prefect.client.schemas.objects import (
    StateDetails,
    StateType,
    WorkPoolStorageConfiguration,
)
from prefect.client.schemas.schedules import (
    SCHEDULE_TYPES,
    CronSchedule,
    IntervalSchedule,
    NoSchedule,
    RRuleSchedule,
)
from prefect.schedules import Schedule
from prefect.settings import PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS
from prefect.types import (
    DateTime,
    KeyValueLabelsField,
    Name,
    NameOrEmpty,
    NonEmptyishName,
    NonNegativeFloat,
    NonNegativeInteger,
    PositiveInteger,
    StrictVariableValue,
)
from prefect.types.names import (
    ArtifactKey,
    BlockDocumentName,
    BlockTypeSlug,
    VariableName,
)
from prefect.utilities.collections import visit_collection
from prefect.utilities.pydantic import get_class_fields_only

if TYPE_CHECKING:
    from prefect._result_records import ResultRecordMetadata

R = TypeVar("R")


class StateCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a new state."""

    type: StateType
    name: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None, examples=["Run started"])
    state_details: StateDetails = Field(default_factory=StateDetails)
    data: Union["ResultRecordMetadata", Any] = Field(
        default=None,
    )


class FlowCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow."""

    name: str = Field(
        default=..., description="The name of the flow", examples=["my-flow"]
    )
    tags: list[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )

    labels: KeyValueLabelsField = Field(default_factory=dict)


class FlowUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow."""

    tags: list[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )


class DeploymentScheduleCreate(ActionBaseModel):
    schedule: SCHEDULE_TYPES = Field(
        default=..., description="The schedule for the deployment."
    )
    active: bool = Field(
        default=True, description="Whether or not the schedule is active."
    )
    max_scheduled_runs: Optional[PositiveInteger] = Field(
        default=None,
        description="The maximum number of scheduled runs for the schedule.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter overrides for the schedule.",
    )
    slug: Optional[str] = Field(
        default=None,
        description="A unique identifier for the schedule.",
    )

    @field_validator("active", mode="wrap")
    @classmethod
    def validate_active(cls, v: Any, handler: Callable[[Any], Any]) -> bool:
        try:
            return handler(v)
        except Exception:
            raise ValueError(
                f"active must be able to be parsed as a boolean, got {v!r} of type {type(v)}"
            )

    @field_validator("max_scheduled_runs")
    @classmethod
    def validate_max_scheduled_runs(cls, v: Optional[int]) -> Optional[int]:
        return validate_schedule_max_scheduled_runs(
            v, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()
        )

    @classmethod
    def from_schedule(cls, schedule: Schedule) -> "DeploymentScheduleCreate":
        if schedule.interval is not None:
            return cls(
                schedule=IntervalSchedule(
                    interval=schedule.interval,
                    timezone=schedule.timezone,
                    anchor_date=schedule.anchor_date,
                ),
                parameters=schedule.parameters,
                active=schedule.active,
                slug=schedule.slug,
            )
        elif schedule.cron is not None:
            return cls(
                schedule=CronSchedule(
                    cron=schedule.cron,
                    timezone=schedule.timezone,
                    day_or=schedule.day_or,
                ),
                parameters=schedule.parameters,
                active=schedule.active,
                slug=schedule.slug,
            )
        elif schedule.rrule is not None:
            return cls(
                schedule=RRuleSchedule(
                    rrule=schedule.rrule,
                    timezone=schedule.timezone,
                ),
                parameters=schedule.parameters,
                active=schedule.active,
                slug=schedule.slug,
            )
        else:
            return cls(
                schedule=NoSchedule(),
            )


class DeploymentScheduleUpdate(ActionBaseModel):
    schedule: Optional[SCHEDULE_TYPES] = Field(
        default=None, description="The schedule for the deployment."
    )
    active: bool = Field(
        default=True, description="Whether or not the schedule is active."
    )

    max_scheduled_runs: Optional[PositiveInteger] = Field(
        default=None,
        description="The maximum number of scheduled runs for the schedule.",
    )
    parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Parameter overrides for the schedule.",
    )
    slug: Optional[str] = Field(
        default=None,
        description="A unique identifier for the schedule.",
    )

    @field_validator("max_scheduled_runs")
    @classmethod
    def validate_max_scheduled_runs(cls, v: Optional[int]) -> Optional[int]:
        return validate_schedule_max_scheduled_runs(
            v, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()
        )


class DeploymentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a deployment."""

    @model_validator(mode="before")
    @classmethod
    def remove_old_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        return remove_old_deployment_fields(values)

    @field_validator("description", "tags", mode="before")
    @classmethod
    def convert_to_strings(
        cls, values: Optional[Union[str, list[str]]]
    ) -> Union[str, list[str]]:
        return convert_to_strings(values)

    name: NameOrEmpty = Field(..., description="The name of the deployment.")
    flow_id: UUID = Field(..., description="The ID of the flow to deploy.")
    paused: Optional[bool] = Field(default=None)
    schedules: list[DeploymentScheduleCreate] = Field(
        default_factory=lambda: [],
        description="A list of schedules for the deployment.",
    )
    concurrency_limit: Optional[int] = Field(
        default=None,
        description="The concurrency limit for the deployment.",
    )
    concurrency_options: Optional[objects.ConcurrencyOptions] = Field(
        default=None,
        description="The concurrency options for the deployment.",
    )
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    parameter_openapi_schema: Optional[dict[str, Any]] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: list[str] = Field(default_factory=list)
    labels: KeyValueLabelsField = Field(default_factory=dict)
    pull_steps: Optional[list[dict[str, Any]]] = Field(default=None)

    work_queue_name: Optional[str] = Field(default=None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    storage_document_id: Optional[UUID] = Field(default=None)
    infrastructure_document_id: Optional[UUID] = Field(default=None)
    description: Optional[str] = Field(default=None)
    path: Optional[str] = Field(default=None)
    entrypoint: Optional[str] = Field(default=None)
    job_variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to flow run infrastructure at runtime.",
    )

    # Versionining
    version: Optional[str] = Field(default=None)
    version_info: Optional[objects.VersionInfo] = Field(
        default=None, description="Version information for the deployment."
    )

    # Branching
    branch: Optional[str] = Field(
        default=None, description="The branch of the deployment."
    )
    base: Optional[UUID] = Field(
        default=None, description="The base deployment of the deployment."
    )
    root: Optional[UUID] = Field(
        default=None, description="The root deployment of the deployment."
    )

    def check_valid_configuration(self, base_job_template: dict[str, Any]) -> None:
        """Check that the combination of base_job_template defaults
        and job_variables conforms to the specified schema.
        """
        variables_schema = deepcopy(base_job_template.get("variables"))

        if variables_schema is not None:
            # jsonschema considers required fields, even if that field has a default,
            # to still be required. To get around this we remove the fields from
            # required if there is a default present.
            required = variables_schema.get("required")
            properties = variables_schema.get("properties")
            if required is not None and properties is not None:
                for k, v in properties.items():
                    if "default" in v and k in required:
                        required.remove(k)

            jsonschema.validate(self.job_variables, variables_schema)


class DeploymentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a deployment."""

    @model_validator(mode="before")
    @classmethod
    def remove_old_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        return remove_old_deployment_fields(values)

    version: Optional[str] = Field(default=None)
    version_info: Optional[objects.VersionInfo] = Field(
        default=None, description="Version information for the deployment."
    )
    description: Optional[str] = Field(default=None)
    parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    paused: Optional[bool] = Field(
        default=None, description="Whether or not the deployment is paused."
    )
    schedules: Optional[list[DeploymentScheduleCreate]] = Field(
        default=None,
        description="A list of schedules for the deployment.",
    )
    concurrency_limit: Optional[int] = Field(
        default=None,
        description="The concurrency limit for the deployment.",
    )
    concurrency_options: Optional[objects.ConcurrencyOptions] = Field(
        default=None,
        description="The concurrency options for the deployment.",
    )
    tags: list[str] = Field(default_factory=list)
    work_queue_name: Optional[str] = Field(default=None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    path: Optional[str] = Field(default=None)
    job_variables: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="Overrides to apply to flow run infrastructure at runtime.",
    )
    entrypoint: Optional[str] = Field(default=None)
    storage_document_id: Optional[UUID] = Field(default=None)
    infrastructure_document_id: Optional[UUID] = Field(default=None)
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    parameter_openapi_schema: Optional[dict[str, Any]] = Field(default_factory=dict)
    pull_steps: Optional[list[dict[str, Any]]] = Field(default=None)

    def check_valid_configuration(self, base_job_template: dict[str, Any]) -> None:
        """Check that the combination of base_job_template defaults
        and job_variables conforms to the specified schema.
        """
        variables_schema = deepcopy(base_job_template.get("variables"))

        if variables_schema is not None:
            # jsonschema considers required fields, even if that field has a default,
            # to still be required. To get around this we remove the fields from
            # required if there is a default present.
            required = variables_schema.get("required")
            properties = variables_schema.get("properties")
            if required is not None and properties is not None:
                for k, v in properties.items():
                    if "default" in v and k in required:
                        required.remove(k)

        if variables_schema is not None:
            jsonschema.validate(self.job_variables, variables_schema)


class DeploymentBranch(ActionBaseModel):
    branch: str = Field(..., description="Name of the branch to create")
    options: objects.DeploymentBranchingOptions = Field(
        default_factory=objects.DeploymentBranchingOptions,
        description="Configuration options for how the deployment should be branched",
    )
    overrides: Optional[DeploymentUpdate] = Field(
        default=None,
        description="Optional values to override in the branched deployment",
    )

    @field_validator("branch")
    @classmethod
    def validate_branch_length(cls, v: str) -> str:
        if len(v.strip()) < 1:
            raise ValueError("Branch name cannot be empty or contain only whitespace")
        return v


class FlowRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run."""

    name: Optional[str] = Field(default=None)
    flow_version: Optional[str] = Field(default=None)
    parameters: Optional[dict[str, Any]] = Field(default_factory=dict)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: list[str] = Field(default_factory=list)
    infrastructure_pid: Optional[str] = Field(default=None)
    job_variables: Optional[dict[str, Any]] = Field(default=None)


class TaskRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a task run"""

    id: Optional[UUID] = Field(None, description="The ID to assign to the task run")
    # TaskRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the task run to create"
    )

    name: Optional[str] = Field(
        default=None,
        description="The name of the task run",
    )
    flow_run_id: Optional[UUID] = Field(default=None)
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
    cache_key: Optional[str] = Field(default=None)
    cache_expiration: Optional[objects.DateTime] = Field(default=None)
    task_version: Optional[str] = Field(default=None)
    empirical_policy: objects.TaskRunPolicy = Field(
        default_factory=objects.TaskRunPolicy,
    )
    tags: list[str] = Field(default_factory=list)
    labels: KeyValueLabelsField = Field(default_factory=dict)
    task_inputs: dict[
        str,
        list[
            Union[
                objects.TaskRunResult,
                objects.FlowRunResult,
                objects.Parameter,
                objects.Constant,
            ]
        ],
    ] = Field(default_factory=dict)


class TaskRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a task run"""

    name: Optional[str] = Field(default=None)


class FlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = Field(default=None, description="The name of the flow run.")
    flow_id: UUID = Field(default=..., description="The id of the flow being run.")
    deployment_id: Optional[UUID] = Field(default=None)
    flow_version: Optional[str] = Field(default=None)
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="The parameters for the flow run."
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="The context for the flow run."
    )
    parent_task_run_id: Optional[UUID] = Field(default=None)
    infrastructure_document_id: Optional[UUID] = Field(default=None)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(default=None)

    labels: KeyValueLabelsField = Field(default_factory=dict)
    work_pool_name: Optional[str] = Field(default=None)
    work_queue_name: Optional[str] = Field(default=None)
    job_variables: Optional[dict[str, Any]] = Field(default=None)


class DeploymentFlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run from a deployment."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = Field(default=None, description="The name of the flow run.")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="The parameters for the flow run."
    )
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description="Whether or not to enforce the parameter schema on this run.",
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="The context for the flow run."
    )
    infrastructure_document_id: Optional[UUID] = Field(default=None)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(default=None)
    parent_task_run_id: Optional[UUID] = Field(default=None)
    work_queue_name: Optional[str] = Field(default=None)
    job_variables: Optional[dict[str, Any]] = Field(default=None)
    labels: KeyValueLabelsField = Field(default_factory=dict)

    @model_validator(mode="before")
    def convert_parameters_to_plain_data(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "parameters" in values:

            def convert_value(value: Any) -> Any:
                if isinstance(value, BaseModel):
                    return value.model_dump(mode="json")
                return value

            values["parameters"] = visit_collection(
                values["parameters"], convert_value, return_data=True
            )
        return values


class SavedSearchCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a saved search."""

    name: str = Field(default=..., description="The name of the saved search.")
    filters: list[objects.SavedSearchFilter] = Field(
        default_factory=lambda: [], description="The filter set for the saved search."
    )


class ConcurrencyLimitCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a concurrency limit."""

    tag: str = Field(
        default=..., description="A tag the concurrency limit is applied to."
    )
    concurrency_limit: int = Field(default=..., description="The concurrency limit.")


class ConcurrencyLimitV2Create(ActionBaseModel):
    """Data used by the Prefect REST API to create a v2 concurrency limit."""

    active: bool = Field(
        default=True, description="Whether the concurrency limit is active."
    )
    name: Name = Field(default=..., description="The name of the concurrency limit.")
    limit: NonNegativeInteger = Field(default=..., description="The concurrency limit.")
    active_slots: NonNegativeInteger = Field(
        default=0, description="The number of active slots."
    )
    denied_slots: NonNegativeInteger = Field(
        default=0, description="The number of denied slots."
    )
    slot_decay_per_second: NonNegativeFloat = Field(
        default=0,
        description="The decay rate for active slots when used as a rate limit.",
    )


class ConcurrencyLimitV2Update(ActionBaseModel):
    """Data used by the Prefect REST API to update a v2 concurrency limit."""

    active: Optional[bool] = Field(default=None)
    name: Optional[Name] = Field(default=None)
    limit: Optional[NonNegativeInteger] = Field(default=None)
    active_slots: Optional[NonNegativeInteger] = Field(default=None)
    denied_slots: Optional[NonNegativeInteger] = Field(default=None)
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(default=None)


class BlockTypeCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block type."""

    name: str = Field(default=..., description="A block type's name")
    slug: BlockTypeSlug = Field(default=..., description="A block type's slug")
    logo_url: Optional[objects.HttpUrl] = Field(
        default=None, description="Web URL for the block type's logo"
    )
    documentation_url: Optional[objects.HttpUrl] = Field(
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


class BlockTypeUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block type."""

    logo_url: Optional[objects.HttpUrl] = Field(default=None)
    documentation_url: Optional[objects.HttpUrl] = Field(default=None)
    description: Optional[str] = Field(default=None)
    code_example: Optional[str] = Field(default=None)

    @classmethod
    def updatable_fields(cls) -> set[str]:
        return get_class_fields_only(cls)


class BlockSchemaCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block schema."""

    fields: dict[str, Any] = Field(
        default_factory=dict, description="The block schema's field schema"
    )
    block_type_id: Optional[UUID] = Field(default=None)
    capabilities: list[str] = Field(
        default_factory=list,
        description="A list of Block capabilities",
    )
    version: str = Field(
        default=objects.DEFAULT_BLOCK_SCHEMA_VERSION,
        description="Human readable identifier for the block schema",
    )


class BlockDocumentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block document."""

    name: Optional[BlockDocumentName] = Field(
        default=None, description="The name of the block document"
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="The block document's data"
    )
    block_schema_id: UUID = Field(
        default=..., description="The block schema ID for the block document"
    )
    block_type_id: UUID = Field(
        default=..., description="The block type ID for the block document"
    )
    is_anonymous: bool = Field(
        default=False,
        description=(
            "Whether the block is anonymous (anonymous blocks are usually created by"
            " Prefect automatically)"
        ),
    )

    @model_validator(mode="before")
    def validate_name_is_present_if_not_anonymous(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        return validate_name_present_on_nonanonymous_blocks(values)


class BlockDocumentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block document."""

    block_schema_id: Optional[UUID] = Field(
        default=None, description="A block schema ID"
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="The block document's data"
    )
    merge_existing_data: bool = Field(
        default=True,
        description="Whether to merge the existing data with the new data or replace it",
    )


class BlockDocumentReferenceCreate(ActionBaseModel):
    """Data used to create block document reference."""

    id: UUID = Field(default_factory=uuid4)
    parent_block_document_id: UUID = Field(
        default=..., description="ID of block document the reference is nested within"
    )
    reference_block_document_id: UUID = Field(
        default=..., description="ID of the nested block document"
    )
    name: str = Field(
        default=..., description="The name that the reference is nested under"
    )


class LogCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a log."""

    name: str = Field(default=..., description="The logger name.")
    level: int = Field(default=..., description="The log level.")
    message: str = Field(default=..., description="The log message.")
    timestamp: DateTime = Field(default=..., description="The log timestamp.")
    flow_run_id: Optional[UUID] = Field(default=None)
    task_run_id: Optional[UUID] = Field(default=None)
    worker_id: Optional[UUID] = Field(default=None)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """
        The worker_id field is only included in logs sent to Prefect Cloud.
        If it's unset, we should not include it in the log payload.
        """
        data = super().model_dump(*args, **kwargs)
        if self.worker_id is None:
            data.pop("worker_id")
        return data


class WorkPoolCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work pool."""

    name: NonEmptyishName = Field(
        description="The name of the work pool.",
    )
    description: Optional[str] = Field(default=None)
    type: str = Field(
        description="The work pool type.", default="prefect-agent"
    )  # TODO: change default
    base_job_template: dict[str, Any] = Field(
        default_factory=dict,
        description="The base job template for the work pool.",
    )
    is_paused: bool = Field(
        default=False,
        description="Whether the work pool is paused.",
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(
        default=None, description="A concurrency limit for the work pool."
    )
    storage_configuration: WorkPoolStorageConfiguration = Field(
        default_factory=WorkPoolStorageConfiguration,
        description="A storage configuration for the work pool.",
    )


class WorkPoolUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work pool."""

    description: Optional[str] = Field(default=None)
    is_paused: Optional[bool] = Field(default=None)
    base_job_template: Optional[dict[str, Any]] = Field(default=None)
    concurrency_limit: Optional[int] = Field(default=None)
    storage_configuration: Optional[WorkPoolStorageConfiguration] = Field(
        default=None,
        description="A storage configuration for the work pool.",
    )


class WorkQueueCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work queue."""

    name: str = Field(default=..., description="The name of the work queue.")
    description: Optional[str] = Field(default=None)
    is_paused: bool = Field(
        default=False,
        description="Whether the work queue is paused.",
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(
        default=None,
        description="A concurrency limit for the work queue.",
    )
    priority: Optional[PositiveInteger] = Field(
        default=None,
        description=(
            "The queue's priority. Lower values are higher priority (1 is the highest)."
        ),
    )

    # DEPRECATED

    filter: Optional[objects.QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )


class WorkQueueUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work queue."""

    name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(default=None)
    priority: Optional[PositiveInteger] = Field(
        None, description="The queue's priority."
    )
    last_polled: Optional[DateTime] = Field(default=None)

    # DEPRECATED

    filter: Optional[objects.QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )


class ArtifactCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create an artifact."""

    key: Optional[ArtifactKey] = Field(default=None)
    type: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    data: Optional[Union[dict[str, Any], Any]] = Field(default=None)
    metadata_: Optional[dict[str, str]] = Field(default=None)
    flow_run_id: Optional[UUID] = Field(default=None)
    task_run_id: Optional[UUID] = Field(default=None)


class ArtifactUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update an artifact."""

    data: Optional[Union[dict[str, Any], Any]] = Field(default=None)
    description: Optional[str] = Field(default=None)
    metadata_: Optional[dict[str, str]] = Field(default=None)


class VariableCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a Variable."""

    name: VariableName = Field(default=...)
    value: StrictVariableValue = Field(
        default=...,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: Optional[list[str]] = Field(default=None)


class VariableUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a Variable."""

    name: Optional[VariableName] = Field(default=None)
    value: StrictVariableValue = Field(
        default=None,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: Optional[list[str]] = Field(default=None)


class GlobalConcurrencyLimitCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a global concurrency limit."""

    name: Name = Field(description="The name of the global concurrency limit.")
    limit: NonNegativeInteger = Field(
        description=(
            "The maximum number of slots that can be occupied on this concurrency"
            " limit."
        )
    )
    active: Optional[bool] = Field(
        default=True,
        description="Whether or not the concurrency limit is in an active state.",
    )
    active_slots: Optional[NonNegativeInteger] = Field(
        default=0,
        description="Number of tasks currently using a concurrency slot.",
    )
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(
        default=0.0,
        description=(
            "Controls the rate at which slots are released when the concurrency limit"
            " is used as a rate limit."
        ),
    )


class GlobalConcurrencyLimitUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a global concurrency limit."""

    name: Optional[Name] = Field(default=None)
    limit: Optional[NonNegativeInteger] = Field(default=None)
    active: Optional[bool] = Field(default=None)
    active_slots: Optional[NonNegativeInteger] = Field(default=None)
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(default=None)
