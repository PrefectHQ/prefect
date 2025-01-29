from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, Sequence, Union

from typing_extensions import TypeAlias

from prefect.events.related import related_resources_from_run_context
from prefect.events.schemas.events import RelatedResource
from prefect.events.utilities import emit_event
from prefect.settings import get_current_settings

if TYPE_CHECKING:
    from prefect.results import ResultStore

LineageResources: TypeAlias = Sequence[Union[RelatedResource, dict[str, str]]]

# Map block types to their URI schemes
STORAGE_URI_SCHEMES = {
    "local-file-system": "file://{path}",
    "s3-bucket": "s3://{storage.bucket_name}/{path}",
    "gcs-bucket": "gs://{storage.bucket}/{path}",
    "azure-blob-storage": "azure-blob://{storage.container_name}/{path}",
}


def get_result_resource_uri(
    store: "ResultStore",
    key: str,
) -> Optional[str]:
    """
    Generate a URI for a result based on its storage backend.

    Args:
        store: A `ResultStore` instance.
        key: The key of the result to generate a URI for.
    """
    storage = store.result_storage
    if storage is None:
        return

    path = store._resolved_key_path(key)

    block_type = storage.get_block_type_slug()
    if block_type and block_type in STORAGE_URI_SCHEMES:
        return STORAGE_URI_SCHEMES[block_type].format(storage=storage, path=path)

    # Generic fallback
    return f"prefect://{block_type}/{path}"


async def emit_lineage_event(
    event_name: str,
    upstream_resources: Optional[LineageResources] = None,
    downstream_resources: Optional[LineageResources] = None,
    direction_of_run_from_event: Literal["upstream", "downstream"] = "downstream",
) -> None:
    """Emit lineage events showing relationships between resources.

    Args:
        event_name: The name of the event to emit
        upstream_resources: Optional list of RelatedResources that were upstream of
            the event
        downstream_resources: Optional list of Resources that were downstream
            of the event
        direction_of_run_from_event: The direction of the current run from
            the event. E.g., if we're in a flow run and
            `direction_of_run_from_event` is "downstream", then the flow run is
            considered downstream of the resource's event.
    """
    from prefect.client.orchestration import get_client  # Avoid a circular import

    if not get_current_settings().experiments.lineage_events_enabled:
        return

    upstream_resources = list(upstream_resources) if upstream_resources else []
    downstream_resources = list(downstream_resources) if downstream_resources else []

    async with get_client() as client:
        context_resources = await related_resources_from_run_context(client)

    tag_resources = [
        res for res in context_resources if res.get("prefect.resource.role") == "tag"
    ]
    context_resources = [
        res for res in context_resources if res.get("prefect.resource.role") != "tag"
    ]

    # NOTE: We handle adding run-related resources to the event here instead of in
    # the EventsWorker because not all run-related resources are upstream from
    # every lineage event (they might be downstream). The EventsWorker only adds
    # related resources to the "related" field in the event, which, for
    # lineage-related events, tracks upstream resources only. For downstream
    # resources, we need to emit an event for each downstream resource.
    if direction_of_run_from_event == "downstream":
        downstream_resources.extend(context_resources)
    else:
        upstream_resources.extend(context_resources)

    # We want to consider all resources upstream and downstream of the event as
    # lineage-related, including flows, flow runs, etc., so we add the label to
    # all resources involved in the event.
    for res in upstream_resources + downstream_resources:
        if "prefect.resource.lineage-group" not in res:
            res["prefect.resource.lineage-group"] = "global"

    # Emit an event for each downstream resource. This is necessary because
    # our event schema allows one primary resource and many related resources,
    # and for the purposes of lineage, related resources can only represent
    # upstream resources.
    for resource in downstream_resources:
        emit_kwargs: Dict[str, Any] = {
            "event": event_name,
            "resource": resource,
            "related": upstream_resources + tag_resources,
        }

        emit_event(**emit_kwargs)


async def emit_result_read_event(
    store: "ResultStore",
    result_key: str,
    downstream_resources: Optional[LineageResources] = None,
    cached: bool = False,
) -> None:
    """
    Emit a lineage event showing a task or flow result was read.

    Args:
        store: A `ResultStore` instance.
        result_key: The key of the result to generate a URI for.
        downstream_resources: List of resources that were
            downstream of the event's resource.
    """
    if not get_current_settings().experiments.lineage_events_enabled:
        return

    result_resource_uri = get_result_resource_uri(store, result_key)
    if result_resource_uri:
        upstream_resources = [
            RelatedResource(
                root={
                    "prefect.resource.id": result_resource_uri,
                    "prefect.resource.role": "result",
                }
            )
        ]
        event_name = "prefect.result.read"
        if cached:
            event_name += ".cached"

        await emit_lineage_event(
            event_name=event_name,
            upstream_resources=upstream_resources,
            downstream_resources=downstream_resources,
            direction_of_run_from_event="downstream",
        )


async def emit_result_write_event(
    store: "ResultStore",
    result_key: str,
    upstream_resources: Optional[LineageResources] = None,
) -> None:
    """
    Emit a lineage event showing a task or flow result was written.

    Args:
        store: A `ResultStore` instance.
        result_key: The key of the result to generate a URI for.
        upstream_resources: Optional list of resources that were
            upstream of the event's resource.
    """
    if not get_current_settings().experiments.lineage_events_enabled:
        return

    result_resource_uri = get_result_resource_uri(store, result_key)
    if result_resource_uri:
        downstream_resources = [
            {
                "prefect.resource.id": result_resource_uri,
                "prefect.resource.role": "result",
            }
        ]
        await emit_lineage_event(
            event_name="prefect.result.write",
            upstream_resources=upstream_resources,
            downstream_resources=downstream_resources,
            direction_of_run_from_event="upstream",
        )


async def emit_external_resource_lineage(
    event_name: str = "prefect.lineage.event",
    upstream_resources: Optional[LineageResources] = None,
    downstream_resources: Optional[LineageResources] = None,
    context_resources: Optional[LineageResources] = None,
) -> None:
    """Emit lineage events connecting external resources to Prefect context resources.

    This function emits events that place the current Prefect context resources
    (like flow runs, task runs) as:
    1. Downstream of any provided upstream external resources
    2. Upstream of any provided downstream external resources

    Args:
        upstream_resources: Optional sequence of resources that are upstream of the
            current Prefect context
        downstream_resources: Optional sequence of resources that are downstream of
            the current Prefect context
    """
    from prefect.client.orchestration import get_client

    if not get_current_settings().experiments.lineage_events_enabled:
        return

    upstream_resources = list(upstream_resources) if upstream_resources else []
    downstream_resources = list(downstream_resources) if downstream_resources else []

    # Get the current Prefect context resources (flow runs, task runs, etc.)
    if not context_resources:
        async with get_client() as client:
            context_resources = await related_resources_from_run_context(client)

    tag_resources = [
        res for res in context_resources if res.get("prefect.resource.role") == "tag"
    ]
    context_resources = [
        res for res in context_resources if res.get("prefect.resource.role") != "tag"
    ]

    # Add lineage group label to all resources
    for res in upstream_resources + downstream_resources + context_resources:
        if "prefect.resource.lineage-group" not in res:
            res["prefect.resource.lineage-group"] = "global"

    # For each context resource, emit an event showing it as downstream of upstream resources
    if upstream_resources:
        for context_resource in context_resources:
            emit_kwargs: Dict[str, Any] = {
                "event": "prefect.lineage.upstream-interaction",
                "resource": context_resource,
                "related": upstream_resources + tag_resources,
            }
            emit_event(**emit_kwargs)

    # For each downstream resource, emit an event showing it as downstream of context resources
    for downstream_resource in downstream_resources:
        emit_kwargs: Dict[str, Any] = {
            "event": "prefect.lineage.downstream-interaction",
            "resource": downstream_resource,
            "related": context_resources + tag_resources,
        }
        emit_event(**emit_kwargs)

        # For each downstream resource, emit an event showing it as downstream of upstream resources
        if upstream_resources:
            direct_emit_kwargs = {
                "event": event_name,
                "resource": downstream_resource,
                "related": upstream_resources + tag_resources,
            }
            emit_event(**direct_emit_kwargs)
