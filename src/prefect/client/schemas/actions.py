import warnings
from copy import copy, deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypeVar, Union
from uuid import UUID, uuid4

import jsonschema

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, root_validator, validator
else:
    from pydantic import Field, root_validator, validator

import prefect.client.schemas.objects as objects
from prefect._internal.compatibility.experimental import experimental_field
from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.fields import DateTimeTZ
from prefect._internal.schemas.serializers import orjson_dumps_extra_compatible
from prefect._internal.schemas.transformations import FieldFrom, copy_model_fields
from prefect._internal.schemas.validators import (
    raise_on_name_alphanumeric_dashes_only,
    raise_on_name_alphanumeric_underscores_only,
    return_none_schedule,
)
from prefect.client.schemas.objects import StateDetails, StateType
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.utilities.pydantic import get_class_fields_only

if TYPE_CHECKING:
    from prefect.deprecated.data_documents import DataDocument
    from prefect.results import BaseResult

R = TypeVar("R")


def validate_block_type_slug(value):
    raise_on_name_alphanumeric_dashes_only(value, field_name="Block type slug")
    return value


def validate_block_document_name(value):
    if value is not None:
        raise_on_name_alphanumeric_dashes_only(value, field_name="Block document name")
    return value


def validate_artifact_key(value):
    raise_on_name_alphanumeric_dashes_only(value, field_name="Artifact key")
    return value


def validate_variable_name(value):
    if value is not None:
        raise_on_name_alphanumeric_underscores_only(value, field_name="Variable name")
    return value


class StateCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a new state."""

    type: StateType
    name: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None, example="Run started")
    state_details: StateDetails = Field(default_factory=StateDetails)
    data: Union["BaseResult[R]", "DataDocument[R]", Any] = Field(
        default=None,
    )


class FlowCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow."""

    name: str = Field(
        default=..., description="The name of the flow", example="my-flow"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        example=["tag-1", "tag-2"],
    )


class FlowUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow."""

    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        example=["tag-1", "tag-2"],
    )


class DeploymentScheduleCreate(ActionBaseModel):
    schedule: SCHEDULE_TYPES = Field(
        default=..., description="The schedule for the deployment."
    )
    active: bool = Field(
        default=True, description="Whether or not the schedule is active."
    )


class DeploymentScheduleUpdate(ActionBaseModel):
    schedule: Optional[SCHEDULE_TYPES] = Field(
        default=None, description="The schedule for the deployment."
    )
    active: bool = Field(
        default=True, description="Whether or not the schedule is active."
    )


@experimental_field(
    "work_pool_name",
    group="work_pools",
    when=lambda x: x is not None,
)
class DeploymentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a deployment."""

    @root_validator(pre=True)
    def remove_old_fields(cls, values):
        # 2.7.7 removed worker_pool_queue_id in lieu of worker_pool_name and
        # worker_pool_queue_name. Those fields were later renamed to work_pool_name
        # and work_queue_name. This validator removes old fields provided
        # by older clients to avoid 422 errors.
        values_copy = copy(values)
        worker_pool_queue_id = values_copy.pop("worker_pool_queue_id", None)
        worker_pool_name = values_copy.pop("worker_pool_name", None)
        worker_pool_queue_name = values_copy.pop("worker_pool_queue_name", None)
        work_pool_queue_name = values_copy.pop("work_pool_queue_name", None)
        if worker_pool_queue_id:
            warnings.warn(
                (
                    "`worker_pool_queue_id` is no longer supported for creating "
                    "deployments. Please use `work_pool_name` and "
                    "`work_queue_name` instead."
                ),
                UserWarning,
            )
        if worker_pool_name or worker_pool_queue_name or work_pool_queue_name:
            warnings.warn(
                (
                    "`worker_pool_name`, `worker_pool_queue_name`, and "
                    "`work_pool_name` are"
                    "no longer supported for creating "
                    "deployments. Please use `work_pool_name` and "
                    "`work_queue_name` instead."
                ),
                UserWarning,
            )
        return values_copy

    name: str = Field(..., description="The name of the deployment.")
    flow_id: UUID = Field(..., description="The ID of the flow to deploy.")
    is_schedule_active: Optional[bool] = Field(None)
    paused: Optional[bool] = Field(None)
    schedules: List[DeploymentScheduleCreate] = Field(
        default_factory=list,
        description="A list of schedules for the deployment.",
    )
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(None)
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = Field(default_factory=list)
    pull_steps: Optional[List[dict]] = Field(None)

    manifest_path: Optional[str] = Field(None)
    work_queue_name: Optional[str] = Field(None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        example="my-work-pool",
    )
    storage_document_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    schedule: Optional[SCHEDULE_TYPES] = Field(None)
    description: Optional[str] = Field(None)
    path: Optional[str] = Field(None)
    version: Optional[str] = Field(None)
    entrypoint: Optional[str] = Field(None)
    infra_overrides: Optional[Dict[str, Any]] = Field(None)

    def check_valid_configuration(self, base_job_template: dict):
        """Check that the combination of base_job_template defaults
        and infra_overrides conforms to the specified schema.
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

            jsonschema.validate(self.infra_overrides, variables_schema)


@experimental_field(
    "work_pool_name",
    group="work_pools",
    when=lambda x: x is not None,
)
class DeploymentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a deployment."""

    @root_validator(pre=True)
    def remove_old_fields(cls, values):
        # 2.7.7 removed worker_pool_queue_id in lieu of worker_pool_name and
        # worker_pool_queue_name. Those fields were later renamed to work_pool_name
        # and work_queue_name. This validator removes old fields provided
        # by older clients to avoid 422 errors.
        values_copy = copy(values)
        worker_pool_queue_id = values_copy.pop("worker_pool_queue_id", None)
        worker_pool_name = values_copy.pop("worker_pool_name", None)
        worker_pool_queue_name = values_copy.pop("worker_pool_queue_name", None)
        work_pool_queue_name = values_copy.pop("work_pool_queue_name", None)
        if worker_pool_queue_id:
            warnings.warn(
                (
                    "`worker_pool_queue_id` is no longer supported for updating "
                    "deployments. Please use `work_pool_name` and "
                    "`work_queue_name` instead."
                ),
                UserWarning,
            )
        if worker_pool_name or worker_pool_queue_name or work_pool_queue_name:
            warnings.warn(
                (
                    "`worker_pool_name`, `worker_pool_queue_name`, and "
                    "`work_pool_name` are"
                    "no longer supported for creating "
                    "deployments. Please use `work_pool_name` and "
                    "`work_queue_name` instead."
                ),
                UserWarning,
            )
        return values_copy

    @validator("schedule")
    def validate_none_schedule(cls, v):
        return return_none_schedule(v)

    version: Optional[str] = Field(None)
    schedule: Optional[SCHEDULE_TYPES] = Field(None)
    description: Optional[str] = Field(None)
    is_schedule_active: bool = Field(None)
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = Field(default_factory=list)
    work_queue_name: Optional[str] = Field(None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        example="my-work-pool",
    )
    path: Optional[str] = Field(None)
    infra_overrides: Optional[Dict[str, Any]] = Field(None)
    entrypoint: Optional[str] = Field(None)
    manifest_path: Optional[str] = Field(None)
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
        and infra_overrides conforms to the specified schema.
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
            jsonschema.validate(self.infra_overrides, variables_schema)


class FlowRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run."""

    name: Optional[str] = Field(None)
    flow_version: Optional[str] = Field(None)
    parameters: Optional[Dict[str, Any]] = Field(None)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: List[str] = Field(default_factory=list)
    infrastructure_pid: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(None)


class TaskRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a task run"""

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
    cache_expiration: Optional[objects.DateTimeTZ] = Field(None)
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
    parameters: dict = Field(
        default_factory=dict, description="The parameters for the flow run."
    )
    context: dict = Field(
        default_factory=dict, description="The context for the flow run."
    )
    parent_task_run_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None)

    class Config(ActionBaseModel.Config):
        json_dumps = orjson_dumps_extra_compatible


class DeploymentFlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run from a deployment."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = Field(default=None, description="The name of the flow run.")
    parameters: dict = Field(
        default_factory=dict, description="The parameters for the flow run."
    )
    context: dict = Field(
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
    _validate_slug_format = validator("slug", allow_reuse=True)(
        validate_block_type_slug
    )


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

    fields: dict = Field(
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

    name: Optional[str] = Field(
        default=None, description="The name of the block document"
    )
    data: dict = Field(default_factory=dict, description="The block document's data")
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

    _validate_name_format = validator("name", allow_reuse=True)(
        validate_block_document_name
    )

    @root_validator
    def validate_name_is_present_if_not_anonymous(cls, values):
        # TODO: We should find an elegant way to reuse this logic from the origin model
        if not values.get("is_anonymous") and not values.get("name"):
            raise ValueError("Names must be provided for block documents.")
        return values


class BlockDocumentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block document."""

    block_schema_id: Optional[UUID] = Field(
        default=None, description="A block schema ID"
    )
    data: dict = Field(default_factory=dict, description="The block document's data")
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


@copy_model_fields
class LogCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a log."""

    name: str = FieldFrom(objects.Log)
    level: int = FieldFrom(objects.Log)
    message: str = FieldFrom(objects.Log)
    timestamp: objects.DateTimeTZ = FieldFrom(objects.Log)
    flow_run_id: Optional[UUID] = FieldFrom(objects.Log)
    task_run_id: Optional[UUID] = FieldFrom(objects.Log)


@copy_model_fields
class WorkPoolCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work pool."""

    name: str = FieldFrom(objects.WorkPool)
    description: Optional[str] = FieldFrom(objects.WorkPool)
    type: str = Field(description="The work pool type.", default="prefect-agent")
    base_job_template: Dict[str, Any] = FieldFrom(objects.WorkPool)
    is_paused: bool = FieldFrom(objects.WorkPool)
    concurrency_limit: Optional[int] = FieldFrom(objects.WorkPool)


@copy_model_fields
class WorkPoolUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work pool."""

    description: Optional[str] = FieldFrom(objects.WorkPool)
    is_paused: Optional[bool] = FieldFrom(objects.WorkPool)
    base_job_template: Optional[Dict[str, Any]] = FieldFrom(objects.WorkPool)
    concurrency_limit: Optional[int] = FieldFrom(objects.WorkPool)


@copy_model_fields
class WorkQueueCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work queue."""

    name: str = FieldFrom(objects.WorkQueue)
    description: Optional[str] = FieldFrom(objects.WorkQueue)
    is_paused: bool = FieldFrom(objects.WorkQueue)
    concurrency_limit: Optional[int] = FieldFrom(objects.WorkQueue)
    priority: Optional[int] = Field(
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


@copy_model_fields
class WorkQueueUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work queue."""

    name: str = FieldFrom(objects.WorkQueue)
    description: Optional[str] = FieldFrom(objects.WorkQueue)
    is_paused: bool = FieldFrom(objects.WorkQueue)
    concurrency_limit: Optional[int] = FieldFrom(objects.WorkQueue)
    priority: Optional[int] = FieldFrom(objects.WorkQueue)
    last_polled: Optional[DateTimeTZ] = FieldFrom(objects.WorkQueue)

    # DEPRECATED

    filter: Optional[objects.QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )


@copy_model_fields
class FlowRunNotificationPolicyCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run notification policy."""

    is_active: bool = FieldFrom(objects.FlowRunNotificationPolicy)
    state_names: List[str] = FieldFrom(objects.FlowRunNotificationPolicy)
    tags: List[str] = FieldFrom(objects.FlowRunNotificationPolicy)
    block_document_id: UUID = FieldFrom(objects.FlowRunNotificationPolicy)
    message_template: Optional[str] = FieldFrom(objects.FlowRunNotificationPolicy)


@copy_model_fields
class FlowRunNotificationPolicyUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run notification policy."""

    is_active: Optional[bool] = FieldFrom(objects.FlowRunNotificationPolicy)
    state_names: Optional[List[str]] = FieldFrom(objects.FlowRunNotificationPolicy)
    tags: Optional[List[str]] = FieldFrom(objects.FlowRunNotificationPolicy)
    block_document_id: Optional[UUID] = FieldFrom(objects.FlowRunNotificationPolicy)
    message_template: Optional[str] = FieldFrom(objects.FlowRunNotificationPolicy)


@copy_model_fields
class ArtifactCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create an artifact."""

    key: Optional[str] = FieldFrom(objects.Artifact)
    type: Optional[str] = FieldFrom(objects.Artifact)
    description: Optional[str] = FieldFrom(objects.Artifact)
    data: Optional[Union[Dict[str, Any], Any]] = FieldFrom(objects.Artifact)
    metadata_: Optional[Dict[str, str]] = FieldFrom(objects.Artifact)
    flow_run_id: Optional[UUID] = FieldFrom(objects.Artifact)
    task_run_id: Optional[UUID] = FieldFrom(objects.Artifact)

    _validate_artifact_format = validator("key", allow_reuse=True)(
        validate_artifact_key
    )


@copy_model_fields
class ArtifactUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update an artifact."""

    data: Optional[Union[Dict[str, Any], Any]] = FieldFrom(objects.Artifact)
    description: Optional[str] = FieldFrom(objects.Artifact)
    metadata_: Optional[Dict[str, str]] = FieldFrom(objects.Artifact)


@copy_model_fields
class VariableCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a Variable."""

    name: str = FieldFrom(objects.Variable)
    value: str = FieldFrom(objects.Variable)
    tags: Optional[List[str]] = FieldFrom(objects.Variable)

    # validators
    _validate_name_format = validator("name", allow_reuse=True)(validate_variable_name)


@copy_model_fields
class VariableUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a Variable."""

    name: Optional[str] = Field(
        default=None,
        description="The name of the variable",
        example="my_variable",
        max_length=objects.MAX_VARIABLE_NAME_LENGTH,
    )
    value: Optional[str] = Field(
        default=None,
        description="The value of the variable",
        example="my-value",
        max_length=objects.MAX_VARIABLE_NAME_LENGTH,
    )
    tags: Optional[List[str]] = FieldFrom(objects.Variable)

    # validators
    _validate_name_format = validator("name", allow_reuse=True)(validate_variable_name)


@copy_model_fields
class GlobalConcurrencyLimitCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a global concurrency limit."""

    name: str = FieldFrom(objects.GlobalConcurrencyLimit)
    limit: int = FieldFrom(objects.GlobalConcurrencyLimit)
    active: Optional[bool] = FieldFrom(objects.GlobalConcurrencyLimit)
    active_slots: Optional[int] = FieldFrom(objects.GlobalConcurrencyLimit)
    slot_decay_per_second: Optional[float] = FieldFrom(objects.GlobalConcurrencyLimit)


@copy_model_fields
class GlobalConcurrencyLimitUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a global concurrency limit."""

    name: Optional[str] = FieldFrom(objects.GlobalConcurrencyLimit)
    limit: Optional[int] = FieldFrom(objects.GlobalConcurrencyLimit)
    active: Optional[bool] = FieldFrom(objects.GlobalConcurrencyLimit)
    active_slots: Optional[int] = FieldFrom(objects.GlobalConcurrencyLimit)
    slot_decay_per_second: Optional[float] = FieldFrom(objects.GlobalConcurrencyLimit)
