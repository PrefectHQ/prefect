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
    Optional,
    Tuple,
)
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Literal, TypeAlias

import prefect.types._datetime
from prefect._internal.retries import retry_async_fn
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.events import messaging
from prefect.server.events.actions import ServerActionTypes
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
from prefect.server.events.ordering import (
    PRECEDING_EVENT_LOOKBACK,
    CausalOrdering,
    EventArrivedEarly,
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
    import logging

    from prefect.server.database.orm_models import ORMAutomationBucket


logger: "logging.Logger" = get_logger(__name__)

AutomationID: TypeAlias = UUID
TriggerID: TypeAlias = UUID


AUTOMATION_BUCKET_BATCH_SIZE = 500


async def evaluate(
    session: AsyncSession,
    trigger: EventTrigger,
    bucket: "ORMAutomationBucket",
    now: prefect.types._datetime.DateTime,
    triggering_event: Optional[ReceivedEvent],
) -> "ORMAutomationBucket | None":
    """Evaluates an Automation, either triggered by a specific event or proactively
    on a time interval.  Evaluating a Automation updates the associated counters for
    each automation, and will fire the associated action if it has met the threshold."""
    automation = trigger.automation

    logging_context = {
        "automation": automation.id,
        "trigger": trigger.id,
        "bucketing_key": bucket.bucketing_key,
        "bucket_start": bucket.start,
        "bucket_end": bucket.end,
        "bucket_initial_count": bucket.count,
        "bucket_last_operation": bucket.last_operation,
        "now": now,
        "triggering_event": (
            {
                "id": triggering_event.id,
                "event": triggering_event.event,
            }
            if triggering_event
            else None
        ),
    }

    # Implementation notes:
    #
    # This triggering algorithm maintains an invariant that there is exactly one
    # time-based "bucket" open and collecting events for each automation at a time. When
    # an event comes in that matches the automation, one of four things can happen:
    #
    # 1. The event would have matched an older bucket that has either expired or has
    #    already filled up, and thus is no longer relevant;
    # 2. The event matches the current bucket, but the bucket does not meet its
    #    threshold yet;
    # 3. The event matches the current bucket, causes it to meet the the threshold, so
    #    we fire immediately and advance the bucket to the next time period.
    # 4. The event matches the current bucket, but the event is for a future time after
    #    the current bucket has expired, so we will start the new bucket and re-evaluate
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
        # current bucket.  We can safely ignore this event/timestamp entirely.  Case #1
        # from the implementation notes above.
        logger.debug(
            "Automation %s (%r) trigger %s got a late event for keys (%r)",
            automation.id,
            automation.name,
            trigger.id,
            bucket.bucketing_key,
            extra=logging_context,
        )
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
    meets_threshold = trigger.meets_threshold(bucket.count)

    if ready_to_fire and meets_threshold:
        logger.debug(
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
            extra=logging_context,
        )

        firing = Firing(
            trigger=trigger,
            trigger_states={TriggerState.Triggered},
            triggered=prefect.types._datetime.now("UTC"),
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
        # before setting up a new future bucket.  Case #2 from the implementation notes
        # above.
        logger.debug(
            "Automation %s (%r) trigger %s has more time for keys (%r)",
            automation.id,
            automation.name,
            trigger.id,
            bucket.bucketing_key,
            extra={
                **logging_context,
                "ready_to_fire": ready_to_fire,
                "meets_threshold": meets_threshold,
            },
        )
        return bucket
    else:
        # Case #2 from the implementation notes above.
        logger.debug(
            "Automation %s (%r) trigger %s not ready to fire for keys (%r)",
            automation.id,
            automation.name,
            trigger.id,
            bucket.bucketing_key,
            extra={
                **logging_context,
                "ready_to_fire": ready_to_fire,
                "meets_threshold": meets_threshold,
                "bucket_current_count": bucket.count,
            },
        )

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

        start = prefect.types._datetime.create_datetime_instance(max(bucket.end, now))
        end = start + trigger.within

        # If we're processing a reactive trigger and leaving the function with a count
        # that we've just spent in the bucket for the next time window, it means that we
        # just processed an event that was in the future. It's possible that this event
        # was sufficient enough to cause the trigger to fire, so we need to evaluate one
        # more time to see if that's the case.  This is case #4 from the implementation
        # notes above.
        if trigger.posture == Posture.Reactive and count > 0:
            bucket = await start_new_bucket(
                session,
                trigger,
                bucketing_key=tuple(bucket.bucketing_key),
                start=start,
                end=end,
                count=0,
            )
            return await evaluate(session, trigger, bucket, now, triggering_event)
        else:
            return await start_new_bucket(
                session,
                trigger,
                bucketing_key=tuple(bucket.bucketing_key),
                start=start,
                end=end,
                count=count,
            )


async def fire(session: AsyncSession, firing: Firing) -> None:
    if isinstance(firing.trigger.parent, Automation):
        await act(firing)
    elif isinstance(firing.trigger.parent, CompositeTrigger):
        await evaluate_composite_trigger(session, firing)
    else:
        raise NotImplementedError(
            f"Cannot fire {firing} with parent trigger type {type(firing.trigger.parent)}"
        )


async def evaluate_composite_trigger(session: AsyncSession, firing: Firing) -> None:
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
                triggered=prefect.types._datetime.now("UTC"),
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
    firings: list[Firing] = [
        cf.child_firing for cf in await get_child_firings(session, trigger)
    ]
    firing_ids: set[UUID] = {f.id for f in firings}

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
        await clear_child_firings(session, trigger, firing_ids=list(firing_ids))

        await fire(
            session,
            Firing(
                trigger=trigger,
                trigger_states={TriggerState.Triggered},
                triggered=prefect.types._datetime.now("UTC"),
                triggering_firings=firings,
            ),
        )


async def act(firing: Firing) -> None:
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
    source_actions: List[Tuple[Optional[ReceivedEvent], ServerActionTypes]] = [
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
            await publisher.publish_data(action.model_dump_json().encode(), {})


__events_clock_lock: Optional[asyncio.Lock] = None
_events_clock: Optional[float] = None
_events_clock_updated: Optional[float] = None


def _events_clock_lock() -> asyncio.Lock:
    global __events_clock_lock
    if __events_clock_lock is None:
        __events_clock_lock = asyncio.Lock()
    return __events_clock_lock


async def update_events_clock(event: ReceivedEvent) -> None:
    global _events_clock, _events_clock_updated
    async with _events_clock_lock():
        # we want the offset to be negative to represent that we are always
        # processing events behind realtime...
        now = prefect.types._datetime.now("UTC").float_timestamp
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

    async with _events_clock_lock():
        if _events_clock is None or _events_clock_updated is None:
            return 0.0

        now: float = prefect.types._datetime.now("UTC").float_timestamp
        offset = (_events_clock - now) + (now - _events_clock_updated)

    return offset


async def reset_events_clock() -> None:
    global _events_clock, _events_clock_updated
    async with _events_clock_lock():
        _events_clock = None
        _events_clock_updated = None


async def reactive_evaluation(event: ReceivedEvent, depth: int = 0) -> None:
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
        await stack.enter_async_context(
            causal_ordering().preceding_event_confirmed(
                reactive_evaluation, event, depth
            )
        )

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

            async with automations_session(begin_transaction=True) as session:
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


# retry on operational errors to account for db flakiness with sqlite
@retry_async_fn(max_attempts=3, retry_on_exceptions=(sa.exc.OperationalError,))
async def get_lost_followers() -> List[ReceivedEvent]:
    """Get followers that have been sitting around longer than our lookback"""
    return await causal_ordering().get_lost_followers()


async def periodic_evaluation(now: prefect.types._datetime.DateTime) -> None:
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


async def evaluate_periodically(periodic_granularity: timedelta) -> None:
    """Runs periodic evaluation on the given interval"""
    logger.debug(
        "Starting periodic evaluation task every %s seconds",
        periodic_granularity.total_seconds(),
    )
    while True:
        try:
            await periodic_evaluation(prefect.types._datetime.now("UTC"))
        except Exception:
            logger.exception("Error running periodic evaluation")
        finally:
            await asyncio.sleep(periodic_granularity.total_seconds())


# The currently loaded automations for this shard, organized both by ID and by
# account and workspace
automations_by_id: Dict[UUID, Automation] = {}
triggers: Dict[TriggerID, EventTrigger] = {}
next_proactive_runs: Dict[TriggerID, prefect.types._datetime.DateTime] = {}

# This lock governs any changes to the set of loaded automations; any routine that will
# add/remove automations must be holding this lock when it does so.  It's best to use
# the methods below to access the loaded set of automations.
__automations_lock: Optional[asyncio.Lock] = None


def _automations_lock() -> asyncio.Lock:
    global __automations_lock
    if __automations_lock is None:
        __automations_lock = asyncio.Lock()
    return __automations_lock


def find_interested_triggers(event: ReceivedEvent) -> Collection[EventTrigger]:
    candidates = triggers.values()
    return [trigger for trigger in candidates if trigger.covers(event)]


def load_automation(automation: Optional[Automation]) -> None:
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


def forget_automation(automation_id: UUID) -> None:
    """Unloads the given automation from memory"""
    if automation := automations_by_id.pop(automation_id, None):
        for trigger in automation.triggers():
            triggers.pop(trigger.id, None)
            next_proactive_runs.pop(trigger.id, None)


async def automation_changed(
    automation_id: UUID,
    event: Literal["automation__created", "automation__updated", "automation__deleted"],
) -> None:
    async with _automations_lock():
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
        load_automation(Automation.model_validate(automation, from_attributes=True))

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
) -> "ORMAutomationBucket | None":
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
    additional_updates: dict[str, ReceivedEvent] = (
        {"last_event": last_event} if last_event else {}
    )
    await session.execute(
        db.queries.insert(db.AutomationBucket)
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
                updated=prefect.types._datetime.now("UTC"),
                **additional_updates,
            ),
        )
    )

    read_bucket = await read_bucket_by_trigger_id(
        session,
        bucket.automation_id,
        bucket.trigger_id,
        tuple(bucket.bucketing_key),
    )

    if TYPE_CHECKING:
        assert read_bucket is not None

    return read_bucket


@db_injector
async def start_new_bucket(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: EventTrigger,
    bucketing_key: Tuple[str, ...],
    start: prefect.types._datetime.DateTime,
    end: prefect.types._datetime.DateTime,
    count: int,
    triggered_at: Optional[prefect.types._datetime.DateTime] = None,
) -> "ORMAutomationBucket":
    """Ensures that a bucket with the given start and end exists with the given count,
    returning the new bucket"""
    automation = trigger.automation

    await session.execute(
        db.queries.insert(db.AutomationBucket)
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
                updated=prefect.types._datetime.now("UTC"),
                triggered_at=triggered_at,
            ),
        )
    )

    read_bucket = await read_bucket_by_trigger_id(
        session,
        automation.id,
        trigger.id,
        tuple(bucketing_key),
    )

    if TYPE_CHECKING:
        assert read_bucket is not None

    return read_bucket


@db_injector
async def ensure_bucket(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: EventTrigger,
    bucketing_key: Tuple[str, ...],
    start: prefect.types._datetime.DateTime,
    end: prefect.types._datetime.DateTime,
    last_event: Optional[ReceivedEvent],
    initial_count: int = 0,
) -> "ORMAutomationBucket":
    """Ensures that a bucket has been started for the given automation and key,
    returning the current bucket.  Will not modify the existing bucket."""
    automation = trigger.automation
    additional_updates: dict[str, ReceivedEvent] = (
        {"last_event": last_event} if last_event else {}
    )
    await session.execute(
        db.queries.insert(db.AutomationBucket)
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

    read_bucket = await read_bucket_by_trigger_id(
        session, automation.id, trigger.id, tuple(bucketing_key)
    )

    if TYPE_CHECKING:
        assert read_bucket is not None

    return read_bucket


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
    db: PrefectDBInterface,
    session: AsyncSession,
    older_than: prefect.types._datetime.DateTime,
) -> None:
    await session.execute(
        sa.delete(db.AutomationBucket).where(db.AutomationBucket.end <= older_than)
    )


async def reset() -> None:
    """Resets the in-memory state of the service"""
    await reset_events_clock()
    automations_by_id.clear()
    triggers.clear()
    next_proactive_runs.clear()


def causal_ordering() -> CausalOrdering:
    return CausalOrdering(scope="")


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

    ordering = causal_ordering()

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

        if await ordering.event_has_been_seen(event_id):
            return

        event = ReceivedEvent.model_validate_json(message.data)

        try:
            await reactive_evaluation(event)
        except EventArrivedEarly:
            pass  # it's fine to ACK this message, since it is safe in the DB

    try:
        logger.debug("Starting reactive evaluation task")
        yield message_handler
    finally:
        proactive_task.cancel()


async def proactive_evaluation(
    trigger: EventTrigger, as_of: prefect.types._datetime.DateTime
) -> prefect.types._datetime.DateTime:
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
                    run_again_at = prefect.types._datetime.create_datetime_instance(
                        next_bucket.end
                    )

            return run_again_at
        finally:
            await session.commit()


async def evaluate_proactive_triggers() -> None:
    for trigger in triggers.values():
        if trigger.posture != Posture.Proactive:
            continue

        next_run = next_proactive_runs.get(
            trigger.id, prefect.types._datetime.now("UTC")
        )
        if next_run > prefect.types._datetime.now("UTC"):
            continue

        try:
            run_again_at = await proactive_evaluation(
                trigger, prefect.types._datetime.now("UTC")
            )
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
