from datetime import datetime, timedelta
from typing import Any, Dict, List, MutableMapping, Optional, Set, Union
from uuid import UUID, uuid4

from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database.orm_models import (
    ORMDeployment,
    ORMFlow,
    ORMFlowRun,
    ORMFlowRunState,
    ORMTaskRun,
    ORMTaskRunState,
    ORMWorkPool,
    ORMWorkQueue,
)
from prefect.server.events.schemas.events import Event
from prefect.server.models import deployments
from prefect.server.schemas.statuses import DeploymentStatus
from prefect.settings import PREFECT_API_EVENTS_RELATED_RESOURCE_CACHE_TTL
from prefect.types._datetime import DateTime, now
from prefect.utilities.text import truncated_to

ResourceData = Dict[str, Dict[str, Any]]
RelatedResourceList = List[Dict[str, str]]


# Some users use state messages to convey error messages and large results; let's
# truncate them so they don't blow out the size of a message
TRUNCATE_STATE_MESSAGES_AT = 100_000


_flow_run_resource_data_cache: MutableMapping[UUID, ResourceData] = TTLCache(
    maxsize=1000,
    ttl=PREFECT_API_EVENTS_RELATED_RESOURCE_CACHE_TTL.value().total_seconds(),
)


async def flow_run_state_change_event(
    session: AsyncSession,
    occurred: datetime,
    flow_run: ORMFlowRun,
    initial_state_id: Optional[UUID],
    initial_state: Optional[schemas.states.State],
    validated_state_id: Optional[UUID],
    validated_state: schemas.states.State,
) -> Event:
    return Event(
        occurred=occurred,
        event=f"prefect.flow-run.{validated_state.name}",
        resource={
            "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
            "prefect.resource.name": flow_run.name,
            "prefect.state-message": truncated_to(
                TRUNCATE_STATE_MESSAGES_AT, validated_state.message
            ),
            "prefect.state-name": validated_state.name or "",
            "prefect.state-timestamp": (
                validated_state.timestamp.isoformat()
                if validated_state.timestamp
                else None
            ),
            "prefect.state-type": validated_state.type.value,
        },
        related=await _flow_run_related_resources_from_orm(
            session=session, flow_run=flow_run
        ),
        payload={
            "intended": {
                "from": _state_type(initial_state),
                "to": _state_type(validated_state),
            },
            "initial_state": state_payload(initial_state),
            "validated_state": state_payload(validated_state),
        },
        # Here we use the state's ID as the ID of the event as well, in order to
        # establish the ordering of the state-change events
        id=validated_state_id,
        follows=initial_state_id if _timing_is_tight(occurred, initial_state) else None,
    )


async def _flow_run_related_resources_from_orm(
    session: AsyncSession, flow_run: ORMFlowRun
) -> RelatedResourceList:
    resource_data = _flow_run_resource_data_cache.get(flow_run.id)
    if not resource_data:
        flow = await models.flows.read_flow(session=session, flow_id=flow_run.flow_id)
        deployment: Optional[ORMDeployment] = None
        if flow_run.deployment_id:
            deployment = await deployments.read_deployment(
                session, deployment_id=flow_run.deployment_id
            )

        work_queue = None
        if flow_run.work_queue_id:
            work_queue = await models.work_queues.read_work_queue(
                session, work_queue_id=flow_run.work_queue_id
            )

        work_pool = work_queue.work_pool if work_queue is not None else None

        task_run: Optional[ORMTaskRun] = None
        if flow_run.parent_task_run_id:
            task_run = await models.task_runs.read_task_run(
                session,
                task_run_id=flow_run.parent_task_run_id,
            )

        resource_data = _as_resource_data(
            flow_run, flow, deployment, work_queue, work_pool, task_run
        )
        _flow_run_resource_data_cache[flow_run.id] = resource_data

    return _resource_data_as_related_resources(
        resource_data,
        excluded_kinds=["flow-run"],
    ) + _provenance_as_related_resources(flow_run.created_by)


def _as_resource_data(
    flow_run: ORMFlowRun,
    flow: Union[ORMFlow, schemas.core.Flow, None],
    deployment: Union[ORMDeployment, schemas.responses.DeploymentResponse, None],
    work_queue: Union[ORMWorkQueue, schemas.responses.WorkQueueResponse, None],
    work_pool: Union[ORMWorkPool, schemas.core.WorkPool, None],
    task_run: Union[ORMTaskRun, schemas.core.TaskRun, None] = None,
) -> ResourceData:
    return {
        "flow-run": {
            "id": str(flow_run.id),
            "name": flow_run.name,
            "tags": flow_run.tags if flow_run.tags else [],
            "role": "flow-run",
        },
        "flow": (
            {
                "id": str(flow.id),
                "name": flow.name,
                "tags": flow.tags if flow.tags else [],
                "role": "flow",
            }
            if flow
            else {}
        ),
        "deployment": (
            {
                "id": str(deployment.id),
                "name": deployment.name,
                "tags": deployment.tags if deployment.tags else [],
                "role": "deployment",
            }
            if deployment
            else {}
        ),
        "work-queue": (
            {
                "id": str(work_queue.id),
                "name": work_queue.name,
                "tags": [],
                "role": "work-queue",
            }
            if work_queue
            else {}
        ),
        "work-pool": (
            {
                "id": str(work_pool.id),
                "name": work_pool.name,
                "tags": [],
                "role": "work-pool",
                "type": work_pool.type,
            }
            if work_pool
            else {}
        ),
        "task-run": (
            {
                "id": str(task_run.id),
                "name": task_run.name,
                "tags": task_run.tags if task_run.tags else [],
                "role": "task-run",
            }
            if task_run
            else {}
        ),
    }


def _resource_data_as_related_resources(
    resource_data: ResourceData,
    excluded_kinds: Optional[List[str]] = None,
) -> RelatedResourceList:
    related = []
    tags: Set[str] = set()

    if excluded_kinds is None:
        excluded_kinds = []

    for kind, data in resource_data.items():
        tags |= set(data.get("tags", []))

        if kind in excluded_kinds or not data:
            continue

        related_resource = {
            "prefect.resource.id": f"prefect.{kind}.{data['id']}",
            "prefect.resource.role": data["role"],
            "prefect.resource.name": data["name"],
        }

        if kind == "work-pool":
            related_resource["prefect.work-pool.type"] = data["type"]

        related.append(related_resource)

    related += [
        {
            "prefect.resource.id": f"prefect.tag.{tag}",
            "prefect.resource.role": "tag",
        }
        for tag in sorted(tags)
    ]

    return related


def _provenance_as_related_resources(
    created_by: Optional[schemas.core.CreatedBy],
) -> RelatedResourceList:
    if not created_by:
        return []

    resource_id: str

    if created_by.type == "DEPLOYMENT":
        resource_id = f"prefect.deployment.{created_by.id}"
    elif created_by.type == "AUTOMATION":
        resource_id = f"prefect.automation.{created_by.id}"
    else:
        return []

    related = {
        "prefect.resource.id": resource_id,
        "prefect.resource.role": "creator",
    }
    if created_by.display_value:
        related["prefect.resource.name"] = created_by.display_value
    return [related]


def _state_type(
    state: Union[ORMFlowRunState, ORMTaskRunState, Optional[schemas.states.State]],
) -> Optional[str]:
    return str(state.type.value) if state else None


def state_payload(state: Optional[schemas.states.State]) -> Optional[Dict[str, str]]:
    """Given a State, return the essential string parts of it for use in an
    event payload"""
    if not state:
        return None
    payload: Dict[str, str] = {"type": state.type.value}
    if state.name:
        payload["name"] = state.name
    if state.message:
        payload["message"] = truncated_to(TRUNCATE_STATE_MESSAGES_AT, state.message)
    if state.is_paused():
        payload["pause_reschedule"] = str(state.state_details.pause_reschedule).lower()
    return payload


def _timing_is_tight(
    occurred: datetime,
    initial_state: Union[
        ORMFlowRunState, ORMTaskRunState, Optional[schemas.states.State]
    ],
) -> bool:
    # Only connect events with event.follows if the timing here is tight, which will
    # help us resolve the order of these events if they happen to be delivered out of
    # order.  If the preceding state change happened a while back, don't worry about
    # it because the order is very likely to be unambiguous.
    TIGHT_TIMING = timedelta(minutes=5)
    if initial_state and initial_state.timestamp:
        return bool(-TIGHT_TIMING < (occurred - initial_state.timestamp) < TIGHT_TIMING)

    return False


async def deployment_status_event(
    session: AsyncSession,
    deployment_id: UUID,
    status: DeploymentStatus,
    occurred: DateTime,
) -> Event:
    deployment = await models.deployments.read_deployment(
        session=session, deployment_id=deployment_id
    )
    assert deployment
    flow = await models.flows.read_flow(session=session, flow_id=deployment.flow_id)
    work_queue = (
        await models.workers.read_work_queue(
            session=session,
            work_queue_id=deployment.work_queue_id,
        )
        if deployment.work_queue_id
        else None
    )

    work_pool = (
        await models.workers.read_work_pool(
            session=session,
            work_pool_id=work_queue.work_pool_id,
        )
        if work_queue and work_queue.work_pool_id
        else None
    )

    related_work_queue_and_pool_info = []

    if flow is not None:
        related_work_queue_and_pool_info.append(
            {
                "prefect.resource.id": f"prefect.flow.{flow.id}",
                "prefect.resource.name": flow.name,
                "prefect.resource.role": "flow",
            }
        )

    if work_queue is not None:
        related_work_queue_and_pool_info.append(
            {
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
                "prefect.resource.role": "work-queue",
            }
        )

    if work_pool is not None:
        related_work_queue_and_pool_info.append(
            {
                "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                "prefect.resource.name": work_pool.name,
                "prefect.work-pool.type": work_pool.type,
                "prefect.resource.role": "work-pool",
            }
        )

    return Event(
        occurred=occurred,
        event=f"prefect.deployment.{status.in_kebab_case()}",
        resource={
            "prefect.resource.id": f"prefect.deployment.{deployment.id}",
            "prefect.resource.name": f"{deployment.name}",
        },
        related=related_work_queue_and_pool_info,
        id=uuid4(),
    )


async def work_queue_status_event(
    session: AsyncSession,
    work_queue: "ORMWorkQueue",
    occurred: DateTime,
) -> Event:
    related_work_pool_info: List[Dict[str, Any]] = []

    if work_queue.work_pool_id:
        work_pool = await models.workers.read_work_pool(
            session=session,
            work_pool_id=work_queue.work_pool_id,
        )

        if work_pool and work_pool.id and work_pool.name:
            related_work_pool_info.append(
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                    "prefect.resource.name": work_pool.name,
                    "prefect.work-pool.type": work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            )

    return Event(
        occurred=occurred,
        event=f"prefect.work-queue.{work_queue.status.in_kebab_case()}",
        resource={
            "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
            "prefect.resource.name": work_queue.name,
            "prefect.resource.role": "work-queue",
        },
        related=related_work_pool_info,
        id=uuid4(),
    )


async def work_pool_status_event(
    event_id: UUID,
    occurred: DateTime,
    pre_update_work_pool: Optional["ORMWorkPool"],
    work_pool: "ORMWorkPool",
) -> Event:
    assert work_pool.status

    return Event(
        id=event_id,
        occurred=occurred,
        event=f"prefect.work-pool.{work_pool.status.in_kebab_case()}",
        resource={
            "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
            "prefect.resource.name": work_pool.name,
            "prefect.work-pool.type": work_pool.type,
        },
        follows=_get_recent_preceding_work_pool_event_id(pre_update_work_pool),
    )


def _get_recent_preceding_work_pool_event_id(
    work_pool: Optional["ORMWorkPool"],
) -> Optional[UUID]:
    """
    Returns the preceding event ID if the work pool transitioned status
    recently to help ensure correct event ordering.
    """
    if not work_pool:
        return None

    time_since_last_event = timedelta(hours=24)
    if work_pool.last_transitioned_status_at:
        time_since_last_event = now("UTC") - work_pool.last_transitioned_status_at

    return (
        work_pool.last_status_event_id
        if time_since_last_event < timedelta(minutes=10)
        else None
    )
