"""
The triggers consumer watches events streaming in from the event bus and decides whether
to act on them based on the automations that users have set up.
"""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Collection,
    Dict,
    List,
    MutableMapping,
    Optional,
    Tuple,
)
from uuid import UUID

import pendulum
import sqlalchemy as sa
from cachetools import TTLCache
from pendulum.datetime import DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Literal, TypeAlias

from prefect.logging import get_logger
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events import messaging
from prefect.server.events.actions import ActionTypes
from prefect.server.events.models.automations import (
    automations_session,
    read_automation,
)
from prefect.server.events.models.composite_trigger_child_firing import (
    clear_child_firings,
    clear_old_child_firings,
    get_child_firings,
    upsert_child_firing,
)
from prefect.server.events.schemas.automations import (
    Automation,
    CompositeTrigger,
    EventTrigger,
    Firing,
    Posture,
    Trigger,
    TriggeredAction,
    TriggerState,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.messaging import Message, MessageHandler
from prefect.settings import PREFECT_EVENTS_EXPIRED_BUCKET_BUFFER

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMAutomationBucket


logger = get_logger(__name__)

AutomationID: TypeAlias = UUID
TriggerID: TypeAlias = UUID


AUTOMATION_BUCKET_BATCH_SIZE = 500

MAX_DEPTH_OF_PRECEDING_EVENT = 20


async def evaluate(
    session: AsyncSession,
    trigger: EventTrigger,
    bucket: "ORMAutomationBucket",
    now: DateTime,
    triggering_event: Optional[ReceivedEvent],
) -> Optional["ORMAutomationBucket"]:
    """Evaluates an Automation, either triggered by a specific event or proactively
    on a time interval.  Evaluating a Automation updates the associated counters for
    each automation, and will fire the associated action if it has met the threshold."""
    automation = trigger.automation

    # Implementation notes:
    #
    # This triggering algorithm maintains an invariant that there is exactly one
    # time-based "bucket" open and collecting events for each automation at a time. When
    # an event comes in that matches the automation, one of three things can happen:
    #
    # 1. The event would have matched an older bucket that has either expired or has
    #    already filled up, and thus is no longer relevant;
    # 2. The event matches the current bucket, but the bucket does not meet it's
    #    threshold yet;
    # 3. The event matches the current bucket, causes it to meet the the threshold, so
    #    we act immediately and advance the bucket to the next time period.
    #
    # Automations are also evaluated proactively without an event to see if they have
    # met their proactive threshold (where not enough events have happened in the time
    # period)

    # If there was a triggering event, then we need to "spend" this count somewhere,
    # either in the currently open bucket or in the next time period's bucket
    count = 1 if triggering_event else 0

    if now < bucket.start:
        # This is an older out-of-order message or a redundant event for a reactive
        # trigger that has has already fired, so it should not should not affect the
        # current bucket.  We can safely ignore this event/timestamp entirely.
        return bucket

    if count and (trigger.immediate or bucket.start <= now < bucket.end):
        # we are still within the automation time period, so spend the count in the
        # current bucket
        bucket = await increment_bucket(session, bucket, count, triggering_event)
        count = 0

    # Reactive automations will fire "eagerly", meaning they will fire as _soon_ as the
    # threshold is reached, then wait for the rest of their time period before
    # firing again.  This is done by creating a new bucket in the future after the
    # trigger has fired.

    # Proactive automations must wait until the whole bucket has expired before they can
    # fire, because we can't know if we'll get one late event just in time to cause the
    # automation _not_ to fire.

    ready_to_fire = trigger.posture == Posture.Reactive or bucket.end <= now

    if ready_to_fire and trigger.meets_threshold(bucket.count):
        logger.info(
            (
                "Automation %s (%r) trigger %s triggered for keys (%r) %s, "
                "having occurred %s times between %s and %s"
            ),
            automation.id,
            automation.name,
            trigger.id,
            bucket.bucketing_key,
            "reactively" if triggering_event else "proactively",
            bucket.count,
            bucket.start,
            bucket.end,
            extra={
                "automation": automation.id,
                "trigger": trigger.id,
                "bucketing_key": bucket.bucketing_key,
                "triggering_event": (
                    {
                        "id": triggering_event.id,
                        "event": triggering_event.event,
                    }
                    if triggering_event
                    else None
                ),
            },
        )

        firing = Firing(
            trigger=trigger,
            trigger_states={TriggerState.Triggered},
            triggered=pendulum.now("UTC"),
            triggering_labels={
                label: value
                for label, value in zip(sorted(trigger.for_each), bucket.bucketing_key)
            },
            triggering_event=triggering_event or bucket.last_event,
        )

        await fire(session, firing)

        # when acting, remove the current bucket from the database immediately to avoid
        # potentially double-acting in the case of a crash between now and the next
        # time we backup buckets to the database
        await remove_bucket(session, bucket)

    elif now < bucket.end:
        # We didn't fire this time, and also the bucket still has more time, so leave
        # before setting up a new future bucket
        return bucket

    # We are now outside of the automation's time period or we triggered this
    # time.  That means it's time to start a new bucket for the next possible time
    # window (if this automation does not require an event to start `after`):
    if trigger.after:
        # remove the bucket because it should only get re-created if we see another
        # appropriate starting event
        return await remove_bucket(session, bucket)
    else:
        if trigger.within == timedelta(seconds=0):
            return None

        start = pendulum.instance(max(bucket.end, now))
        return await start_new_bucket(
            session,
            trigger,
            bucketing_key=bucket.bucketing_key,
            start=start,
            end=start + trigger.within,
            count=count,
        )


async def fire(session: AsyncSession, firing: Firing):
    if isinstance(firing.trigger.parent, Automation):
        await act(firing)
    elif isinstance(firing.trigger.parent, CompositeTrigger):
        await evaluate_composite_trigger(session, firing)
    else:
        raise NotImplementedError(
            f"Cannot fire {firing} with parent trigger type {type(firing.trigger.parent)}"
        )


async def evaluate_composite_trigger(session: AsyncSession, firing: Firing):
    automation = firing.trigger.automation

    assert isinstance(firing.trigger.parent, CompositeTrigger)
    trigger: CompositeTrigger = firing.trigger.parent

    # If we only need to see 1 child firing,
    # then the parent trigger can fire immediately.
    if trigger.num_expected_firings == 1:
        logger.info(
            "Automation %s (%r) %s trigger %s fired (shortcut)",
            automation.id,
            automation.name,
            trigger.type,
            trigger.id,
            extra={
                "automation": automation.id,
                "trigger": trigger.id,
                "trigger_type": trigger.type,
                "firings": firing.id,
            },
        )
        await fire(
            session,
            Firing(
                trigger=trigger,
                trigger_states={TriggerState.Triggered},
                triggered=pendulum.now("UTC"),
                triggering_firings=[firing],
            ),
        )
        return

    # If we're only looking within a certain time horizon, remove any older firings that
    # should no longer be considered as satisfying this trigger
    if trigger.within is not None:
        await clear_old_child_firings(
            session, trigger, firing.triggered - trigger.within
        )

    # Otherwise we need N child firings. We'll upsert this firing and then check
    # what the current state of the world is. If we have enough firings, we'll
    # fire the parent trigger.
    await upsert_child_firing(session, firing)
    firings = [cf.child_firing for cf in await get_child_firings(session, trigger)]
    firing_ids = {f.id for f in firings}

    # If our current firing no longer exists when we read firings
    # another firing has superseded it, and we should defer to that one
    if firing.id not in firing_ids:
        return

    if trigger.ready_to_fire(firings):
        logger.info(
            "Automation %s (%r) %s trigger %s fired",
            automation.id,
            automation.name,
            trigger.type,
            trigger.id,
            extra={
                "automation": automation.id,
                "trigger": trigger.id,
                "trigger_type": trigger.type,
                "firings": ",".join(str(f.id) for f in firings),
            },
        )

        # clear by firing id
        await clear_child_firings(session, trigger, firing_ids=firing_ids)
        await fire(
            session,
            Firing(
                trigger=trigger,
                trigger_states={TriggerState.Triggered},
                triggered=pendulum.now("UTC"),
                triggering_firings=firings,
            ),
        )


async def act(firing: Firing):
    """Given a Automation that has been triggered, the triggering labels and event
    (if there was one), publish an action for the `actions` service to process."""
    automation = firing.trigger.automation

    state_change_events: Dict[TriggerState, ReceivedEvent] = {
        trigger_state: firing.trigger.create_automation_state_change_event(
            firing=firing,
            trigger_state=trigger_state,
        )
        for trigger_state in sorted(firing.trigger_states, key=list(TriggerState).index)
    }
    await messaging.publish(state_change_events.values())

    # By default, all `automation.actions` are fired
    source_actions: List[Tuple[Optional[ReceivedEvent], ActionTypes]] = [
        (firing.triggering_event, action) for action in automation.actions
    ]

    # Conditionally add in actions that fire on specific trigger states
    if TriggerState.Triggered in firing.trigger_states:
        source_actions += [
            (state_change_events[TriggerState.Triggered], action)
            for action in automation.actions_on_trigger
        ]

    if TriggerState.Resolved in firing.trigger_states:
        source_actions += [
            (state_change_events[TriggerState.Resolved], action)
            for action in automation.actions_on_resolve
        ]

    actions = [
        TriggeredAction(
            automation=automation,
            firing=firing,
            triggered=firing.triggered,
            triggering_labels=firing.triggering_labels,
            triggering_event=action_triggering_event,
            action=action,
            action_index=index,
        )
        for index, (action_triggering_event, action) in enumerate(source_actions)
    ]

    async with messaging.create_actions_publisher() as publisher:
        for action in actions:
            await publisher.publish_data(action.json().encode(), {})


_events_clock_lock = asyncio.Lock()
_events_clock: Optional[float] = None
_events_clock_updated: Optional[float] = None


async def update_events_clock(event: ReceivedEvent):
    global _events_clock, _events_clock_updated
    async with _events_clock_lock:
        # we want the offset to be negative to represent that we are always
        # processing events behind realtime...
        now = pendulum.now("UTC").float_timestamp
        event_timestamp = event.occurred.float_timestamp
        offset = event_timestamp - now

        # ...and we should clamp this value to zero so we don't inadvertently look like
        # we are processing the future
        if offset > 0.0:
            event_timestamp = now

        if not _events_clock or event_timestamp >= _events_clock:
            _events_clock = event_timestamp

        _events_clock_updated = now


async def get_events_clock() -> Optional[float]:
    global _events_clock
    return _events_clock


async def get_events_clock_offset() -> float:
    """Calculate the current clock offset.  This takes into account both the `occurred`
    of the last event, as well as the time we _saw_ the last event.  This helps to
    ensure that in low volume environments, we don't end up getting huge offsets."""
    global _events_clock, _events_clock_updated

    async with _events_clock_lock:
        if _events_clock is None or _events_clock_updated is None:
            return 0.0

        now: float = pendulum.now("UTC").float_timestamp
        offset = (_events_clock - now) + (now - _events_clock_updated)

    return offset


async def reset_events_clock():
    global _events_clock, _events_clock_updated
    async with _events_clock_lock:
        _events_clock = None
        _events_clock_updated = None


async def reactive_evaluation(event: ReceivedEvent, depth: int = 0):
    """
    Evaluate all automations that may apply to this event.

    Args:
    event (ReceivedEvent): The event to evaluate. This object contains all the necessary information
        about the event, including its type, associated resources, and metadata.
    depth (int, optional): The current recursion depth. This is used to prevent infinite recursion
        due to cyclic event dependencies. Defaults to 0 and is incremented with
        each recursive call.

    """
    async with AsyncExitStack() as stack:
        await update_events_clock(event)
        await stack.enter_async_context(with_preceding_event_confirmed(event, depth))

        interested_triggers = find_interested_triggers(event)
        if not interested_triggers:
            return

        for trigger in interested_triggers:
            logger.info(
                "Automation %s, trigger %s covers event %r (%s) for %r at %r",
                trigger.automation.id,
                trigger.id,
                event.event,
                event.id,
                event.resource.id,
                event.occurred.isoformat(),
            )

            bucketing_key = trigger.bucketing_key(event)

            async with automations_session() as session:
                try:
                    bucket: Optional["ORMAutomationBucket"] = None

                    if trigger.after and trigger.starts_after(event.event):
                        # When an event matches both the after and expect, each event
                        # can both start a new bucket and increment the bucket that was
                        # started by the previous event.  Here we offset the bucket to
                        # start at -1 so that the first event will leave the bucket at 0
                        # after evaluation.  See the tests:
                        #
                        #   test_same_event_in_expect_and_after_never_reacts_immediately
                        #   test_same_event_in_expect_and_after_reacts_after_threshold_is_met
                        #   test_same_event_in_expect_and_after_proactively_does_not_fire
                        #   test_same_event_in_expect_and_after_proactively_fires
                        #
                        # in test_triggers_regressions.py for examples of how we expect
                        # this to behave.
                        #
                        # https://github.com/PrefectHQ/nebula/issues/4201
                        initial_count = -1 if trigger.expects(event.event) else 0
                        bucket = await ensure_bucket(
                            session,
                            trigger,
                            bucketing_key,
                            start=event.occurred,
                            end=event.occurred + trigger.within,
                            last_event=event,
                            initial_count=initial_count,
                        )

                    if (
                        not bucket
                        and not trigger.after
                        and trigger.expects(event.event)
                    ):
                        # When ensuring a bucket and _creating it for the first time_,
                        # use an old time so that we can catch any other events flowing
                        # through the system at the same time even if they are out of
                        # order.  After the trigger fires and creates its next bucket,
                        # time will start from that point forward.  We'll use our
                        # preceding event lookback variable as the horizon that we'll
                        # accept these older events.
                        #
                        # https://github.com/PrefectHQ/nebula/issues/7230
                        start = event.occurred - PRECEDING_EVENT_LOOKBACK

                        bucket = await ensure_bucket(
                            session,
                            trigger,
                            bucketing_key=bucketing_key,
                            start=start,
                            end=event.occurred + trigger.within,
                            last_event=event,
                        )

                    if not trigger.expects(event.event):
                        continue

                    if not bucket:
                        bucket = await read_bucket(session, trigger, bucketing_key)
                        if not bucket:
                            continue

                    await evaluate(
                        session,
                        trigger,
                        bucket,
                        event.occurred,
                        triggering_event=event,
                    )
                finally:
                    await session.commit()


async def periodic_evaluation(now: DateTime):
    """Periodic tasks that should be run regularly, but not as often as every event"""
    offset = await get_events_clock_offset()
    as_of = now + timedelta(seconds=offset)

    logger.debug("Running periodic evaluation as of %s (offset %ss)", as_of, offset)

    # Any followers that have been sitting around longer than our lookback are never
    # going to see their leader event (maybe it was lost or took too long to arrive).
    # These events can just be evaluated now in the order they occurred.
    for event in await get_lost_followers():
        await reactive_evaluation(event)

    async with automations_session() as session:
        await sweep_closed_buckets(
            session,
            as_of - PREFECT_EVENTS_EXPIRED_BUCKET_BUFFER.value(),
        )
        await session.commit()


async def evaluate_periodically(periodic_granularity: timedelta):
    """Runs periodic evaluation on the given interval"""
    logger.debug(
        "Starting periodic evaluation task every %s seconds",
        periodic_granularity.total_seconds(),
    )
    while True:
        try:
            await periodic_evaluation(pendulum.now("UTC"))
        except Exception:
            logger.exception("Error running periodic evaluation")
        finally:
            await asyncio.sleep(periodic_granularity.total_seconds())


# The currently loaded automations for this shard, organized both by ID and by
# account and workspace
automations_by_id: Dict[UUID, Automation] = {}
triggers: Dict[TriggerID, EventTrigger] = {}
next_proactive_runs: Dict[TriggerID, DateTime] = {}

# This lock governs any changes to the set of loaded automations; any routine that will
# add/remove automations must be holding this lock when it does so.  It's best to use
# the methods below to access the loaded set of automations.
automations_lock = asyncio.Lock()


def find_interested_triggers(event: ReceivedEvent) -> Collection[EventTrigger]:
    candidates = triggers.values()
    return [trigger for trigger in candidates if trigger.covers(event)]


def load_automation(automation: Optional[Automation]):
    """Loads the given automation into memory so that it is available for evaluations"""
    if not automation:
        return

    event_triggers = automation.triggers_of_type(EventTrigger)

    if not automation.enabled or not event_triggers:
        forget_automation(automation.id)
        return

    automations_by_id[automation.id] = automation

    for trigger in event_triggers:
        triggers[trigger.id] = trigger
        next_proactive_runs.pop(trigger.id, None)


def forget_automation(automation_id: UUID):
    """Unloads the given automation from memory"""
    if automation := automations_by_id.pop(automation_id, None):
        for trigger in automation.triggers():
            triggers.pop(trigger.id, None)
            next_proactive_runs.pop(trigger.id, None)


async def automation_changed(
    automation_id: UUID,
    event: Literal["automation__created", "automation__updated", "automation__deleted"],
):
    async with automations_lock:
        if event in ("automation__deleted", "automation__updated"):
            forget_automation(automation_id)

        if event in ("automation__created", "automation__updated"):
            async with automations_session() as session:
                automation = await read_automation(session, automation_id)
                load_automation(automation)


@db_injector
async def load_automations(db: PrefectDBInterface, session: AsyncSession):
    """Loads all automations for the given set of accounts"""
    query = sa.select(db.Automation)

    logger.debug("Loading automations")

    result = await session.execute(query)
    for automation in result.scalars().all():
        load_automation(Automation.from_orm(automation))

    logger.debug(
        "Loaded %s automations with %s triggers", len(automations_by_id), len(triggers)
    )


@db_injector
async def remove_buckets_exceeding_threshold(
    db: PrefectDBInterface, session: AsyncSession, trigger: EventTrigger
):
    """Deletes bucket where the count has already exceeded the threshold"""
    assert isinstance(trigger, EventTrigger), repr(trigger)
    await session.execute(
        sa.delete(db.AutomationBucket).where(
            db.AutomationBucket.automation_id == trigger.automation.id,
            db.AutomationBucket.trigger_id == trigger.id,
            db.AutomationBucket.count >= trigger.threshold,
        )
    )


@db_injector
async def read_buckets_for_automation(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: Trigger,
    batch_size: int = AUTOMATION_BUCKET_BATCH_SIZE,
) -> AsyncGenerator["ORMAutomationBucket", None]:
    """Yields buckets for the given automation and trigger in batches."""
    offset = 0

    while True:
        query = (
            sa.select(db.AutomationBucket)
            .where(
                db.AutomationBucket.automation_id == trigger.automation.id,
                db.AutomationBucket.trigger_id == trigger.id,
            )
            .order_by(db.AutomationBucket.start)
            .limit(batch_size)
            .offset(offset)
        )

        result = await session.execute(query)
        buckets = result.scalars().all()

        if not buckets:
            break

        for bucket in buckets:
            yield bucket

        offset += batch_size


@db_injector
async def read_bucket(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: Trigger,
    bucketing_key: Tuple[str, ...],
) -> Optional["ORMAutomationBucket"]:
    """Gets the bucket this event would fall into for the given Automation, if there is
    one currently"""
    return await read_bucket_by_trigger_id(
        session,
        trigger.automation.id,
        trigger.id,
        bucketing_key,
    )


@db_injector
async def read_bucket_by_trigger_id(
    db: PrefectDBInterface,
    session: AsyncSession,
    automation_id: UUID,
    trigger_id: UUID,
    bucketing_key: Tuple[str, ...],
) -> Optional["ORMAutomationBucket"]:
    """Gets the bucket this event would fall into for the given Automation, if there is
    one currently"""
    query = sa.select(db.AutomationBucket).where(
        db.AutomationBucket.automation_id == automation_id,
        db.AutomationBucket.trigger_id == trigger_id,
        db.AutomationBucket.bucketing_key == bucketing_key,
    )
    result = await session.execute(query)
    bucket = result.scalars().first()
    if bucket:
        await session.refresh(bucket)

    return bucket


@db_injector
async def increment_bucket(
    db: PrefectDBInterface,
    session: AsyncSession,
    bucket: "ORMAutomationBucket",
    count: int,
    last_event: Optional[ReceivedEvent],
) -> "ORMAutomationBucket":
    """Adds the given count to the bucket, returning the new bucket"""
    additional_updates: dict = {"last_event": last_event} if last_event else {}
    await session.execute(
        db.insert(db.AutomationBucket)
        .values(
            automation_id=bucket.automation_id,
            trigger_id=bucket.trigger_id,
            bucketing_key=bucket.bucketing_key,
            start=bucket.start,
            end=bucket.end,
            count=count,
            last_operation="increment_bucket[insert]",
        )
        .on_conflict_do_update(
            index_elements=[
                db.AutomationBucket.automation_id,
                db.AutomationBucket.trigger_id,
                db.AutomationBucket.bucketing_key,
            ],
            set_=dict(
                count=db.AutomationBucket.count + count,
                last_operation="increment_bucket[update]",
                updated=pendulum.now("UTC"),
                **additional_updates,
            ),
        )
    )

    return await read_bucket_by_trigger_id(
        session,
        bucket.automation_id,
        bucket.trigger_id,
        bucket.bucketing_key,
    )


@db_injector
async def start_new_bucket(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: EventTrigger,
    bucketing_key: Tuple[str, ...],
    start: DateTime,
    end: DateTime,
    count: int,
    triggered_at: Optional[DateTime] = None,
) -> "ORMAutomationBucket":
    """Ensures that a bucket with the given start and end exists with the given count,
    returning the new bucket"""
    automation = trigger.automation

    await session.execute(
        db.insert(db.AutomationBucket)
        .values(
            automation_id=automation.id,
            trigger_id=trigger.id,
            bucketing_key=bucketing_key,
            start=start,
            end=end,
            count=count,
            last_operation="start_new_bucket[insert]",
            triggered_at=triggered_at,
        )
        .on_conflict_do_update(
            index_elements=[
                db.AutomationBucket.automation_id,
                db.AutomationBucket.trigger_id,
                db.AutomationBucket.bucketing_key,
            ],
            set_=dict(
                start=start,
                end=end,
                count=count,
                last_operation="start_new_bucket[update]",
                updated=pendulum.now("UTC"),
                triggered_at=triggered_at,
            ),
        )
    )

    return await read_bucket_by_trigger_id(
        session,
        automation.id,
        trigger.id,
        bucketing_key,
    )


@db_injector
async def ensure_bucket(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: EventTrigger,
    bucketing_key: Tuple[str, ...],
    start: DateTime,
    end: DateTime,
    last_event: Optional[ReceivedEvent],
    initial_count: int = 0,
) -> "ORMAutomationBucket":
    """Ensures that a bucket has been started for the given automation and key,
    returning the current bucket.  Will not modify the existing bucket."""
    automation = trigger.automation
    additional_updates: dict = {"last_event": last_event} if last_event else {}
    await session.execute(
        db.insert(db.AutomationBucket)
        .values(
            automation_id=automation.id,
            trigger_id=trigger.id,
            bucketing_key=bucketing_key,
            last_event=last_event,
            start=start,
            end=end,
            count=initial_count,
            last_operation="ensure_bucket[insert]",
        )
        .on_conflict_do_update(
            index_elements=[
                db.AutomationBucket.automation_id,
                db.AutomationBucket.trigger_id,
                db.AutomationBucket.bucketing_key,
            ],
            set_=dict(
                # no-op, but this counts as an update so the query returns a row
                count=db.AutomationBucket.count,
                **additional_updates,
            ),
        )
    )

    return await read_bucket_by_trigger_id(
        session, automation.id, trigger.id, bucketing_key
    )


@db_injector
async def remove_bucket(
    db: PrefectDBInterface, session: AsyncSession, bucket: "ORMAutomationBucket"
):
    """Removes the given bucket from the database"""
    await session.execute(
        sa.delete(db.AutomationBucket).where(
            db.AutomationBucket.automation_id == bucket.automation_id,
            db.AutomationBucket.trigger_id == bucket.trigger_id,
            db.AutomationBucket.bucketing_key == bucket.bucketing_key,
        )
    )


@db_injector
async def sweep_closed_buckets(
    db: PrefectDBInterface, session: AsyncSession, older_than: DateTime
) -> None:
    await session.execute(
        sa.delete(db.AutomationBucket).where(db.AutomationBucket.end <= older_than)
    )


# How long we'll retain preceding events (to aid with ordering)
PRECEDING_EVENT_LOOKBACK = timedelta(minutes=15)

# How long we'll retain events we've processed (to prevent re-processing an event)
PROCESSED_EVENT_LOOKBACK = timedelta(minutes=30)


class EventArrivedEarly(Exception):
    def __init__(self, event: ReceivedEvent):
        self.event = event


class MaxDepthExceeded(Exception):
    def __init__(self, event: ReceivedEvent):
        self.event = event


SEEN_EXPIRATION = max(PRECEDING_EVENT_LOOKBACK, PROCESSED_EVENT_LOOKBACK)


_seen_events: MutableMapping[UUID, bool] = TTLCache(
    maxsize=10000, ttl=SEEN_EXPIRATION.total_seconds()
)


async def event_has_been_seen(id: UUID) -> bool:
    return _seen_events.get(id, False)


async def record_event_as_seen(event: ReceivedEvent) -> None:
    _seen_events[event.id] = True


@asynccontextmanager
async def with_preceding_event_confirmed(event: ReceivedEvent, depth: int = 0):
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
    if event.event == "prefect.log.write":
        # special case, we know that log writes are extremely high volume and also that
        # we do not tag these in event.follows links, so just exit early and don't
        # incur the expense of bookkeeping with these
        yield
        return

    if event.follows:
        if not await event_has_been_seen(event.follows):
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
                await record_follower(event)
                raise EventArrivedEarly(event)

    yield

    await record_event_as_seen(event)

    # we have just processed an event that other events were waiting on, so let's
    # react to them now in the order they occurred
    for waiter in await get_followers(event):
        await reactive_evaluation(waiter, depth + 1)

    # if this event was itself waiting on something, let's consider it as resolved now
    # that it has been processed
    if event.follows:
        await forget_follower(event)


@db_injector
async def record_follower(db: PrefectDBInterface, event: ReceivedEvent):
    """Remember that this event is waiting on another event to arrive"""
    assert event.follows

    async with db.session_context(begin_transaction=True) as session:
        await session.execute(
            sa.insert(db.AutomationEventFollower).values(
                leader_event_id=event.follows,
                follower_event_id=event.id,
                received=event.received,
                follower=event,
            )
        )


@db_injector
async def forget_follower(db: PrefectDBInterface, follower: ReceivedEvent):
    """Forget that this event is waiting on another event to arrive"""
    assert follower.follows

    async with db.session_context(begin_transaction=True) as session:
        await session.execute(
            sa.delete(db.AutomationEventFollower).where(
                db.AutomationEventFollower.follower_event_id == follower.id
            )
        )


@db_injector
async def get_followers(
    db: PrefectDBInterface, leader: ReceivedEvent
) -> List[ReceivedEvent]:
    """Returns events that were waiting on this leader event to arrive"""
    async with db.session_context() as session:
        query = sa.select(db.AutomationEventFollower.follower).where(
            db.AutomationEventFollower.leader_event_id == leader.id
        )
        result = await session.execute(query)
        followers = result.scalars().all()
        return sorted(followers, key=lambda e: e.occurred)


@db_injector
async def get_lost_followers(db: PrefectDBInterface) -> List[ReceivedEvent]:
    """Returns events that were waiting on a leader event that never arrived"""
    earlier = pendulum.now("UTC") - PRECEDING_EVENT_LOOKBACK

    async with db.session_context(begin_transaction=True) as session:
        query = sa.select(db.AutomationEventFollower.follower).where(
            db.AutomationEventFollower.received < earlier
        )
        result = await session.execute(query)
        followers = result.scalars().all()

        # forget these followers, since they are never going to see their leader event

        await session.execute(
            sa.delete(db.AutomationEventFollower).where(
                db.AutomationEventFollower.received < earlier
            )
        )

        return sorted(followers, key=lambda e: e.occurred)


async def reset():
    """Resets the in-memory state of the service"""
    reset_events_clock()
    automations_by_id.clear()
    triggers.clear()
    next_proactive_runs.clear()


@asynccontextmanager
async def consumer(
    periodic_granularity: timedelta = timedelta(seconds=5),
) -> AsyncGenerator[MessageHandler, None]:
    """The `triggers.consumer` processes all Events arriving on the event bus to
    determine if they meet the automation criteria, queuing up a corresponding
    `TriggeredAction` for the `actions` service if the automation criteria is met."""
    async with automations_session() as session:
        await load_automations(session)

    proactive_task = asyncio.create_task(evaluate_periodically(periodic_granularity))

    async def message_handler(message: Message):
        if not message.data:
            logger.warning("Message had no data")

            return

        if not message.attributes:
            logger.warning("Message had no attributes")

            return

        if message.attributes.get("event") == "prefect.log.write":
            return

        try:
            event_id = UUID(message.attributes["id"])
        except (KeyError, ValueError, TypeError):
            logger.warning(
                "Unable to get event ID from message attributes: %s",
                repr(message.attributes),
            )
            return

        if await event_has_been_seen(event_id):
            return

        event = ReceivedEvent.parse_raw(message.data)

        try:
            await reactive_evaluation(event)
        except EventArrivedEarly:
            pass  # it's fine to ACK this message, since it is safe in the DB

    try:
        logger.debug("Starting reactive evaluation task")
        yield message_handler
    finally:
        proactive_task.cancel()


async def proactive_evaluation(trigger: EventTrigger, as_of: DateTime) -> DateTime:
    """The core proactive evaluation operation for a single Automation"""
    assert isinstance(trigger, EventTrigger), repr(trigger)
    automation = trigger.automation

    offset = await get_events_clock_offset()
    as_of += timedelta(seconds=offset)

    logger.debug(
        "Evaluating automation %s trigger %s proactively as of %s (offset %ss)",
        automation.id,
        trigger.id,
        as_of,
        offset,
    )

    # By default, the next run will come after the full trigger window, but it
    # may be sooner based on the state of the buckets
    run_again_at = as_of + trigger.within

    async with automations_session() as session:
        try:
            if not trigger.for_each:
                await ensure_bucket(
                    session,
                    trigger,
                    bucketing_key=tuple(),
                    start=as_of,
                    end=as_of + trigger.within,
                    last_event=None,
                )

            # preemptively delete buckets where possible without
            # evaluating them in memory
            await remove_buckets_exceeding_threshold(session, trigger)

            async for bucket in read_buckets_for_automation(session, trigger):
                next_bucket = await evaluate(
                    session, trigger, bucket, as_of, triggering_event=None
                )
                if next_bucket and as_of < next_bucket.end < run_again_at:
                    run_again_at = pendulum.instance(next_bucket.end)

            return run_again_at
        finally:
            await session.commit()


async def evaluate_proactive_triggers():
    for trigger in triggers.values():
        if trigger.posture != Posture.Proactive:
            continue

        next_run = next_proactive_runs.get(trigger.id, pendulum.now("UTC"))
        if next_run > pendulum.now("UTC"):
            continue

        try:
            run_again_at = await proactive_evaluation(trigger, pendulum.now("UTC"))
            logger.debug(
                "Automation %s trigger %s will run again at %s",
                trigger.automation.id,
                trigger.id,
                run_again_at,
            )
            next_proactive_runs[trigger.id] = run_again_at
        except Exception:
            logger.exception(
                "Error evaluating automation %s trigger %s proactively",
                trigger.automation.id,
                trigger.id,
            )
