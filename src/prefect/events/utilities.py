from __future__ import annotations

import datetime
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

import prefect.types._datetime
from prefect.logging.loggers import get_logger

from .clients import (
    AssertingEventsClient,
    AssertingPassthroughEventsClient,
    PrefectCloudEventsClient,
    PrefectEventsClient,
)
from .schemas.events import Event, RelatedResource
from .worker import EventsWorker, should_emit_events

if TYPE_CHECKING:
    import logging

TIGHT_TIMING = timedelta(minutes=5)

logger: "logging.Logger" = get_logger(__name__)


def emit_event(
    event: str,
    resource: dict[str, str],
    occurred: datetime.datetime | None = None,
    related: list[dict[str, str]] | list[RelatedResource] | None = None,
    payload: dict[str, Any] | None = None,
    id: UUID | None = None,
    follows: Event | None = None,
    **kwargs: dict[str, Any] | None,
) -> Event | None:
    """
    Send an event to Prefect.

    Args:
        event: The name of the event that happened.
        resource: The primary Resource this event concerns.
        occurred: When the event happened from the sender's perspective.
                  Defaults to the current datetime.
        related: A list of additional Resources involved in this event.
        payload: An open-ended set of data describing what happened.
        id: The sender-provided identifier for this event. Defaults to a random
            UUID.
        follows: The event that preceded this one. If the preceding event
            happened more than 5 minutes prior to this event the follows
            relationship will not be set.

    Returns:
        The event that was emitted if worker is using a client that emit
        events, otherwise None
    """
    if not should_emit_events():
        return None

    try:
        operational_clients = [
            AssertingPassthroughEventsClient,
            AssertingEventsClient,
            PrefectCloudEventsClient,
            PrefectEventsClient,
        ]
        worker_instance = EventsWorker.instance()

        if worker_instance.client_type not in operational_clients:
            return None

        event_kwargs: dict[str, Any] = {
            "event": event,
            "resource": resource,
            **kwargs,
        }

        if occurred is None:
            occurred = prefect.types._datetime.now("UTC")
        event_kwargs["occurred"] = occurred

        if related is not None:
            event_kwargs["related"] = related

        if payload is not None:
            event_kwargs["payload"] = payload

        if id is not None:
            event_kwargs["id"] = id

        if follows is not None:
            if -TIGHT_TIMING < (occurred - follows.occurred) < TIGHT_TIMING:
                event_kwargs["follows"] = follows.id

        event_obj = Event(**event_kwargs)
        worker_instance.send(event_obj)

        return event_obj
    except Exception:
        logger.exception(f"Error emitting event: {event}")
        return None
