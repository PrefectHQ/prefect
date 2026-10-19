"""
Held `expect` events for proactive triggers with `after`.

Events for one bucketing key can be evaluated in any order, so an `expect` event can be
evaluated before the `after` event that opens its window, or counted in one window
before a later `after` event rolls it. Every `expect`-only event is held here, and each
bucket that opens or rolls counts the held events that occurred inside its window.
"""

import hashlib
from datetime import datetime
from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.events.ordering import PRECEDING_EVENT_LOOKBACK
from prefect.server.events.schemas.automations import EventTrigger, Posture
from prefect.server.events.schemas.events import ReceivedEvent

# Bounds the rows for a key that takes many `expect` events within the lookback. Past
# it, a late bucket counts only the newest held events.  A trigger whose threshold is
# higher keeps that many instead, or a window it opens late could never meet it.
HELD_EXPECT_EVENTS_LIMIT = 100


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
    same key that are too old or beyond the limit"""
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
    await session.execute(
        sa.delete(db.AutomationHeldEvent).where(
            *for_key,
            db.AutomationHeldEvent.occurred < event.occurred - PRECEDING_EVENT_LOOKBACK,
        )
    )
    newest = (
        sa.select(db.AutomationHeldEvent.id)
        .where(*for_key)
        .order_by(db.AutomationHeldEvent.occurred.desc())
        .limit(max(HELD_EXPECT_EVENTS_LIMIT, trigger.threshold))
    )
    await session.execute(
        sa.delete(db.AutomationHeldEvent).where(
            *for_key, db.AutomationHeldEvent.id.not_in(newest)
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
    older_than: datetime,
) -> None:
    """Delete every held event that was held before `older_than`"""
    await session.execute(
        sa.delete(db.AutomationHeldEvent).where(
            db.AutomationHeldEvent.updated < older_than
        )
    )
