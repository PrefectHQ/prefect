"""
Held `expect` events for proactive triggers with `after`.

Events for one bucketing key can be evaluated in any order, so an `expect` event can be
evaluated before the `after` event that opens its window, or counted in one window
before a later `after` event rolls it. Every `expect`-only event is held here, and each
bucket that opens or rolls counts the held events that occurred inside its window.
"""

import calendar
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.events.ordering import PRECEDING_EVENT_LOOKBACK
from prefect.server.events.schemas.automations import EventTrigger, Posture
from prefect.server.events.schemas.events import ReceivedEvent

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# A lost follower waits up to the lookback before it is evaluated, and an `after`
# event among them can open a window over events that occurred up to one lookback
# before it.  A held event must outlast both, so it is kept for twice the lookback.
HELD_EXPECT_EVENTS_RETENTION = 2 * PRECEDING_EVENT_LOOKBACK


def slot_start(occurred: datetime, width: timedelta) -> datetime:
    """The start of the slot that contains `occurred`, where slots are `width` wide
    and aligned to the epoch"""
    # The offset from the epoch is built from plain `datetime` parts, because
    # subtracting a `datetime` from a pendulum `DateTime` gives a duration that
    # cannot be divided by a `timedelta`.
    since_epoch = timedelta(
        seconds=calendar.timegm(occurred.utctimetuple()),
        microseconds=occurred.microsecond,
    )
    return EPOCH + since_epoch // width * width


def holds_expect_events(trigger: EventTrigger) -> bool:
    """Whether the trigger holds its `expect`-only events for the buckets that open
    later"""
    return trigger.posture == Posture.Proactive and bool(trigger.after)


@db_injector
async def acquire_bucketing_key_lock(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: EventTrigger,
    bucketing_key: Sequence[str],
) -> None:
    """
    Acquire a transaction-scoped lock on one bucketing key of a trigger.

    The lock is released when the transaction commits or rolls back.
    """
    # Holding an event and opening a bucket each read what the other writes. Without
    # the lock, two server replicas can each miss the other's uncommitted write, and
    # the held event is never counted.
    if db.dialect.name != "postgresql":
        # SQLite allows one writer at a time, and a transaction that read before
        # another one committed cannot write, so neither side misses the other.
        return

    digest = hashlib.blake2b(
        "\x1f".join([str(trigger.id), *bucketing_key]).encode(), digest_size=8
    ).digest()
    lock_key = int.from_bytes(digest, "big", signed=True)
    await session.execute(
        sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key}
    )


def _for_key(
    db: PrefectDBInterface, trigger: EventTrigger, bucketing_key: Sequence[str]
) -> list[sa.ColumnElement[bool]]:
    return [
        db.AutomationHeldEvent.automation_id == trigger.automation.id,
        db.AutomationHeldEvent.trigger_id == trigger.id,
        db.AutomationHeldEvent.bucketing_key == bucketing_key,
    ]


@db_injector
async def is_held(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: EventTrigger,
    bucketing_key: Sequence[str],
    event: ReceivedEvent,
) -> bool:
    """Whether the event is already held for this trigger and key"""
    result = await session.execute(
        sa.select(sa.literal(True)).where(
            *_for_key(db, trigger, bucketing_key),
            db.AutomationHeldEvent.event_id == event.id,
        )
    )
    return result.scalar() is not None


@db_injector
async def hold_event(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: EventTrigger,
    bucketing_key: Sequence[str],
    event: ReceivedEvent,
) -> None:
    """Hold the event for the buckets that open later, and drop held events for the
    same key that are too old or that no window needs to meet its threshold"""
    await session.execute(
        db.queries.insert(db.AutomationHeldEvent)
        .values(
            automation_id=trigger.automation.id,
            trigger_id=trigger.id,
            bucketing_key=bucketing_key,
            event_id=event.id,
            occurred=event.occurred,
        )
        .on_conflict_do_nothing(
            index_elements=[
                db.AutomationHeldEvent.automation_id,
                db.AutomationHeldEvent.trigger_id,
                db.AutomationHeldEvent.bucketing_key,
                db.AutomationHeldEvent.event_id,
            ]
        )
    )

    for_key = _for_key(db, trigger, bucketing_key)

    # The horizon is measured from the newest held event, not from this one.
    # Otherwise events held newest first, as in a backfill, each measure an older
    # horizon, never drop the newer events, and grow the key without bound until
    # the sweep.  A window `within` wide that rolls back over the newest event can
    # reach events up to `within` before it, so the horizon is never shorter.
    newest = await session.scalar(
        sa.select(sa.func.max(db.AutomationHeldEvent.occurred)).where(*for_key)
    )
    horizon = max(HELD_EXPECT_EVENTS_RETENTION, trigger.within)
    await session.execute(
        sa.delete(db.AutomationHeldEvent).where(
            *for_key,
            db.AutomationHeldEvent.occurred < (newest or event.occurred) - horizon,
        )
    )

    # Time is divided into slots `within` wide, aligned to the epoch, and each slot
    # keeps its first and last `threshold` events.  A window covers the end of one
    # slot and the start of the next, so it counts at least the smaller of the
    # threshold and the number of events that occurred inside it.  A count at the
    # threshold already stops a proactive trigger from firing, so the dropped
    # events change no outcome.  Only the new event's slot has changed, so only
    # that slot is trimmed.
    start = slot_start(event.occurred, trigger.within)
    in_slot = [
        *for_key,
        db.AutomationHeldEvent.occurred >= start,
        db.AutomationHeldEvent.occurred < start + trigger.within,
    ]
    first = (
        sa.select(db.AutomationHeldEvent.id)
        .where(*in_slot)
        .order_by(
            db.AutomationHeldEvent.occurred.asc(),
            db.AutomationHeldEvent.event_id.asc(),
        )
        .limit(trigger.threshold)
    )
    last = (
        sa.select(db.AutomationHeldEvent.id)
        .where(*in_slot)
        .order_by(
            db.AutomationHeldEvent.occurred.desc(),
            db.AutomationHeldEvent.event_id.desc(),
        )
        .limit(trigger.threshold)
    )
    await session.execute(
        sa.delete(db.AutomationHeldEvent).where(
            *in_slot,
            db.AutomationHeldEvent.id.not_in(first),
            db.AutomationHeldEvent.id.not_in(last),
        )
    )


@db_injector
def held_events_in_window(
    db: PrefectDBInterface,
    trigger: EventTrigger,
    bucketing_key: Sequence[str],
    start: datetime,
    end: datetime,
) -> sa.ScalarSelect[int]:
    """A scalar subquery counting the events held for this trigger and key that
    occurred in the window from `start` (inclusive) to `end` (exclusive)"""
    return (
        sa.select(sa.func.count())
        .where(
            *_for_key(db, trigger, bucketing_key),
            db.AutomationHeldEvent.occurred >= start,
            db.AutomationHeldEvent.occurred < end,
        )
        .scalar_subquery()
    )


@db_injector
async def sweep_held_events(
    db: PrefectDBInterface,
    session: AsyncSession,
    now: datetime,
) -> None:
    """Delete every held event that was held more than `HELD_EXPECT_EVENTS_RETENTION`
    before `now`, unless a bucket for its key has not ended by `now`"""
    # `within` has no upper bound, so a bucket can stay open longer than the
    # retention, and an `after` event that occurred inside it can still roll it
    # back over its held events.
    open_bucket = sa.exists().where(
        db.AutomationBucket.automation_id == db.AutomationHeldEvent.automation_id,
        db.AutomationBucket.trigger_id == db.AutomationHeldEvent.trigger_id,
        db.AutomationBucket.bucketing_key == db.AutomationHeldEvent.bucketing_key,
        db.AutomationBucket.end > now,
    )
    await session.execute(
        sa.delete(db.AutomationHeldEvent).where(
            db.AutomationHeldEvent.updated < now - HELD_EXPECT_EVENTS_RETENTION,
            ~open_bucket,
        )
    )
