import asyncio
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from uuid import UUID

import pendulum
from pendulum.datetime import DateTime

from .schemas.events import RelatedResource

if TYPE_CHECKING:
    from prefect._internal.schemas.bases import ObjectBaseModel
    from prefect.client.orchestration import PrefectClient

ResourceCacheEntry = Dict[str, Union[str, "ObjectBaseModel", None]]
RelatedResourceCache = Dict[str, Tuple[ResourceCacheEntry, DateTime]]

MAX_CACHE_SIZE = 100
RESOURCE_CACHE: RelatedResourceCache = {}


def tags_as_related_resources(tags: Iterable[str]) -> List[RelatedResource]:
    return [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.tag.{tag}",
                "prefect.resource.role": "tag",
            }
        )
        for tag in sorted(tags)
    ]


def object_as_related_resource(kind: str, role: str, object: Any) -> RelatedResource:
    resource_id = f"prefect.{kind}.{object.id}"

    return RelatedResource.model_validate(
        {
            "prefect.resource.id": resource_id,
            "prefect.resource.role": role,
            "prefect.resource.name": object.name,
        }
    )


async def related_resources_from_run_context(
    client: "PrefectClient",
    exclude: Optional[Set[str]] = None,
) -> List[RelatedResource]:
    from prefect.client.schemas.objects import FlowRun
    from prefect.context import FlowRunContext, TaskRunContext

    if exclude is None:
        exclude = set()

    flow_run_context = FlowRunContext.get()
    task_run_context = TaskRunContext.get()

    if not flow_run_context and not task_run_context:
        return []

    flow_run_id: Optional[UUID] = getattr(
        getattr(flow_run_context, "flow_run", None), "id", None
    ) or getattr(getattr(task_run_context, "task_run", None), "flow_run_id", None)
    if flow_run_id is None:
        return []

    related_objects: List[ResourceCacheEntry] = []

    async def dummy_read():
        return {}

    if flow_run_context:
        related_objects.append(
            {
                "kind": "flow-run",
                "role": "flow-run",
                "object": flow_run_context.flow_run,
            },
        )
    else:
        related_objects.append(
            await _get_and_cache_related_object(
                kind="flow-run",
                role="flow-run",
                client_method=client.read_flow_run,
                obj_id=flow_run_id,
                cache=RESOURCE_CACHE,
            )
        )

    if task_run_context:
        related_objects.append(
            {
                "kind": "task-run",
                "role": "task-run",
                "object": task_run_context.task_run,
            },
        )

    flow_run = related_objects[0]["object"]

    if isinstance(flow_run, FlowRun):
        related_objects += list(
            await asyncio.gather(
                _get_and_cache_related_object(
                    kind="flow",
                    role="flow",
                    client_method=client.read_flow,
                    obj_id=flow_run.flow_id,
                    cache=RESOURCE_CACHE,
                ),
                (
                    _get_and_cache_related_object(
                        kind="deployment",
                        role="deployment",
                        client_method=client.read_deployment,
                        obj_id=flow_run.deployment_id,
                        cache=RESOURCE_CACHE,
                    )
                    if flow_run.deployment_id
                    else dummy_read()
                ),
                (
                    _get_and_cache_related_object(
                        kind="work-queue",
                        role="work-queue",
                        client_method=client.read_work_queue,
                        obj_id=flow_run.work_queue_id,
                        cache=RESOURCE_CACHE,
                    )
                    if flow_run.work_queue_id
                    else dummy_read()
                ),
                (
                    _get_and_cache_related_object(
                        kind="work-pool",
                        role="work-pool",
                        client_method=client.read_work_pool,
                        obj_id=flow_run.work_pool_name,
                        cache=RESOURCE_CACHE,
                    )
                    if flow_run.work_pool_name
                    else dummy_read()
                ),
            )
        )

    related = []
    tags = set()

    for entry in related_objects:
        obj_ = entry.get("object")
        if obj_ is None:
            continue

        assert isinstance(entry["kind"], str) and isinstance(entry["role"], str)

        resource = object_as_related_resource(
            kind=entry["kind"], role=entry["kind"], object=obj_
        )

        if resource.id in exclude:
            continue

        related.append(resource)
        if hasattr(obj_, "tags"):
            tags |= set(obj_.tags)

    related += [
        resource
        for resource in tags_as_related_resources(tags)
        if resource.id not in exclude
    ]

    return related


async def _get_and_cache_related_object(
    kind: str,
    role: str,
    client_method: Callable[[Union[UUID, str]], Awaitable[Optional["ObjectBaseModel"]]],
    obj_id: Union[UUID, str],
    cache: RelatedResourceCache,
) -> ResourceCacheEntry:
    cache_key = f"{kind}.{obj_id}"
    entry = None

    if cache_key in cache:
        entry, _ = cache[cache_key]
    else:
        obj_ = await client_method(obj_id)
        entry = {
            "kind": kind,
            "object": obj_,
        }

    cache[cache_key] = (entry, pendulum.now("UTC"))

    # In the case of a worker or agent this cache could be long-lived. To keep
    # from running out of memory only keep `MAX_CACHE_SIZE` entries in the
    # cache.
    if len(cache) > MAX_CACHE_SIZE:
        oldest_key = sorted(
            [(key, timestamp) for key, (_, timestamp) in cache.items()],
            key=lambda k: k[1],
        )[0][0]

        if oldest_key:
            del cache[oldest_key]

    # Because the role is event specific and can change depending on the
    # type of event being emitted, this adds the role from the args to the
    # entry before returning it rather than storing it in the cache.
    entry["role"] = role
    return entry
