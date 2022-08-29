"""
Reduced schemas for accepting API actions.
"""
import re
from typing import List, Optional
from uuid import UUID

from pydantic import Field, validator

import prefect.orion.schemas as schemas
from prefect.orion.utilities.schemas import PrefectBaseModel

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


class FlowCreate(
    schemas.core.Flow.subclass(
        name="FlowCreate",
        include_fields=["name", "tags"],
    )
):
    """Data used by the Orion API to create a flow."""

    class Config:
        extra = "forbid"


class FlowUpdate(
    schemas.core.Flow.subclass(name="FlowUpdate", include_fields=["tags"])
):
    """Data used by the Orion API to update a flow."""

    class Config:
        extra = "forbid"


class DeploymentCreate(
    schemas.core.Deployment.subclass(
        name="DeploymentCreate",
        include_fields=[
            "name",
            "version",
            "flow_id",
            "schedule",
            "is_schedule_active",
            "work_queue_name",
            "description",
            "tags",
            "parameters",
            "manifest_path",
            "parameter_openapi_schema",
            "storage_document_id",
            "path",
            "entrypoint",
            "infrastructure_document_id",
            "infra_overrides",
        ],
    )
):
    """Data used by the Orion API to create a deployment."""

    class Config:
        extra = "forbid"


class DeploymentUpdate(
    schemas.core.Deployment.subclass(
        name="DeploymentUpdate",
        include_fields=[
            "version",
            "schedule",
            "is_schedule_active",
            "description",
            "work_queue_name",
            "tags",
            "manifest_path",
            "path",
            "entrypoint",
            "parameters",
            "storage_document_id",
            "infrastructure_document_id",
            "infra_overrides",
        ],
    )
):
    """Data used by the Orion API to update a deployment."""

    class Config:
        extra = "forbid"


class FlowRunUpdate(
    schemas.core.FlowRun.subclass(
        name="FlowRunUpdate",
        include_fields=[
            "flow_version",
            "parameters",
            "name",
            "tags",
            "empirical_policy",
        ],
    )
):
    """Data used by the Orion API to update a flow run."""

    class Config:
        extra = "forbid"


class StateCreate(
    schemas.states.State.subclass(
        name="StateCreate",
        include_fields=[
            "type",
            "name",
            "message",
            "data",
            "state_details",
        ],
    )
):
    """Data used by the Orion API to create a new state."""

    class Config:
        extra = "forbid"


class TaskRunCreate(
    schemas.core.TaskRun.subclass(
        name="TaskRunCreate",
        include_fields=[
            "name",
            "flow_run_id",
            "task_key",
            "dynamic_key",
            "cache_key",
            "cache_expiration",
            "task_version",
            "empirical_policy",
            "tags",
            "task_inputs",
        ],
    )
):
    """Data used by the Orion API to create a task run"""

    # TaskRunCreate states must be provided as StateCreate objects
    state: StateCreate = Field(None, description="The state of the task run to create")


class FlowRunCreate(
    schemas.core.FlowRun.subclass(
        name="FlowRunCreate",
        include_fields=[
            "name",
            "flow_id",
            "deployment_id",
            "flow_version",
            "parameters",
            "context",
            "tags",
            "idempotency_key",
            "parent_task_run_id",
            "empirical_policy",
            "infrastructure_document_id",
        ],
    )
):
    """Data used by the Orion API to create a flow run."""

    class Config:
        extra = "forbid"

    # FlowRunCreate states must be provided as StateCreate objects
    state: StateCreate = Field(None, description="The state of the flow run to create")


class DeploymentFlowRunCreate(
    schemas.core.FlowRun.subclass(
        name="FlowRunCreate",
        include_fields=[
            "name",
            "parameters",
            "context",
            "tags",
            "idempotency_key",
            "empirical_policy",
            "infrastructure_document_id",
        ],
    )
):
    """Data used by the Orion API to create a flow run from a deployment."""

    class Config:
        extra = "forbid"

    # FlowRunCreate states must be provided as StateCreate objects
    state: StateCreate = Field(None, description="The state of the flow run to create")


class SavedSearchCreate(
    schemas.core.SavedSearch.subclass(
        name="SavedSearchCreate",
        include_fields=["name", "filters"],
    )
):
    """Data used by the Orion API to create a saved search."""

    class Config:
        extra = "forbid"


class ConcurrencyLimitCreate(
    schemas.core.ConcurrencyLimit.subclass(
        name="ConcurrencyLimitCreate",
        include_fields=["tag", "concurrency_limit"],
    )
):
    """Data used by the Orion API to create a concurrency limit."""

    class Config:
        extra = "forbid"


class BlockTypeCreate(
    schemas.core.BlockType.subclass(
        name="BlockTypeCreate",
        include_fields=[
            "name",
            "slug",
            "logo_url",
            "documentation_url",
            "description",
            "code_example",
        ],
    )
):
    """Data used by the Orion API to create a block type."""

    class Config:
        extra = "forbid"

    # validators
    _validate_slug_format = validator("slug", allow_reuse=True)(
        validate_block_type_slug
    )


class BlockTypeUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a block type."""

    class Config:
        extra = "forbid"

    logo_url: Optional[str] = None
    documentation_url: Optional[str] = None
    description: Optional[str] = None
    code_example: Optional[str] = None


class BlockSchemaCreate(
    schemas.core.BlockSchema.subclass(
        name="BlockSchemaCreate",
        include_fields=["fields", "capabilities", "block_type_id", "version"],
    )
):
    """Data used by the Orion API to create a block schema."""

    class Config:
        extra = "forbid"


class BlockDocumentCreate(
    schemas.core.BlockDocument.subclass(
        name="BlockDocumentCreate",
        include_fields=[
            "name",
            "data",
            "block_schema_id",
            "block_type_id",
            "is_anonymous",
        ],
    )
):
    """Data used by the Orion API to create a block document."""

    class Config:
        extra = "forbid"

    # validators
    _validate_name_format = validator("name", allow_reuse=True)(
        validate_block_document_name
    )


class BlockDocumentUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a block document."""

    class Config:
        extra = "forbid"

    data: Optional[dict] = None


class BlockDocumentReferenceCreate(
    schemas.core.BlockDocumentReference.subclass(
        name="BlockDocumentReferenceCreate",
        include_fields=[
            "id",
            "name",
            "parent_block_document_id",
            "reference_block_document_id",
        ],
    )
):
    """Data used to create block document reference."""

    class Config:
        extra = "forbid"


class LogCreate(
    schemas.core.Log.subclass(
        name="LogCreate",
        include_fields=[
            "name",
            "level",
            "message",
            "timestamp",
            "flow_run_id",
            "task_run_id",
        ],
    )
):
    """Data used by the Orion API to create a log."""

    class Config:
        extra = "forbid"


class WorkQueueCreate(
    schemas.core.WorkQueue.subclass(
        "WorkQueueCreate",
        include_fields=[
            "name",
            "description",
            "is_paused",
            "concurrency_limit",
            # DEPRECATED: filters are deprecated
            "filter",
        ],
    )
):
    """Data used by the Orion API to create a work queue."""

    class Config:
        extra = "forbid"


class WorkQueueUpdate(
    schemas.core.WorkQueue.subclass(
        "WorkQueueUpdate",
        include_fields=[
            "description",
            "is_paused",
            "concurrency_limit",
            # DEPRECATED: filters are deprecated
            "filter",
        ],
    )
):
    """Data used by the Orion API to update a work queue."""

    class Config:
        extra = "forbid"

    # DEPRECATED: names should not be updated, left here only for backwards-compatibility
    name: Optional[str] = Field(
        None, description="The name of the work queue.", deprecated=True
    )


class FlowRunNotificationPolicyCreate(
    schemas.core.FlowRunNotificationPolicy.subclass(
        "FlowRunNotificationPolicyCreate",
        include_fields=[
            "is_active",
            "state_names",
            "tags",
            "block_document_id",
            "message_template",
        ],
    )
):
    """Data used by the Orion API to create a flow run notification policy."""

    class Config:
        extra = "forbid"


class FlowRunNotificationPolicyUpdate(PrefectBaseModel):
    """Data used by the Orion API to update a flow run notification policy."""

    class Config:
        extra = "forbid"

    is_active: Optional[bool] = None
    state_names: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    block_document_id: Optional[UUID] = None
    message_template: Optional[str] = None
