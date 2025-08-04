from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator
from uuid import UUID

import anyio

import prefect.types._datetime
from prefect.logging import get_logger
from prefect.server.events.ordering import (
    MAX_DEPTH_OF_PRECEDING_EVENT,
    PRECEDING_EVENT_LOOKBACK,
    SEEN_EXPIRATION,
    EventArrivedEarly,
    MaxDepthExceeded,
    event_handler,
)
from prefect.server.events.ordering import CausalOrdering as _CausalOrdering
from prefect.server.events.schemas.events import Event, ReceivedEvent

logger: logging.Logger = get_logger(__name__)

# How long we'll wait for an in-flight event to be processed for follower handling
IN_FLIGHT_EVENT_TIMEOUT = timedelta(seconds=8)


class EventBeingProcessed(Exception):
    """Indicates that an event is currently being processed and should not be processed
    until it is finished. This may happen due to concurrent processing."""

    def __init__(self, event: ReceivedEvent):
        self.event = event


class CausalOrdering(_CausalOrdering):
    # Class-level storage for different scopes
    _instances: dict[str, "CausalOrdering"] = {}
    _locks: dict[str, asyncio.Lock] = {}

    def __new__(cls, scope: str) -> "CausalOrdering":
        if scope not in cls._instances:
            cls._instances[scope] = super().__new__(cls)
        return cls._instances[scope]

    def __init__(self, scope: str):
        # Only initialize once per scope
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.scope: str = scope
        self._processing_events: set[UUID] = set()
        self._seen_events: dict[UUID, datetime] = {}
        self._followers: dict[UUID, set[UUID]] = {}  # leader_id -> set of follower_ids
        self._events: dict[UUID, ReceivedEvent] = {}  # event_id -> event
        self._waitlist: dict[UUID, datetime] = {}  # event_id -> received_time

        # Each scope gets its own lock
        if scope not in self.__class__._locks:
            self.__class__._locks[scope] = asyncio.Lock()
        self._lock = self.__class__._locks[scope]

        self._initialized = True

    def clear(self) -> None:
        """Clear all data for this scope."""
        self._processing_events.clear()
        self._seen_events.clear()
        self._followers.clear()
        self._events.clear()
        self._waitlist.clear()

    @classmethod
    def clear_all_scopes(cls) -> None:
        """Clear all data for all scopes - useful for testing."""
        for instance in cls._instances.values():
            instance.clear()
        cls._instances.clear()
        cls._locks.clear()

    async def record_event_as_processing(self, event: ReceivedEvent) -> bool:
        """Record that an event is being processed, returning False if already processing."""
        async with self._lock:
            if event.id in self._processing_events:
                return False
            self._processing_events.add(event.id)
            return True

    async def event_has_started_processing(self, event: UUID | Event) -> bool:
        event_id = event.id if isinstance(event, Event) else event
        async with self._lock:
            return event_id in self._processing_events

    async def forget_event_is_processing(self, event: ReceivedEvent) -> None:
        async with self._lock:
            self._processing_events.discard(event.id)

    async def event_has_been_seen(self, event: UUID | Event) -> bool:
        event_id = event.id if isinstance(event, Event) else event
        async with self._lock:
            if event_id not in self._seen_events:
                return False
            # Clean up expired entries
            now = prefect.types._datetime.now("UTC")
            return now - self._seen_events[event_id] < SEEN_EXPIRATION

    async def record_event_as_seen(self, event: ReceivedEvent) -> None:
        async with self._lock:
            self._seen_events[event.id] = datetime.now(timezone.utc)
            # Cleanup old seen events periodically
            await self._cleanup_seen_events()

    async def _cleanup_seen_events(self) -> None:
        """Remove expired seen events to prevent memory leaks."""
        now = datetime.now(timezone.utc)
        expired_ids = [
            event_id
            for event_id, seen_time in self._seen_events.items()
            if now - seen_time >= SEEN_EXPIRATION
        ]
        for event_id in expired_ids:
            del self._seen_events[event_id]

    async def record_follower(self, event: ReceivedEvent) -> None:
        """Remember that this event is waiting on another event to arrive."""
        assert event.follows

        async with self._lock:
            self._events[event.id] = event
            if event.follows not in self._followers:
                self._followers[event.follows] = set()
            self._followers[event.follows].add(event.id)
            self._waitlist[event.id] = event.received

    async def forget_follower(self, follower: ReceivedEvent) -> None:
        """Forget that this event is waiting on another event to arrive."""
        assert follower.follows

        async with self._lock:
            self._waitlist.pop(follower.id, None)
            if follower.follows in self._followers:
                self._followers[follower.follows].discard(follower.id)
                if not self._followers[follower.follows]:
                    del self._followers[follower.follows]
            self._events.pop(follower.id, None)

    async def get_followers(self, leader: ReceivedEvent) -> list[ReceivedEvent]:
        """Returns events that were waiting on this leader event to arrive."""
        async with self._lock:
            follower_ids = self._followers.get(leader.id, set()).copy()

        follower_events: list[ReceivedEvent] = []
        for follower_id in follower_ids:
            if follower_id in self._events:
                follower_events.append(self._events[follower_id])

        # Sort by occurred time to maintain causal order
        return sorted(follower_events, key=lambda f: f.occurred)

    async def followers_by_id(self, follower_ids: list[UUID]) -> list[ReceivedEvent]:
        """Returns the events with the given IDs, in the order they occurred."""
        async with self._lock:
            follower_events = [
                self._events[fid] for fid in follower_ids if fid in self._events
            ]

        return sorted(follower_events, key=lambda f: f.occurred)

    async def get_lost_followers(self) -> list[ReceivedEvent]:
        """Returns events that were waiting on a leader event that never arrived."""
        cutoff_time = prefect.types._datetime.now("UTC") - PRECEDING_EVENT_LOOKBACK

        async with self._lock:
            lost_ids = [
                event_id
                for event_id, received_time in self._waitlist.items()
                if received_time <= cutoff_time
            ]

            # Remove lost followers from our tracking
            lost_events: list[ReceivedEvent] = []
            for event_id in lost_ids:
                if event_id in self._events:
                    event = self._events[event_id]
                    lost_events.append(event)

                    # Clean up tracking for this lost event
                    if event.follows and event.follows in self._followers:
                        self._followers[event.follows].discard(event_id)
                        if not self._followers[event.follows]:
                            del self._followers[event.follows]

                    del self._events[event_id]
                    del self._waitlist[event_id]

        return sorted(lost_events, key=lambda f: f.occurred)

    @asynccontextmanager
    async def event_is_processing(
        self, event: ReceivedEvent
    ) -> AsyncGenerator[None, None]:
        """Mark an event as being processed for the duration of its lifespan through
        the ordering system."""
        if not await self.record_event_as_processing(event):
            self._log(event, "is already being processed")
            raise EventBeingProcessed(event)

        try:
            yield
            await self.record_event_as_seen(event)
        finally:
            await self.forget_event_is_processing(event)

    async def wait_for_leader(self, event: ReceivedEvent) -> None:
        """Given an event, wait for its leader to be processed before proceeding, or
        raise EventArrivedEarly if we would wait too long in this attempt."""
        # If this event doesn't follow anything (meaningfully), it's ready to go now
        if not event.follows or event.follows == event.id:
            return

        # If this is an old event, we won't have accurate bookkeeping for its leader
        # so we're just going to send it
        age = prefect.types._datetime.now("UTC") - event.received
        if age >= PRECEDING_EVENT_LOOKBACK:
            return

        # If the leader has already been seen, keep on trucking
        if await self.event_has_been_seen(event.follows):
            return

        # Check if the leader is currently being processed, and if so, poll until it's
        # done being processed as a quicker alternative to sitting on the waitlist
        if await self.event_has_started_processing(event.follows):
            try:
                with anyio.fail_after(IN_FLIGHT_EVENT_TIMEOUT.total_seconds()):
                    while not await self.event_has_been_seen(event.follows):
                        await asyncio.sleep(0.25)
                    return
            except asyncio.TimeoutError:
                self._log(
                    event,
                    "timed out waiting for its in-flight leader %s, will treat as lost",
                    event.follows,
                )

        # Otherwise, we'll stop processing now and sit on the waitlist until the leader
        # eventually comes through the system
        self._log(event, "arrived before the event it follows %s", event.follows)

        await self.record_follower(event)
        raise EventArrivedEarly(event)

    @asynccontextmanager
    async def preceding_event_confirmed(
        self,
        handler: event_handler,
        event: ReceivedEvent,
        depth: int = 0,
    ) -> AsyncGenerator[None, None]:
        """
        Events may optionally declare that they logically follow another event, so that
        we can preserve important event orderings in the face of unreliable delivery and
        ordering of messages from the queues.

        This function keeps track of the ID of each event that this shard has
        successfully processed going back to the PRECEDING_EVENT_LOOKBACK period. If an
        event arrives that must follow another one, confirm that we have recently seen
        and processed that event before proceeding.

        Args:
            handler: The function to call when an out-of-order event is
                ready to be processed
            event: The event to be processed. This object should include
                metadata indicating if and what event it follows.
            depth: The current recursion depth, used to prevent infinite
                recursion due to cyclic dependencies between events. Defaults to 0.

        Raises EventArrivedEarly if the current event shouldn't be processed yet.
        """
        if depth > MAX_DEPTH_OF_PRECEDING_EVENT:
            # There is either a cyclic set of events or a chain
            # of events that is too long
            self._log(
                event,
                "has exceeded the maximum recursion depth %s",
                MAX_DEPTH_OF_PRECEDING_EVENT,
            )
            raise MaxDepthExceeded(event)

        async with self.event_is_processing(event):
            await self.wait_for_leader(event)
            yield

        # We have just processed an event that other events may have been waiting
        # on, so let's react to them now in the order they occurred
        try:
            for waiter in await self.get_followers(event):
                await handler(waiter, depth=depth + 1)
        except MaxDepthExceeded:
            # We'll only process the first MAX_DEPTH_OF_PRECEDING_EVENT followers.
            # If we hit this limit, we'll just log and move on.
            self._log(
                event,
                "reached its max depth of %s followers processed.",
                MAX_DEPTH_OF_PRECEDING_EVENT,
            )

        # If this event was itself waiting on a leader, let's consider it as
        # resolved now that it has been processed
        if event.follows and event.follows != event.id:
            await self.forget_follower(event)

    def _log(self, event: ReceivedEvent, message: str, *args: Any) -> None:
        logger.info(
            "Event %r (%s) for %r " + message,
            event.event,
            event.id,
            event.resource.id,
            *args,
            extra={
                "event_id": event.id,
                "follows": event.follows,
                "resource_id": event.resource.id,
            },
        )
