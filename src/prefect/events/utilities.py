from typing import Any, Dict, List, Optional
from uuid import UUID

from prefect.server.utilities.schemas import DateTimeTZ

from .schemas import Event
from .worker import EventsWorker


def emit_event(
    event: str,
    resource: Dict[str, str],
    occurred: Optional[DateTimeTZ] = None,
    related: Optional[List[Dict[str, str]]] = None,
    payload: Optional[Dict[str, Any]] = None,
    id: Optional[UUID] = None,
) -> None:
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
    """
    event_kwargs = {
        "event": event,
        "resource": resource,
    }

    if occurred is not None:
        event_kwargs["occurred"] = occurred

    if related is not None:
        event_kwargs["related"] = related

    if payload is not None:
        event_kwargs["payload"] = payload

    if id is not None:
        event_kwargs["id"] = id

    event_obj = Event(**event_kwargs)
    EventsWorker.instance().send(event_obj)
