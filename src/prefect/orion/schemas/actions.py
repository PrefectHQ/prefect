"""
Reduced schemas for accepting API actions.
"""
import re
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import Field, validator

import prefect.orion.schemas as schemas
from prefect.orion.utilities.schemas import From, PrefectBaseModel, copy_model_fields

LOWERCASE_LETTERS_AND_DASHES_ONLY_REGEX = "^[a-z0-9-]*$"


def validate_block_type_slug(value):
    if not bool(re.match(LOWERCASE_LETTERS_AND_DASHES_ONLY_REGEX, value)):
        raise ValueError(
            "slug must only contain lowercase letters, numbers, and dashes"
        )
    return value


def validate_block_document_name(value):
    if value is not None and not bool(
        re.match(LOWERCASE_LETTERS_AND_DASHES_ONLY_REGEX, value)
    ):
        raise ValueError(
            "name must only contain lowercase letters, numbers, and dashes"
        )
    return value


@copy_model_fields
class FlowCreate(PrefectBaseModel):
    """Data used by the Orion API to create a flow."""

    name: str = From(schemas.core.Flow)
    tags: List[str] = From(schemas.core.Flow)

    class Config:
        extra = "forbid"


@copy_model_fields
class FlowUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a flow."""

    tags: List[str] = From(schemas.core.Flow)

    class Config:
        extra = "forbid"


@copy_model_fields
class DeploymentCreate(PrefectBaseModel):
    """Data used by the Orion API to create a deployment."""

    name: str = From(schemas.core.Deployment)
    version: Optional[str] = From(schemas.core.Deployment)
    description: str = From(schemas.core.Deployment)
    flow_id: UUID = From(schemas.core.Deployment)
    schedule: schemas.schedules.SCHEDULE_TYPES = From(schemas.core.Deployment)
    is_schedule_active: bool = From(schemas.core.Deployment)
    infra_overrides: Dict[str, Any] = From(schemas.core.Deployment)
    parameters: Dict[str, Any] = From(schemas.core.Deployment)
    tags: List[str] = From(schemas.core.Deployment)
    work_queue_name: Optional[str] = From(schemas.core.Deployment)
    parameter_openapi_schema: Dict[str, Any] = From(schemas.core.Deployment)
    path: str = From(schemas.core.Deployment)
    entrypoint: str = From(schemas.core.Deployment)
    manifest_path: str = From(schemas.core.Deployment)
    storage_document_id: Optional[UUID] = From(schemas.core.Deployment)
    infrastructure_document_id: Optional[UUID] = From(schemas.core.Deployment)

    class Config:
        extra = "forbid"


@copy_model_fields
class DeploymentUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a deployment."""

    version: Optional[str] = From(schemas.core.Deployment)
    description: str = From(schemas.core.Deployment)
    schedule: schemas.schedules.SCHEDULE_TYPES = From(schemas.core.Deployment)
    is_schedule_active: bool = From(schemas.core.Deployment)
    infra_overrides: Dict[str, Any] = From(schemas.core.Deployment)
    parameters: Dict[str, Any] = From(schemas.core.Deployment)
    tags: List[str] = From(schemas.core.Deployment)
    work_queue_name: Optional[str] = From(schemas.core.Deployment)
    path: str = From(schemas.core.Deployment)
    entrypoint: str = From(schemas.core.Deployment)
    manifest_path: str = From(schemas.core.Deployment)
    storage_document_id: Optional[UUID] = From(schemas.core.Deployment)
    infrastructure_document_id: Optional[UUID] = From(schemas.core.Deployment)

    class Config:
        extra = "forbid"


@copy_model_fields
class FlowRunUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a flow run."""

    name: str = From(schemas.core.FlowRun)
    flow_version: str = From(schemas.core.FlowRun)
    parameters: dict = From(schemas.core.FlowRun)
    empirical_policy: schemas.core.FlowRunPolicy = From(schemas.core.FlowRun)
    tags: List[str] = From(schemas.core.FlowRun)

    class Config:
        extra = "forbid"


@copy_model_fields
class StateCreate(PrefectBaseModel):
    """Data used by the Orion API to create a new state."""

    type: schemas.states.StateType = From(schemas.states.State)
    name: str = From(schemas.states.State)
    timestamp: schemas.core.DateTimeTZ = From(schemas.states.State)
    message: str = From(schemas.states.State)
    data: schemas.data.DataDocument = From(schemas.states.State)
    state_details: schemas.states.StateDetails = From(schemas.states.State)

    class Config:
        extra = "ignore"


@copy_model_fields
class TaskRunCreate(PrefectBaseModel):
    """Data used by the Orion API to create a task run"""

    # TaskRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the task run to create"
    )

    name: str = From(schemas.core.TaskRun)
    flow_run_id: UUID = From(schemas.core.TaskRun)
    task_key: str = From(schemas.core.TaskRun)
    dynamic_key: str = From(schemas.core.TaskRun)
    cache_key: str = From(schemas.core.TaskRun)
    cache_expiration: schemas.core.DateTimeTZ = From(schemas.core.TaskRun)
    task_version: str = From(schemas.core.TaskRun)
    empirical_policy: schemas.core.TaskRunPolicy = From(schemas.core.TaskRun)
    tags: List[str] = From(schemas.core.TaskRun)
    task_inputs: Dict[
        str,
        List[
            Union[
                schemas.core.TaskRunResult,
                schemas.core.Parameter,
                schemas.core.Constant,
            ]
        ],
    ] = From(schemas.core.TaskRun)


@copy_model_fields
class FlowRunCreate(PrefectBaseModel):
    """Data used by the Orion API to create a flow run."""

    class Config:
        extra = "forbid"

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: str = From(schemas.core.FlowRun)
    flow_id: UUID = From(schemas.core.FlowRun)
    deployment_id: UUID = From(schemas.core.FlowRun)
    flow_version: str = From(schemas.core.FlowRun)
    parameters: dict = From(schemas.core.FlowRun)
    context: dict = From(schemas.core.FlowRun)
    parent_task_run_id: UUID = From(schemas.core.FlowRun)
    infrastructure_document_id: Optional[UUID] = From(schemas.core.FlowRun)
    empirical_policy: schemas.core.FlowRunPolicy = From(schemas.core.FlowRun)
    tags: List[str] = From(schemas.core.FlowRun)
    idempotency_key: str = From(schemas.core.FlowRun)


@copy_model_fields
class DeploymentFlowRunCreate(PrefectBaseModel):
    """Data used by the Orion API to create a flow run from a deployment."""

    class Config:
        extra = "forbid"

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = From(schemas.core.FlowRun)
    parameters: dict = From(schemas.core.FlowRun)
    context: dict = From(schemas.core.FlowRun)
    infrastructure_document_id: Optional[UUID] = From(schemas.core.FlowRun)
    empirical_policy: schemas.core.FlowRunPolicy = From(schemas.core.FlowRun)
    tags: List[str] = From(schemas.core.FlowRun)
    idempotency_key: str = From(schemas.core.FlowRun)


@copy_model_fields
class SavedSearchCreate(PrefectBaseModel):
    """Data used by the Orion API to create a saved search."""

    name: str = From(schemas.core.SavedSearch)
    filters: List[schemas.core.SavedSearchFilter] = From(schemas.core.SavedSearch)

    class Config:
        extra = "forbid"


@copy_model_fields
class ConcurrencyLimitCreate(PrefectBaseModel):
    """Data used by the Orion API to create a concurrency limit."""

    tag: str = From(schemas.core.ConcurrencyLimit)
    concurrency_limit: int = From(schemas.core.ConcurrencyLimit)

    class Config:
        extra = "forbid"


@copy_model_fields
class BlockTypeCreate(PrefectBaseModel):
    """Data used by the Orion API to create a block type."""

    name: str = From(schemas.core.BlockType)
    slug: str = From(schemas.core.BlockType)
    logo_url: Optional[schemas.core.HttpUrl] = From(schemas.core.BlockType)
    documentation_url: Optional[schemas.core.HttpUrl] = From(schemas.core.BlockType)
    description: Optional[str] = From(schemas.core.BlockType)
    code_example: Optional[str] = From(schemas.core.BlockType)

    class Config:
        extra = "forbid"

    # validators
    _validate_slug_format = validator("slug", allow_reuse=True)(
        validate_block_type_slug
    )


@copy_model_fields
class BlockTypeUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a block type."""

    class Config:
        extra = "forbid"

    logo_url: Optional[schemas.core.HttpUrl] = From(schemas.core.BlockType)
    documentation_url: Optional[schemas.core.HttpUrl] = From(schemas.core.BlockType)
    description: Optional[str] = From(schemas.core.BlockType)
    code_example: Optional[str] = From(schemas.core.BlockType)


@copy_model_fields
class BlockSchemaCreate(PrefectBaseModel):
    """Data used by the Orion API to create a block schema."""

    fields: dict = From(schemas.core.BlockSchema)
    block_type_id: Optional[UUID] = From(schemas.core.BlockSchema)
    capabilities: List[str] = From(schemas.core.BlockSchema)
    version: str = From(schemas.core.BlockSchema)

    class Config:
        extra = "forbid"


@copy_model_fields
class BlockDocumentCreate(PrefectBaseModel):
    """Data used by the Orion API to create a block document."""

    name: Optional[str] = From(schemas.core.BlockDocument)
    data: dict = From(schemas.core.BlockDocument)
    block_schema_id: UUID = From(schemas.core.BlockDocument)
    block_type_id: UUID = From(schemas.core.BlockDocument)
    is_anonymous: bool = From(schemas.core.BlockDocument)

    class Config:
        extra = "forbid"

    # validators
    _validate_name_format = validator("name", allow_reuse=True)(
        validate_block_document_name
    )


@copy_model_fields
class BlockDocumentUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a block document."""

    data: dict = From(schemas.core.BlockDocument)

    class Config:
        extra = "forbid"


@copy_model_fields
class BlockDocumentReferenceCreate(PrefectBaseModel):
    """Data used to create block document reference."""

    id: UUID = From(schemas.core.BlockDocumentReference)
    parent_block_document_id: UUID = From(schemas.core.BlockDocumentReference)
    reference_block_document_id: UUID = From(schemas.core.BlockDocumentReference)
    name: str = From(schemas.core.BlockDocumentReference)

    class Config:
        extra = "forbid"


@copy_model_fields
class LogCreate(PrefectBaseModel):
    """Data used by the Orion API to create a log."""

    name: str = From(schemas.core.Log)
    level: int = From(schemas.core.Log)
    message: str = From(schemas.core.Log)
    timestamp: schemas.core.DateTimeTZ = From(schemas.core.Log)
    flow_run_id: UUID = From(schemas.core.Log)
    task_run_id: Optional[UUID] = From(schemas.core.Log)

    class Config:
        extra = "forbid"


@copy_model_fields
class WorkQueueCreate(PrefectBaseModel):
    """Data used by the Orion API to create a work queue."""

    name: str = From(schemas.core.WorkQueue)
    description: Optional[str] = From(schemas.core.WorkQueue)
    is_paused: bool = From(schemas.core.WorkQueue)
    concurrency_limit: Optional[int] = From(schemas.core.WorkQueue)

    # DEPRECATED

    filter: Optional[schemas.core.QueueFilter] = Field(
        None,
        description="Filter criteria for the work queue.",
        deprecated=True,
    )

    class Config:
        extra = "forbid"


@copy_model_fields
class WorkQueueUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a work queue."""

    description: Optional[str] = From(schemas.core.WorkQueue)
    is_paused: bool = From(schemas.core.WorkQueue)
    concurrency_limit: Optional[int] = From(schemas.core.WorkQueue)

    # DEPRECATED

    filter: Optional[schemas.core.QueueFilter] = Field(
        None,
        description="Filter criteria for the work queue.",
        deprecated=True,
    )

    # Names should not be updated, left here only for backwards-compatibility
    name: Optional[str] = Field(
        default=None, description="The name of the work queue.", deprecated=True
    )

    class Config:
        extra = "forbid"


@copy_model_fields
class FlowRunNotificationPolicyCreate(PrefectBaseModel):
    """Data used by the Orion API to create a flow run notification policy."""

    is_active: bool = From(schemas.core.FlowRunNotificationPolicy)
    state_names: List[str] = From(schemas.core.FlowRunNotificationPolicy)
    tags: List[str] = From(schemas.core.FlowRunNotificationPolicy)
    block_document_id: UUID = From(schemas.core.FlowRunNotificationPolicy)
    message_template: str = From(schemas.core.FlowRunNotificationPolicy)

    class Config:
        extra = "forbid"


@copy_model_fields
class FlowRunNotificationPolicyUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a flow run notification policy."""

    class Config:
        extra = "forbid"

    is_active: Optional[bool] = From(schemas.core.FlowRunNotificationPolicy)
    state_names: Optional[List[str]] = From(schemas.core.FlowRunNotificationPolicy)
    tags: Optional[List[str]] = From(schemas.core.FlowRunNotificationPolicy)
    block_document_id: Optional[UUID] = From(schemas.core.FlowRunNotificationPolicy)
    message_template: Optional[str] = From(schemas.core.FlowRunNotificationPolicy)
