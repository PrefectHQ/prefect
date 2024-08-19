from datetime import timedelta
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import pendulum
from pydantic_extra_types.pendulum_dt import DateTime

from .clients import (
    AssertingEventsClient,
    AssertingPassthroughEventsClient,
    PrefectCloudEventsClient,
    PrefectEventsClient,
)
from .schemas.events import Event, RelatedResource
from .worker import EventsWorker, should_emit_events

TIGHT_TIMING = timedelta(minutes=5)


def emit_event(
    event: str,
    resource: Dict[str, str],
    occurred: Optional[DateTime] = None,
    related: Optional[Union[List[Dict[str, str]], List[RelatedResource]]] = None,
    payload: Optional[Dict[str, Any]] = None,
    id: Optional[UUID] = None,
    follows: Optional[Event] = None,
) -> Optional[Event]:
    """
    Send an event to Prefect Cloud.

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

    operational_clients = [
        AssertingPassthroughEventsClient,
        AssertingEventsClient,
        PrefectCloudEventsClient,
        PrefectEventsClient,
    ]
    worker_instance = EventsWorker.instance()

    if worker_instance.client_type not in operational_clients:
        return None

    event_kwargs: Dict[str, Any] = {
        "event": event,
        "resource": resource,
    }

    if occurred is None:
        occurred = pendulum.now("UTC")
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
