from typing import Literal, Optional, Union
from uuid import UUID

from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.events import Event, RelatedResource, emit_event


def emit_concurrency_event(
    phase: Union[Literal["acquired"], Literal["released"]],
    primary_limit: MinimalConcurrencyLimitResponse,
    related_limits: list[MinimalConcurrencyLimitResponse],
    task_run_id: UUID,
    follows: Union[Event, None] = None,
) -> Union[Event, None]:
    resource: dict[str, str] = {
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


def emit_concurrency_acquisition_events(
    limits: list[MinimalConcurrencyLimitResponse],
    task_run_id: UUID,
) -> dict[UUID, Optional[Event]]:
    events: dict[UUID, Optional[Event]] = {}
    for limit in limits:
        event = emit_concurrency_event("acquired", limit, limits, task_run_id)
        events[limit.id] = event

    return events


def emit_concurrency_release_events(
    limits: list[MinimalConcurrencyLimitResponse],
    events: dict[UUID, Optional[Event]],
    task_run_id: UUID,
) -> None:
    for limit in limits:
        emit_concurrency_event("released", limit, limits, task_run_id, events[limit.id])
