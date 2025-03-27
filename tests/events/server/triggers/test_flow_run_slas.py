import datetime
from datetime import timedelta
from typing import Callable, List, Union, cast
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
from prefect.server.events.schemas.events import Event, ReceivedEvent
from prefect.types import DateTime


@pytest.fixture
async def stuck_flow_runs_sla(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> EventTrigger:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Stuck Flow Runs",
            description="Any Flow Runs that start and don't complete in 1 minute",
            trigger=EventTrigger(
                # Match flow runs with a wildcard on the resource ID
                match={
                    "prefect.resource.id": "prefect.flow-run.*",
                },
                # Track the SLA of _each_ flow run resource that matches
                for_each={"prefect.resource.id"},
                # the expected start events
                after={"prefect.flow-run.running"},
                # the expected end events
                expect={"prefect.flow-run.completed", "prefect.flow-run.cancelled"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(minutes=1),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return cast(EventTrigger, automation.trigger)


@pytest.fixture
def fast_and_happy_flow(frozen_time: DateTime) -> List[Event]:
    """This fast and happy flow runs multiple times successfully in a short period of
    time, which should not trigger any SLA conditions and should also not mask the
    fact that a slower run got stuck"""
    return [
        # First scheduled run
        Event(
            occurred=frozen_time + timedelta(seconds=1),
            event="prefect.flow-run.scheduled",
            resource={"prefect.resource.id": "prefect.flow-run.FASTBOI-1"},
            related=[],
            payload={},
            id=uuid4(),
        ),
        Event(
            occurred=frozen_time + timedelta(seconds=2),
            event="prefect.flow-run.pending",
            resource={"prefect.resource.id": "prefect.flow-run.FASTBOI-1"},
            related=[],
            payload={},
            id=uuid4(),
        ),
        Event(
            occurred=frozen_time + timedelta(seconds=3),
            event="prefect.flow-run.running",
            resource={"prefect.resource.id": "prefect.flow-run.FASTBOI-1"},
            related=[],
            payload={},
            id=uuid4(),
        ),
        Event(
            occurred=frozen_time + timedelta(seconds=10),
            event="prefect.flow-run.completed",
            resource={"prefect.resource.id": "prefect.flow-run.FASTBOI-1"},
            related=[],
            payload={},
            id=uuid4(),
        ),
        # Second run (not scheduled)
        Event(
            occurred=frozen_time + timedelta(seconds=22),
            event="prefect.flow-run.pending",
            resource={"prefect.resource.id": "prefect.flow-run.FASTBOI-2"},
            related=[],
            payload={},
            id=uuid4(),
        ),
        Event(
            occurred=frozen_time + timedelta(seconds=23),
            event="prefect.flow-run.running",
            resource={"prefect.resource.id": "prefect.flow-run.FASTBOI-2"},
            related=[],
            payload={},
            id=uuid4(),
        ),
        Event(
            occurred=frozen_time + timedelta(seconds=30),
            event="prefect.flow-run.completed",
            resource={"prefect.resource.id": "prefect.flow-run.FASTBOI-2"},
            related=[],
            payload={},
            id=uuid4(),
        ),
    ]


@pytest.fixture
def stuck_flow(frozen_time: DateTime) -> List[Event]:
    """This flow gets stuck and doesn't complete in the time allotted"""
    resource = {"prefect.resource.id": "prefect.flow-run.SLOWBOI"}
    return [
        Event(
            occurred=frozen_time + timedelta(seconds=2),
            event="prefect.flow-run.scheduled",
            resource=resource,
            related=[],
            payload={},
            id=uuid4(),
        ),
        Event(
            occurred=frozen_time + timedelta(seconds=3),
            event="prefect.flow-run.pending",
            resource=resource,
            related=[],
            payload={},
            id=uuid4(),
        ),
        Event(
            occurred=frozen_time + timedelta(seconds=4),
            event="prefect.flow-run.running",
            resource=resource,
            related=[],
            payload={},
            id=uuid4(),
        ),
    ]


@pytest.fixture
def received_events(
    fast_and_happy_flow: List[Event],
    stuck_flow: List[Event],
) -> List[ReceivedEvent]:
    return [
        event.receive()
        for event in sorted(fast_and_happy_flow + stuck_flow, key=lambda e: e.occurred)
    ]


async def test_automation_covers_all_the_events_we_expect(
    stuck_flow_runs_sla: EventTrigger,
    received_events: List[ReceivedEvent],
):
    COVERED = {
        "prefect.flow-run.running",
        "prefect.flow-run.completed",
        "prefect.flow-run.cancelled",
    }
    covered_events = [event for event in received_events if event.event in COVERED]
    assert covered_events

    for event in covered_events:
        assert stuck_flow_runs_sla.covers(event)


async def test_only_the_stuck_flow_triggers(
    stuck_flow_runs_sla: EventTrigger,
    received_events: List[ReceivedEvent],
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    for event in received_events:
        await triggers.reactive_evaluation(event)

    # No reactive triggers exist, and it hasn't been a minute yet so no proactive
    # triggers should have fired either
    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        stuck_flow_runs_sla, frozen_time + timedelta(seconds=50)
    )
    # It still hasn't been a minute
    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        stuck_flow_runs_sla, frozen_time + timedelta(seconds=64)
    )

    last_event = received_events[5]
    assert last_event.occurred == frozen_time + timedelta(seconds=4)
    assert last_event.resource.id == "prefect.flow-run.SLOWBOI"
    assert last_event.event == "prefect.flow-run.running"

    # Now it's been long enough for the SLA to fire, since it started running
    # at T=4 and now it's T=64
    assert_acted_with(
        Firing(
            trigger=stuck_flow_runs_sla,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            # it should only be the SLOWBOI run at this point
            triggering_labels={"prefect.resource.id": "prefect.flow-run.SLOWBOI"},
            # The triggering event is the last event, because the `posture` is `Proactive`
            triggering_event=last_event,
        ),
    )


@pytest.fixture
async def stuck_flow_runs_sla_with_wildcard_expect(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> EventTrigger:
    """Regression test fixture, see test below"""
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Stuck Flow Runs",
            description="Any Flow Runs that start and don't complete in 1 minute",
            trigger=EventTrigger(
                # Match flow runs with a wildcard on the resource ID
                match={
                    "prefect.resource.id": "prefect.flow-run.*",
                },
                # Track the SLA of _each_ flow run resource that matches
                for_each={"prefect.resource.id"},
                # the expected start events
                after={"prefect.flow-run.running"},
                # the expected end events, which are a superset of the `after`; this
                # is how we have configured the UI
                expect={"prefect.flow-run.*"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(minutes=1),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    return cast(EventTrigger, automation.trigger)


async def test_the_stuck_flow_triggers_with_a_wildcard_expect_that_is_a_superset(
    stuck_flow_runs_sla_with_wildcard_expect: EventTrigger,
    received_events: List[ReceivedEvent],
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    """Regression test for observed failures to trigger proactive automations when
    the `after` event is a subset of the `expect` events"""
    for event in received_events:
        await triggers.reactive_evaluation(event)

    # No reactive triggers exist, and it hasn't been a minute yet so no proactive
    # triggers should have fired either
    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        stuck_flow_runs_sla_with_wildcard_expect,
        frozen_time + timedelta(seconds=50),
    )
    # It still hasn't been a minute
    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        stuck_flow_runs_sla_with_wildcard_expect,
        frozen_time + timedelta(seconds=64),
    )

    last_event = received_events[5]
    assert last_event.occurred == frozen_time + timedelta(seconds=4)
    assert last_event.resource.id == "prefect.flow-run.SLOWBOI"
    assert last_event.event == "prefect.flow-run.running"

    # Now it's been long enough for the SLA to fire, since it started running
    # at T=4 and now it's T=64
    assert_acted_with(
        Firing(
            trigger=stuck_flow_runs_sla_with_wildcard_expect,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            # it should only be the SLOWBOI run at this point
            triggering_labels={"prefect.resource.id": "prefect.flow-run.SLOWBOI"},
            # The triggering event is the last event, because the `posture` is `Proactive`
            triggering_event=last_event,
            triggering_value=None,
        ),
    )


@pytest.fixture
async def only_scheduled_run_notifications(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> EventTrigger:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Scheduled run notifications",
            description="Reacts to the completion of any Flow Runs that were scheduled",
            trigger=EventTrigger(
                # Match flow runs with a wildcard on the resource ID
                match={
                    "prefect.resource.id": "prefect.flow-run.*",
                },
                # Track the SLA of _each_ flow run resource that matches
                for_each={"prefect.resource.id"},
                # Only match for flow runs that started off scheduled, then later went completed
                after={"prefect.flow-run.scheduled"},
                expect={"prefect.flow-run.completed"},
                posture=Posture.Reactive,
                threshold=0,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    await automations_session.commit()
    triggers.load_automation(automation)
    return cast(EventTrigger, automation.trigger)


async def test_react_only_to_scheduled_flows_completing(
    only_scheduled_run_notifications: EventTrigger,
    received_events: List[ReceivedEvent],
    act: mock.AsyncMock,
    assert_acted_with: Callable[[Union[Firing, List[Firing]]], None],
    frozen_time: DateTime,
):
    for event in received_events:
        await triggers.reactive_evaluation(event)

    # Even though two runs completed, only one of them started from a scheduled event
    expected_triggering_event = received_events[6]
    assert expected_triggering_event.resource.id == "prefect.flow-run.FASTBOI-1"
    assert expected_triggering_event.event == "prefect.flow-run.completed"
    assert_acted_with(
        Firing(
            trigger=only_scheduled_run_notifications,
            trigger_states={TriggerState.Triggered},
            triggered=frozen_time,  # type: ignore
            triggering_labels={"prefect.resource.id": "prefect.flow-run.FASTBOI-1"},
            triggering_event=expected_triggering_event,
        ),
    )


@pytest.fixture
async def any_event_after_pending(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> EventTrigger:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Get ready!",
            description="Reacts to any flow run that leaves Pending",
            trigger=EventTrigger(
                match={
                    "prefect.resource.id": "prefect.flow-run.*",
                },
                for_each={"prefect.resource.id"},
                # Only match for flow runs go pending...
                after={"prefect.flow-run.pending"},
                # ...then go to any other state
                expect=set(),
                posture=Posture.Reactive,
                threshold=0,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    await automations_session.commit()
    triggers.load_automation(automation)
    return cast(EventTrigger, automation.trigger)


async def test_react_to_runs_that_go_to_any_state_after_pending(
    any_event_after_pending: EventTrigger,
    received_events: List[ReceivedEvent],
    act: mock.AsyncMock,
    frozen_time: DateTime,
):
    for event in received_events:
        await triggers.reactive_evaluation(event)

    # all of the runs did this
    assert act.await_count == 3


# Regression test for https://github.com/PrefectHQ/nebula/issues/3521
# where a customer reported a proactive notification erroneously firing even when
# their flow run had completed (2 hours earlier)


@pytest.fixture
async def automation_from_3521(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Regression Test #3521",
            description="",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                match_related={
                    "prefect.resource.id": [
                        "prefect.flow.f1f1f1f1",
                        "prefect.flow.f2f2f2f2",
                    ],
                    "prefect.resource.role": "flow",
                },
                for_each={"prefect.resource.id"},
                after={"prefect.flow-run.Running"},
                # ...then go to any other state
                expect={"prefect.flow-run.*"},
                posture=Posture.Proactive,
                within=7200.0,
                threshold=1,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    await automations_session.commit()
    triggers.load_automation(automation)
    return automation


@pytest.fixture
def trigger_from_3521(automation_from_3521: Automation) -> EventTrigger:
    return cast(EventTrigger, automation_from_3521.trigger)


@pytest.fixture
async def sequence_of_events_3521(
    start_of_test: DateTime,
) -> List[Union[ReceivedEvent, DateTime]]:
    baseline: DateTime = start_of_test

    pending = Event(
        occurred=baseline + datetime.timedelta(minutes=0),
        event="prefect.flow-run.Pending",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        related=[
            {
                "prefect.resource.id": "prefect.flow.f1f1f1f1",
                "prefect.resource.role": "flow",
            }
        ],
        id=uuid4(),
    ).receive()

    running = Event(
        occurred=baseline + datetime.timedelta(minutes=1),
        event="prefect.flow-run.Running",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        related=[
            {
                "prefect.resource.id": "prefect.flow.f1f1f1f1",
                "prefect.resource.role": "flow",
            }
        ],
        id=uuid4(),
        follows=pending.id,
    ).receive()

    completed = Event(
        occurred=baseline + datetime.timedelta(minutes=4),
        event="prefect.flow-run.Completed",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        related=[
            {
                "prefect.resource.id": "prefect.flow.f1f1f1f1",
                "prefect.resource.role": "flow",
            }
        ],
        id=uuid4(),
        follows=running.id,
    ).receive()

    return [
        pending,
        running,
        # throw a random event for the same resource ID in the middle
        Event(
            occurred=baseline + datetime.timedelta(minutes=2),
            event="prefect.log.write",
            resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            related=[
                {
                    "prefect.resource.id": "prefect.flow.f1f1f1f1",
                    "prefect.resource.role": "flow",
                }
            ],
            id=uuid4(),
        ).receive(),
        baseline + datetime.timedelta(minutes=3),
        completed,
        baseline + datetime.timedelta(minutes=5),
        baseline
        + datetime.timedelta(minutes=119),  # just shy of the 2 hour mark since Pending
        baseline
        + datetime.timedelta(minutes=120),  # just at the 2 hour mark since Pending
        baseline
        + datetime.timedelta(minutes=121),  # just at the 2 hour mark since Running
        baseline
        + datetime.timedelta(
            minutes=123
        ),  # just shy of the 2 hour mark since Completed
        baseline
        + datetime.timedelta(minutes=124),  # just at the 2 hour mark since Completed
        baseline
        + datetime.timedelta(minutes=125),  # just past the the 2 hour mark for anything
        baseline + datetime.timedelta(minutes=250),  # an additional full cycle later
    ]


async def test_regression_3521_negative_case(
    trigger_from_3521: EventTrigger,
    sequence_of_events_3521: List[Union[ReceivedEvent, DateTime]],
    act: mock.AsyncMock,
):
    # we expect no action to ever be called for these
    for item in sequence_of_events_3521:
        if isinstance(item, ReceivedEvent):
            await triggers.reactive_evaluation(event=item)
        elif isinstance(item, datetime.datetime):
            await triggers.proactive_evaluation(trigger_from_3521, as_of=item)
        else:  # pragma: no cover
            raise NotImplementedError()

        act.assert_not_awaited()


async def test_regression_3521_positive_case(
    trigger_from_3521: EventTrigger,
    sequence_of_events_3521: List[Union[ReceivedEvent, DateTime]],
    act: mock.AsyncMock,
):
    # if we never get the completed event, the automation should fire
    for item in sequence_of_events_3521:
        if isinstance(item, ReceivedEvent):
            if item.event == "prefect.flow-run.Completed":
                continue
            await triggers.reactive_evaluation(event=item)
        elif isinstance(item, datetime.datetime):
            await triggers.proactive_evaluation(trigger_from_3521, as_of=item)
        else:  # pragma: no cover
            raise NotImplementedError()

    act.assert_awaited_once()


async def test_regression_3521_side_quest(
    trigger_from_3521: EventTrigger,
    sequence_of_events_3521: List[Union[ReceivedEvent, DateTime]],
    act: mock.AsyncMock,
):
    """While testing this issue, found another issue where sweeping older buckets might
    cause buckets to disappear before they are checked if there are long lags between
    proactive evaluations"""
    # if we never get the completed event, the automation should fire
    for item in sequence_of_events_3521:
        if isinstance(item, ReceivedEvent):
            if item.event == "prefect.flow-run.Completed":
                continue
            await triggers.reactive_evaluation(event=item)
        elif isinstance(item, datetime.datetime):
            continue  # do not run proactive evaluations for a while
        else:  # pragma: no cover
            raise NotImplementedError()

    act.assert_not_awaited()

    # now run one at the end, which represents a time after the automation should have
    # triggered but didn't
    assert isinstance(item, datetime.datetime)
    await triggers.proactive_evaluation(trigger_from_3521, as_of=item)
    act.assert_awaited_once()

    act.reset_mock()

    # but make sure that no further triggers happen later...
    await triggers.proactive_evaluation(
        trigger_from_3521, as_of=item + datetime.timedelta(minutes=1)
    )
    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        trigger_from_3521, as_of=item + datetime.timedelta(minutes=200)
    )
    act.assert_not_awaited()


# Regression test for https://github.com/PrefectHQ/nebula/issues/3244.  This is a
# broader issue to attempt to process order-critical messages in the right order.  It
# follows from #3521 (regression tests above) where a customer reported a proactive
# notification erroneously firing even when their flow run had completed (2 hours
# earlier).  The important difference in these tests is that we're going to flip the
# order of the Completed and Running events, but they will have the correct causal
# links with each other.  Also, we're going to simplify the automation so that it
# is just looking for a Completed after a Running to hone in on what the causal ordering
# will help with.


@pytest.fixture
async def automation_from_3244(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Regression Test #3521",
            description="",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                match_related={
                    "prefect.resource.id": [
                        "prefect.flow.f1f1f1f1",
                        "prefect.flow.f2f2f2f2",
                    ],
                    "prefect.resource.role": "flow",
                },
                for_each={"prefect.resource.id"},
                after={"prefect.flow-run.Running"},
                expect={"prefect.flow-run.Completed"},
                posture=Posture.Proactive,
                within=7200.0,
                threshold=1,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    await automations_session.commit()
    triggers.load_automation(automation)
    return automation


@pytest.fixture
def trigger_from_3244(automation_from_3244: Automation) -> EventTrigger:
    return cast(EventTrigger, automation_from_3244.trigger)


@pytest.fixture
async def sequence_of_events_3244(
    start_of_test: DateTime,
) -> List[Union[ReceivedEvent, DateTime]]:
    baseline: DateTime = start_of_test

    pending = Event(
        occurred=baseline + datetime.timedelta(minutes=0),
        event="prefect.flow-run.Pending",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        related=[
            {
                "prefect.resource.id": "prefect.flow.f1f1f1f1",
                "prefect.resource.role": "flow",
            }
        ],
        id=uuid4(),
    ).receive()

    running = Event(
        occurred=baseline + datetime.timedelta(minutes=1),
        event="prefect.flow-run.Running",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        related=[
            {
                "prefect.resource.id": "prefect.flow.f1f1f1f1",
                "prefect.resource.role": "flow",
            }
        ],
        id=uuid4(),
        follows=pending.id,
    ).receive()

    completed = Event(
        occurred=baseline + datetime.timedelta(minutes=4),
        event="prefect.flow-run.Completed",
        resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
        related=[
            {
                "prefect.resource.id": "prefect.flow.f1f1f1f1",
                "prefect.resource.role": "flow",
            }
        ],
        id=uuid4(),
        follows=running.id,
    ).receive()

    return [
        pending,
        completed,  # the completed will arrive before the running
        # throw a random event for the same resource ID in the middle
        Event(
            occurred=baseline + datetime.timedelta(minutes=2),
            event="prefect.log.write",
            resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            related=[
                {
                    "prefect.resource.id": "prefect.flow.f1f1f1f1",
                    "prefect.resource.role": "flow",
                }
            ],
            id=uuid4(),
        ).receive(),
        running,
        baseline + datetime.timedelta(minutes=3),
        baseline
        + datetime.timedelta(
            minutes=4
        ),  # this is the slot to redeliver the Completed event
        baseline + datetime.timedelta(minutes=5),
        baseline
        + datetime.timedelta(minutes=119),  # just shy of the 2 hour mark since Pending
        baseline
        + datetime.timedelta(minutes=120),  # just at the 2 hour mark since Pending
        baseline
        + datetime.timedelta(minutes=121),  # just at the 2 hour mark since Running
        baseline
        + datetime.timedelta(
            minutes=123
        ),  # just shy of the 2 hour mark since Completed
        baseline
        + datetime.timedelta(minutes=124),  # just at the 2 hour mark since Completed
        baseline
        + datetime.timedelta(minutes=125),  # just past the the 2 hour mark for anything
        baseline + datetime.timedelta(minutes=250),  # an additional full cycle later
    ]


async def test_regression_3244_negative_case(
    trigger_from_3244: EventTrigger,
    sequence_of_events_3244: List[Union[ReceivedEvent, DateTime]],
    act: mock.AsyncMock,
    automations_session: AsyncSession,
):
    # we expect no action to ever be called for these
    for index, item in enumerate(sequence_of_events_3244):
        if isinstance(item, ReceivedEvent):
            # The first time Completed comes through, it's too early, so we should
            # expect the EventArrivedEarly exception; this will record the Completed
            # event to be handled once the preceding event arrives
            if item.event == "prefect.flow-run.Completed" and index == 1:
                with pytest.raises(triggers.EventArrivedEarly):
                    await triggers.reactive_evaluation(event=item)
            else:
                await triggers.reactive_evaluation(event=item)
        elif isinstance(item, datetime.datetime):
            await triggers.proactive_evaluation(trigger_from_3244, as_of=item)
        else:  # pragma: no cover
            raise NotImplementedError()

        act.assert_not_awaited()


async def test_regression_3244_positive_case(
    trigger_from_3244: EventTrigger,
    sequence_of_events_3244: List[Union[ReceivedEvent, DateTime]],
    act: mock.AsyncMock,
):
    # if we never get the completed event, the automation should fire
    for item in sequence_of_events_3244:
        if isinstance(item, ReceivedEvent):
            if item.event == "prefect.flow-run.Completed":
                continue
            await triggers.reactive_evaluation(event=item)
        elif isinstance(item, datetime.datetime):
            await triggers.proactive_evaluation(trigger_from_3244, as_of=item)
        else:  # pragma: no cover
            raise NotImplementedError()

    act.assert_awaited_once()


# Regression test for https://github.com/PrefectHQ/nebula/issues/3803, where proactive
# triggers that are shorter than our message queueing backlog might erroneously fire.
# For example:
#
# wall clock | event.occurred | event.event
# ------------------------------------------------------
#          0 |            -10 | prefect.flow-run.Pending
#        1-5 |              - | 5 minutes worth of backlogged events
#          5 |              - | proactive evaluation runs here using now("UTC")
#          6 |             -9 | prefect.flow-run.Running
#
# In this case, the Running event was only 1 minute after the pending event, but it
# took 6 minutes of wall clock time to get there.  Running proactive evaluation using
# the wall clock time will make a proactive trigger erroneously fire.


@pytest.fixture
async def automation_from_3803(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> Automation:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Regression Test #3803",
            description="",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                for_each={"prefect.resource.id"},
                # expecting any state after Pending
                after={"prefect.flow-run.Pending"},
                expect={"prefect.flow-run.*"},
                posture=Posture.Proactive,
                within=timedelta(minutes=5),
                threshold=1,
            ),
            actions=[actions.DoNothing()],
        ),
    )
    await automations_session.commit()
    triggers.load_automation(automation)
    return automation


@pytest.fixture
def trigger_from_3803(automation_from_3803: Automation) -> EventTrigger:
    return cast(EventTrigger, automation_from_3803.trigger)


async def test_regression_3803_negative_case(
    reset_events_clock: None,
    trigger_from_3803: EventTrigger,
    act: mock.AsyncMock,
    start_of_test: DateTime,
    automations_session: AsyncSession,
):
    await triggers.reactive_evaluation(
        Event(
            occurred=start_of_test - datetime.timedelta(minutes=20),
            event="prefect.flow-run.Pending",
            resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            id=uuid4(),
        ).receive()
    )

    # These are the crucial ones: we should _not_ be firing here because the triggers
    # local offset should be preventing it
    # Before the fix, the trigger would have just fired here prematurely
    await triggers.proactive_evaluation(
        trigger_from_3803, start_of_test + datetime.timedelta(minutes=1)
    )
    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        trigger_from_3803, start_of_test + datetime.timedelta(minutes=4)
    )
    act.assert_not_awaited()

    # Now later the Running event comes in, and it only occurred a minute apart,
    # 19 minutes ago
    await triggers.reactive_evaluation(
        Event(
            occurred=start_of_test - datetime.timedelta(minutes=19),
            event="prefect.flow-run.Running",
            resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            id=uuid4(),
        ).receive()
    )

    # We shouldn't fire later because the Running event closed it out
    await triggers.proactive_evaluation(
        trigger_from_3803, start_of_test + datetime.timedelta(minutes=6)
    )
    act.assert_not_awaited()


async def test_regression_3803_positive_case_no_events_at_all(
    reset_events_clock: None,
    trigger_from_3803: EventTrigger,
    act: mock.AsyncMock,
    start_of_test: DateTime,
    automations_session: AsyncSession,
):
    await triggers.reactive_evaluation(
        Event(
            occurred=start_of_test - datetime.timedelta(minutes=20),
            event="prefect.flow-run.Pending",
            resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            id=uuid4(),
        ).receive()
    )

    # These are the crucial ones: we should _not_ be firing here because the triggers
    # local offset should be preventing it
    # Before the fix, the trigger would have just fired here prematurely
    await triggers.proactive_evaluation(
        trigger_from_3803, start_of_test + datetime.timedelta(minutes=1)
    )
    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        trigger_from_3803, start_of_test + datetime.timedelta(minutes=4)
    )
    act.assert_not_awaited()

    # No other event arrives at all

    # We should fire later because the Running event never closed it out
    await triggers.proactive_evaluation(
        trigger_from_3803, start_of_test + datetime.timedelta(minutes=6)
    )
    act.assert_awaited_once()


async def test_regression_3803_positive_case_no_relevant_event(
    reset_events_clock: None,
    trigger_from_3803: EventTrigger,
    act: mock.AsyncMock,
    start_of_test: DateTime,
    automations_session: AsyncSession,
):
    await triggers.reactive_evaluation(
        Event(
            occurred=start_of_test - datetime.timedelta(minutes=20),
            event="prefect.flow-run.Pending",
            resource={"prefect.resource.id": "prefect.flow-run.frfrfrfr"},
            id=uuid4(),
        ).receive()
    )

    # These are the crucial ones: we should _not_ be firing here because the triggers
    # local offset should be preventing it
    # Before the fix, the trigger would have just fired here prematurely
    await triggers.proactive_evaluation(
        trigger_from_3803,
        start_of_test + datetime.timedelta(minutes=1),
    )
    act.assert_not_awaited()

    await triggers.proactive_evaluation(
        trigger_from_3803, start_of_test + datetime.timedelta(minutes=4)
    )
    act.assert_not_awaited()

    # Another event comes by and ticks the clock for us to the point past where the
    # pending automation should have fired
    await triggers.reactive_evaluation(
        Event(
            occurred=start_of_test - datetime.timedelta(minutes=6),
            event="something.else",
            resource={"prefect.resource.id": "any.other.resource"},
            id=uuid4(),
        ).receive()
    )

    # We should fire now because the Running event never closed it out
    await triggers.proactive_evaluation(
        trigger_from_3803, start_of_test + datetime.timedelta(minutes=6)
    )
    act.assert_awaited_once()
