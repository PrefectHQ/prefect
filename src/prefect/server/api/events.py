from typing import List

from prefect._vendor.fastapi import Response, WebSocket, status

from prefect.logging import get_logger
from prefect.server.events import messaging
from prefect.server.events.schemas.events import Event
from prefect.server.utilities import subscriptions
from prefect.server.utilities.server import PrefectRouter

logger = get_logger(__name__)


router = PrefectRouter(prefix="/events", tags=["Events"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def create_events(events: List[Event]):
    """Record a batch of Events"""
    await messaging.publish([event.receive() for event in events])


@router.websocket("/in")
async def stream_events_in(websocket: WebSocket) -> None:
    """Open a WebSocket to stream incoming Events"""

    await websocket.accept()

    try:
        async with messaging.create_event_publisher() as publisher:
            async for event_json in websocket.iter_text():
                event = Event.parse_raw(event_json)
                await publisher.publish_event(event.receive())
    except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:  # pragma: no cover
        pass  # it's fine if a client disconnects either normally or abnormally

    return None
