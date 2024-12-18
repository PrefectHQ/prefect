from typing import Literal, Optional, Union
from uuid import UUID

from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.events import Event, RelatedResource, emit_event


def _emit_concurrency_event(
    phase: Union[Literal["acquired"], Literal["released"]],
    primary_limit: MinimalConcurrencyLimitResponse,
    related_limits: list[MinimalConcurrencyLimitResponse],
    slots: int,
    follows: Union[Event, None] = None,
) -> Union[Event, None]:
    resource: dict[str, str] = {
        "prefect.resource.id": f"prefect.concurrency-limit.{primary_limit.id}",
        "prefect.resource.name": primary_limit.name,
        "slots-acquired": str(slots),
        "limit": str(primary_limit.limit),
    }

    related = [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.concurrency-limit.{limit.id}",
                "prefect.resource.role": "concurrency-limit",
            }
        )
        for limit in related_limits
        if limit.id != primary_limit.id
    ]

    return emit_event(
        f"prefect.concurrency-limit.{phase}",
        resource=resource,
        related=related,
        follows=follows,
    )


def emit_concurrency_acquisition_events(
    limits: list[MinimalConcurrencyLimitResponse],
    occupy: int,
) -> dict[UUID, Optional[Event]]:
    events: dict[UUID, Optional[Event]] = {}
    for limit in limits:
        event = _emit_concurrency_event("acquired", limit, limits, occupy)
        events[limit.id] = event

    return events


def emit_concurrency_release_events(
    limits: list[MinimalConcurrencyLimitResponse],
    occupy: int,
    events: dict[UUID, Optional[Event]],
) -> None:
    for limit in limits:
        _emit_concurrency_event("released", limit, limits, occupy, events[limit.id])
