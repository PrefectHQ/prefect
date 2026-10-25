"""Publishing server-side events as background work."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from docket import Logged, Retry
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.logging import get_logger
from prefect.server.events.clients import PrefectServerEventsClient
from prefect.server.events.schemas.events import Event
from prefect.server.utilities._docket import get_docket
from prefect.server.utilities._post_commit import call_after_commit

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


async def publish_event(
    event: Event,
    event_id: Annotated[UUID, Logged],
    *,
    retry: Retry = Retry(attempts=5, delay=timedelta(seconds=0.5)),
) -> None:
    """Publish an event to the server's event stream (docket task).

    Args:
        event: the event to publish
        event_id: the event's id, logged by docket to identify the task
    """
    async with PrefectServerEventsClient() as events:
        await events.emit(event)


def publish_after_commit(session: AsyncSession, event: Event) -> None:
    """Publish `event` after the session's transaction commits.

    The event is handed to docket as the commit unwinds, so publishing it gets a task's
    retries and observability, and subscribers only ever see events for states they can
    read. Transitions that are rolled back publish nothing.

    Without a docket - when the orchestration engine is driven directly against a
    session rather than by a running server - the event is published in-line instead,
    still after the commit.
    """

    async def publish() -> None:
        docket = get_docket()
        if docket is None:
            await publish_event(event, event.id)
            return

        await docket.add(publish_event, key=f"publish-event:{event.id}")(
            event, event.id
        )

    call_after_commit(session, publish)
