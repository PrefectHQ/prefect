"""
Reduced schemas for accepting API actions.
"""
import json
import warnings
from copy import copy, deepcopy
from typing import Any, Dict, Generator, List, Optional, Union
from uuid import UUID

import jsonschema

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, root_validator, validator
else:
    from pydantic import Field, root_validator, validator

import prefect.server.schemas as schemas
from prefect._internal.compatibility.experimental import experimental_field
from prefect.server.utilities.schemas import get_class_fields_only
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.server.utilities.schemas.fields import DateTimeTZ
from prefect.server.utilities.schemas.serializers import orjson_dumps_extra_compatible
from prefect.server.utilities.schemas.transformations import (
    FieldFrom,
    copy_model_fields,
)
from prefect.server.utilities.schemas.validators import (
    raise_on_name_alphanumeric_dashes_only,
    raise_on_name_alphanumeric_underscores_only,
)
from prefect.utilities.templating import find_placeholders
from prefect.utilities.validation import (
    validate_schema,
    validate_values_conform_to_schema,
)


def validate_block_type_slug(value):
    raise_on_name_alphanumeric_dashes_only(value, field_name="Block type slug")
    return value


def validate_block_document_name(value):
    if value is not None:
        raise_on_name_alphanumeric_dashes_only(value, field_name="Block document name")
    return value


def validate_artifact_key(value):
    if value is not None:
        raise_on_name_alphanumeric_dashes_only(value, field_name="Artifact key")
    return value


def validate_variable_name(value):
    raise_on_name_alphanumeric_underscores_only(value, field_name="Variable name")
    return value


class ActionBaseModel(PrefectBaseModel):
    class Config:
        extra = "forbid"

    def __iter__(self):
        # By default, `pydantic.BaseModel.__iter__` yields from `self.__dict__` directly
        # instead  of going through `_iter`. We want tor retain our custom logic in
        # `_iter` during `dict(model)` calls which is what Pydantic uses for
        # `parse_obj(model)`
        yield from self._iter(to_dict=True)

    def _iter(self, *args, **kwargs) -> Generator[tuple, None, None]:
        # Drop fields that are marked as `ignored` from json and dictionary outputs
        exclude = kwargs.pop("exclude", None) or set()
        for name, field in self.__fields__.items():
            if field.field_info.extra.get("ignored"):
                exclude.add(name)

        return super()._iter(*args, **kwargs, exclude=exclude)


@copy_model_fields
class FlowCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow."""

    name: str = FieldFrom(schemas.core.Flow)
    tags: List[str] = FieldFrom(schemas.core.Flow)


@copy_model_fields
class FlowUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow."""

    tags: List[str] = FieldFrom(schemas.core.Flow)


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

    name: str = FieldFrom(schemas.core.Deployment)
    flow_id: UUID = FieldFrom(schemas.core.Deployment)
    is_schedule_active: Optional[bool] = FieldFrom(schemas.core.Deployment)
    enforce_parameter_schema: bool = FieldFrom(schemas.core.Deployment)
    parameter_openapi_schema: Optional[Dict[str, Any]] = FieldFrom(
        schemas.core.Deployment
    )
    parameters: Dict[str, Any] = FieldFrom(schemas.core.Deployment)
    tags: List[str] = FieldFrom(schemas.core.Deployment)
    pull_steps: Optional[List[dict]] = FieldFrom(schemas.core.Deployment)

    manifest_path: Optional[str] = FieldFrom(schemas.core.Deployment)
    work_queue_name: Optional[str] = FieldFrom(schemas.core.Deployment)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        example="my-work-pool",
    )
    storage_document_id: Optional[UUID] = FieldFrom(schemas.core.Deployment)
    infrastructure_document_id: Optional[UUID] = FieldFrom(schemas.core.Deployment)
    schedule: Optional[schemas.schedules.SCHEDULE_TYPES] = FieldFrom(
        schemas.core.Deployment
    )
    description: Optional[str] = FieldFrom(schemas.core.Deployment)
    path: Optional[str] = FieldFrom(schemas.core.Deployment)
    version: Optional[str] = FieldFrom(schemas.core.Deployment)
    entrypoint: Optional[str] = FieldFrom(schemas.core.Deployment)
    infra_overrides: Optional[Dict[str, Any]] = FieldFrom(schemas.core.Deployment)

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

    @validator("parameters")
    def _validate_parameters_conform_to_schema(cls, value, values):
        """Validate that the parameters conform to the parameter schema."""
        if values.get("enforce_parameter_schema"):
            validate_values_conform_to_schema(
                value, values.get("parameter_openapi_schema"), ignore_required=True
            )
        return value

    @validator("parameter_openapi_schema")
    def _validate_parameter_openapi_schema(cls, value, values):
        """Validate that the parameter_openapi_schema is a valid json schema."""
        if values.get("enforce_parameter_schema"):
            validate_schema(value)
        return value


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

    version: Optional[str] = FieldFrom(schemas.core.Deployment)
    schedule: Optional[schemas.schedules.SCHEDULE_TYPES] = FieldFrom(
        schemas.core.Deployment
    )
    description: Optional[str] = FieldFrom(schemas.core.Deployment)
    is_schedule_active: bool = FieldFrom(schemas.core.Deployment)
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = FieldFrom(schemas.core.Deployment)
    work_queue_name: Optional[str] = FieldFrom(schemas.core.Deployment)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        example="my-work-pool",
    )
    path: Optional[str] = FieldFrom(schemas.core.Deployment)
    infra_overrides: Optional[Dict[str, Any]] = FieldFrom(schemas.core.Deployment)
    entrypoint: Optional[str] = FieldFrom(schemas.core.Deployment)
    manifest_path: Optional[str] = FieldFrom(schemas.core.Deployment)
    storage_document_id: Optional[UUID] = FieldFrom(schemas.core.Deployment)
    infrastructure_document_id: Optional[UUID] = FieldFrom(schemas.core.Deployment)
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


@copy_model_fields
class FlowRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run."""

    name: Optional[str] = FieldFrom(schemas.core.FlowRun)
    flow_version: Optional[str] = FieldFrom(schemas.core.FlowRun)
    parameters: dict = FieldFrom(schemas.core.FlowRun)
    empirical_policy: schemas.core.FlowRunPolicy = FieldFrom(schemas.core.FlowRun)
    tags: List[str] = FieldFrom(schemas.core.FlowRun)
    infrastructure_pid: Optional[str] = FieldFrom(schemas.core.FlowRun)


@copy_model_fields
class StateCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a new state."""

    type: schemas.states.StateType = FieldFrom(schemas.states.State)
    name: Optional[str] = FieldFrom(schemas.states.State)
    message: Optional[str] = FieldFrom(schemas.states.State)
    data: Optional[Any] = FieldFrom(schemas.states.State)
    state_details: schemas.states.StateDetails = FieldFrom(schemas.states.State)

    # DEPRECATED

    timestamp: Optional[DateTimeTZ] = Field(
        default=None,
        repr=False,
        ignored=True,
    )
    id: Optional[UUID] = Field(default=None, repr=False, ignored=True)


@copy_model_fields
class TaskRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a task run"""

    # TaskRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the task run to create"
    )

    name: str = FieldFrom(schemas.core.TaskRun)
    flow_run_id: Optional[UUID] = FieldFrom(schemas.core.TaskRun)
    task_key: str = FieldFrom(schemas.core.TaskRun)
    dynamic_key: str = FieldFrom(schemas.core.TaskRun)
    cache_key: Optional[str] = FieldFrom(schemas.core.TaskRun)
    cache_expiration: Optional[DateTimeTZ] = FieldFrom(schemas.core.TaskRun)
    task_version: Optional[str] = FieldFrom(schemas.core.TaskRun)
    empirical_policy: schemas.core.TaskRunPolicy = FieldFrom(schemas.core.TaskRun)
    tags: List[str] = FieldFrom(schemas.core.TaskRun)
    task_inputs: Dict[
        str,
        List[
            Union[
                schemas.core.TaskRunResult,
                schemas.core.Parameter,
                schemas.core.Constant,
            ]
        ],
    ] = FieldFrom(schemas.core.TaskRun)


@copy_model_fields
class TaskRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a task run"""

    name: str = FieldFrom(schemas.core.TaskRun)


@copy_model_fields
class FlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: str = FieldFrom(schemas.core.FlowRun)
    flow_id: UUID = FieldFrom(schemas.core.FlowRun)
    flow_version: Optional[str] = FieldFrom(schemas.core.FlowRun)
    parameters: dict = FieldFrom(schemas.core.FlowRun)
    context: dict = FieldFrom(schemas.core.FlowRun)
    parent_task_run_id: Optional[UUID] = FieldFrom(schemas.core.FlowRun)
    infrastructure_document_id: Optional[UUID] = FieldFrom(schemas.core.FlowRun)
    empirical_policy: schemas.core.FlowRunPolicy = FieldFrom(schemas.core.FlowRun)
    tags: List[str] = FieldFrom(schemas.core.FlowRun)
    idempotency_key: Optional[str] = FieldFrom(schemas.core.FlowRun)

    # DEPRECATED

    deployment_id: Optional[UUID] = Field(
        None,
        description=(
            "DEPRECATED: The id of the deployment associated with this flow run, if"
            " available."
        ),
        deprecated=True,
    )

    class Config(ActionBaseModel.Config):
        json_dumps = orjson_dumps_extra_compatible


@copy_model_fields
class DeploymentFlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run from a deployment."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = FieldFrom(schemas.core.FlowRun)
    parameters: dict = FieldFrom(schemas.core.FlowRun)
    context: dict = FieldFrom(schemas.core.FlowRun)
    infrastructure_document_id: Optional[UUID] = FieldFrom(schemas.core.FlowRun)
    empirical_policy: schemas.core.FlowRunPolicy = FieldFrom(schemas.core.FlowRun)
    tags: List[str] = FieldFrom(schemas.core.FlowRun)
    idempotency_key: Optional[str] = FieldFrom(schemas.core.FlowRun)
    parent_task_run_id: Optional[UUID] = FieldFrom(schemas.core.FlowRun)
    work_queue_name: Optional[str] = FieldFrom(schemas.core.FlowRun)


@copy_model_fields
class SavedSearchCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a saved search."""

    name: str = FieldFrom(schemas.core.SavedSearch)
    filters: List[schemas.core.SavedSearchFilter] = FieldFrom(schemas.core.SavedSearch)


@copy_model_fields
class ConcurrencyLimitCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a concurrency limit."""

    tag: str = FieldFrom(schemas.core.ConcurrencyLimit)
    concurrency_limit: int = FieldFrom(schemas.core.ConcurrencyLimit)


@copy_model_fields
class ConcurrencyLimitV2Create(ActionBaseModel):
    """Data used by the Prefect REST API to create a v2 concurrency limit."""

    active: bool = FieldFrom(schemas.core.ConcurrencyLimitV2)
    name: str = FieldFrom(schemas.core.ConcurrencyLimitV2)
    limit: int = FieldFrom(schemas.core.ConcurrencyLimitV2)
    active_slots: int = FieldFrom(schemas.core.ConcurrencyLimitV2)
    denied_slots: int = FieldFrom(schemas.core.ConcurrencyLimitV2)
    slot_decay_per_second: float = FieldFrom(schemas.core.ConcurrencyLimitV2)


@copy_model_fields
class ConcurrencyLimitV2Update(ActionBaseModel):
    """Data used by the Prefect REST API to update a v2 concurrency limit."""

    active: Optional[bool] = FieldFrom(schemas.core.ConcurrencyLimitV2)
    name: Optional[str] = FieldFrom(schemas.core.ConcurrencyLimitV2)
    limit: Optional[int] = FieldFrom(schemas.core.ConcurrencyLimitV2)
    active_slots: Optional[int] = FieldFrom(schemas.core.ConcurrencyLimitV2)
    denied_slots: Optional[int] = FieldFrom(schemas.core.ConcurrencyLimitV2)
    slot_decay_per_second: Optional[float] = FieldFrom(schemas.core.ConcurrencyLimitV2)


@copy_model_fields
class BlockTypeCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block type."""

    name: str = FieldFrom(schemas.core.BlockType)
    slug: str = FieldFrom(schemas.core.BlockType)
    logo_url: Optional[schemas.core.HttpUrl] = FieldFrom(schemas.core.BlockType)
    documentation_url: Optional[schemas.core.HttpUrl] = FieldFrom(
        schemas.core.BlockType
    )
    description: Optional[str] = FieldFrom(schemas.core.BlockType)
    code_example: Optional[str] = FieldFrom(schemas.core.BlockType)

    # validators
    _validate_slug_format = validator("slug", allow_reuse=True)(
        validate_block_type_slug
    )


@copy_model_fields
class BlockTypeUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block type."""

    logo_url: Optional[schemas.core.HttpUrl] = FieldFrom(schemas.core.BlockType)
    documentation_url: Optional[schemas.core.HttpUrl] = FieldFrom(
        schemas.core.BlockType
    )
    description: Optional[str] = FieldFrom(schemas.core.BlockType)
    code_example: Optional[str] = FieldFrom(schemas.core.BlockType)

    @classmethod
    def updatable_fields(cls) -> set:
        return get_class_fields_only(cls)


@copy_model_fields
class BlockSchemaCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block schema."""

    fields: dict = FieldFrom(schemas.core.BlockSchema)
    block_type_id: Optional[UUID] = FieldFrom(schemas.core.BlockSchema)
    capabilities: List[str] = FieldFrom(schemas.core.BlockSchema)
    version: str = FieldFrom(schemas.core.BlockSchema)


@copy_model_fields
class BlockDocumentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block document."""

    name: Optional[str] = FieldFrom(schemas.core.BlockDocument)
    data: dict = FieldFrom(schemas.core.BlockDocument)
    block_schema_id: UUID = FieldFrom(schemas.core.BlockDocument)
    block_type_id: UUID = FieldFrom(schemas.core.BlockDocument)
    is_anonymous: bool = FieldFrom(schemas.core.BlockDocument)

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
    data: dict = FieldFrom(schemas.core.BlockDocument)
    merge_existing_data: bool = True


@copy_model_fields
class BlockDocumentReferenceCreate(ActionBaseModel):
    """Data used to create block document reference."""

    id: UUID = FieldFrom(schemas.core.BlockDocumentReference)
    parent_block_document_id: UUID = FieldFrom(schemas.core.BlockDocumentReference)
    reference_block_document_id: UUID = FieldFrom(schemas.core.BlockDocumentReference)
    name: str = FieldFrom(schemas.core.BlockDocumentReference)


@copy_model_fields
class LogCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a log."""

    name: str = FieldFrom(schemas.core.Log)
    level: int = FieldFrom(schemas.core.Log)
    message: str = FieldFrom(schemas.core.Log)
    timestamp: DateTimeTZ = FieldFrom(schemas.core.Log)
    flow_run_id: Optional[UUID] = FieldFrom(schemas.core.Log)
    task_run_id: Optional[UUID] = FieldFrom(schemas.core.Log)


def validate_base_job_template(v):
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
        template_variables.update({placeholder.name for placeholder in found_variables})

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


@copy_model_fields
class WorkPoolCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work pool."""

    name: str = FieldFrom(schemas.core.WorkPool)
    description: Optional[str] = FieldFrom(schemas.core.WorkPool)
    type: str = Field(description="The work pool type.", default="prefect-agent")
    base_job_template: Dict[str, Any] = FieldFrom(schemas.core.WorkPool)
    is_paused: bool = FieldFrom(schemas.core.WorkPool)
    concurrency_limit: Optional[int] = FieldFrom(schemas.core.WorkPool)

    _validate_base_job_template = validator("base_job_template", allow_reuse=True)(
        validate_base_job_template
    )


@copy_model_fields
class WorkPoolUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work pool."""

    description: Optional[str] = FieldFrom(schemas.core.WorkPool)
    is_paused: Optional[bool] = FieldFrom(schemas.core.WorkPool)
    base_job_template: Optional[Dict[str, Any]] = FieldFrom(schemas.core.WorkPool)
    concurrency_limit: Optional[int] = FieldFrom(schemas.core.WorkPool)

    _validate_base_job_template = validator("base_job_template", allow_reuse=True)(
        validate_base_job_template
    )


@copy_model_fields
class WorkQueueCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work queue."""

    name: str = FieldFrom(schemas.core.WorkQueue)
    description: Optional[str] = FieldFrom(schemas.core.WorkQueue)
    is_paused: bool = FieldFrom(schemas.core.WorkQueue)
    concurrency_limit: Optional[int] = FieldFrom(schemas.core.WorkQueue)
    priority: Optional[int] = Field(
        default=None,
        description=(
            "The queue's priority. Lower values are higher priority (1 is the highest)."
        ),
    )

    # DEPRECATED

    filter: Optional[schemas.core.QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )


@copy_model_fields
class WorkQueueUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work queue."""

    name: str = FieldFrom(schemas.core.WorkQueue)
    description: Optional[str] = FieldFrom(schemas.core.WorkQueue)
    is_paused: bool = FieldFrom(schemas.core.WorkQueue)
    concurrency_limit: Optional[int] = FieldFrom(schemas.core.WorkQueue)
    priority: Optional[int] = FieldFrom(schemas.core.WorkQueue)
    last_polled: Optional[DateTimeTZ] = FieldFrom(schemas.core.WorkQueue)

    # DEPRECATED

    filter: Optional[schemas.core.QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )


@copy_model_fields
class FlowRunNotificationPolicyCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run notification policy."""

    is_active: bool = FieldFrom(schemas.core.FlowRunNotificationPolicy)
    state_names: List[str] = FieldFrom(schemas.core.FlowRunNotificationPolicy)
    tags: List[str] = FieldFrom(schemas.core.FlowRunNotificationPolicy)
    block_document_id: UUID = FieldFrom(schemas.core.FlowRunNotificationPolicy)
    message_template: Optional[str] = FieldFrom(schemas.core.FlowRunNotificationPolicy)


@copy_model_fields
class FlowRunNotificationPolicyUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run notification policy."""

    is_active: Optional[bool] = FieldFrom(schemas.core.FlowRunNotificationPolicy)
    state_names: Optional[List[str]] = FieldFrom(schemas.core.FlowRunNotificationPolicy)
    tags: Optional[List[str]] = FieldFrom(schemas.core.FlowRunNotificationPolicy)
    block_document_id: Optional[UUID] = FieldFrom(
        schemas.core.FlowRunNotificationPolicy
    )
    message_template: Optional[str] = FieldFrom(schemas.core.FlowRunNotificationPolicy)


@copy_model_fields
class ArtifactCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create an artifact."""

    key: Optional[str] = FieldFrom(schemas.core.Artifact)
    type: Optional[str] = FieldFrom(schemas.core.Artifact)
    description: Optional[str] = FieldFrom(schemas.core.Artifact)
    data: Optional[Union[Dict[str, Any], Any]] = FieldFrom(schemas.core.Artifact)
    metadata_: Optional[Dict[str, str]] = FieldFrom(schemas.core.Artifact)
    flow_run_id: Optional[UUID] = FieldFrom(schemas.core.Artifact)
    task_run_id: Optional[UUID] = FieldFrom(schemas.core.Artifact)

    _validate_artifact_format = validator("key", allow_reuse=True)(
        validate_artifact_key
    )


@copy_model_fields
class ArtifactUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update an artifact."""

    data: Optional[Union[Dict[str, Any], Any]] = FieldFrom(schemas.core.Artifact)
    description: Optional[str] = FieldFrom(schemas.core.Artifact)
    metadata_: Optional[Dict[str, str]] = FieldFrom(schemas.core.Artifact)


@copy_model_fields
class VariableCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a Variable."""

    name: str = FieldFrom(schemas.core.Variable)
    value: str = FieldFrom(schemas.core.Variable)
    tags: Optional[List[str]] = FieldFrom(schemas.core.Variable)

    # validators
    _validate_name_format = validator("name", allow_reuse=True)(validate_variable_name)


@copy_model_fields
class VariableUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a Variable."""

    name: Optional[str] = Field(
        default=None,
        description="The name of the variable",
        example="my_variable",
        max_length=schemas.core.MAX_VARIABLE_NAME_LENGTH,
    )
    value: Optional[str] = Field(
        default=None,
        description="The value of the variable",
        example="my-value",
        max_length=schemas.core.MAX_VARIABLE_VALUE_LENGTH,
    )
    tags: Optional[List[str]] = FieldFrom(schemas.core.Variable)

    # validators
    _validate_name_format = validator("name", allow_reuse=True)(validate_variable_name)
