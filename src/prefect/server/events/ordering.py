"""
Manages the partial causal ordering of events for a particular consumer.  This module
maintains a buffer of events to be processed, aiming to process them in the order they
occurred causally.
"""

from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import (
    List,
    Mapping,
    MutableMapping,
    Protocol,
    Union,
)
from uuid import UUID

import pendulum
import sqlalchemy as sa
from cachetools import TTLCache
from typing_extensions import Self

from prefect.logging import get_logger
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.database.orm_models import AutomationEventFollower
from prefect.server.events.schemas.events import Event, ReceivedEvent

logger = get_logger(__name__)

# How long we'll retain preceding events (to aid with ordering)
PRECEDING_EVENT_LOOKBACK = timedelta(minutes=15)

# How long we'll retain events we've processed (to prevent re-processing an event)
PROCESSED_EVENT_LOOKBACK = timedelta(minutes=30)

# How long we'll remember that we've seen an event
SEEN_EXPIRATION = max(PRECEDING_EVENT_LOOKBACK, PROCESSED_EVENT_LOOKBACK)

# How deep we'll allow the recursion to go when processing events
MAX_DEPTH_OF_PRECEDING_EVENT = 20


class EventArrivedEarly(Exception):
    def __init__(self, event: ReceivedEvent):
        self.event = event


class MaxDepthExceeded(Exception):
    def __init__(self, event: ReceivedEvent):
        self.event = event


class event_handler(Protocol):
    async def __call__(self, event: ReceivedEvent, depth: int = 0):
        ...  # pragma: no cover


class CausalOrdering:
    _seen_events: Mapping[str, MutableMapping[UUID, bool]] = defaultdict(
        lambda: TTLCache(maxsize=10000, ttl=SEEN_EXPIRATION.total_seconds())
    )

    scope: str

    def __init__(self, scope: str):
        self.scope = scope

    async def event_has_been_seen(self, event: Union[UUID, Event]) -> bool:
        id = event.id if isinstance(event, Event) else event
        return self._seen_events[self.scope].get(id, False)

    async def record_event_as_seen(self, event: ReceivedEvent) -> None:
        self._seen_events[self.scope][event.id] = True

    @db_injector
    async def record_follower(db: PrefectDBInterface, self: Self, event: ReceivedEvent):
        """Remember that this event is waiting on another event to arrive"""
        assert event.follows

        async with db.session_context(begin_transaction=True) as session:
            await session.execute(
                sa.insert(AutomationEventFollower).values(
                    scope=self.scope,
                    leader_event_id=event.follows,
                    follower_event_id=event.id,
                    received=event.received,
                    follower=event,
                )
            )

    @db_injector
    async def forget_follower(
        db: PrefectDBInterface, self: Self, follower: ReceivedEvent
    ):
        """Forget that this event is waiting on another event to arrive"""
        assert follower.follows

        async with db.session_context(begin_transaction=True) as session:
            await session.execute(
                sa.delete(AutomationEventFollower).where(
                    AutomationEventFollower.scope == self.scope,
                    AutomationEventFollower.follower_event_id == follower.id,
                )
            )

    @db_injector
    async def get_followers(
        db: PrefectDBInterface, self: Self, leader: ReceivedEvent
    ) -> List[ReceivedEvent]:
        """Returns events that were waiting on this leader event to arrive"""
        async with db.session_context() as session:
            query = sa.select(AutomationEventFollower.follower).where(
                AutomationEventFollower.scope == self.scope,
                AutomationEventFollower.leader_event_id == leader.id,
            )
            result = await session.execute(query)
            followers = result.scalars().all()
            return sorted(followers, key=lambda e: e.occurred)

    @db_injector
    async def get_lost_followers(db: PrefectDBInterface, self) -> List[ReceivedEvent]:
        """Returns events that were waiting on a leader event that never arrived"""
        earlier = pendulum.now("UTC") - PRECEDING_EVENT_LOOKBACK

        async with db.session_context(begin_transaction=True) as session:
            query = sa.select(AutomationEventFollower.follower).where(
                AutomationEventFollower.scope == self.scope,
                AutomationEventFollower.received < earlier,
            )
            result = await session.execute(query)
            followers = result.scalars().all()

            # forget these followers, since they are never going to see their leader event

            await session.execute(
                sa.delete(AutomationEventFollower).where(
                    AutomationEventFollower.scope == self.scope,
                    AutomationEventFollower.received < earlier,
                )
            )

            return sorted(followers, key=lambda e: e.occurred)

    @asynccontextmanager
    async def preceding_event_confirmed(
        self, handler: event_handler, event: ReceivedEvent, depth: int = 0
    ):
        """Events may optionally declare that they logically follow another event, so that
        we can preserve important event orderings in the face of unreliable delivery and
        ordering of messages from the queues.

        This function keeps track of the ID of each event that this shard has successfully
        processed going back to the PRECEDING_EVENT_LOOKBACK period.  If an event arrives
        that must follow another one, confirm that we have recently seen and processed that
        event before proceeding.

        Args:
        event (ReceivedEvent): The event to be processed. This object should include metadata indicating
            if and what event it follows.
        depth (int, optional): The current recursion depth, used to prevent infinite recursion due to
            cyclic dependencies between events. Defaults to 0.


        Raises EventArrivedEarly if the current event shouldn't be processed yet."""

        if depth > MAX_DEPTH_OF_PRECEDING_EVENT:
            logger.exception(
                "Event %r (%s) for %r has exceeded the maximum recursion depth of %s",
                event.event,
                event.id,
                event.resource.id,
                MAX_DEPTH_OF_PRECEDING_EVENT,
            )
            raise MaxDepthExceeded(event)

        if event.follows:
            if not await self.event_has_been_seen(event.follows):
                age = pendulum.now("UTC") - event.received
                if age < PRECEDING_EVENT_LOOKBACK:
                    logger.debug(
                        "Event %r (%s) for %r arrived before the event it follows %s",
                        event.event,
                        event.id,
                        event.resource.id,
                        event.follows,
                    )

                    # record this follower for safe-keeping
                    await self.record_follower(event)
                    raise EventArrivedEarly(event)

        yield

        await self.record_event_as_seen(event)

        # we have just processed an event that other events were waiting on, so let's
        # react to them now in the order they occurred
        for waiter in await self.get_followers(event):
            await handler(waiter, depth + 1)

        # if this event was itself waiting on something, let's consider it as resolved now
        # that it has been processed
        if event.follows:
            await self.forget_follower(event)
