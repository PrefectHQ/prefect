"""
Manages the partial causal ordering of events for a particular consumer.  This module
maintains a buffer of events to be processed, aiming to process them in the order they
occurred causally.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Union
from uuid import UUID, uuid4

import anyio

from prefect.logging import get_logger
from prefect.server.events.ordering import (
    MAX_DEPTH_OF_PRECEDING_EVENT,
    PRECEDING_EVENT_LOOKBACK,
    SEEN_EXPIRATION,
    EventArrivedEarly,
    MaxDepthExceeded,
    event_handler,
)
from prefect.server.events.ordering import (
    CausalOrdering as _CausalOrdering,
)
from prefect.server.events.ordering.memory import EventBeingProcessed
from prefect.server.events.schemas.events import Event, ReceivedEvent
from prefect_redis.client import get_async_redis_client

logger = get_logger(__name__)


class EventProcessingCompletion:
    """Holds the result of completing event processing, including any followers."""

    def __init__(self):
        self.followers: list[ReceivedEvent] = []


# How long we'll wait for an in-flight event to be processed for follower handling,
# which crucially needs to be lower than the stream ack deadline
IN_FLIGHT_EVENT_TIMEOUT = timedelta(seconds=8)

# Lua script to atomically complete event processing and get followers.
# This prevents a race condition where a follower parks itself between
# DEL processing and SMEMBERS followers.
#
# The race without this script:
# 1. Leader: SET seen
# 2. Leader: DEL processing
# 3. Follower: CHECK seen (might miss due to timing/replica lag)
# 4. Follower: CHECK processing (nil - already deleted)
# 5. Follower: SADD followers (parks itself)
# 6. Leader: SMEMBERS followers (empty - already executed before step 5)
#
# With this script, steps 1, 2, and 6 happen atomically, so there's no window
# for the follower to slip in between.
COMPLETE_PROCESSING_SCRIPT = """
local seen_key = KEYS[1]
local followers_key = KEYS[2]
local processing_key = KEYS[3]
local seen_ttl = tonumber(ARGV[1])

-- 1. SET seen with TTL
redis.call('SET', seen_key, '1', 'EX', seen_ttl)

-- 2. SMEMBERS followers and DEL to "claim" them atomically.
-- This prevents a race where a follower could unpark after seeing seen=true
-- but before the leader finishes iterating followers. By deleting the
-- followers set, any follower doing a double-check will see it's been
-- claimed and should NOT self-process.
local followers = redis.call('SMEMBERS', followers_key)
redis.call('DEL', followers_key)

-- 3. DEL processing
redis.call('DEL', processing_key)

return followers
"""


class CausalOrdering(_CausalOrdering):
    def __init__(self, scope: str):
        self.redis = get_async_redis_client()
        super().__init__(scope=scope)

    def _key(self, key: str) -> str:
        if not self.scope:
            return key
        return f"{self.scope}:{key}"

    async def record_event_as_processing(self, event: ReceivedEvent) -> bool:
        """
        Record that an event is being processed, returning False if the event is already
        being processed.
        """
        success = await self.redis.set(
            self._key(f"processing:{event.id}"),
            1,
            ex=IN_FLIGHT_EVENT_TIMEOUT * 2,
            nx=True,
        )
        return bool(success)

    async def event_has_started_processing(self, event: Union[UUID, Event]) -> bool:
        id = event.id if isinstance(event, Event) else event
        return await self.redis.exists(self._key(f"processing:{id}")) == 1

    async def forget_event_is_processing(self, event: ReceivedEvent) -> None:
        await self.redis.delete(self._key(f"processing:{event.id}"))

    async def event_has_been_seen(self, event: Union[UUID, Event]) -> bool:
        id = event.id if isinstance(event, Event) else event
        return await self.redis.exists(self._key(f"seen:{id}")) == 1

    async def record_event_as_seen(self, event: ReceivedEvent) -> None:
        await self.redis.set(self._key(f"seen:{event.id}"), 1, ex=SEEN_EXPIRATION)

    async def record_follower(self, event: ReceivedEvent):
        """Remember that this event is waiting on another event to arrive"""
        assert event.follows

        async with self.redis.pipeline() as p:
            await p.set(self._key(f"event:{event.id}"), event.model_dump_json())
            await p.sadd(self._key(f"followers:{event.follows}"), str(event.id))
            await p.zadd(
                self._key("waitlist"), {str(event.id): event.received.timestamp()}
            )
            await p.execute()

    async def forget_follower(self, follower: ReceivedEvent):
        """Forget that this event is waiting on another event to arrive"""
        assert follower.follows

        async with self.redis.pipeline() as p:
            await p.zrem(self._key("waitlist"), str(follower.id))
            await p.srem(self._key(f"followers:{follower.follows}"), str(follower.id))
            await p.delete(self._key(f"event:{follower.id}"))
            await p.execute()

    async def get_lost_followers(self) -> list[ReceivedEvent]:
        """Returns events that were waiting on a leader event that never arrived"""
        async with self.redis.pipeline() as p:
            temporary_set = str(uuid4())
            earlier = (
                datetime.now(timezone.utc) - PRECEDING_EVENT_LOOKBACK
            ).timestamp()

            # Move all of the events that are older than the lookback period into a
            # temporary set...
            await p.zrangestore(
                temporary_set, self._key("waitlist"), 0, earlier, byscore=True
            )
            # Then remove them from the waitlist set...
            await p.zremrangebyscore(self._key("waitlist"), 0, earlier)
            # Then return them...
            await p.zrange(temporary_set, 0, -1)
            # And finally, remove the temporary set
            await p.delete(temporary_set)

            _, _, follower_ids, _ = await p.execute()

        follower_ids = [UUID(i) for i in follower_ids]

        return await self.followers_by_id(follower_ids)

    async def followers_by_id(self, follower_ids: list[UUID]) -> list[ReceivedEvent]:
        """Returns the events with the given IDs, in the order they occurred"""
        async with self.redis.pipeline() as p:
            for follower_id in follower_ids:
                await p.get(self._key(f"event:{follower_id}"))
            follower_jsons: list[str] = await p.execute()

        return sorted(
            [ReceivedEvent.model_validate_json(f) for f in follower_jsons if f],
            key=lambda f: f.occurred,
        )

    async def get_followers(self, leader: ReceivedEvent) -> list[ReceivedEvent]:
        """Returns events that were waiting on this leader event to arrive"""
        follower_ids = [
            i for i in await self.redis.smembers(self._key(f"followers:{leader.id}"))
        ]
        follower_ids = [UUID(i) for i in follower_ids]
        return await self.followers_by_id(follower_ids)

    async def complete_event_and_get_followers(
        self, event: ReceivedEvent
    ) -> list[ReceivedEvent]:
        """
        Atomically marks the event as seen, retrieves any waiting followers,
        and releases the processing lock.

        This operation is atomic to prevent a race condition where a follower
        could park itself between the lock release and the followers check.
        """
        follower_ids = await self.redis.eval(
            COMPLETE_PROCESSING_SCRIPT,
            3,  # number of keys
            self._key(f"seen:{event.id}"),
            self._key(f"followers:{event.id}"),
            self._key(f"processing:{event.id}"),
            int(SEEN_EXPIRATION.total_seconds()),  # seen TTL
        )
        follower_ids = [UUID(i) for i in follower_ids]
        return await self.followers_by_id(follower_ids)

    @asynccontextmanager
    async def event_is_processing(
        self, event: ReceivedEvent
    ) -> AsyncGenerator[EventProcessingCompletion, None]:
        """Mark an event as being processed for the duration of its lifespan through
        the ordering system.

        Yields an EventProcessingCompletion object that will be populated with
        any followers after successful processing.
        """
        if not await self.record_event_as_processing(event):
            self._log(event, "is already being processed")
            raise EventBeingProcessed(event)

        completion = EventProcessingCompletion()
        success = False
        try:
            yield completion
            # On success, atomically: SET seen, SMEMBERS followers, DEL processing
            # This prevents a race condition where followers could be orphaned
            completion.followers = await self.complete_event_and_get_followers(event)
            success = True
        finally:
            if not success:
                # On failure, just release the processing lock
                await self.forget_event_is_processing(event)

    async def wait_for_leader(self, event: ReceivedEvent):
        """Given an event, wait for its leader to be processed before proceeding, or
        raise EventArrivedEarly if we would wait too long in this attempt."""
        # If this event doesn't follow anything (meaningfully), it's ready to go now
        if not event.follows or event.follows == event.id:
            return

        # If this is an old event, we won't have accurate bookkeeping for its leader
        # so we're just going to send it
        age = datetime.now(timezone.utc) - event.received
        if age >= PRECEDING_EVENT_LOOKBACK:
            return

        # If the leader has already been seen, keep on trucking
        if await self.event_has_been_seen(event.follows):
            return

        # check if the leader is currently being processed, and if so, poll until it's
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

        # Double-check: the leader may have completed between our checks and parking.
        # This prevents a race where:
        # 1. Follower checks seen -> False
        # 2. Leader completes (SET seen, SMEMBERS+DEL followers, DEL processing)
        # 3. Follower checks processing -> False
        # 4. Follower parks itself
        # 5. Orphan! (leader already checked followers before we parked)
        #
        # By checking seen again after parking, we detect this race.
        # However, if the leader claimed us (deleted from followers set), we should
        # NOT self-process - the leader will process us. Only unpark if we're still
        # in the followers set (meaning leader hasn't claimed us).
        if await self.event_has_been_seen(event.follows):
            # Check if leader claimed us by checking if we're still in followers set
            still_in_followers = await self.redis.sismember(
                self._key(f"followers:{event.follows}"), str(event.id)
            )
            if still_in_followers:
                # Leader didn't claim us (or hasn't run yet), safe to unpark
                await self.forget_follower(event)
                return
            # Leader claimed us - don't self-process or clean up anything.
            # Leader will call forget_follower() after successful processing.
            # If we deleted event:{id} here, followers_by_id() would miss us.

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
        successfully processed going back to the PRECEDING_EVENT_LOOKBACK period.  If an
        event arrives that must follow another one, confirm that we have recently seen
        and processed that event before proceeding.

        Args: handler (event_handler): The function to call when an out-of-order event
        is
            ready to be processed
        event (ReceivedEvent): The event to be processed. This object should include
            metadata indicating if and what event it follows.
        depth (int, optional): The current recursion depth, used to prevent infinite
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

        async with self.event_is_processing(event) as completion:
            await self.wait_for_leader(event)
            yield

        # we have just processed an event that other events may have been waiting
        # on, so let's react to them now in the order they occurred.
        # The followers were retrieved atomically during completion to prevent
        # a race condition where followers could be orphaned.
        #
        # Note: We call handler(waiter) directly without wrapping in preceding_event_confirmed.
        # If the handler wants recursive chain resolution (e.g., A→B→C), it should call
        # preceding_event_confirmed itself. This matches the original design where handlers
        # like the test's "evaluate" function handle their own causal ordering.
        #
        # IMPORTANT: forget_follower is called AFTER handler succeeds. If handler fails,
        # the follower remains in waitlist and can be recovered by get_lost_followers().
        try:
            for waiter in completion.followers:
                await handler(waiter, depth=depth + 1)
                await self.forget_follower(waiter)
        except MaxDepthExceeded:
            # We'll only process followers up to the MAX_DEPTH_OF_PRECEDING_EVENT.
            # If we hit this limit, we'll just log and move on.
            self._log(
                event,
                "reached its max depth of %s followers processed.",
                MAX_DEPTH_OF_PRECEDING_EVENT,
            )

        # if this event was itself waiting on a leader, let's consider it as
        # resolved now that it has been processed
        if event.follows and event.follows != event.id:
            await self.forget_follower(event)

    def _log(self, event: ReceivedEvent, message: str, *args: Any):
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
