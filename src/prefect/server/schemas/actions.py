"""
Reduced schemas for accepting API actions.
"""

import json
from copy import deepcopy
from typing import Any, Dict, Generator, List, Optional, Union
from uuid import UUID, uuid4

from prefect._internal.compatibility.deprecated import DeprecatedInfraOverridesField
from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, HttpUrl, root_validator, validator
else:
    from pydantic import Field, HttpUrl, root_validator, validator

import prefect.server.schemas as schemas
from prefect._internal.schemas.validators import (
    get_or_create_run_name,
    get_or_create_state_name,
    raise_on_name_alphanumeric_dashes_only,
    raise_on_name_alphanumeric_underscores_only,
    raise_on_name_with_banned_characters,
    remove_old_deployment_fields,
    set_default_scheduled_time,
    set_deployment_schedules,
    validate_cache_key_length,
    validate_max_metadata_length,
    validate_message_template_variables,
    validate_name_present_on_nonanonymous_blocks,
    validate_parameter_openapi_schema,
    validate_parameters_conform_to_schema,
    validate_parent_and_ref_diff,
    validate_schedule_max_scheduled_runs,
)
from prefect.server.utilities.schemas import get_class_fields_only
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.server.utilities.schemas.fields import DateTimeTZ
from prefect.server.utilities.schemas.serializers import orjson_dumps_extra_compatible
from prefect.settings import PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS
from prefect.types import NonNegativeFloat, NonNegativeInteger, PositiveInteger
from prefect.utilities.collections import listrepr
from prefect.utilities.names import generate_slug
from prefect.utilities.templating import find_placeholders


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

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        return raise_on_name_with_banned_characters(v)


class FlowUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow."""

    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        return raise_on_name_with_banned_characters(v)


class DeploymentScheduleCreate(ActionBaseModel):
    active: bool = Field(
        default=True, description="Whether or not the schedule is active."
    )
    schedule: schemas.schedules.SCHEDULE_TYPES = Field(
        default=..., description="The schedule for the deployment."
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

    @validator("max_scheduled_runs")
    def validate_max_scheduled_runs(cls, v):
        return validate_schedule_max_scheduled_runs(
            v, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()
        )


class DeploymentScheduleUpdate(ActionBaseModel):
    active: Optional[bool] = Field(
        default=None, description="Whether or not the schedule is active."
    )
    schedule: Optional[schemas.schedules.SCHEDULE_TYPES] = Field(
        default=None, description="The schedule for the deployment."
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

    @validator("max_scheduled_runs")
    def validate_max_scheduled_runs(cls, v):
        return validate_schedule_max_scheduled_runs(
            v, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()
        )


class DeploymentCreate(DeprecatedInfraOverridesField, ActionBaseModel):
    """Data used by the Prefect REST API to create a deployment."""

    @root_validator
    def populate_schedules(cls, values):
        return set_deployment_schedules(values)

    @root_validator(pre=True)
    def remove_old_fields(cls, values):
        return remove_old_deployment_fields(values)

    name: str = Field(
        default=...,
        description="The name of the deployment.",
        examples=["my-deployment"],
    )
    flow_id: UUID = Field(
        default=..., description="The ID of the flow associated with the deployment."
    )
    is_schedule_active: bool = Field(
        default=True, description="Whether the schedule is active."
    )
    paused: bool = Field(
        default=False, description="Whether or not the deployment is paused."
    )
    schedules: List[DeploymentScheduleCreate] = Field(
        default_factory=list,
        description="A list of schedules for the deployment.",
    )
    enforce_parameter_schema: bool = Field(
        default=False,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The parameter schema of the flow, including defaults.",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of deployment tags.",
        examples=[["tag-1", "tag-2"]],
    )
    pull_steps: Optional[List[dict]] = Field(None)

    manifest_path: Optional[str] = Field(None)
    work_queue_name: Optional[str] = Field(None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    storage_document_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    schedule: Optional[schemas.schedules.SCHEDULE_TYPES] = Field(
        None, description="The schedule for the deployment."
    )
    description: Optional[str] = Field(None)
    path: Optional[str] = Field(None)
    version: Optional[str] = Field(None)
    entrypoint: Optional[str] = Field(None)
    job_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides for the flow's infrastructure configuration.",
    )

    def check_valid_configuration(self, base_job_template: dict):
        """
        Check that the combination of base_job_template defaults and job_variables
        conforms to the specified schema.

        NOTE: This method does not hydrate block references in default values within the
        base job template to validate them. Failing to do this can cause user-facing
        errors. Instead of this method, use `validate_job_variables_for_deployment`
        function from `prefect_cloud.orion.api.validation`.
        """
        # This import is here to avoid a circular import
        from prefect.utilities.schema_tools import validate

        variables_schema = deepcopy(base_job_template.get("variables"))

        if variables_schema is not None:
            validate(
                self.job_variables,
                variables_schema,
                raise_on_error=True,
                preprocess=True,
                ignore_required=True,
            )

    @validator("parameters")
    def _validate_parameters_conform_to_schema(cls, value, values):
        return validate_parameters_conform_to_schema(value, values)

    @validator("parameter_openapi_schema")
    def _validate_parameter_openapi_schema(cls, value, values):
        return validate_parameter_openapi_schema(value, values)


class DeploymentUpdate(DeprecatedInfraOverridesField, ActionBaseModel):
    """Data used by the Prefect REST API to update a deployment."""

    @root_validator(pre=True)
    def remove_old_fields(cls, values):
        return remove_old_deployment_fields(values)

    version: Optional[str] = Field(None)
    schedule: Optional[schemas.schedules.SCHEDULE_TYPES] = Field(
        None, description="The schedule for the deployment."
    )
    description: Optional[str] = Field(None)
    is_schedule_active: bool = Field(
        default=True, description="Whether the schedule is active."
    )
    paused: bool = Field(
        default=False, description="Whether or not the deployment is paused."
    )
    schedules: List[DeploymentScheduleCreate] = Field(
        default_factory=list,
        description="A list of schedules for the deployment.",
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of deployment tags.",
        examples=[["tag-1", "tag-2"]],
    )
    work_queue_name: Optional[str] = Field(None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    path: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Overrides for the flow's infrastructure configuration.",
    )
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

    class Config:
        allow_population_by_field_name = True

    def check_valid_configuration(self, base_job_template: dict):
        """
        Check that the combination of base_job_template defaults and job_variables
        conforms to the schema specified in the base_job_template.

        NOTE: This method does not hydrate block references in default values within the
        base job template to validate them. Failing to do this can cause user-facing
        errors. Instead of this method, use `validate_job_variables_for_deployment`
        function from `prefect_cloud.orion.api.validation`.
        """
        # This import is here to avoid a circular import
        from prefect.utilities.schema_tools import validate

        variables_schema = deepcopy(base_job_template.get("variables"))

        if variables_schema is not None:
            errors = validate(
                self.job_variables,
                variables_schema,
                raise_on_error=False,
                preprocess=True,
                ignore_required=True,
            )
            if errors:
                for error in errors:
                    raise error


class FlowRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run."""

    name: Optional[str] = Field(None)
    flow_version: Optional[str] = Field(None)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    empirical_policy: schemas.core.FlowRunPolicy = Field(
        default_factory=schemas.core.FlowRunPolicy
    )
    tags: List[str] = Field(default_factory=list)
    infrastructure_pid: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(None)

    @validator("name", pre=True)
    def set_name(cls, name):
        return get_or_create_run_name(name)


class StateCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a new state."""

    type: schemas.states.StateType = Field(
        default=..., description="The type of the state to create"
    )
    name: Optional[str] = Field(
        default=None, description="The name of the state to create"
    )
    message: Optional[str] = Field(
        default=None, description="The message of the state to create"
    )
    data: Optional[Any] = Field(
        default=None, description="The data of the state to create"
    )
    state_details: schemas.states.StateDetails = Field(
        default_factory=schemas.states.StateDetails,
        description="The details of the state to create",
    )

    timestamp: Optional[DateTimeTZ] = Field(
        default=None,
        repr=False,
        ignored=True,
    )
    id: Optional[UUID] = Field(default=None, repr=False, ignored=True)

    @validator("name", always=True)
    def default_name_from_type(cls, v, *, values, **kwargs):
        return get_or_create_state_name(v, values)

    @root_validator
    def default_scheduled_start_time(cls, values):
        return set_default_scheduled_time(cls, values)


class TaskRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a task run"""

    id: Optional[UUID] = Field(
        default=None,
        description="The ID to use for the task run. If not provided, a random UUID will be generated.",
    )

    # TaskRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the task run to create"
    )

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
    cache_expiration: Optional[DateTimeTZ] = Field(
        default=None, description="Specifies when the cached state should expire."
    )
    task_version: Optional[str] = Field(
        default=None, description="The version of the task being run."
    )
    empirical_policy: schemas.core.TaskRunPolicy = Field(
        default_factory=schemas.core.TaskRunPolicy,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the task run.",
        examples=[["tag-1", "tag-2"]],
    )
    task_inputs: Dict[
        str,
        List[
            Union[
                schemas.core.TaskRunResult,
                schemas.core.Parameter,
                schemas.core.Constant,
            ]
        ],
    ] = Field(
        default_factory=dict,
        description="The inputs to the task run.",
    )

    @validator("name", pre=True)
    def set_name(cls, name):
        return get_or_create_run_name(name)

    @validator("cache_key")
    def validate_cache_key(cls, cache_key):
        return validate_cache_key_length(cache_key)


class TaskRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a task run"""

    name: str = Field(
        default_factory=lambda: generate_slug(2), examples=["my-task-run"]
    )

    @validator("name", pre=True)
    def set_name(cls, name):
        return get_or_create_run_name(name)


class FlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description=(
            "The name of the flow run. Defaults to a random slug if not specified."
        ),
        examples=["my-flow-run"],
    )
    flow_id: UUID = Field(default=..., description="The id of the flow being run.")
    flow_version: Optional[str] = Field(
        default=None, description="The version of the flow being run."
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="The context of the flow run.",
    )
    parent_task_run_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    empirical_policy: schemas.core.FlowRunPolicy = Field(
        default_factory=schemas.core.FlowRunPolicy,
        description="The empirical policy for the flow run.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the flow run.",
        examples=[["tag-1", "tag-2"]],
    )
    idempotency_key: Optional[str] = Field(
        None,
        description=(
            "An optional idempotency key. If a flow run with the same idempotency key"
            " has already been created, the existing flow run will be returned."
        ),
    )

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

    @validator("name", pre=True)
    def set_name(cls, name):
        return get_or_create_run_name(name)


class DeploymentFlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run from a deployment."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description=(
            "The name of the flow run. Defaults to a random slug if not specified."
        ),
        examples=["my-flow-run"],
    )
    parameters: Dict[str, Any] = Field(default_factory=dict)
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description="Whether or not to enforce the parameter schema on this run.",
    )
    context: Dict[str, Any] = Field(default_factory=dict)
    infrastructure_document_id: Optional[UUID] = Field(None)
    empirical_policy: schemas.core.FlowRunPolicy = Field(
        default_factory=schemas.core.FlowRunPolicy,
        description="The empirical policy for the flow run.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the flow run.",
        examples=[["tag-1", "tag-2"]],
    )
    idempotency_key: Optional[str] = Field(
        None,
        description=(
            "An optional idempotency key. If a flow run with the same idempotency key"
            " has already been created, the existing flow run will be returned."
        ),
    )
    parent_task_run_id: Optional[UUID] = Field(None)
    work_queue_name: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(None)

    @validator("name", pre=True)
    def set_name(cls, name):
        return get_or_create_run_name(name)


class SavedSearchCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a saved search."""

    name: str = Field(default=..., description="The name of the saved search.")
    filters: List[schemas.core.SavedSearchFilter] = Field(
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
    name: str = Field(default=..., description="The name of the concurrency limit.")
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

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        return raise_on_name_with_banned_characters(v)


class ConcurrencyLimitV2Update(ActionBaseModel):
    """Data used by the Prefect REST API to update a v2 concurrency limit."""

    active: Optional[bool] = Field(None)
    name: Optional[str] = Field(None)
    limit: Optional[NonNegativeInteger] = Field(None)
    active_slots: Optional[NonNegativeInteger] = Field(None)
    denied_slots: Optional[NonNegativeInteger] = Field(None)
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(None)

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        return raise_on_name_with_banned_characters(v)


class BlockTypeCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block type."""

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

    # validators
    _validate_slug_format = validator("slug", allow_reuse=True)(
        validate_block_type_slug
    )

    _validate_name_characters = validator("name", check_fields=False)(
        raise_on_name_with_banned_characters
    )


class BlockTypeUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block type."""

    logo_url: Optional[schemas.core.HttpUrl] = Field(None)
    documentation_url: Optional[schemas.core.HttpUrl] = Field(None)
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
    block_type_id: Optional[UUID] = Field(default=..., description="A block type ID")

    capabilities: List[str] = Field(
        default_factory=list,
        description="A list of Block capabilities",
    )
    version: str = Field(
        default=schemas.core.DEFAULT_BLOCK_SCHEMA_VERSION,
        description="Human readable identifier for the block schema",
    )


class BlockDocumentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block document."""

    name: Optional[str] = Field(
        default=None,
        description=(
            "The block document's name. Not required for anonymous block documents."
        ),
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="The block document's data"
    )
    block_schema_id: UUID = Field(default=..., description="A block schema ID")

    block_type_id: UUID = Field(default=..., description="A block type ID")

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
        return validate_name_present_on_nonanonymous_blocks(values)


class BlockDocumentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block document."""

    block_schema_id: Optional[UUID] = Field(
        default=None, description="A block schema ID"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="The block document's data"
    )
    merge_existing_data: bool = True


class BlockDocumentReferenceCreate(ActionBaseModel):
    """Data used to create block document reference."""

    id: UUID = Field(
        default_factory=uuid4, description="The block document reference ID"
    )
    parent_block_document_id: UUID = Field(
        default=..., description="ID of the parent block document"
    )
    reference_block_document_id: UUID = Field(
        default=..., description="ID of the nested block document"
    )
    name: str = Field(
        default=..., description="The name that the reference is nested under"
    )

    @root_validator
    def validate_parent_and_ref_are_different(cls, values):
        return validate_parent_and_ref_diff(values)


class LogCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a log."""

    name: str = Field(default=..., description="The logger name.")
    level: int = Field(default=..., description="The log level.")
    message: str = Field(default=..., description="The log message.")
    timestamp: DateTimeTZ = Field(default=..., description="The log timestamp.")
    flow_run_id: Optional[UUID] = Field(None)
    task_run_id: Optional[UUID] = Field(None)


def validate_base_job_template(v):
    if v == dict():
        return v

    job_config = v.get("job_configuration")
    variables_schema = v.get("variables")
    if not (job_config and variables_schema):
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

    provided_variables = set(variables_schema.get("properties", {}).keys())
    if not template_variables.issubset(provided_variables):
        missing_variables = template_variables - provided_variables
        raise ValueError(
            "The variables specified in the job configuration template must be "
            "present as properties in the variables schema. "
            "Your job configuration uses the following undeclared "
            f"variable(s): {' ,'.join(missing_variables)}."
        )
    return v


class WorkPoolCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work pool."""

    name: str = Field(..., description="The name of the work pool.")
    description: Optional[str] = Field(None, description="The work pool description.")
    type: str = Field(description="The work pool type.", default="prefect-agent")
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

    _validate_base_job_template = validator("base_job_template", allow_reuse=True)(
        validate_base_job_template
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        return raise_on_name_with_banned_characters(v)


class WorkPoolUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work pool."""

    description: Optional[str] = Field(None)
    is_paused: Optional[bool] = Field(None)
    base_job_template: Optional[Dict[str, Any]] = Field(None)
    concurrency_limit: Optional[NonNegativeInteger] = Field(None)

    _validate_base_job_template = validator("base_job_template", allow_reuse=True)(
        validate_base_job_template
    )

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        return raise_on_name_with_banned_characters(v)


class WorkQueueCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work queue."""

    name: str = Field(default=..., description="The name of the work queue.")
    description: Optional[str] = Field(
        default="", description="An optional description for the work queue."
    )
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(
        None, description="The work queue's concurrency limit."
    )
    priority: Optional[PositiveInteger] = Field(
        None,
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

    @validator("name", check_fields=False)
    def validate_name_characters(cls, v):
        return raise_on_name_with_banned_characters(v)


class WorkQueueUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work queue."""

    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(None)
    priority: Optional[PositiveInteger] = Field(None)
    last_polled: Optional[DateTimeTZ] = Field(None)

    # DEPRECATED

    filter: Optional[schemas.core.QueueFilter] = Field(
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
            f" {listrepr(sorted(schemas.core.FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS), sep=', ')}"
        ),
        examples=[
            "Flow run {flow_run_name} with id {flow_run_id} entered state"
            " {flow_run_state_name}."
        ],
    )

    @validator("message_template")
    def validate_message_template_variables(cls, v):
        return validate_message_template_variables(v)


class FlowRunNotificationPolicyUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run notification policy."""

    is_active: Optional[bool] = Field(None)
    state_names: Optional[List[str]] = Field(None)
    tags: Optional[List[str]] = Field(None)
    block_document_id: Optional[UUID] = Field(None)
    message_template: Optional[str] = Field(None)

    @validator("message_template")
    def validate_message_template_variables(cls, v):
        return validate_message_template_variables(v)


class ArtifactCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create an artifact."""

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

    _validate_metadata_length = validator("metadata_")(validate_max_metadata_length)

    _validate_artifact_format = validator("key", allow_reuse=True)(
        validate_artifact_key
    )


class ArtifactUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update an artifact."""

    data: Optional[Union[Dict[str, Any], Any]] = Field(None)
    description: Optional[str] = Field(None)
    metadata_: Optional[Dict[str, str]] = Field(None)

    _validate_metadata_length = validator("metadata_", allow_reuse=True)(
        validate_max_metadata_length
    )


class VariableCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a Variable."""

    name: str = Field(
        default=...,
        description="The name of the variable",
        examples=["my-variable"],
        max_length=schemas.core.MAX_VARIABLE_NAME_LENGTH,
    )
    value: str = Field(
        default=...,
        description="The value of the variable",
        examples=["my-value"],
        max_length=schemas.core.MAX_VARIABLE_VALUE_LENGTH,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of variable tags",
        examples=[["tag-1", "tag-2"]],
    )

    # validators
    _validate_name_format = validator("name", allow_reuse=True)(validate_variable_name)


class VariableUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a Variable."""

    name: Optional[str] = Field(
        default=None,
        description="The name of the variable",
        examples=["my-variable"],
        max_length=schemas.core.MAX_VARIABLE_NAME_LENGTH,
    )
    value: Optional[str] = Field(
        default=None,
        description="The value of the variable",
        examples=["my-value"],
        max_length=schemas.core.MAX_VARIABLE_VALUE_LENGTH,
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="A list of variable tags",
        examples=[["tag-1", "tag-2"]],
    )

    # validators
    _validate_name_format = validator("name", allow_reuse=True)(validate_variable_name)
