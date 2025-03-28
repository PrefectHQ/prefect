import datetime
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events import actions
from prefect.server.events.models.automations import create_automation
from prefect.server.events.models.composite_trigger_child_firing import (
    clear_child_firings,
    clear_old_child_firings,
    get_child_firings,
    upsert_child_firing,
)
from prefect.server.events.schemas.automations import (
    Automation,
    CompoundTrigger,
    EventTrigger,
    Firing,
    Posture,
    TriggerState,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.triggers import load_automation
from prefect.types import DateTime


@pytest.fixture
async def raise_the_alarm(automations_session: AsyncSession) -> Automation:
    automation = await create_automation(
        session=automations_session,
        automation=Automation(
            name="Raise the Alarm",
            trigger=CompoundTrigger(
                triggers=[
                    EventTrigger(
                        expect={"dragon.seen"},
                        match={
                            "color": "red",
                        },
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                    EventTrigger(
                        expect={"dragon.seen"},
                        match={
                            "color": "green",
                        },
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                ],
                require="all",
                within=timedelta(seconds=10),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    load_automation(automation)
    await automations_session.commit()
    return automation


@pytest.fixture
def saw_a_red_and_green_dragon(
    raise_the_alarm: Automation,
) -> CompoundTrigger:
    assert isinstance(raise_the_alarm.trigger, CompoundTrigger)
    return raise_the_alarm.trigger


@pytest.fixture
def saw_a_red_dragon(
    saw_a_red_and_green_dragon: CompoundTrigger,
) -> EventTrigger:
    return saw_a_red_and_green_dragon.triggers[0]


@pytest.fixture
def saw_a_green_dragon(
    saw_a_red_and_green_dragon: CompoundTrigger,
) -> EventTrigger:
    return saw_a_red_and_green_dragon.triggers[1]


@pytest.fixture
def baby_red_dragon_passed_by(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=1),
        event="dragon.seen",
        resource={
            "age": "whelp",
            "color": "red",
            "prefect.resource.id": "red-dragon-id",
        },
        id=uuid4(),
    )


@pytest.fixture
def old_red_dragon_passed_by(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=1),
        event="dragon.seen",
        resource={
            "age": "old",
            "color": "red",
            "prefect.resource.id": "red-dragon-id",
        },
        id=uuid4(),
    )


@pytest.fixture
def green_dragon_passed_by(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=1),
        event="dragon.seen",
        resource={
            "color": "green",
            "prefect.resource.id": "green-dragon-id",
        },
        id=uuid4(),
    )


async def test_insert_compound_trigger_child_firing(
    automations_session: AsyncSession,
    raise_the_alarm: Automation,
    saw_a_red_and_green_dragon: CompoundTrigger,
    saw_a_red_dragon: EventTrigger,
    baby_red_dragon_passed_by: ReceivedEvent,
    frozen_time: DateTime,
):
    firing = Firing(
        trigger=saw_a_red_dragon,
        trigger_states={TriggerState.Triggered},
        triggered=frozen_time + datetime.timedelta(seconds=1),
        triggering_labels={},
        triggering_event=baby_red_dragon_passed_by,
    )
    res = await upsert_child_firing(
        session=automations_session,
        firing=firing,
    )

    assert res and res.id
    assert res.automation_id == raise_the_alarm.id
    assert res.parent_trigger_id == saw_a_red_and_green_dragon.id
    assert res.child_trigger_id == saw_a_red_dragon.id
    assert res.child_firing_id == firing.id
    assert res.child_fired_at == firing.triggered

    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 1
    assert child_firings[0].id == res.id
    assert child_firings[0].child_firing_id == firing.id


async def test_upsert_compound_trigger_child_firing(
    automations_session: AsyncSession,
    raise_the_alarm: Automation,
    saw_a_red_and_green_dragon: CompoundTrigger,
    saw_a_red_dragon: EventTrigger,
    baby_red_dragon_passed_by: ReceivedEvent,
    old_red_dragon_passed_by: ReceivedEvent,
    frozen_time: DateTime,
):
    await upsert_child_firing(
        session=automations_session,
        firing=Firing(
            trigger=saw_a_red_dragon,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,
            triggering_labels={},
            triggering_event=baby_red_dragon_passed_by,
        ),
    )

    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 1
    assert (
        child_firings[0].child_firing.triggering_event.id
        == baby_red_dragon_passed_by.id
    )

    await upsert_child_firing(
        session=automations_session,
        firing=Firing(
            trigger=saw_a_red_dragon,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,
            triggering_labels={},
            triggering_event=old_red_dragon_passed_by,
        ),
    )
    automations_session.expunge_all()

    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 1
    assert (
        child_firings[0].child_firing.triggering_event.id == old_red_dragon_passed_by.id
    )


async def test_get_child_firings(
    automations_session: AsyncSession,
    raise_the_alarm: Automation,
    saw_a_red_and_green_dragon: CompoundTrigger,
    saw_a_red_dragon: EventTrigger,
    saw_a_green_dragon: EventTrigger,
    baby_red_dragon_passed_by: ReceivedEvent,
    old_red_dragon_passed_by: ReceivedEvent,
    green_dragon_passed_by: ReceivedEvent,
    frozen_time: DateTime,
):
    # saw a red dragon
    await upsert_child_firing(
        session=automations_session,
        firing=Firing(
            trigger=saw_a_red_dragon,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,
            triggering_labels={},
            triggering_event=baby_red_dragon_passed_by,
        ),
    )
    # saw a green dragon
    await upsert_child_firing(
        session=automations_session,
        firing=Firing(
            trigger=saw_a_green_dragon,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,
            triggering_labels={},
            triggering_event=green_dragon_passed_by,
        ),
    )
    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 2
    event_ids = {cf.child_firing.triggering_event.id for cf in child_firings}
    assert baby_red_dragon_passed_by.id in event_ids
    assert green_dragon_passed_by.id in event_ids


async def test_clear_child_firings(
    automations_session: AsyncSession,
    raise_the_alarm: Automation,
    saw_a_red_and_green_dragon: CompoundTrigger,
    saw_a_red_dragon: EventTrigger,
    baby_red_dragon_passed_by: ReceivedEvent,
    frozen_time: DateTime,
):
    firing = Firing(
        trigger=saw_a_red_dragon,
        trigger_states={TriggerState.Triggered},
        triggered=frozen_time,
        triggering_labels={},
        triggering_event=baby_red_dragon_passed_by,
    )
    await upsert_child_firing(session=automations_session, firing=firing)
    # passing a random firing id, should not delete anything
    await clear_child_firings(
        session=automations_session,
        trigger=saw_a_red_and_green_dragon,
        firing_ids={uuid4()},
    )
    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 1
    # passing a specific firing id, should delete
    await clear_child_firings(
        session=automations_session,
        trigger=saw_a_red_and_green_dragon,
        firing_ids={firing.id},
    )
    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 0


async def test_clear_old_child_firings(
    automations_session: AsyncSession,
    saw_a_red_and_green_dragon: CompoundTrigger,
    saw_a_red_dragon: EventTrigger,
    baby_red_dragon_passed_by: ReceivedEvent,
    frozen_time: DateTime,
):
    # old, should be cleared
    await upsert_child_firing(
        session=automations_session,
        firing=Firing(
            trigger=saw_a_red_dragon,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time - timedelta(hours=1),
            triggering_labels={},
            triggering_event=baby_red_dragon_passed_by,
        ),
    )
    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 1

    await clear_old_child_firings(
        session=automations_session,
        trigger=saw_a_red_and_green_dragon,
        fired_before=frozen_time - timedelta(minutes=20),
    )

    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 0

    # new, only 5 minutes old
    await upsert_child_firing(
        session=automations_session,
        firing=Firing(
            trigger=saw_a_red_dragon,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time - timedelta(minutes=5),
            triggering_labels={},
            triggering_event=baby_red_dragon_passed_by,
        ),
    )
    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 1

    await clear_old_child_firings(
        session=automations_session,
        trigger=saw_a_red_and_green_dragon,
        fired_before=frozen_time - timedelta(minutes=20),
    )

    child_firings = await get_child_firings(
        session=automations_session, trigger=saw_a_red_and_green_dragon
    )
    assert len(child_firings) == 1
