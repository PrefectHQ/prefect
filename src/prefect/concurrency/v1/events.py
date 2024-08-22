from typing import Dict, List, Literal, Optional, Union
from uuid import UUID

from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.events import Event, RelatedResource, emit_event


def _emit_concurrency_event(
    phase: Union[Literal["acquired"], Literal["released"]],
    primary_limit: MinimalConcurrencyLimitResponse,
    related_limits: List[MinimalConcurrencyLimitResponse],
    task_run_id: UUID,
    follows: Union[Event, None] = None,
) -> Union[Event, None]:
    resource: Dict[str, str] = {
        "prefect.resource.id": f"prefect.concurrency-limit.v1.{primary_limit.id}",
        "prefect.resource.name": primary_limit.name,
        "limit": str(primary_limit.limit),
        "task_run_id": str(task_run_id),
    }

    related = [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.concurrency-limit.v1.{limit.id}",
                "prefect.resource.role": "concurrency-limit",
            }
        )
        for limit in related_limits
        if limit.id != primary_limit.id
    ]

    return emit_event(
        f"prefect.concurrency-limit.v1.{phase}",
        resource=resource,
        related=related,
        follows=follows,
    )


def _emit_concurrency_acquisition_events(
    limits: List[MinimalConcurrencyLimitResponse],
    task_run_id: UUID,
) -> Dict[UUID, Optional[Event]]:
    events = {}
    for limit in limits:
        event = _emit_concurrency_event("acquired", limit, limits, task_run_id)
        events[limit.id] = event

    return events


def _emit_concurrency_release_events(
    limits: List[MinimalConcurrencyLimitResponse],
    events: Dict[UUID, Optional[Event]],
    task_run_id: UUID,
) -> None:
    for limit in limits:
        _emit_concurrency_event(
            "released", limit, limits, task_run_id, events[limit.id]
        )
