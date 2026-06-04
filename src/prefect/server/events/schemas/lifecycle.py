"""Typed payloads and builders for `prefect.<object>.{created,updated,deleted}`
lifecycle events.

Each payload describes a domain object's post-state — everything a consumer
needs to act on the change without reading the object back from the API. The
shapes mirror Prefect Cloud's lifecycle-event payloads so the two emit the same
thing, minus Cloud-only concepts (accounts, workspaces, actors).

The builders here are pure functions of an ORM object and a timestamp, with no
dependency on the model layer, so any model module can import them without
risking a circular import.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from pydantic import ConfigDict, Field

from prefect._internal.uuid7 import uuid7
from prefect.server.events.schemas.events import Event
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.types import KeyValueLabels, StrictVariableValue
from prefect.types._datetime import DateTime

if TYPE_CHECKING:
    from prefect.server.database.orm_models import (
        BlockType,
        ConcurrencyLimit,
        ConcurrencyLimitV2,
        ORMArtifactCollection,
        ORMFlow,
        ORMVariable,
    )
    from prefect.server.events.schemas.automations import Automation
    from prefect.server.schemas.core import BlockDocument

RelatedResourceList = List[Dict[str, str]]


def _lifecycle_event(
    kind: str,
    action: str,
    resource_id: str,
    resource_name: Optional[str],
    payload: Dict[str, Any],
    occurred: DateTime,
    related: Optional[RelatedResourceList] = None,
) -> Event:
    resource: Dict[str, str] = {"prefect.resource.id": resource_id}
    if resource_name is not None:
        resource["prefect.resource.name"] = resource_name
    return Event(
        occurred=occurred,
        event=f"prefect.{kind}.{action}",
        resource=resource,
        related=related or [],
        payload=payload,
        id=uuid7(),
    )


class VariableEventPayload(PrefectBaseModel):
    """A variable's post-state: its name, value, and tags."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    value: StrictVariableValue
    tags: List[str] = Field(default_factory=list)


def variable_created_event(variable: "ORMVariable", occurred: DateTime) -> Event:
    """Create an event for variable creation."""
    return _variable_event("created", variable, occurred)


def variable_updated_event(variable: "ORMVariable", occurred: DateTime) -> Event:
    """Create an event for variable updates, carrying the full post-state."""
    return _variable_event("updated", variable, occurred)


def variable_deleted_event(variable: "ORMVariable", occurred: DateTime) -> Event:
    """Create an event for variable deletion."""
    return _variable_event("deleted", variable, occurred)


def _variable_event(action: str, variable: "ORMVariable", occurred: DateTime) -> Event:
    return _lifecycle_event(
        kind="variable",
        action=action,
        resource_id=f"prefect.variable.{variable.id}",
        resource_name=variable.name,
        payload=VariableEventPayload.model_validate(variable).model_dump(mode="json"),
        occurred=occurred,
    )


class FlowEventPayload(PrefectBaseModel):
    """A flow's post-state: its name, tags, and labels."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    tags: List[str] = Field(default_factory=list)
    labels: Optional[KeyValueLabels] = Field(default_factory=dict)


def flow_created_event(flow: "ORMFlow", occurred: DateTime) -> Event:
    """Create an event for flow creation."""
    return _flow_event("created", flow, occurred)


def flow_updated_event(flow: "ORMFlow", occurred: DateTime) -> Event:
    """Create an event for flow updates, carrying the full post-state."""
    return _flow_event("updated", flow, occurred)


def flow_deleted_event(flow: "ORMFlow", occurred: DateTime) -> Event:
    """Create an event for flow deletion."""
    return _flow_event("deleted", flow, occurred)


def _flow_event(action: str, flow: "ORMFlow", occurred: DateTime) -> Event:
    return _lifecycle_event(
        kind="flow",
        action=action,
        resource_id=f"prefect.flow.{flow.id}",
        resource_name=flow.name,
        payload=FlowEventPayload.model_validate(flow).model_dump(mode="json"),
        occurred=occurred,
    )


class BlockTypeEventPayload(PrefectBaseModel):
    """A block type's post-state: its identity, presentation, and protection."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    logo_url: Optional[str] = None
    documentation_url: Optional[str] = None
    description: Optional[str] = None
    code_example: Optional[str] = None
    is_protected: bool = False


def block_type_created_event(block_type: "BlockType", occurred: DateTime) -> Event:
    """Create an event for block type creation."""
    return _block_type_event("created", block_type, occurred)


def block_type_updated_event(block_type: "BlockType", occurred: DateTime) -> Event:
    """Create an event for block type updates, carrying the full post-state."""
    return _block_type_event("updated", block_type, occurred)


def block_type_deleted_event(block_type: "BlockType", occurred: DateTime) -> Event:
    """Create an event for block type deletion."""
    return _block_type_event("deleted", block_type, occurred)


def _block_type_event(
    action: str, block_type: "BlockType", occurred: DateTime
) -> Event:
    return _lifecycle_event(
        kind="block-type",
        action=action,
        resource_id=f"prefect.block-type.{block_type.id}",
        resource_name=block_type.name,
        payload=BlockTypeEventPayload.model_validate(block_type).model_dump(
            mode="json"
        ),
        occurred=occurred,
    )


class BlockDocumentBlockType(PrefectBaseModel):
    """The block type a block document belongs to, nested on its block schema."""

    id: UUID
    name: str


class BlockSchemaEventPayload(PrefectBaseModel):
    """The schema a block document conforms to, with its block type nested."""

    capabilities: List[str] = Field(default_factory=list)
    block_type: Optional[BlockDocumentBlockType] = None


class BlockDocumentEventPayload(PrefectBaseModel):
    """A block document's post-state: its name, the non-secret string values of
    its data, and the nested block schema (capabilities and block type)."""

    name: Optional[str] = None
    data: Dict[str, str] = Field(default_factory=dict)
    block_schema: Optional[BlockSchemaEventPayload] = None


def block_document_created_event(
    block_document: "BlockDocument", occurred: DateTime
) -> Event:
    """Create an event for block document creation."""
    return _block_document_event("created", block_document, occurred)


def block_document_updated_event(
    block_document: "BlockDocument", occurred: DateTime
) -> Event:
    """Create an event for block document updates, carrying the full post-state."""
    return _block_document_event("updated", block_document, occurred)


def block_document_deleted_event(
    block_document: "BlockDocument", occurred: DateTime
) -> Event:
    """Create an event for block document deletion."""
    return _block_document_event("deleted", block_document, occurred)


def _block_document_event(
    action: str, block_document: "BlockDocument", occurred: DateTime
) -> Event:
    schema = block_document.block_schema
    secret_keys = set(
        (schema.fields.get("secret_fields") or []) if schema is not None else []
    )

    block_schema_payload: Optional[BlockSchemaEventPayload] = None
    if schema is not None:
        block_schema_payload = BlockSchemaEventPayload(
            capabilities=schema.capabilities,
            block_type=BlockDocumentBlockType(
                id=block_document.block_type_id,
                name=block_document.block_type_name or "",
            ),
        )

    payload = BlockDocumentEventPayload(
        name=block_document.name,
        data={
            key: value
            for key, value in block_document.data.items()
            if key not in secret_keys and isinstance(value, str)
        },
        block_schema=block_schema_payload,
    )

    related: RelatedResourceList = [
        {
            "prefect.resource.id": f"prefect.block-type.{block_document.block_type_id}",
            "prefect.resource.role": "block-type",
        },
        {
            "prefect.resource.id": (
                f"prefect.block-schema.{block_document.block_schema_id}"
            ),
            "prefect.resource.role": "block-schema",
        },
    ]
    if block_document.block_type_name:
        related[0]["prefect.resource.name"] = block_document.block_type_name

    return _lifecycle_event(
        kind="block-document",
        action=action,
        resource_id=f"prefect.block-document.{block_document.id}",
        resource_name=block_document.name,
        payload=payload.model_dump(mode="json"),
        occurred=occurred,
        related=related,
    )


class ConcurrencyLimitV2EventPayload(PrefectBaseModel):
    """A global concurrency limit's published configuration. Runtime slot
    accounting is intentionally omitted — the event carries configuration."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    limit: int
    active: bool
    slot_decay_per_second: float


def concurrency_limit_v2_created_event(
    concurrency_limit: "ConcurrencyLimitV2", occurred: DateTime
) -> Event:
    """Create an event for global concurrency limit creation."""
    return _concurrency_limit_v2_event("created", concurrency_limit, occurred)


def concurrency_limit_v2_updated_event(
    concurrency_limit: "ConcurrencyLimitV2", occurred: DateTime
) -> Event:
    """Create an event for global concurrency limit updates, with post-state."""
    return _concurrency_limit_v2_event("updated", concurrency_limit, occurred)


def concurrency_limit_v2_deleted_event(
    concurrency_limit: "ConcurrencyLimitV2", occurred: DateTime
) -> Event:
    """Create an event for global concurrency limit deletion."""
    return _concurrency_limit_v2_event("deleted", concurrency_limit, occurred)


def _concurrency_limit_v2_event(
    action: str, concurrency_limit: "ConcurrencyLimitV2", occurred: DateTime
) -> Event:
    return _lifecycle_event(
        kind="concurrency-limit",
        action=action,
        resource_id=f"prefect.concurrency-limit.{concurrency_limit.id}",
        resource_name=concurrency_limit.name,
        payload=ConcurrencyLimitV2EventPayload.model_validate(
            concurrency_limit
        ).model_dump(mode="json"),
        occurred=occurred,
    )


class ConcurrencyLimitEventPayload(PrefectBaseModel):
    """A tag-based (v1) concurrency limit's configuration: the tag it applies to
    and its limit. Active slot run-ids are runtime accounting and are omitted."""

    model_config = ConfigDict(from_attributes=True)

    tag: str
    concurrency_limit: int


def concurrency_limit_created_event(
    concurrency_limit: "ConcurrencyLimit", occurred: DateTime
) -> Event:
    """Create an event for tag-based concurrency limit creation."""
    return _concurrency_limit_event("created", concurrency_limit, occurred)


def concurrency_limit_updated_event(
    concurrency_limit: "ConcurrencyLimit", occurred: DateTime
) -> Event:
    """Create an event for tag-based concurrency limit updates, with post-state."""
    return _concurrency_limit_event("updated", concurrency_limit, occurred)


def concurrency_limit_deleted_event(
    concurrency_limit: "ConcurrencyLimit", occurred: DateTime
) -> Event:
    """Create an event for tag-based concurrency limit deletion."""
    return _concurrency_limit_event("deleted", concurrency_limit, occurred)


def _concurrency_limit_event(
    action: str, concurrency_limit: "ConcurrencyLimit", occurred: DateTime
) -> Event:
    return _lifecycle_event(
        kind="concurrency-limit",
        action=action,
        resource_id=f"prefect.concurrency-limit.{concurrency_limit.id}",
        resource_name=concurrency_limit.tag,
        payload=ConcurrencyLimitEventPayload.model_validate(
            concurrency_limit
        ).model_dump(mode="json"),
        occurred=occurred,
    )


class ArtifactCollectionEventPayload(PrefectBaseModel):
    """An artifact collection's post-state: the collection key, the artifact
    type, and its data and description. The latest artifact and its flow/task
    runs ride the event's `related` resources, not the payload."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    type: Optional[str] = None
    data: Optional[Any] = None
    description: Optional[str] = None


def artifact_collection_created_event(
    artifact_collection: "ORMArtifactCollection", occurred: DateTime
) -> Event:
    """Create an event for artifact collection creation."""
    return _artifact_collection_event("created", artifact_collection, occurred)


def artifact_collection_updated_event(
    artifact_collection: "ORMArtifactCollection", occurred: DateTime
) -> Event:
    """Create an event for artifact collection updates, carrying the post-state."""
    return _artifact_collection_event("updated", artifact_collection, occurred)


def artifact_collection_deleted_event(
    artifact_collection: "ORMArtifactCollection", occurred: DateTime
) -> Event:
    """Create an event for artifact collection deletion."""
    return _artifact_collection_event("deleted", artifact_collection, occurred)


def _artifact_collection_event(
    action: str, artifact_collection: "ORMArtifactCollection", occurred: DateTime
) -> Event:
    related: RelatedResourceList = [
        {
            "prefect.resource.id": (
                f"prefect.artifact.{artifact_collection.latest_id}"
            ),
            "prefect.resource.role": "latest",
        }
    ]
    if artifact_collection.flow_run_id:
        related.append(
            {
                "prefect.resource.id": (
                    f"prefect.flow-run.{artifact_collection.flow_run_id}"
                ),
                "prefect.resource.role": "flow-run",
            }
        )
    if artifact_collection.task_run_id:
        related.append(
            {
                "prefect.resource.id": (
                    f"prefect.task-run.{artifact_collection.task_run_id}"
                ),
                "prefect.resource.role": "task-run",
            }
        )

    return _lifecycle_event(
        kind="artifact-collection",
        action=action,
        resource_id=f"prefect.artifact-collection.{artifact_collection.id}",
        resource_name=artifact_collection.key,
        payload=ArtifactCollectionEventPayload.model_validate(
            artifact_collection
        ).model_dump(mode="json"),
        occurred=occurred,
        related=related,
    )


def automation_created_event(automation: "Automation", occurred: DateTime) -> Event:
    """Create an event for automation creation."""
    return _automation_event("created", automation, occurred)


def automation_updated_event(automation: "Automation", occurred: DateTime) -> Event:
    """Create an event for automation updates, carrying the full post-state."""
    return _automation_event("updated", automation, occurred)


def automation_deleted_event(automation: "Automation", occurred: DateTime) -> Event:
    """Create an event for automation deletion."""
    return _automation_event("deleted", automation, occurred)


def _automation_event(
    action: str, automation: "Automation", occurred: DateTime
) -> Event:
    return _lifecycle_event(
        kind="automation",
        action=action,
        resource_id=f"prefect.automation.{automation.id}",
        resource_name=automation.name,
        payload=automation.model_dump(mode="json"),
        occurred=occurred,
    )
