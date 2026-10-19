"""Held `expect` events stay bounded in count and lifetime, whatever the volume."""

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface
from prefect.server.events import actions, triggers
from prefect.server.events.models import automation_held_events
from prefect.server.events.models.automation_held_events import (
    HELD_EXPECT_EVENTS_RETENTION,
)
from prefect.server.events.models.automations import create_automation
from prefect.server.events.ordering import PRECEDING_EVENT_LOOKBACK
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Posture,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.types._datetime import DateTime, now

pytestmark = pytest.mark.clear_db

KEY = ("woodchuck",)
WITHIN = timedelta(seconds=60)


@pytest.fixture
def threshold() -> int:
    return 1


@pytest.fixture
def within() -> timedelta:
    return WITHIN


@pytest.fixture
async def trigger(
    automations_session: AsyncSession, threshold: int, within: timedelta
) -> EventTrigger:
    automation = await create_automation(
        automations_session,
        Automation(
            name="held events test",
            trigger=EventTrigger(
                after={"animal.woke"},
                expect={"animal.walked"},
                for_each={"prefect.resource.id"},
                posture=Posture.Proactive,
                threshold=threshold,
                within=within,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    assert isinstance(automation.trigger, EventTrigger)
    return automation.trigger


def walked(occurred: datetime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=occurred,
        event="animal.walked",
        resource={"prefect.resource.id": "woodchuck"},
        id=uuid4(),
    )


async def held_occurrences(
    db: PrefectDBInterface, session: AsyncSession
) -> list[DateTime]:
    result = await session.execute(
        sa.select(db.AutomationHeldEvent.occurred).order_by(
            db.AutomationHeldEvent.occurred
        )
    )
    return list(result.scalars().all())


async def hold_all(
    session: AsyncSession, trigger: EventTrigger, occurrences: Iterable[datetime]
) -> None:
    for occurred in occurrences:
        await automation_held_events.hold_event(session, trigger, KEY, walked(occurred))


async def held_event_ids(db: PrefectDBInterface, session: AsyncSession) -> set[UUID]:
    result = await session.execute(sa.select(db.AutomationHeldEvent.event_id))
    return set(result.scalars().all())


async def count_in_window(
    session: AsyncSession, trigger: EventTrigger, start: datetime
) -> int:
    result = await session.execute(
        sa.select(
            automation_held_events.held_events_in_window(
                trigger, KEY, start, start + WITHIN
            )
        )
    )
    return result.scalar_one()


@pytest.fixture
def slot_start(frozen_time: DateTime) -> datetime:
    """The start of the slot that contains `frozen_time`: slots are `within` wide
    and aligned to the epoch"""
    width = WITHIN.total_seconds()
    return datetime.fromtimestamp(
        frozen_time.timestamp() // width * width, timezone.utc
    )


@pytest.mark.parametrize("threshold", [1, 2, 3])
@pytest.mark.parametrize(
    "evaluation_order",
    [
        pytest.param(sorted, id="oldest-first"),
        pytest.param(reversed, id="newest-first"),
    ],
)
async def test_a_slot_keeps_its_first_and_last_events_up_to_the_threshold(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    slot_start: datetime,
    threshold: int,
    evaluation_order: Callable[[list[datetime]], Iterable[datetime]],
):
    """Of the ten events held in one slot, whatever order they arrive in, the slot
    keeps the first and the last `threshold` of them."""
    occurrences = [slot_start + timedelta(seconds=i) for i in range(10)]
    await hold_all(automations_session, trigger, evaluation_order(occurrences))

    assert (
        await held_occurrences(db, automations_session)
        == occurrences[:threshold] + occurrences[-threshold:]
    )


async def test_events_at_the_same_instant_are_kept_by_event_id(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    slot_start: datetime,
):
    """Among events that occurred at the same instant, the slot keeps the lowest and
    the highest event ids."""
    events = [walked(slot_start) for _ in range(5)]
    for event in events:
        await automation_held_events.hold_event(
            automations_session, trigger, KEY, event
        )

    ids = sorted(event.id for event in events)
    assert await held_event_ids(db, automations_session) == {ids[0], ids[-1]}


@pytest.mark.parametrize("threshold", [1, 3])
@pytest.mark.parametrize(
    "window_offset",
    [
        pytest.param(timedelta(seconds=-59), id="one-event-at-the-end"),
        pytest.param(timedelta(seconds=-58), id="two-events-at-the-end"),
        pytest.param(timedelta(seconds=0), id="the-first-slot"),
        pytest.param(timedelta(seconds=30), id="half-of-each-slot"),
        pytest.param(timedelta(seconds=59, milliseconds=500), id="near-the-boundary"),
        pytest.param(timedelta(seconds=60), id="the-second-slot"),
        pytest.param(timedelta(seconds=118), id="two-events-at-the-start"),
        pytest.param(timedelta(seconds=119), id="one-event-at-the-start"),
    ],
)
async def test_any_window_counts_held_events_up_to_the_threshold(
    automations_session: AsyncSession,
    trigger: EventTrigger,
    slot_start: datetime,
    threshold: int,
    window_offset: timedelta,
):
    """Sixty events are held in each of two slots. A window opened anywhere over
    them counts at least as many as it covers, up to the threshold."""
    occurrences = [slot_start + timedelta(seconds=i) for i in range(120)]
    await hold_all(automations_session, trigger, occurrences)

    start = slot_start + window_offset
    occurred_inside = sum(start <= o < start + WITHIN for o in occurrences)
    counted = await count_in_window(automations_session, trigger, start)
    assert min(counted, threshold) == min(occurred_inside, threshold)


@pytest.mark.parametrize(
    "lone_offset, crowd_offset",
    [
        pytest.param(timedelta(0), WITHIN, id="crowd-in-the-next-slot"),
        pytest.param(WITHIN, timedelta(0), id="crowd-in-the-previous-slot"),
    ],
)
async def test_holding_an_event_trims_only_its_own_slot(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    slot_start: datetime,
    lone_offset: timedelta,
    crowd_offset: timedelta,
):
    """An event alone in its slot stays, however many events are held in a
    neighboring slot after it."""
    lone = slot_start + lone_offset + timedelta(seconds=30)
    crowd = [
        slot_start + crowd_offset + timedelta(milliseconds=100 * i) for i in range(110)
    ]
    await hold_all(automations_session, trigger, [lone, *crowd])

    assert await held_occurrences(db, automations_session) == sorted(
        [lone, crowd[0], crowd[-1]]
    )


@pytest.mark.parametrize(
    "age, kept",
    [
        pytest.param(
            PRECEDING_EVENT_LOOKBACK + timedelta(seconds=90),
            True,
            id="between-one-and-two-lookbacks",
        ),
        pytest.param(
            2 * PRECEDING_EVENT_LOOKBACK + timedelta(seconds=90),
            False,
            id="older-than-two-lookbacks",
        ),
    ],
)
async def test_held_events_older_than_two_lookbacks_are_dropped(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    frozen_time: DateTime,
    age: timedelta,
    kept: bool,
):
    """An event that occurred more than two lookbacks before a newer one leaves the
    held set. One lookback is not enough to drop it, because a lost follower can
    still open a window over it."""
    newer = frozen_time + age
    await automation_held_events.hold_event(
        automations_session, trigger, KEY, walked(frozen_time)
    )
    await automation_held_events.hold_event(
        automations_session, trigger, KEY, walked(newer)
    )

    assert (frozen_time in await held_occurrences(db, automations_session)) is kept


@pytest.mark.parametrize(
    "swept_after, kept",
    [
        pytest.param(
            PRECEDING_EVENT_LOOKBACK + timedelta(seconds=1), True, id="one-lookback"
        ),
        pytest.param(
            2 * PRECEDING_EVENT_LOOKBACK + timedelta(seconds=1),
            False,
            id="two-lookbacks",
        ),
    ],
)
async def test_held_events_outlast_one_lookback(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    swept_after: timedelta,
    kept: bool,
):
    """Causal ordering holds a lost follower for up to the lookback before it is
    evaluated, so a held event lives past one lookback after it is held, and is
    swept on its own within two."""
    await automation_held_events.hold_event(
        automations_session, trigger, KEY, walked(now("UTC"))
    )
    await automations_session.commit()

    await triggers.periodic_evaluation(now("UTC") + swept_after)
    assert bool(await held_occurrences(db, automations_session)) is kept


@pytest.mark.parametrize(
    "bucketing_key, swept_after, kept",
    [
        pytest.param(KEY, timedelta(hours=1), True, id="its-bucket-is-open"),
        pytest.param(KEY, timedelta(hours=3), False, id="its-bucket-has-ended"),
        pytest.param(
            ("groundhog",), timedelta(hours=1), False, id="another-key-is-open"
        ),
    ],
)
async def test_held_events_outlast_the_retention_while_their_bucket_is_open(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    bucketing_key: tuple[str, ...],
    swept_after: timedelta,
    kept: bool,
):
    """A window that is open longer than the retention can still roll back over
    an event held for its key, so the sweep keeps that event until the window
    ends."""
    held_at = now("UTC")
    await automation_held_events.hold_event(
        automations_session, trigger, KEY, walked(held_at)
    )
    await triggers.ensure_bucket(
        automations_session,
        trigger,
        bucketing_key,
        start=held_at,
        end=held_at + timedelta(hours=2),
        last_event=None,
    )
    await automations_session.commit()

    await triggers.periodic_evaluation(held_at + swept_after)
    assert bool(await held_occurrences(db, automations_session)) is kept


LONG_WITHIN = timedelta(hours=1)


@pytest.mark.parametrize("within", [LONG_WITHIN])
@pytest.mark.parametrize("threshold", [2])
async def test_events_one_window_apart_are_both_kept_past_the_retention(
    automations_session: AsyncSession,
    trigger: EventTrigger,
    slot_start: datetime,
):
    """Two events occurred more than the retention apart but less than `within`
    apart, so one window can cover both. Both stay held, and a window that opens over
    them counts both."""
    first = slot_start + timedelta(minutes=1)
    await hold_all(
        automations_session,
        trigger,
        [first, first + HELD_EXPECT_EVENTS_RETENTION + WITHIN],
    )

    opened = await triggers.ensure_bucket(
        automations_session,
        trigger,
        KEY,
        start=first,
        end=first + LONG_WITHIN,
        last_event=None,
    )

    assert opened.count == 2


async def test_holding_events_newest_first_keeps_the_held_set_bounded(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    slot_start: datetime,
):
    """One event in each of 120 slots is held newest first, as a backfill would
    hold them. Only the events within the retention of the newest one stay."""
    occurrences = [slot_start + k * WITHIN + timedelta(seconds=30) for k in range(120)]
    await hold_all(automations_session, trigger, reversed(occurrences))

    within_the_retention = HELD_EXPECT_EVENTS_RETENTION // WITHIN + 1
    assert (
        await held_occurrences(db, automations_session)
        == occurrences[-within_the_retention:]
    )


async def test_event_is_held_whether_or_not_a_bucket_exists(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    frozen_time: DateTime,
):
    """With no bucket, the event is held and the caller gets nothing to count it in.
    With a bucket, the event is held too, and the caller gets the bucket to count
    the event in."""
    early = walked(frozen_time)
    assert (
        await triggers.hold_expect_event(automations_session, trigger, KEY, early)
        is None
    )

    opened = await triggers.ensure_bucket(
        automations_session,
        trigger,
        KEY,
        start=frozen_time,
        end=frozen_time + trigger.within,
        last_event=None,
    )
    later = frozen_time + timedelta(seconds=1)
    found = await triggers.hold_expect_event(
        automations_session, trigger, KEY, walked(later)
    )

    assert found is not None
    assert found.id == opened.id
    assert await held_occurrences(db, automations_session) == [frozen_time, later]


async def test_held_event_evaluated_again_gives_nothing_to_count(
    automations_session: AsyncSession,
    trigger: EventTrigger,
    frozen_time: DateTime,
):
    """A held event was already counted by the window that opened over it, so a
    second evaluation of it returns no bucket."""
    event = walked(frozen_time)
    await triggers.hold_expect_event(automations_session, trigger, KEY, event)
    await triggers.ensure_bucket(
        automations_session,
        trigger,
        KEY,
        start=frozen_time,
        end=frozen_time + trigger.within,
        last_event=None,
    )

    assert (
        await triggers.hold_expect_event(automations_session, trigger, KEY, event)
        is None
    )
