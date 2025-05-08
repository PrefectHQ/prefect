from datetime import timedelta
from typing import Callable, List, Optional, Union
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events import actions, triggers
from prefect.server.events.models import automations
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Firing,
    Posture,
    TriggerState,
)
from prefect.server.events.schemas.events import (
    ReceivedEvent,
    ResourceSpecification,
    matches,
)
from prefect.settings import PREFECT_EVENTS_EXPIRED_BUCKET_BUFFER
from prefect.types import DateTime


def test_triggers_have_identifiers(arachnophobia: Automation):
    assert arachnophobia.id
    assert arachnophobia.trigger.id
    assert arachnophobia.trigger.id != arachnophobia.id

    new_copy = EventTrigger.model_validate(
        arachnophobia.trigger.model_dump(exclude={"id"})
    )
    assert new_copy.id != arachnophobia.trigger.id


@pytest.fixture
def arachnophobia_trigger(arachnophobia: Automation) -> EventTrigger:
    assert isinstance(arachnophobia.trigger, EventTrigger)
    return arachnophobia.trigger


def test_trigger_covers(
    arachnophobia_trigger: EventTrigger,
    daddy_long_legs_walked: ReceivedEvent,
):
    assert arachnophobia_trigger.covers(daddy_long_legs_walked)


def test_trigger_does_not_cover(
    arachnophobia_trigger: EventTrigger,
    woodchonk_walked: ReceivedEvent,
):
    assert not arachnophobia_trigger.covers(woodchonk_walked)


@pytest.fixture
def my_poor_lilies_trigger(my_poor_lilies: Automation) -> EventTrigger:
    assert isinstance(my_poor_lilies.trigger, EventTrigger)
    return my_poor_lilies.trigger


def test_trigger_covers_related_resource(
    my_poor_lilies_trigger: EventTrigger,
    woodchonk_nibbled: ReceivedEvent,
):
    assert my_poor_lilies_trigger.covers(woodchonk_nibbled)


def test_trigger_does_not_cover_related(
    my_poor_lilies_trigger: EventTrigger,
    woodchonk_walked: ReceivedEvent,
):
    assert not my_poor_lilies_trigger.covers(woodchonk_walked)


def test_triggers_are_wired_to_their_root_automations_and_parents(
    arachnophobia: Automation,
):
    assert arachnophobia.trigger.automation is arachnophobia
    assert arachnophobia.trigger.parent is arachnophobia


def test_trigger_covers_multiple_related_resources_positive(
    my_poor_lilies_trigger: EventTrigger,
    woodchonk_nibbled: ReceivedEvent,
):
    # only trigger if that pesky 'chonk ate both my lilies AND my tulips
    my_poor_lilies_trigger.match_related = [
        ResourceSpecification(
            {
                "prefect.resource.role": "meal",
                "genus": "Hemerocallis",
            }
        ),
        ResourceSpecification(
            {
                "prefect.resource.role": "meal",
                "genus": "Tulipa",
            }
        ),
    ]
    assert my_poor_lilies_trigger.covers(woodchonk_nibbled)


def test_trigger_covers_multiple_related_resources_negative(
    my_poor_lilies_trigger: EventTrigger,
    woodchonk_nibbled: ReceivedEvent,
):
    # only trigger if that pesky 'chonk ate both my lilies AND my daffodils
    my_poor_lilies_trigger.match_related = [
        ResourceSpecification(
            {
                "prefect.resource.role": "meal",
                "genus": "Hemerocallis",
            }
        ),
        ResourceSpecification(
            {
                "prefect.resource.role": "meal",
                "genus": "Narcissus",
            }
        ),
    ]
    # Nope, the 'chonk only ate my lilies and my tulips, not my daffodils
    assert not my_poor_lilies_trigger.covers(woodchonk_nibbled)


@pytest.fixture
def animal_lover_trigger(animal_lover: Automation) -> EventTrigger:
    assert isinstance(animal_lover.trigger, EventTrigger)
    return animal_lover.trigger


def test_no_expects_means_all_events(
    animal_lover_trigger: EventTrigger,
    daddy_long_legs_walked: ReceivedEvent,
    woodchonk_nibbled: ReceivedEvent,
):
    assert animal_lover_trigger.covers(daddy_long_legs_walked)
    assert animal_lover_trigger.covers(woodchonk_nibbled)


@pytest.mark.parametrize(
    "expected, value",
    [
        ("*", "any.old.thing"),
        ("any.old.*", "any.old.thing"),
        ("any.old.*", "any.old.stuff"),
        ("exactamundo", "exactamundo"),
    ],
)
def test_matches(expected: str, value: Optional[str]):
    assert matches(expected, value)


@pytest.mark.parametrize(
    "expected, value",
    [
        ("*", None),
        ("any.old.*", "any.other.stuff"),
        ("any.old.*", "any.old"),
        ("exactamundo", "positively not"),
    ],
)
def test_does_not_match(expected: str, value: Optional[str]):
    assert not matches(expected, value)


@pytest.fixture
async def effective_automations(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
    arachnophobia: Automation,
    chonk_lonely: Automation,
    chonk_party: Automation,
    chonk_sadness: Automation,
):
    for automation in [arachnophobia, chonk_party, chonk_sadness, chonk_lonely]:
        persisted = await automations.create_automation(automations_session, automation)
        automation.created = persisted.created
        automation.updated = persisted.updated
        triggers.load_automation(persisted)
    await automations_session.commit()
    return [arachnophobia, chonk_lonely, chonk_party, chonk_sadness]


async def test_reactive_automation_triggers_can_trigger_immediately(
    effective_automations,
    arachnophobia: Automation,
    daddy_long_legs_walked: ReceivedEvent,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    await triggers.reactive_evaluation(daddy_long_legs_walked)
    assert_acted_with(
        Firing(
            trigger=arachnophobia.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={},
            triggering_event=daddy_long_legs_walked,
        ),
    )

    act.reset_mock()

    # The minimum window is 10 seconds, so advance to just after that
    daddy_long_legs_walked.occurred += timedelta(seconds=10, microseconds=1)

    await triggers.reactive_evaluation(daddy_long_legs_walked)
    assert_acted_with(
        Firing(
            trigger=arachnophobia.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={},
            triggering_event=daddy_long_legs_walked,
        ),
    )


async def test_reactive_automation_triggers_only_on_expected_events(
    effective_automations,
    arachnophobia: Automation,
    daddy_long_legs_walked: ReceivedEvent,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/2776, where
    we were triggering actions for events that didn't actually match the expect"""

    # this is not the event we're expecting
    daddy_long_legs_walked.event = "animal.snoozed"

    await triggers.reactive_evaluation(daddy_long_legs_walked)

    act.assert_not_awaited()

    act.reset_mock()

    # this is the event we're expecting
    daddy_long_legs_walked.event = "animal.walked"

    await triggers.reactive_evaluation(daddy_long_legs_walked)
    assert_acted_with(
        Firing(
            trigger=arachnophobia.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={},
            triggering_event=daddy_long_legs_walked,
        ),
    )


async def test_reactive_automation_triggers_as_soon_as_it_can(
    effective_automations,
    chonk_party: Automation,
    woodchonk_walked: ReceivedEvent,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()

    woodchonk_walked.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()

    # it fires here because the threshold of > 2 has been met

    woodchonk_walked.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_walked)
    assert_acted_with(
        Firing(
            trigger=chonk_party.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={},
            triggering_event=woodchonk_walked,
        ),
    )
    act.reset_mock()

    # it will not fire again while we're in the original window

    woodchonk_walked.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()

    woodchonk_walked.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()

    # if we jump ahead to a new time window, it will fire again after three events

    woodchonk_walked.occurred += timedelta(seconds=20)
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()

    woodchonk_walked.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()

    woodchonk_walked.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_walked)
    assert_acted_with(
        Firing(
            trigger=chonk_party.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={},
            triggering_event=woodchonk_walked,
        ),
    )


async def test_reactive_automation_does_not_trigger_if_threshold_not_met(
    effective_automations,
    woodchonk_walked: ReceivedEvent,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
):
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()

    woodchonk_walked.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()

    # 20 seconds later is not within the automation period, so this won't fire

    woodchonk_walked.occurred += timedelta(seconds=20)
    await triggers.reactive_evaluation(woodchonk_walked)
    act.assert_not_awaited()


async def test_reactive_automation_triggers_immediately_even_if_event_matches_after(
    effective_automations,
    woodchonk_table_for_one: ReceivedEvent,
    chonk_lonely: Automation,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/3091"""

    # First, we need an event that trivially matches the "after" criteria
    trivial_after_match_event = woodchonk_table_for_one.model_copy(
        update={"event": "animal.eat"}
    )

    assert isinstance(chonk_lonely.trigger, EventTrigger)
    assert not chonk_lonely.trigger.after, "Automation has non-trivial after criteria"
    assert not chonk_lonely.trigger.expects(trivial_after_match_event.event)

    # Next, we receive this trivial "after" match
    await triggers.reactive_evaluation(trivial_after_match_event)
    act.assert_not_awaited()

    # Sometime after this trivial match, which exceeds 'within',
    # actually receive expected events. We should trigger after seeing 3 of them.
    woodchonk_table_for_one.occurred += timedelta(seconds=500)
    await triggers.reactive_evaluation(woodchonk_table_for_one)
    assert_acted_with(
        Firing(
            trigger=chonk_lonely.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={},
            triggering_event=woodchonk_table_for_one,
        ),
    )


async def test_reactive_automation_triggers_for_each_related_label(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
    woodchonk_nibbled: ReceivedEvent,
    woodchonk_gobbled: ReceivedEvent,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    """Test that we can create an automation that is tracked separate for each value
    of a related resource's labels."""

    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Let me know when I've lost 3 of any flower species",
            trigger=EventTrigger(
                expect={"animal.ingested"},
                for_each={"related:meal:genus", "related:meal:species"},
                posture=Posture.Reactive,
                threshold=3,
                within=timedelta(minutes=10),
            ),
            actions=[actions.DoNothing()],
            enabled=True,
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()

    woodchonk_nibbled.id = uuid4()
    woodchonk_nibbled.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_nibbled)
    act.assert_not_awaited()

    woodchonk_nibbled.id = uuid4()
    woodchonk_nibbled.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_nibbled)
    act.assert_not_awaited()

    woodchonk_gobbled.id = uuid4()
    woodchonk_gobbled.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_gobbled)
    act.assert_not_awaited()

    woodchonk_nibbled.id = uuid4()
    woodchonk_nibbled.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_nibbled)
    assert_acted_with(
        Firing(
            trigger=automation.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={
                "related:meal:genus": "Hemerocallis",
                "related:meal:species": "fulva",
            },
            triggering_event=woodchonk_nibbled,
        ),
    )
    act.reset_mock()

    woodchonk_gobbled.id = uuid4()
    woodchonk_gobbled.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_gobbled)
    act.assert_not_awaited()

    woodchonk_gobbled.id = uuid4()
    woodchonk_gobbled.occurred += timedelta(seconds=1)
    await triggers.reactive_evaluation(woodchonk_gobbled)
    assert_acted_with(
        Firing(
            trigger=automation.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={
                "related:meal:genus": "Dicentra",
                "related:meal:species": "cucullaria",
            },
            triggering_event=woodchonk_gobbled,
        ),
    )


async def test_proactive_trigger_fires_after_time_expires(
    effective_automations: List[Automation],
    chonk_sadness: Automation,
    start_of_test: DateTime,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    async def run_proactive_evaluation(automations: List[Automation], as_of: DateTime):
        for automation in automations:
            trigger = automation.trigger
            assert isinstance(trigger, EventTrigger), repr(trigger)
            await triggers.proactive_evaluation(trigger, as_of)

    await run_proactive_evaluation(effective_automations, start_of_test)
    act.assert_not_awaited()

    await run_proactive_evaluation(
        effective_automations, start_of_test + timedelta(seconds=9)
    )
    act.assert_not_awaited()

    await run_proactive_evaluation(
        effective_automations,
        start_of_test + timedelta(seconds=10),
    )
    act.assert_not_awaited()

    await run_proactive_evaluation(
        effective_automations,
        start_of_test + timedelta(seconds=30),
    )
    assert_acted_with(
        Firing(
            trigger=chonk_sadness.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={},
        ),
    )
    act.reset_mock()

    # The period should start over after 30 seconds

    await run_proactive_evaluation(
        effective_automations,
        start_of_test + timedelta(seconds=31),
    )
    act.assert_not_awaited()

    await run_proactive_evaluation(
        effective_automations,
        start_of_test + timedelta(seconds=60),
    )
    assert_acted_with(
        Firing(
            trigger=chonk_sadness.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={},
        ),
    )


async def test_reactive_triggers_clean_up_after_themselves_if_they_do_fire(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
    start_of_test: DateTime,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/2935, where
    expired buckets were left in the DB by Reactive automations"""

    # This automation was taken verbatim from an automation in staging that exhibited
    # the behavior, with only the flow ID changed
    automation = await automations.create_automation(
        automations_session,
        Automation(
            id=uuid4(),
            name="Repro for #2935",
            trigger=EventTrigger(
                after=[],
                match={"prefect.resource.id": "prefect.flow-run.*"},
                expect=["prefect.flow-run.Failed"],
                within=10.0,
                posture="Reactive",
                for_each=["prefect.resource.id"],
                threshold=1,
                match_related={
                    "prefect.resource.id": ["prefect.flow.ffffffff"],
                    "prefect.resource.role": "flow",
                },
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()

    trigger = automation.trigger
    assert isinstance(trigger, EventTrigger), repr(trigger)

    now = start_of_test

    # A Running event is not relevant to this Automation and should not cause a bucket
    # to be created
    running_event = ReceivedEvent(
        occurred=now,
        event="prefect.flow-run.Running",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        related=[
            {
                "prefect.resource.id": "prefect.flow.ffffffff",
                "prefect.resource.role": "flow",
            }
        ],
        received=now,
        id=uuid4(),
    )

    # Previously any event was 'covered' if the automation
    # trigger did not contain `after` criteria
    assert not trigger.after

    await triggers.reactive_evaluation(running_event)
    act.assert_not_awaited()

    # There should be no bucket, because this event was irrelevant
    bucketing_key = trigger.bucketing_key(running_event)
    bucket = await triggers.read_bucket(automations_session, trigger, bucketing_key)
    assert not bucket

    now += timedelta(seconds=1)

    # The failed event _is_ relevant and should cause this automation to fire
    failed_event = ReceivedEvent(
        occurred=now,
        event="prefect.flow-run.Failed",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        related=[
            {
                "prefect.resource.id": "prefect.flow.ffffffff",
                "prefect.resource.role": "flow",
            }
        ],
        received=now,
        id=uuid4(),
    )
    assert trigger.covers(failed_event)

    await triggers.reactive_evaluation(failed_event)
    act.assert_awaited_once()

    # There is a bucket, because this event caused an immediate trigger, and thus
    # scheduled the next bucket into the future
    assert trigger.bucketing_key(failed_event) == bucketing_key
    bucket = await triggers.read_bucket(automations_session, trigger, bucketing_key)
    assert bucket
    assert bucket.start == now + timedelta(seconds=10)
    assert bucket.end == bucket.start + timedelta(seconds=10)

    # Now run proactive evaluation to sweep any buckets that have ended

    # When we're just at the `end` of the bucket, that's too early, so the bucket should
    # still be there
    await triggers.reset_events_clock()
    now += timedelta(seconds=10) + timedelta(seconds=10)  # the start  # the end
    await triggers.periodic_evaluation(now)
    bucket = await triggers.read_bucket(automations_session, trigger, bucketing_key)
    assert bucket

    # Only when we're past the bucket's `end` by a short buffer can we remove it, this
    # avoids contention with other in-flight changes to buckets
    await triggers.reset_events_clock()
    now += PREFECT_EVENTS_EXPIRED_BUCKET_BUFFER.value() + timedelta(seconds=1)
    await triggers.periodic_evaluation(now)
    bucket = await triggers.read_bucket(automations_session, trigger, bucketing_key)
    assert not bucket


async def test_follower_messages_are_processed_when_leaders_arrive(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
    start_of_test: DateTime,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    automation = await automations.create_automation(
        automations_session,
        Automation(
            id=uuid4(),
            name="Testing out-of-order events",
            trigger=EventTrigger(
                after=[],
                match={"prefect.resource.id": "prefect.flow-run.*"},
                expect=["prefect.flow-run.Failed"],
                within=10.0,
                posture="Reactive",
                for_each=["prefect.resource.id"],
                threshold=1,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()

    pending = ReceivedEvent(
        occurred=start_of_test,
        event="prefect.flow-run.Pending",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=start_of_test + timedelta(seconds=2),
        id=uuid4(),
    )

    running = ReceivedEvent(
        occurred=start_of_test + timedelta(minutes=1),
        event="prefect.flow-run.Running",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=start_of_test + timedelta(minutes=1, seconds=2),
        id=uuid4(),
        follows=pending.id,
    )

    failed = ReceivedEvent(
        occurred=start_of_test + timedelta(minutes=3),
        event="prefect.flow-run.Failed",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=start_of_test + timedelta(minutes=2, seconds=3),
        id=uuid4(),
        follows=running.id,
    )

    await triggers.reactive_evaluation(pending)
    # the Pending event is irrelevant
    act.assert_not_awaited()

    with pytest.raises(triggers.EventArrivedEarly):
        await triggers.reactive_evaluation(failed)
    # Failed is the event we want, but it's too early so we shouldn't have acted yet
    act.assert_not_awaited()

    await triggers.reactive_evaluation(running)
    assert_acted_with(
        Firing(
            trigger=automation.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            triggering_event=failed,  # we reacted due to the Failed event, not Running
        ),
    )


async def test_old_follower_messages_are_processed_immediately(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
    start_of_test: DateTime,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    automation = await automations.create_automation(
        automations_session,
        Automation(
            id=uuid4(),
            name="Testing out-of-order events",
            trigger=EventTrigger(
                after=[],
                match={"prefect.resource.id": "prefect.flow-run.*"},
                expect=["prefect.flow-run.Failed"],
                within=10.0,
                posture="Reactive",
                for_each=["prefect.resource.id"],
                threshold=1,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()

    base_date = start_of_test - timedelta(hours=1)

    pending = ReceivedEvent(
        occurred=base_date,
        event="prefect.flow-run.Pending",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=base_date + timedelta(seconds=1),
        id=uuid4(),
    )

    running = ReceivedEvent(
        occurred=base_date + timedelta(minutes=1),
        event="prefect.flow-run.Running",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=base_date + timedelta(minutes=1, seconds=2),
        id=uuid4(),
        follows=pending.id,
    )

    failed = ReceivedEvent(
        occurred=base_date + timedelta(minutes=3),
        event="prefect.flow-run.Failed",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=base_date + timedelta(minutes=2, seconds=3),
        id=uuid4(),
        follows=running.id,
    )

    await triggers.reactive_evaluation(pending)
    # the Pending event is irrelevant
    act.assert_not_awaited()

    await triggers.reactive_evaluation(failed)
    # Failed is the event we want, and the message is so late that we'll just need to
    # process it out of order
    assert_acted_with(
        Firing(
            trigger=automation.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            triggering_event=failed,
        ),
    )

    await triggers.reactive_evaluation(running)


async def test_lost_followers_are_processed_during_proactive_evaluation(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
    start_of_test: DateTime,
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
):
    automation = await automations.create_automation(
        automations_session,
        Automation(
            id=uuid4(),
            name="Testing out-of-order events",
            trigger=EventTrigger(
                after=[],
                match={"prefect.resource.id": "prefect.flow-run.*"},
                expect=["prefect.flow-run.Failed"],
                within=10.0,
                posture="Reactive",
                for_each=["prefect.resource.id"],
                threshold=1,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()

    base_date = start_of_test - timedelta(minutes=15)

    # this event will never be seen by the triggers system
    bogus = ReceivedEvent(
        occurred=base_date,
        event="nope",
        resource={"prefect.resource.id": "never"},
        received=base_date,
        id=uuid4(),
    )

    pending = ReceivedEvent(
        occurred=base_date,
        event="prefect.flow-run.Pending",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=base_date + timedelta(seconds=1),
        id=uuid4(),
    )

    # have both of these events follow something that is never coming
    running = ReceivedEvent(
        occurred=base_date + timedelta(minutes=1),
        event="prefect.flow-run.Running",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=base_date + timedelta(minutes=1, seconds=2),
        id=uuid4(),
        follows=bogus.id,
    )

    failed = ReceivedEvent(
        occurred=base_date + timedelta(minutes=3),
        event="prefect.flow-run.Failed",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        received=base_date + timedelta(minutes=2, seconds=3),
        id=uuid4(),
        follows=bogus.id,
    )

    await triggers.reactive_evaluation(pending)
    # the Pending event is irrelevant
    act.assert_not_awaited()

    with pytest.raises(triggers.EventArrivedEarly):
        await triggers.reactive_evaluation(failed)
    # Failed is the event we want, but it's too early so we shouldn't have acted yet
    act.assert_not_awaited()

    with pytest.raises(triggers.EventArrivedEarly):
        await triggers.reactive_evaluation(running)
    # The Running event is also early and this Running event is _not_ the leader here,
    # so nothing should have fired
    act.assert_not_awaited()

    # A proactive evaluation happening before the timeout should not process these
    # events
    with mock.patch(
        "prefect.server.events.triggers.prefect.types._datetime.now"
    ) as the_future:
        the_future.return_value = base_date + timedelta(minutes=10)
        await triggers.periodic_evaluation(base_date + timedelta(minutes=10))

    act.assert_not_awaited()

    # Only after a later proactive evaluation are these processed; use a mock for
    # DateTime.now because the age calculation for the TTLCache of recently seen events
    # is based on the current wall-clock time
    with mock.patch(
        "prefect.server.events.triggers.prefect.types._datetime.now"
    ) as the_future:
        the_future.return_value = base_date + timedelta(minutes=20)
        await triggers.periodic_evaluation(base_date + timedelta(minutes=20))

    assert_acted_with(
        Firing(
            trigger=automation.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=the_future.return_value,
            triggering_labels={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            triggering_event=failed,
        ),
    )
