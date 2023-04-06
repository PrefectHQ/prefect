from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple
from uuid import UUID

from .schemas import RelatedResource

if TYPE_CHECKING:
    from prefect.client.schemas import FlowRun
    from prefect.server.schemas.core import Flow

related_resource_cache: Dict[UUID, Tuple[Optional["FlowRun"], Optional["Flow"]]] = {}


async def related_resources_from_run_context(
    exclude: Optional[Set[str]] = None,
) -> List[RelatedResource]:
    from prefect.context import FlowRunContext, TaskRunContext

    if exclude is None:
        exclude = set()

    flow_run_id: Optional[UUID] = None
    flow_run: Optional["FlowRun"] = None
    flow: Optional["Flow"] = None

    flow_run_context = FlowRunContext.get()

    if flow_run_context is None:
        task_run_context = TaskRunContext.get()
        if task_run_context is None:
            return []

        flow_run_id = task_run_context.task_run.flow_run_id

        if flow_run_id in related_resource_cache:
            flow_run, flow = related_resource_cache[flow_run_id]
        else:
            client = task_run_context.client
            flow_run = await client.read_flow_run(flow_run_id)
            flow = await client.read_flow(flow_run.flow_id) if flow_run else None
            related_resource_cache[flow_run_id] = (flow_run, flow)
    else:
        flow_run_id = flow_run_context.flow_run.id

        if flow_run_id in related_resource_cache:
            flow_run, flow = related_resource_cache[flow_run_id]
        else:
            client = flow_run_context.client
            flow_run = flow_run_context.flow_run
            # The `flow` attached to the run context is an instance of the
            # actual flow function itself and not the database representation.
            # We request the database version here to ensure we have the id and
            # tags needed to emit in the event.
            flow = await client.read_flow(flow_run.flow_id)
            related_resource_cache[flow_run_id] = (flow_run, flow)

    related = []
    tags = set()

    if flow_run and f"prefect.flow-run.{flow_run.id}" not in exclude:
        related.append(
            RelatedResource(
                __root__={
                    "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                    "prefect.resource.role": "flow-run",
                    "prefect.name": flow_run.name,
                }
            )
        )
        tags |= set(flow_run.tags)

    if flow and f"prefect.flow.{flow.id}" not in exclude:
        related.append(
            RelatedResource(
                __root__={
                    "prefect.resource.id": f"prefect.flow.{flow.id}",
                    "prefect.resource.role": "flow",
                    "prefect.name": flow.name,
                }
            )
        )
        tags |= set(flow.tags)

    related += [
        RelatedResource(
            __root__={
                "prefect.resource.id": f"prefect.tag.{tag}",
                "prefect.resource.role": "tag",
            }
        )
        for tag in sorted(tags)
        if f"prefect.tag.{tag}" not in exclude
    ]

    return related
