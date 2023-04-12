from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Union
from uuid import UUID

from .schemas import RelatedResource

if TYPE_CHECKING:
    from prefect.client.schemas import FlowRun
    from prefect.server.schemas.core import Flow


ObjectDict = Dict[str, Union["Flow", "FlowRun"]]
related_resource_cache: Dict[UUID, ObjectDict] = {}


def tags_as_related_resources(tags: Iterable[str]) -> List[RelatedResource]:
    return [
        RelatedResource(
            __root__={
                "prefect.resource.id": f"prefect.tag.{tag}",
                "prefect.resource.role": "tag",
            }
        )
        for tag in sorted(tags)
    ]


def object_as_related_resource(kind: str, role: str, object: Any) -> RelatedResource:
    resource_id = f"prefect.{kind}.{object.id}"

    return RelatedResource(
        __root__={
            "prefect.resource.id": resource_id,
            "prefect.resource.role": role,
            "prefect.resource.name": object.name,
        }
    )


async def related_resources_from_run_context(
    exclude: Optional[Set[str]] = None,
) -> List[RelatedResource]:
    from prefect.client.orchestration import get_client
    from prefect.context import FlowRunContext, TaskRunContext

    if exclude is None:
        exclude = set()

    flow_run_context = FlowRunContext.get()
    task_run_context = TaskRunContext.get()

    if not flow_run_context and not task_run_context:
        return []

    flow_run_id: UUID = (
        flow_run_context.flow_run.id
        if flow_run_context
        else task_run_context.task_run.flow_run_id
    )

    objects = related_resource_cache.get(flow_run_id, {})

    async with get_client() as client:
        if "flow-run" not in objects:
            flow_run = await client.read_flow_run(flow_run_id)
            if flow_run:
                objects["flow-run"] = flow_run

        if "flow" not in objects and "flow-run" in objects:
            flow = await client.read_flow(objects["flow-run"].flow_id)
            if flow:
                objects["flow"] = flow

        related_resource_cache[flow_run_id] = objects

    related = []
    tags = set()

    for kind, obj in objects.items():
        resource = object_as_related_resource(kind=kind, role=kind, object=obj)

        if resource.id in exclude:
            continue

        related.append(resource)
        tags |= set(obj.tags)

    related += [
        resource
        for resource in tags_as_related_resources(tags)
        if resource.id not in exclude
    ]

    return related
