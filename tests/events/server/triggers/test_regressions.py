import asyncio
import random
from datetime import timedelta
from typing import Callable, List, Union
from unittest import mock
from uuid import UUID, uuid4

import pendulum
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
from prefect.server.events.schemas.events import Event, ReceivedEvent
from prefect.server.models import work_queues
from prefect.server.schemas.actions import WorkQueueCreate
from prefect.server.schemas.core import WorkQueue


@pytest.fixture
def act(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    mock_act = mock.AsyncMock()
    monkeypatch.setattr("prefect.server.events.triggers.act", mock_act)
    return mock_act


@pytest.fixture
async def work_queue(
    session: AsyncSession,
) -> WorkQueue:
    work_queue = await work_queues.create_work_queue(
        session=session,
        work_queue=WorkQueueCreate(name="my-work-queue"),
    )
    await session.commit()
    return work_queue


@pytest.fixture
async def unhealthy_work_queue_automation(
    work_queue: WorkQueue,
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    # Automation for issue 8871: https://github.com/PrefectHQ/prefect/issues/8871
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Alert about unhealthy work queues",
            description="Any work queues that are unhealthy for more than 2 hours",
            trigger=EventTrigger(
                match={
                    "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                },
                for_each={"prefect.resource.id"},
                after={"prefect.work-queue.unhealthy"},
                expect={"prefect.work-queue.healthy"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(minutes=119),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return automation


@pytest.fixture
def work_queue_health_unhealthy(
    work_queue: WorkQueue,
    frozen_time: pendulum.DateTime,
) -> List[ReceivedEvent]:
    events = [
        Event(
            occurred=frozen_time,
            event="prefect.work-queue.unhealthy",
            resource={"prefect.resource.id": f"prefect.work-queue.{work_queue.id}"},
            related=[],
            payload={},
            id=uuid4(),
        )
    ]

    return [event.receive() for event in events]


@pytest.fixture
def work_queue_health_healthy(
    work_queue: WorkQueue,
    frozen_time: pendulum.DateTime,
) -> List[ReceivedEvent]:
    events = (
        Event(
            occurred=frozen_time,
            event="prefect.work-queue.unhealthy",
            resource={"prefect.resource.id": f"prefect.work-queue.{work_queue.id}"},
            related=[],
            payload={},
            id=uuid4(),
        ),
        Event(
            occurred=frozen_time + timedelta(minutes=20),
            event="prefect.work-queue.healthy",
            resource={"prefect.resource.id": f"prefect.work-queue.{work_queue.id}"},
            related=[],
            payload={},
            id=uuid4(),
        ),
    )

    return [event.receive() for event in events]


async def test_alerts_work_queue_unhealthy(
    unhealthy_work_queue_automation: Automation,
    work_queue,
    work_queue_health_unhealthy: List[ReceivedEvent],
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: pendulum.DateTime,
):
    assert isinstance(unhealthy_work_queue_automation.trigger, EventTrigger)

    for event in work_queue_health_unhealthy:
        await triggers.reactive_evaluation(event)

    await triggers.proactive_evaluation(
        unhealthy_work_queue_automation.trigger,
        frozen_time + timedelta(minutes=21),
    )

    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        unhealthy_work_queue_automation.trigger,
        frozen_time + timedelta(hours=2),
    )

    assert_acted_with(
        Firing(
            trigger=unhealthy_work_queue_automation.trigger,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}"
            },
            triggering_event=work_queue_health_unhealthy[-1],
        ),
    )


async def test_does_not_alert_work_queue_went_healthy(
    unhealthy_work_queue_automation: Automation,
    work_queue_health_healthy: List[ReceivedEvent],
    act: mock.AsyncMock,
    frozen_time: pendulum.DateTime,
):
    assert isinstance(unhealthy_work_queue_automation.trigger, EventTrigger)

    for event in work_queue_health_healthy:
        await triggers.reactive_evaluation(event)

    await triggers.proactive_evaluation(
        unhealthy_work_queue_automation.trigger,
        frozen_time + timedelta(minutes=21),
    )

    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        unhealthy_work_queue_automation.trigger,
        frozen_time + timedelta(hours=2),
    )

    act.assert_not_awaited()


@pytest.fixture
async def reactive_immediate_expect_and_after(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    # Automation for https://github.com/PrefectHQ/nebula/issues/4201
    # If we set `within` to 0, we can never react, because we'll never be "after" an
    # event that we're also expecting
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Both expect and after",
            trigger=EventTrigger(
                after={"some-event"},
                expect={"some-event"},
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=0),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return automation


async def test_same_event_in_expect_and_after_never_reacts_immediately(
    act: mock.AsyncMock,
    frozen_time: pendulum.DateTime,
    reactive_immediate_expect_and_after: Automation,
):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/4201, where
    having the same event in after and expect causes weird behavior

    Case one: Reactive, within = 0 (immediately fires on all events) -> this will never
    fire because there's no time for an event to come after itself like this
    """
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time,
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_not_awaited()

    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=1),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_not_awaited()

    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=2),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_not_awaited()

    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=3),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_not_awaited()


@pytest.fixture
async def reactive_extended_expect_and_after(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    # Automation for https://github.com/PrefectHQ/nebula/issues/4201
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Both expect and after",
            trigger=EventTrigger(
                after={"some-event"},
                expect={"some-event"},
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=5),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return automation


async def test_same_event_in_expect_and_after_reacts_after_threshold_is_met(
    act: mock.AsyncMock,
    frozen_time: pendulum.DateTime,
    reactive_extended_expect_and_after: Automation,
):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/4201, where
    having the same event in after and expect causes weird behavior.

    Case two: Reactive, within > 0 -> this will fire on the second (or `threshold + 1`)
    occurrence of the event in the window
    """
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=1),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_not_awaited()

    act.reset_mock()
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=2),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_awaited_once()  # we've reached the threshold, fire

    # now the window should have been cleared, so we can fire again

    act.reset_mock()
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=3),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_not_awaited()  # another hit for the `after`, may fire on the next one

    act.reset_mock()
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=4),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_awaited_once()  # we've reached the threshold, fire

    # now advance far past the previous windows

    act.reset_mock()
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=61),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_not_awaited()

    act.reset_mock()
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=62),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    act.assert_awaited_once()  # we've reached the threshold, fire


@pytest.fixture
async def proactive_extended_expect_and_after(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    # Automation for https://github.com/PrefectHQ/nebula/issues/4201
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Both expect and after",
            trigger=EventTrigger(
                after={"some-event"},
                expect={"some-event"},
                posture=Posture.Proactive,
                threshold=2,
                within=timedelta(seconds=10),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return automation


async def test_same_event_in_expect_and_after_proactively_does_not_fire(
    act: mock.AsyncMock,
    frozen_time: pendulum.DateTime,
    proactive_extended_expect_and_after: Automation,
):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/4201, where
    having the same event in after and expect causes weird behavior

    Case three (negative): Proactive -> this will not fire if get `threshold - 1`
    events during the window
    """
    assert isinstance(proactive_extended_expect_and_after.trigger, EventTrigger)

    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=1),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )

    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=1),
    )
    act.assert_not_awaited()  # won't act here, but this should have "armed" the trigger

    act.reset_mock()
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=2),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=2),
    )
    act.assert_not_awaited()  # won't act here, we're within the window

    act.reset_mock()
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=3),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=3),
    )
    act.assert_not_awaited()  # won't act here, we've reached the threshold

    act.reset_mock()
    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=10),
    )
    act.assert_not_awaited()  # won't act here, we've reached the threshold

    act.reset_mock()
    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=11),
    )
    act.assert_not_awaited()  # won't act here, we've reached the threshold


async def test_same_event_in_expect_and_after_proactively_fires(
    act: mock.AsyncMock,
    frozen_time: pendulum.DateTime,
    proactive_extended_expect_and_after: Automation,
):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/4201, where
    having the same event in after and expect causes weird behavior

    Case three (positive): Proactive -> this will fire if we don't get `threshold - 1`
    events during the window
    """
    assert isinstance(proactive_extended_expect_and_after.trigger, EventTrigger)

    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=1),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )

    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=2),
    )
    act.assert_not_awaited()  # won't act here, this should have "armed" the trigger

    act.reset_mock()
    await triggers.reactive_evaluation(
        Event(
            occurred=frozen_time + timedelta(seconds=3),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )
    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=4),
    )
    act.assert_not_awaited()  # won't act here, we're within the window

    act.reset_mock()
    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=11),
    )
    act.assert_awaited_once()  # act here, we haven't reached the threshold of 2

    act.reset_mock()
    await triggers.proactive_evaluation(
        proactive_extended_expect_and_after.trigger,
        frozen_time + timedelta(seconds=30),
    )
    act.assert_not_awaited()  # won't act here, we haven't "armed" the trigger again


@pytest.fixture
async def rapid_fire_automation(
    work_queue: WorkQueue,
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    # Automation for https://github.com/PrefectHQ/nebula/issues/4201
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Reacts instantly to each event",
            trigger=EventTrigger(
                expect={"some-event"},
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=0),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return automation


async def test_rapid_fire_events(
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    start_of_test: pendulum.DateTime,
    rapid_fire_automation: Automation,
    automations_session: AsyncSession,
    frozen_time: pendulum.DateTime,
):
    """Regression test for https://github.com/PrefectHQ/prefect/issues/11199, where very
    rapidly arriving events wouldn't all trigger an action.

    Note: there's a small false negative rate in this test when we're trying to detect
    the timing bug, where one out of several dozen runs may accidentally show that we
    got N out of N actions fired (i.e. like the bug isn't present).  When the bug is
    fixed, this has 100% accuracy and should not introduce any test flakes.
    """
    events = [
        Event(
            occurred=start_of_test + timedelta(microseconds=i),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=UUID(int=i),
        ).receive()
        for i in range(50)
    ]

    random.shuffle(events)

    await asyncio.gather(*[triggers.reactive_evaluation(event) for event in events])

    assert act.await_count == len(events)
    assert_acted_with(
        [
            Firing(
                trigger=rapid_fire_automation.trigger,
                trigger_states={TriggerState.Triggered},
                triggered=frozen_time,  # type: ignore
                triggering_labels={},
                triggering_event=event,
            )
            for event in events
        ],
    )


@pytest.fixture
async def rapid_fire_automation_with_a_threshold(
    work_queue: WorkQueue,
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    # Automation for https://github.com/PrefectHQ/nebula/issues/4201
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Excepts 10 events within in sixty seconds",
            trigger=EventTrigger(
                expect={"some-event"},
                posture=Posture.Reactive,
                threshold=10,
                within=timedelta(seconds=60),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return automation


async def test_rapid_fire_events_with_a_threshold(
    act: mock.AsyncMock,
    start_of_test: pendulum.DateTime,
    rapid_fire_automation_with_a_threshold: Automation,
    automations_session: AsyncSession,
    frozen_time: pendulum.DateTime,
):
    """Regression test for https://github.com/PrefectHQ/nebula/issues/7230, where very
    rapidly arriving events wouldn't cause a trigger to fire if it had a `threshold` >1
    and a non-zero `within`.
    """
    events = [
        Event(
            occurred=start_of_test + timedelta(microseconds=i),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=UUID(int=i),
        ).receive()
        for i in range(10)
    ]

    # the worst case of this situation is when the events are handled in reverse order,
    # because the bucket's start time will be the last event's time, and so all of the
    # subsequent events

    events.reverse()
    for event in events:
        await triggers.reactive_evaluation(event)

    act.assert_awaited_once()

    firing: Firing = act.await_args[0][0]  # type: ignore
    assert isinstance(firing, Firing)
    assert firing.trigger == rapid_fire_automation_with_a_threshold.trigger
    assert firing.trigger_states == {TriggerState.Triggered}
    assert firing.triggered == frozen_time
    assert firing.triggering_labels == {}
    assert firing.triggering_event == events[-1]


@pytest.fixture
async def simple_recurring_automation(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Expects 1 event every 10 seconds",
            trigger=EventTrigger(
                expect={"some-event"},
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=10),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return automation


async def test_reactive_automation_can_trigger_on_events_arriving_in_the_future(
    act: mock.AsyncMock,
    simple_recurring_automation: Automation,
    start_of_test: pendulum.DateTime,
    frozen_time: pendulum.DateTime,
):
    """Regression test for an issue where a simple reactive recurring automation would
    not trigger when the event arrived slightly in the future."""

    await triggers.reactive_evaluation(
        Event(
            occurred=start_of_test,
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )

    act.assert_awaited_once()
    act.reset_mock()

    await triggers.reactive_evaluation(
        Event(
            occurred=start_of_test + timedelta(seconds=999),
            event="some-event",
            resource={"prefect.resource.id": "some.resource"},
            id=uuid4(),
        ).receive()
    )

    act.assert_awaited_once()
