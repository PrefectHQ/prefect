"""Held `expect` events stay bounded in count and lifetime, whatever the volume."""

from datetime import timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface
from prefect.server.events import actions, triggers
from prefect.server.events.models import automation_held_events
from prefect.server.events.models.automation_held_events import (
    HELD_EXPECT_EVENTS_LIMIT,
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


@pytest.fixture
async def trigger(automations_session: AsyncSession) -> EventTrigger:
    automation = await create_automation(
        automations_session,
        Automation(
            name="held events test",
            trigger=EventTrigger(
                after={"animal.woke"},
                expect={"animal.walked"},
                for_each={"prefect.resource.id"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(seconds=60),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    assert isinstance(automation.trigger, EventTrigger)
    return automation.trigger


def walked(occurred: DateTime) -> ReceivedEvent:
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


async def test_held_events_keep_only_the_newest_up_to_the_limit(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    frozen_time: DateTime,
):
    """A key that takes more events than the limit keeps only the newest ones."""
    for i in range(HELD_EXPECT_EVENTS_LIMIT + 10):
        await automation_held_events.hold_event(
            automations_session,
            trigger,
            KEY,
            walked(frozen_time + timedelta(seconds=i)),
        )

    occurrences = await held_occurrences(db, automations_session)
    assert len(occurrences) == HELD_EXPECT_EVENTS_LIMIT
    assert occurrences[0] == frozen_time + timedelta(seconds=10)


async def test_held_events_older_than_the_lookback_are_dropped(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
    frozen_time: DateTime,
):
    """An event that occurred more than the lookback before the newest one leaves
    the held events."""
    newer = frozen_time + PRECEDING_EVENT_LOOKBACK + timedelta(seconds=1)
    await automation_held_events.hold_event(
        automations_session, trigger, KEY, walked(frozen_time)
    )
    await automation_held_events.hold_event(
        automations_session, trigger, KEY, walked(newer)
    )

    assert await held_occurrences(db, automations_session) == [newer]


async def test_held_events_are_swept_after_the_lookback(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    trigger: EventTrigger,
):
    """Held events leave on their own, without another event for their key."""
    await automation_held_events.hold_event(
        automations_session, trigger, KEY, walked(now("UTC"))
    )
    await automations_session.commit()

    await triggers.periodic_evaluation(now("UTC"))
    assert await held_occurrences(db, automations_session) != []

    await triggers.periodic_evaluation(
        now("UTC") + PRECEDING_EVENT_LOOKBACK + timedelta(seconds=1)
    )
    assert await held_occurrences(db, automations_session) == []


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
    """A held event was already counted by the bucket that opened over it, so a
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
