from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypeVar, Union
from uuid import UUID, uuid4

import jsonschema
from pydantic import Field, field_validator, model_validator
from pydantic_extra_types.pendulum_dt import DateTime

import prefect.client.schemas.objects as objects
from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    convert_to_strings,
    remove_old_deployment_fields,
    validate_artifact_key,
    validate_block_document_name,
    validate_block_type_slug,
    validate_message_template_variables,
    validate_name_present_on_nonanonymous_blocks,
    validate_schedule_max_scheduled_runs,
    validate_variable_name,
)
from prefect.client.schemas.objects import (
    StateDetails,
    StateType,
)
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.settings import PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS
from prefect.types import (
    MAX_VARIABLE_NAME_LENGTH,
    Name,
    NonEmptyishName,
    NonNegativeFloat,
    NonNegativeInteger,
    PositiveInteger,
    StrictVariableValue,
)
from prefect.utilities.collections import listrepr
from prefect.utilities.pydantic import get_class_fields_only

if TYPE_CHECKING:
    from prefect.results import BaseResult, ResultRecordMetadata

R = TypeVar("R")


class StateCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a new state."""

    type: StateType
    name: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None, examples=["Run started"])
    state_details: StateDetails = Field(default_factory=StateDetails)
    data: Union["BaseResult[R]", "ResultRecordMetadata", Any] = Field(
        default=None,
    )


class FlowCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow."""

    name: str = Field(
        default=..., description="The name of the flow", examples=["my-flow"]
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )


class FlowUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow."""

    tags: List[str] = Field(
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


class DeploymentScheduleUpdate(ActionBaseModel):
    schedule: Optional[SCHEDULE_TYPES] = Field(
        default=None, description="The schedule for the deployment."
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

    catchup: Optional[bool] = Field(
        default=None,
        description="Whether or not a worker should catch up on Late runs for the schedule.",
    )

    @field_validator("max_scheduled_runs")
    @classmethod
    def validate_max_scheduled_runs(cls, v):
        return validate_schedule_max_scheduled_runs(
            v, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()
        )


class DeploymentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a deployment."""

    @model_validator(mode="before")
    @classmethod
    def remove_old_fields(cls, values):
        return remove_old_deployment_fields(values)

    @field_validator("description", "tags", mode="before")
    @classmethod
    def convert_to_strings(cls, values):
        return convert_to_strings(values)

    name: str = Field(..., description="The name of the deployment.")
    flow_id: UUID = Field(..., description="The ID of the flow to deploy.")
    paused: Optional[bool] = Field(None)
    schedules: List[DeploymentScheduleCreate] = Field(
        default_factory=list,
        description="A list of schedules for the deployment.",
    )
    concurrency_limit: Optional[int] = Field(
        default=None,
        description="The concurrency limit for the deployment.",
    )
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = Field(default_factory=list)
    pull_steps: Optional[List[dict]] = Field(None)

    work_queue_name: Optional[str] = Field(None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    storage_document_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    description: Optional[str] = Field(None)
    path: Optional[str] = Field(None)
    version: Optional[str] = Field(None)
    entrypoint: Optional[str] = Field(None)
    job_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to flow run infrastructure at runtime.",
    )

    def check_valid_configuration(self, base_job_template: dict):
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
    def remove_old_fields(cls, values):
        return remove_old_deployment_fields(values)

    version: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    paused: Optional[bool] = Field(
        default=None, description="Whether or not the deployment is paused."
    )
    schedules: Optional[List[DeploymentScheduleCreate]] = Field(
        default=None,
        description="A list of schedules for the deployment.",
    )
    concurrency_limit: Optional[int] = Field(
        default=None,
        description="The concurrency limit for the deployment.",
    )
    tags: List[str] = Field(default_factory=list)
    work_queue_name: Optional[str] = Field(None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    path: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Overrides to apply to flow run infrastructure at runtime.",
    )
    entrypoint: Optional[str] = Field(None)
    storage_document_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )

    def check_valid_configuration(self, base_job_template: dict):
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


class FlowRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run."""

    name: Optional[str] = Field(None)
    flow_version: Optional[str] = Field(None)
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: List[str] = Field(default_factory=list)
    infrastructure_pid: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(None)


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
    flow_run_id: Optional[UUID] = Field(None)
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
    cache_key: Optional[str] = Field(None)
    cache_expiration: Optional[objects.DateTime] = Field(None)
    task_version: Optional[str] = Field(None)
    empirical_policy: objects.TaskRunPolicy = Field(
        default_factory=objects.TaskRunPolicy,
    )
    tags: List[str] = Field(default_factory=list)
    task_inputs: Dict[
        str,
        List[
            Union[
                objects.TaskRunResult,
                objects.Parameter,
                objects.Constant,
            ]
        ],
    ] = Field(default_factory=dict)


class TaskRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a task run"""

    name: Optional[str] = Field(None)


class FlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = Field(default=None, description="The name of the flow run.")
    flow_id: UUID = Field(default=..., description="The id of the flow being run.")
    deployment_id: Optional[UUID] = Field(None)
    flow_version: Optional[str] = Field(None)
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="The parameters for the flow run."
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="The context for the flow run."
    )
    parent_task_run_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None)


class DeploymentFlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run from a deployment."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = Field(default=None, description="The name of the flow run.")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="The parameters for the flow run."
    )
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description="Whether or not to enforce the parameter schema on this run.",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="The context for the flow run."
    )
    infrastructure_document_id: Optional[UUID] = Field(None)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None)
    parent_task_run_id: Optional[UUID] = Field(None)
    work_queue_name: Optional[str] = Field(None)
    job_variables: Optional[dict] = Field(None)


class SavedSearchCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a saved search."""

    name: str = Field(default=..., description="The name of the saved search.")
    filters: List[objects.SavedSearchFilter] = Field(
        default_factory=list, description="The filter set for the saved search."
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

    active: Optional[bool] = Field(None)
    name: Optional[Name] = Field(None)
    limit: Optional[NonNegativeInteger] = Field(None)
    active_slots: Optional[NonNegativeInteger] = Field(None)
    denied_slots: Optional[NonNegativeInteger] = Field(None)
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(None)


class BlockTypeCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block type."""

    name: str = Field(default=..., description="A block type's name")
    slug: str = Field(default=..., description="A block type's slug")
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

    # validators
    _validate_slug_format = field_validator("slug")(validate_block_type_slug)


class BlockTypeUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block type."""

    logo_url: Optional[objects.HttpUrl] = Field(None)
    documentation_url: Optional[objects.HttpUrl] = Field(None)
    description: Optional[str] = Field(None)
    code_example: Optional[str] = Field(None)

    @classmethod
    def updatable_fields(cls) -> set:
        return get_class_fields_only(cls)


class BlockSchemaCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block schema."""

    fields: Dict[str, Any] = Field(
        default_factory=dict, description="The block schema's field schema"
    )
    block_type_id: Optional[UUID] = Field(None)
    capabilities: List[str] = Field(
        default_factory=list,
        description="A list of Block capabilities",
    )
    version: str = Field(
        default=objects.DEFAULT_BLOCK_SCHEMA_VERSION,
        description="Human readable identifier for the block schema",
    )


class BlockDocumentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block document."""

    name: Optional[Name] = Field(
        default=None, description="The name of the block document"
    )
    data: Dict[str, Any] = Field(
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

    _validate_name_format = field_validator("name")(validate_block_document_name)

    @model_validator(mode="before")
    def validate_name_is_present_if_not_anonymous(cls, values):
        return validate_name_present_on_nonanonymous_blocks(values)


class BlockDocumentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block document."""

    block_schema_id: Optional[UUID] = Field(
        default=None, description="A block schema ID"
    )
    data: Dict[str, Any] = Field(
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
    flow_run_id: Optional[UUID] = Field(None)
    task_run_id: Optional[UUID] = Field(None)


class WorkPoolCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work pool."""

    name: NonEmptyishName = Field(
        description="The name of the work pool.",
    )
    description: Optional[str] = Field(None)
    type: str = Field(
        description="The work pool type.", default="prefect-agent"
    )  # TODO: change default
    base_job_template: Dict[str, Any] = Field(
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


class WorkPoolUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work pool."""

    description: Optional[str] = Field(None)
    is_paused: Optional[bool] = Field(None)
    base_job_template: Optional[Dict[str, Any]] = Field(None)
    concurrency_limit: Optional[int] = Field(None)


class WorkQueueCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work queue."""

    name: str = Field(default=..., description="The name of the work queue.")
    description: Optional[str] = Field(None)
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

    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(None)
    priority: Optional[PositiveInteger] = Field(
        None, description="The queue's priority."
    )
    last_polled: Optional[DateTime] = Field(None)

    # DEPRECATED

    filter: Optional[objects.QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )


class FlowRunNotificationPolicyCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run notification policy."""

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
            f" {listrepr(sorted(objects.FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS), sep=', ')}"
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


class FlowRunNotificationPolicyUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run notification policy."""

    is_active: Optional[bool] = Field(None)
    state_names: Optional[List[str]] = Field(None)
    tags: Optional[List[str]] = Field(None)
    block_document_id: Optional[UUID] = Field(None)
    message_template: Optional[str] = Field(None)


class ArtifactCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create an artifact."""

    key: Optional[str] = Field(None)
    type: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    data: Optional[Union[Dict[str, Any], Any]] = Field(None)
    metadata_: Optional[Dict[str, str]] = Field(None)
    flow_run_id: Optional[UUID] = Field(None)
    task_run_id: Optional[UUID] = Field(None)

    _validate_artifact_format = field_validator("key")(validate_artifact_key)


class ArtifactUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update an artifact."""

    data: Optional[Union[Dict[str, Any], Any]] = Field(None)
    description: Optional[str] = Field(None)
    metadata_: Optional[Dict[str, str]] = Field(None)


class VariableCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a Variable."""

    name: str = Field(
        default=...,
        description="The name of the variable",
        examples=["my_variable"],
        max_length=MAX_VARIABLE_NAME_LENGTH,
    )
    value: StrictVariableValue = Field(
        default=...,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: Optional[List[str]] = Field(default=None)

    # validators
    _validate_name_format = field_validator("name")(validate_variable_name)


class VariableUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a Variable."""

    name: Optional[str] = Field(
        default=None,
        description="The name of the variable",
        examples=["my_variable"],
        max_length=MAX_VARIABLE_NAME_LENGTH,
    )
    value: StrictVariableValue = Field(
        default=None,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: Optional[List[str]] = Field(default=None)

    # validators
    _validate_name_format = field_validator("name")(validate_variable_name)


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

    name: Optional[Name] = Field(None)
    limit: Optional[NonNegativeInteger] = Field(None)
    active: Optional[bool] = Field(None)
    active_slots: Optional[NonNegativeInteger] = Field(None)
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(None)
