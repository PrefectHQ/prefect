from typing import Dict, List, Literal, Optional

from prefect.events.related import related_resources_from_run_context
from prefect.events.utilities import emit_event
from prefect.settings import get_current_settings

# Map block types to their URI schemes
STORAGE_URI_SCHEMES = {
    "local-file-system": lambda storage, path: f"file://{storage._resolve_path(path)}",
    "s3-bucket": lambda storage,
    path: f"s3://{storage.bucket_name}/{storage._resolve_path(path)}",
    "gcs-bucket": lambda storage,
    path: f"gs://{storage.bucket}/{storage._resolve_path(path)}",
    "azure-blob-storage": lambda storage,
    path: f"azure-blob://{storage.container_name}/{storage._resolve_path(path)}",
}


def get_result_resource_uri(store, key: str) -> Optional[str]:
    """
    Generate a URI for a result based on its storage backend.

    Args:
        store: A `ResultStore` instance.
        key: The key of the result to generate a URI for.

    TODO: Can't type-hint `store` because of a circular import.
    """
    from prefect.results import ResultStore

    if isinstance(store, ResultStore):
        storage = store.result_storage
        if storage is None:
            return

        # Get the block type name
        block_type = storage.get_block_type_slug()
        if block_type and block_type in STORAGE_URI_SCHEMES:
            return STORAGE_URI_SCHEMES[block_type](storage, key)

    # Generic fallback
    return f"prefect://{block_type}/{key}"


async def emit_lineage_event(
    event_name: str,
    upstream_resources: Optional[List[Dict[str, str]]] = None,
    downstream_resources: Optional[List[Dict[str, str]]] = None,
    direction_of_related_resources: Literal["upstream", "downstream"] = "upstream",
) -> None:
    """Emit lineage events showing relationships between resources.

    Args:
        event_name: The name of the event to emit
        upstream_resources: Optional list of RelatedResources that were upstream of
            the event
        downstream_resources: Optional list of Resources that were downstream
            of the event
    """
    if not get_current_settings().experiments.lineage_events_enabled:
        return

    upstream_resources = upstream_resources or []
    downstream_resources = downstream_resources or []

    for related_resource in upstream_resources:
        role = related_resource.get("prefect.resource.role")
        if not role:
            # Upstream resources must have a role. Instead of failing if this is
            # missing, we'll assign a generic role.
            related_resource["prefect.resource.role"] = "related"

    if direction_of_related_resources == "downstream":
        # Set the involved resources to force the EventsWorker to exclude these
        # from the related resources. Related resources are always considered
        # "upstream," but in some cases, we instead want to include these as
        # downstream resources.
        from prefect.client.orchestration import get_client  # Avoid a circular import

        with get_client() as client:
            involved_resources = await related_resources_from_run_context(client)
    else:
        # The EventsWorker will automatically include these as as upstream
        # resources for us, so no action is necessary.
        involved_resources = []

    # Emit an event for each downstream resource. This is necessary because
    # our event schema allows one primary resource and many related resources,
    # and for the purposes of lineage, related resources can only represent
    # upstream resources.
    for resource in downstream_resources:
        role = resource.get("prefect.resource.role")
        # Downstream resources need to have the lineage-resource role for
        # Prefect to consider them for lineage.
        resource["prefect.resource.role"] = "lineage-resource"

        if role and role != "lineage-resource":
            # TODO: The fact that lineage resources can only have the
            # "lineage-resource" role is a sign that we should revisit how we're
            # marking lineage resources. Should we be say there is a downstream
            # role AND we want to track lineage?
            resource["prefect.resource.downstream-role"] = role

        emit_event(
            event=event_name,
            resource=resource,
            related=upstream_resources,
            involved=involved_resources,
        )


async def emit_result_read_event(
    store,
    result_key: str,
    downstream_resources: Optional[List[Dict[str, str]]] = None,
    cached: bool = False,
) -> None:
    """
    Emit a lineage event showing a task or flow result was read.

    Args:
        store: A `ResultStore` instance.
        result_key: The key of the result to generate a URI for.
        downstream_resources: List of Resource objects that were
            downstream of the event

    TODO: Can't type-hint `store` because of a circular import.
    """
    if not get_current_settings().experiments.lineage_events_enabled:
        return

    result_resource_uri = get_result_resource_uri(store, result_key)
    if result_resource_uri:
        upstream_resources = [
            {
                "prefect.resource.id": result_resource_uri,
                "prefect.resource.role": "result",
            }
        ]
        event_name = "prefect.result.read"
        if cached:
            event_name += ".cached"

        await emit_lineage_event(
            event_name=event_name,
            upstream_resources=upstream_resources,
            downstream_resources=downstream_resources,
            direction_of_related_resources="downstream",
        )


async def emit_result_write_event(
    store,
    result_key: str,
    upstream_resources: Optional[List[Dict[str, str]]] = None,
) -> None:
    """
    Emit a lineage event showing a result was written

    Args:
        store: A `ResultStore` instance.
        result_key: The key of the result to generate a URI for.
        upstream_resources: Optional list of RelatedResource objects that were
            upstream of the event

    TODO: Can't type-hint `store` because of a circular import.
    """
    if not get_current_settings().experiments.lineage_events_enabled:
        return

    result_resource_uri = get_result_resource_uri(store, result_key)
    if result_resource_uri:
        downstream_resources = [
            {
                "prefect.resource.id": result_resource_uri,
                "prefect.resource.role": "result",
                # TODO: See comment in emit_lineage_event about "downstream-role"
                "prefect.resource.downstream-role": "result",
            }
        ]
        await emit_lineage_event(
            event_name="prefect.result.write",
            upstream_resources=upstream_resources,
            downstream_resources=downstream_resources,
        )
