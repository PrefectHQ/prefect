import warnings
from copy import copy, deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypeVar, Union
from uuid import UUID

import jsonschema
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


@copy_model_fields
class FlowCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow."""

    name: str = FieldFrom(objects.Flow)
    tags: List[str] = FieldFrom(objects.Flow)


@copy_model_fields
class FlowUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow."""

    tags: List[str] = FieldFrom(objects.Flow)


@experimental_field(
    "work_pool_name",
    group="work_pools",
    when=lambda x: x is not None,
)
@copy_model_fields
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

    name: str = FieldFrom(objects.Deployment)
    flow_id: UUID = FieldFrom(objects.Deployment)
    is_schedule_active: Optional[bool] = FieldFrom(objects.Deployment)
    parameters: Dict[str, Any] = FieldFrom(objects.Deployment)
    tags: List[str] = FieldFrom(objects.Deployment)
    pull_steps: Optional[List[dict]] = FieldFrom(objects.Deployment)

    manifest_path: Optional[str] = FieldFrom(objects.Deployment)
    work_queue_name: Optional[str] = FieldFrom(objects.Deployment)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        example="my-work-pool",
    )
    storage_document_id: Optional[UUID] = FieldFrom(objects.Deployment)
    infrastructure_document_id: Optional[UUID] = FieldFrom(objects.Deployment)
    schedule: Optional[SCHEDULE_TYPES] = FieldFrom(objects.Deployment)
    description: Optional[str] = FieldFrom(objects.Deployment)
    parameter_openapi_schema: Optional[Dict[str, Any]] = FieldFrom(objects.Deployment)
    path: Optional[str] = FieldFrom(objects.Deployment)
    version: Optional[str] = FieldFrom(objects.Deployment)
    entrypoint: Optional[str] = FieldFrom(objects.Deployment)
    infra_overrides: Optional[Dict[str, Any]] = FieldFrom(objects.Deployment)

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
@copy_model_fields
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

    version: Optional[str] = FieldFrom(objects.Deployment)
    schedule: Optional[SCHEDULE_TYPES] = FieldFrom(objects.Deployment)
    description: Optional[str] = FieldFrom(objects.Deployment)
    is_schedule_active: bool = FieldFrom(objects.Deployment)
    parameters: Dict[str, Any] = FieldFrom(objects.Deployment)
    tags: List[str] = FieldFrom(objects.Deployment)
    work_queue_name: Optional[str] = FieldFrom(objects.Deployment)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        example="my-work-pool",
    )
    path: Optional[str] = FieldFrom(objects.Deployment)
    infra_overrides: Optional[Dict[str, Any]] = FieldFrom(objects.Deployment)
    entrypoint: Optional[str] = FieldFrom(objects.Deployment)
    manifest_path: Optional[str] = FieldFrom(objects.Deployment)
    storage_document_id: Optional[UUID] = FieldFrom(objects.Deployment)
    infrastructure_document_id: Optional[UUID] = FieldFrom(objects.Deployment)

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


@copy_model_fields
class FlowRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run."""

    name: Optional[str] = FieldFrom(objects.FlowRun)
    flow_version: Optional[str] = FieldFrom(objects.FlowRun)
    parameters: dict = FieldFrom(objects.FlowRun)
    empirical_policy: objects.FlowRunPolicy = FieldFrom(objects.FlowRun)
    tags: List[str] = FieldFrom(objects.FlowRun)
    infrastructure_pid: Optional[str] = FieldFrom(objects.FlowRun)


@copy_model_fields
class TaskRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a task run"""

    # TaskRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the task run to create"
    )

    name: str = FieldFrom(objects.TaskRun)
    flow_run_id: UUID = FieldFrom(objects.TaskRun)
    task_key: str = FieldFrom(objects.TaskRun)
    dynamic_key: str = FieldFrom(objects.TaskRun)
    cache_key: Optional[str] = FieldFrom(objects.TaskRun)
    cache_expiration: Optional[objects.DateTimeTZ] = FieldFrom(objects.TaskRun)
    task_version: Optional[str] = FieldFrom(objects.TaskRun)
    empirical_policy: objects.TaskRunPolicy = FieldFrom(objects.TaskRun)
    tags: List[str] = FieldFrom(objects.TaskRun)
    task_inputs: Dict[
        str,
        List[
            Union[
                objects.TaskRunResult,
                objects.Parameter,
                objects.Constant,
            ]
        ],
    ] = FieldFrom(objects.TaskRun)


@copy_model_fields
class TaskRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a task run"""

    name: str = FieldFrom(objects.TaskRun)


@copy_model_fields
class FlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: str = FieldFrom(objects.FlowRun)
    flow_id: UUID = FieldFrom(objects.FlowRun)
    deployment_id: Optional[UUID] = FieldFrom(objects.FlowRun)
    flow_version: Optional[str] = FieldFrom(objects.FlowRun)
    parameters: dict = FieldFrom(objects.FlowRun)
    context: dict = FieldFrom(objects.FlowRun)
    parent_task_run_id: Optional[UUID] = FieldFrom(objects.FlowRun)
    infrastructure_document_id: Optional[UUID] = FieldFrom(objects.FlowRun)
    empirical_policy: objects.FlowRunPolicy = FieldFrom(objects.FlowRun)
    tags: List[str] = FieldFrom(objects.FlowRun)
    idempotency_key: Optional[str] = FieldFrom(objects.FlowRun)

    class Config(ActionBaseModel.Config):
        json_dumps = orjson_dumps_extra_compatible


@copy_model_fields
class DeploymentFlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run from a deployment."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = FieldFrom(objects.FlowRun)
    parameters: dict = FieldFrom(objects.FlowRun)
    context: dict = FieldFrom(objects.FlowRun)
    infrastructure_document_id: Optional[UUID] = FieldFrom(objects.FlowRun)
    empirical_policy: objects.FlowRunPolicy = FieldFrom(objects.FlowRun)
    tags: List[str] = FieldFrom(objects.FlowRun)
    idempotency_key: Optional[str] = FieldFrom(objects.FlowRun)
    parent_task_run_id: Optional[UUID] = FieldFrom(objects.FlowRun)


@copy_model_fields
class SavedSearchCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a saved search."""

    name: str = FieldFrom(objects.SavedSearch)
    filters: List[objects.SavedSearchFilter] = FieldFrom(objects.SavedSearch)


@copy_model_fields
class ConcurrencyLimitCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a concurrency limit."""

    tag: str = FieldFrom(objects.ConcurrencyLimit)
    concurrency_limit: int = FieldFrom(objects.ConcurrencyLimit)


@copy_model_fields
class BlockTypeCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block type."""

    name: str = FieldFrom(objects.BlockType)
    slug: str = FieldFrom(objects.BlockType)
    logo_url: Optional[objects.HttpUrl] = FieldFrom(objects.BlockType)
    documentation_url: Optional[objects.HttpUrl] = FieldFrom(objects.BlockType)
    description: Optional[str] = FieldFrom(objects.BlockType)
    code_example: Optional[str] = FieldFrom(objects.BlockType)

    # validators
    _validate_slug_format = validator("slug", allow_reuse=True)(
        validate_block_type_slug
    )


@copy_model_fields
class BlockTypeUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block type."""

    logo_url: Optional[objects.HttpUrl] = FieldFrom(objects.BlockType)
    documentation_url: Optional[objects.HttpUrl] = FieldFrom(objects.BlockType)
    description: Optional[str] = FieldFrom(objects.BlockType)
    code_example: Optional[str] = FieldFrom(objects.BlockType)

    @classmethod
    def updatable_fields(cls) -> set:
        return get_class_fields_only(cls)


@copy_model_fields
class BlockSchemaCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block schema."""

    fields: dict = FieldFrom(objects.BlockSchema)
    block_type_id: Optional[UUID] = FieldFrom(objects.BlockSchema)
    capabilities: List[str] = FieldFrom(objects.BlockSchema)
    version: str = FieldFrom(objects.BlockSchema)


@copy_model_fields
class BlockDocumentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block document."""

    name: Optional[str] = FieldFrom(objects.BlockDocument)
    data: dict = FieldFrom(objects.BlockDocument)
    block_schema_id: UUID = FieldFrom(objects.BlockDocument)
    block_type_id: UUID = FieldFrom(objects.BlockDocument)
    is_anonymous: bool = FieldFrom(objects.BlockDocument)

    _validate_name_format = validator("name", allow_reuse=True)(
        validate_block_document_name
    )

    @root_validator
    def validate_name_is_present_if_not_anonymous(cls, values):
        # TODO: We should find an elegant way to reuse this logic from the origin model
        if not values.get("is_anonymous") and not values.get("name"):
            raise ValueError("Names must be provided for block documents.")
        return values


@copy_model_fields
class BlockDocumentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block document."""

    block_schema_id: Optional[UUID] = Field(
        default=None, description="A block schema ID"
    )
    data: dict = FieldFrom(objects.BlockDocument)
    merge_existing_data: bool = True


@copy_model_fields
class BlockDocumentReferenceCreate(ActionBaseModel):
    """Data used to create block document reference."""

    id: UUID = FieldFrom(objects.BlockDocumentReference)
    parent_block_document_id: UUID = FieldFrom(objects.BlockDocumentReference)
    reference_block_document_id: UUID = FieldFrom(objects.BlockDocumentReference)
    name: str = FieldFrom(objects.BlockDocumentReference)


@copy_model_fields
class LogCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a log."""

    name: str = FieldFrom(objects.Log)
    level: int = FieldFrom(objects.Log)
    message: str = FieldFrom(objects.Log)
    timestamp: objects.DateTimeTZ = FieldFrom(objects.Log)
    flow_run_id: UUID = FieldFrom(objects.Log)
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
