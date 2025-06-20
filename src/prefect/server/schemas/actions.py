"""
Reduced schemas for accepting API actions.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Annotated, Any, ClassVar, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import (
    AfterValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

import prefect.server.schemas as schemas
from prefect._internal.schemas.validators import (
    get_or_create_run_name,
    remove_old_deployment_fields,
    validate_cache_key_length,
    validate_max_metadata_length,
    validate_name_present_on_nonanonymous_blocks,
    validate_parameter_openapi_schema,
    validate_parameters_conform_to_schema,
    validate_parent_and_ref_diff,
    validate_schedule_max_scheduled_runs,
)
from prefect.server.utilities.schemas import get_class_fields_only
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.settings import PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS
from prefect.types import (
    DateTime,
    KeyValueLabels,
    Name,
    NonEmptyishName,
    NonNegativeFloat,
    NonNegativeInteger,
    PositiveInteger,
    StrictVariableValue,
)
from prefect.types._datetime import now
from prefect.types.names import (
    ArtifactKey,
    BlockDocumentName,
    BlockTypeSlug,
    VariableName,
)
from prefect.utilities.names import generate_slug
from prefect.utilities.templating import find_placeholders


class ActionBaseModel(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class FlowCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow."""

    name: Name = Field(
        default=..., description="The name of the flow", examples=["my-flow"]
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )
    labels: Union[KeyValueLabels, None] = Field(
        default_factory=dict,
        description="A dictionary of key-value labels. Values can be strings, numbers, or booleans.",
        examples=[{"key": "value1", "key2": 42}],
    )


class FlowUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow."""

    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )


class DeploymentScheduleCreate(ActionBaseModel):
    active: bool = Field(
        default=True, description="Whether or not the schedule is active."
    )
    schedule: schemas.schedules.SCHEDULE_TYPES = Field(
        default=..., description="The schedule for the deployment."
    )
    max_scheduled_runs: Optional[PositiveInteger] = Field(
        default=None,
        description="The maximum number of scheduled runs for the schedule.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="A dictionary of parameter value overrides."
    )
    slug: Optional[str] = Field(
        default=None,
        description="A unique identifier for the schedule.",
    )

    @field_validator("max_scheduled_runs")
    @classmethod
    def validate_max_scheduled_runs(
        cls, v: PositiveInteger | None
    ) -> PositiveInteger | None:
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

    max_scheduled_runs: Optional[PositiveInteger] = Field(
        default=None,
        description="The maximum number of scheduled runs for the schedule.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="A dictionary of parameter value overrides."
    )
    slug: Optional[str] = Field(
        default=None,
        description="A unique identifier for the schedule.",
    )

    @field_validator("max_scheduled_runs")
    @classmethod
    def validate_max_scheduled_runs(
        cls, v: PositiveInteger | None
    ) -> PositiveInteger | None:
        return validate_schedule_max_scheduled_runs(
            v, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()
        )


class DeploymentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a deployment."""

    name: str = Field(
        default=...,
        description="The name of the deployment.",
        examples=["my-deployment"],
    )
    flow_id: UUID = Field(
        default=..., description="The ID of the flow associated with the deployment."
    )
    paused: bool = Field(
        default=False, description="Whether or not the deployment is paused."
    )
    schedules: list[DeploymentScheduleCreate] = Field(
        default_factory=lambda: [],
        description="A list of schedules for the deployment.",
    )
    concurrency_limit: Optional[PositiveInteger] = Field(
        default=None, description="The deployment's concurrency limit."
    )
    concurrency_options: Optional[schemas.core.ConcurrencyOptions] = Field(
        default=None, description="The deployment's concurrency options."
    )
    global_concurrency_limit_id: Optional[UUID] = Field(
        default=None,
        description="The ID of the global concurrency limit to apply to the deployment.",
    )
    enforce_parameter_schema: bool = Field(
        default=True,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="The parameter schema of the flow, including defaults.",
        json_schema_extra={"additionalProperties": True},
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
        json_schema_extra={"additionalProperties": True},
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of deployment tags.",
        examples=[["tag-1", "tag-2"]],
    )
    labels: Union[KeyValueLabels, None] = Field(
        default_factory=dict,
        description="A dictionary of key-value labels. Values can be strings, numbers, or booleans.",
        examples=[{"key": "value1", "key2": 42}],
    )
    pull_steps: Optional[List[dict[str, Any]]] = Field(None)

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
        description="Overrides for the flow's infrastructure configuration.",
        json_schema_extra={"additionalProperties": True},
    )

    version_info: Optional[schemas.core.VersionInfo] = Field(
        default=None, description="A description of this version of the deployment."
    )

    def check_valid_configuration(self, base_job_template: dict[str, Any]) -> None:
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

    @model_validator(mode="before")
    @classmethod
    def remove_old_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        return remove_old_deployment_fields(values)

    @model_validator(mode="before")
    def _validate_parameters_conform_to_schema(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        values["parameters"] = validate_parameters_conform_to_schema(
            values.get("parameters", {}), values
        )
        values["parameter_openapi_schema"] = validate_parameter_openapi_schema(
            values.get("parameter_openapi_schema"), values
        )
        return values

    @model_validator(mode="before")
    def _validate_concurrency_limits(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate that a deployment does not have both a concurrency limit and global concurrency limit."""
        if values.get("concurrency_limit") and values.get(
            "global_concurrency_limit_id"
        ):
            raise ValueError(
                "A deployment cannot have both a concurrency limit and a global concurrency limit."
            )
        return values


class DeploymentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a deployment."""

    @model_validator(mode="before")
    @classmethod
    def remove_old_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        return remove_old_deployment_fields(values)

    version: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    paused: bool = Field(
        default=False, description="Whether or not the deployment is paused."
    )
    schedules: list[DeploymentScheduleUpdate] = Field(
        default_factory=lambda: [],
        description="A list of schedules for the deployment.",
    )
    concurrency_limit: Optional[PositiveInteger] = Field(
        default=None, description="The deployment's concurrency limit."
    )
    concurrency_options: Optional[schemas.core.ConcurrencyOptions] = Field(
        default=None, description="The deployment's concurrency options."
    )
    global_concurrency_limit_id: Optional[UUID] = Field(
        default=None,
        description="The ID of the global concurrency limit to apply to the deployment.",
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The parameter schema of the flow, including defaults.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of deployment tags.",
        examples=[["tag-1", "tag-2"]],
    )
    work_queue_name: Optional[str] = Field(default=None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    path: Optional[str] = Field(default=None)
    job_variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Overrides for the flow's infrastructure configuration.",
    )
    pull_steps: Optional[List[dict[str, Any]]] = Field(default=None)
    entrypoint: Optional[str] = Field(default=None)
    storage_document_id: Optional[UUID] = Field(default=None)
    infrastructure_document_id: Optional[UUID] = Field(default=None)
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    version_info: Optional[schemas.core.VersionInfo] = Field(
        default=None, description="A description of this version of the deployment."
    )

    def check_valid_configuration(self, base_job_template: dict[str, Any]) -> None:
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

        if variables_schema is not None and self.job_variables is not None:
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

    @model_validator(mode="before")
    def _validate_concurrency_limits(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate that a deployment does not have both a concurrency limit and global concurrency limit."""
        if values.get("concurrency_limit") and values.get(
            "global_concurrency_limit_id"
        ):
            raise ValueError(
                "A deployment cannot have both a concurrency limit and a global concurrency limit."
            )
        return values


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

    @field_validator("name", mode="before")
    @classmethod
    def set_name(cls, name: str) -> str:
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

    @model_validator(mode="after")
    def default_name_from_type(self):
        """If a name is not provided, use the type"""
        # if `type` is not in `values` it means the `type` didn't pass its own
        # validation check and an error will be raised after this function is called
        name = self.name
        if name is None and self.type:
            self.name = " ".join([v.capitalize() for v in self.type.value.split("_")])
        return self

    @model_validator(mode="after")
    def default_scheduled_start_time(self):
        from prefect.server.schemas.states import StateType

        if self.type == StateType.SCHEDULED:
            if not self.state_details.scheduled_time:
                self.state_details.scheduled_time = now("UTC")

        return self


class TaskRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a task run"""

    id: Optional[UUID] = Field(
        default=None,
        description="The ID to assign to the task run. If not provided, a random UUID will be generated.",
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
    cache_expiration: Optional[DateTime] = Field(
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
    labels: Union[KeyValueLabels, None] = Field(
        default_factory=dict,
        description="A dictionary of key-value labels. Values can be strings, numbers, or booleans.",
        examples=[{"key": "value1", "key2": 42}],
    )
    task_inputs: Dict[
        str,
        List[
            Union[
                schemas.core.TaskRunResult,
                schemas.core.FlowRunResult,
                schemas.core.Parameter,
                schemas.core.Constant,
            ]
        ],
    ] = Field(
        default_factory=dict,
        description="The inputs to the task run.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def set_name(cls, name: str) -> str:
        return get_or_create_run_name(name)

    @field_validator("cache_key")
    @classmethod
    def validate_cache_key(cls, cache_key: str | None) -> str | None:
        return validate_cache_key_length(cache_key)


class TaskRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a task run"""

    name: str = Field(
        default_factory=lambda: generate_slug(2), examples=["my-task-run"]
    )

    @field_validator("name", mode="before")
    @classmethod
    def set_name(cls, name: str) -> str:
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
    labels: Union[KeyValueLabels, None] = Field(
        default_factory=dict,
        description="A dictionary of key-value labels. Values can be strings, numbers, or booleans.",
        examples=[{"key": "value1", "key2": 42}],
    )
    idempotency_key: Optional[str] = Field(
        None,
        description=(
            "An optional idempotency key. If a flow run with the same idempotency key"
            " has already been created, the existing flow run will be returned."
        ),
    )
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the work pool to run the flow run in.",
    )
    work_queue_name: Optional[str] = Field(
        default=None,
        description="The name of the work queue to place the flow run in.",
    )
    job_variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The job variables to use when setting up flow run infrastructure.",
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

    @field_validator("name", mode="before")
    @classmethod
    def set_name(cls, name: str) -> str:
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
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        json_schema_extra={"additionalProperties": True},
    )
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
    labels: Union[KeyValueLabels, None] = Field(
        None,
        description="A dictionary of key-value labels. Values can be strings, numbers, or booleans.",
        examples=[{"key": "value1", "key2": 42}],
    )
    parent_task_run_id: Optional[UUID] = Field(None)
    work_queue_name: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        json_schema_extra={"additionalProperties": True},
    )

    @field_validator("name", mode="before")
    @classmethod
    def set_name(cls, name: str) -> str:
        return get_or_create_run_name(name)


class SavedSearchCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a saved search."""

    name: str = Field(default=..., description="The name of the saved search.")
    filters: list[schemas.core.SavedSearchFilter] = Field(
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

    active: Optional[bool] = Field(None)
    name: Optional[Name] = Field(None)
    limit: Optional[NonNegativeInteger] = Field(None)
    active_slots: Optional[NonNegativeInteger] = Field(None)
    denied_slots: Optional[NonNegativeInteger] = Field(None)
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(None)


class BlockTypeCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block type."""

    name: Name = Field(default=..., description="A block type's name")
    slug: BlockTypeSlug = Field(default=..., description="A block type's slug")
    logo_url: Optional[str] = Field(  # TODO: HttpUrl
        default=None, description="Web URL for the block type's logo"
    )
    documentation_url: Optional[str] = Field(  # TODO: HttpUrl
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

    logo_url: Optional[str] = Field(None)  # TODO: HttpUrl
    documentation_url: Optional[str] = Field(None)  # TODO: HttpUrl
    description: Optional[str] = Field(None)
    code_example: Optional[str] = Field(None)

    @classmethod
    def updatable_fields(cls) -> set[str]:
        return get_class_fields_only(cls)


class BlockSchemaCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block schema."""

    fields: dict[str, Any] = Field(
        default_factory=dict, description="The block schema's field schema"
    )
    block_type_id: UUID = Field(default=..., description="A block type ID")

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

    name: Optional[BlockDocumentName] = Field(
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

    @model_validator(mode="before")
    def validate_parent_and_ref_are_different(cls, values):
        return validate_parent_and_ref_diff(values)


class LogCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a log."""

    name: str = Field(default=..., description="The logger name.")
    level: int = Field(default=..., description="The log level.")
    message: str = Field(default=..., description="The log message.")
    timestamp: DateTime = Field(default=..., description="The log timestamp.")
    flow_run_id: Optional[UUID] = Field(None)
    task_run_id: Optional[UUID] = Field(None)


def validate_base_job_template(v: dict[str, Any]) -> dict[str, Any]:
    if v == dict():
        return v

    job_config = v.get("job_configuration")
    variables_schema = v.get("variables")
    if not (job_config and variables_schema):
        raise ValueError(
            "The `base_job_template` must contain both a `job_configuration` key"
            " and a `variables` key."
        )
    template_variables: set[str] = set()
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

    name: NonEmptyishName = Field(..., description="The name of the work pool.")
    description: Optional[str] = Field(
        default=None, description="The work pool description."
    )
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

    storage_configuration: schemas.core.WorkPoolStorageConfiguration = Field(
        default_factory=schemas.core.WorkPoolStorageConfiguration,
        description="The storage configuration for the work pool.",
    )

    _validate_base_job_template = field_validator("base_job_template")(
        validate_base_job_template
    )


class WorkPoolUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work pool."""

    description: Optional[str] = Field(default=None)
    is_paused: Optional[bool] = Field(default=None)
    base_job_template: Optional[Dict[str, Any]] = Field(default=None)
    concurrency_limit: Optional[NonNegativeInteger] = Field(default=None)
    storage_configuration: Optional[schemas.core.WorkPoolStorageConfiguration] = Field(
        default=None,
        description="The storage configuration for the work pool.",
    )
    _validate_base_job_template = field_validator("base_job_template")(
        validate_base_job_template
    )


class WorkQueueCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work queue."""

    name: Name = Field(default=..., description="The name of the work queue.")
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


class WorkQueueUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work queue."""

    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(None)
    priority: Optional[PositiveInteger] = Field(None)
    last_polled: Optional[DateTime] = Field(None)

    # DEPRECATED

    filter: Optional[schemas.core.QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )


class ArtifactCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create an artifact."""

    key: Optional[ArtifactKey] = Field(
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
    metadata_: Optional[
        Annotated[dict[str, str], AfterValidator(validate_max_metadata_length)]
    ] = Field(
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
    def from_result(cls, data: Any | dict[str, Any]) -> "ArtifactCreate":
        artifact_info: dict[str, Any] = dict()
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


class ArtifactUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update an artifact."""

    data: Optional[Union[Dict[str, Any], Any]] = Field(None)
    description: Optional[str] = Field(None)
    metadata_: Optional[
        Annotated[dict[str, str], AfterValidator(validate_max_metadata_length)]
    ] = Field(None)


class VariableCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a Variable."""

    name: VariableName = Field(default=...)
    value: StrictVariableValue = Field(
        default=...,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: list[str] = Field(
        default_factory=list,
        description="A list of variable tags",
        examples=[["tag-1", "tag-2"]],
    )


class VariableUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a Variable."""

    name: Optional[VariableName] = Field(default=None)
    value: StrictVariableValue = Field(
        default=None,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="A list of variable tags",
        examples=[["tag-1", "tag-2"]],
    )
