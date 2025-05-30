import base64
from typing import TYPE_CHECKING, List, Optional

from fastapi import Response, WebSocket, status
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends, Path
from fastapi.params import Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.status import WS_1002_PROTOCOL_ERROR

from prefect.logging import get_logger
from prefect.server.api.dependencies import is_ephemeral_request
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.events import messaging, stream
from prefect.server.events.counting import (
    Countable,
    InvalidEventCountParameters,
    TimeUnit,
)
from prefect.server.events.filters import EventFilter, EventOrder
from prefect.server.events.models.automations import automations_session
from prefect.server.events.pipeline import EventsPipeline
from prefect.server.events.schemas.events import Event, EventCount, EventPage
from prefect.server.events.storage import (
    INTERACTIVE_PAGE_SIZE,
    InvalidTokenError,
    database,
)
from prefect.server.utilities import subscriptions
from prefect.server.utilities.server import PrefectRouter
from prefect.settings import (
    PREFECT_EVENTS_MAXIMUM_WEBSOCKET_BACKFILL,
    PREFECT_EVENTS_WEBSOCKET_BACKFILL_PAGE_SIZE,
)

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


router: PrefectRouter = PrefectRouter(prefix="/events", tags=["Events"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def create_events(
    events: List[Event],
    ephemeral_request: bool = Depends(is_ephemeral_request),
) -> None:
    """
    Record a batch of Events.

    For more information, see https://docs.prefect.io/v3/concepts/events.
    """
    if ephemeral_request:
        await EventsPipeline().process_events(events)
    else:
        received_events = [event.receive() for event in events]
        await messaging.publish(received_events)


@router.websocket("/in")
async def stream_events_in(websocket: WebSocket) -> None:
    """Open a WebSocket to stream incoming Events"""

    await websocket.accept()

    try:
        async with messaging.create_event_publisher() as publisher:
            async for event_json in websocket.iter_text():
                event = Event.model_validate_json(event_json)
                await publisher.publish_event(event.receive())
    except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:  # pragma: no cover
        pass  # it's fine if a client disconnects either normally or abnormally

    return None


@router.websocket("/out")
async def stream_workspace_events_out(
    websocket: WebSocket,
) -> None:
    """Open a WebSocket to stream Events"""
    websocket = await subscriptions.accept_prefect_socket(
        websocket,
    )
    if not websocket:
        return

    try:
        # After authentication, the next message is expected to be a filter message, any
        # other type of message will close the connection.
        message = await websocket.receive_json()

        if message["type"] != "filter":
            return await websocket.close(
                WS_1002_PROTOCOL_ERROR, reason="Expected 'filter' message"
            )

        wants_backfill = message.get("backfill", True)

        try:
            filter = EventFilter.model_validate(message["filter"])
        except Exception as e:
            return await websocket.close(
                WS_1002_PROTOCOL_ERROR, reason=f"Invalid filter: {e}"
            )

        filter.occurred.clamp(PREFECT_EVENTS_MAXIMUM_WEBSOCKET_BACKFILL.value())
        filter.order = EventOrder.ASC

        # subscribe to the ongoing event stream first so we don't miss events...
        async with stream.events(filter) as event_stream:
            # ...then if the user wants, backfill up to the last 1k events...
            if wants_backfill:
                backfilled_ids = set()

                async with automations_session() as session:
                    backfill, _, next_page = await database.query_events(
                        session=session,
                        filter=filter,
                        page_size=PREFECT_EVENTS_WEBSOCKET_BACKFILL_PAGE_SIZE.value(),
                    )

                    while backfill:
                        for event in backfill:
                            backfilled_ids.add(event.id)
                            await websocket.send_json(
                                {
                                    "type": "event",
                                    "event": event.model_dump(mode="json"),
                                }
                            )

                        if not next_page:
                            break

                        backfill, _, next_page = await database.query_next_page(
                            session=session,
                            page_token=next_page,
                        )

            # ...before resuming the ongoing stream of events
            async for event in event_stream:
                if not event:
                    if await subscriptions.still_connected(websocket):
                        continue
                    break

                if wants_backfill and event.id in backfilled_ids:
                    backfilled_ids.remove(event.id)
                    continue

                await websocket.send_json(
                    {"type": "event", "event": event.model_dump(mode="json")}
                )

    except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:  # pragma: no cover
        pass  # it's fine if a client disconnects either normally or abnormally

    return None


def verified_page_token(
    page_token: str = Query(..., alias="page-token"),
) -> str:
    try:
        page_token = base64.b64decode(page_token.encode()).decode()
    except Exception:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if not page_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return page_token


@router.post(
    "/filter",
)
async def read_events(
    request: Request,
    filter: Optional[EventFilter] = Body(
        None,
        description=(
            "Additional optional filter criteria to narrow down the set of Events"
        ),
    ),
    limit: int = Body(
        INTERACTIVE_PAGE_SIZE,
        ge=0,
        le=INTERACTIVE_PAGE_SIZE,
        embed=True,
        description="The number of events to return with each page",
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> EventPage:
    """
    Queries for Events matching the given filter criteria in the given Account.  Returns
    the first page of results, and the URL to request the next page (if there are more
    results).
    """
    filter = filter or EventFilter()
    async with db.session_context() as session:
        events, total, next_token = await database.query_events(
            session=session,
            filter=filter,
            page_size=limit,
        )

        return EventPage(
            events=events,
            total=total,
            next_page=generate_next_page_link(request, next_token),
        )


@router.get(
    "/filter/next",
)
async def read_account_events_page(
    request: Request,
    page_token: str = Depends(verified_page_token),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> EventPage:
    """
    Returns the next page of Events for a previous query against the given Account, and
    the URL to request the next page (if there are more results).
    """
    async with db.session_context() as session:
        try:
            events, total, next_token = await database.query_next_page(
                session=session, page_token=page_token
            )
        except InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        return EventPage(
            events=events,
            total=total,
            next_page=generate_next_page_link(request, next_token),
        )


def generate_next_page_link(
    request: Request,
    page_token: Optional[str],
) -> Optional[str]:
    if not page_token:
        return None

    next_page = (
        f"{request.base_url}api/events/filter/next"
        f"?page-token={base64.b64encode(page_token.encode()).decode()}"
    )
    return next_page


@router.post(
    "/count-by/{countable}",
)
async def count_account_events(
    filter: EventFilter,
    countable: Countable = Path(...),
    time_unit: TimeUnit = Body(default=TimeUnit.day),
    time_interval: float = Body(default=1.0, ge=0.01),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[EventCount]:
    """
    Returns distinct objects and the count of events associated with them.  Objects
    that can be counted include the day the event occurred, the type of event, or
    the IDs of the resources associated with the event.
    """
    async with db.session_context() as session:
        return await handle_event_count_request(
            session=session,
            filter=filter,
            countable=countable,
            time_unit=time_unit,
            time_interval=time_interval,
        )


async def handle_event_count_request(
    session: AsyncSession,
    filter: EventFilter,
    countable: Countable,
    time_unit: TimeUnit,
    time_interval: float,
) -> List[EventCount]:
    try:
        return await database.count_events(
            session=session,
            filter=filter,
            countable=countable,
            time_unit=time_unit,
            time_interval=time_interval,
        )
    except InvalidEventCountParameters as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )
