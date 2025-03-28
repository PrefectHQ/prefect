from datetime import timedelta
from typing import List
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events import actions
from prefect.server.events.models import automations
from prefect.server.events.schemas.automations import (
    Automation,
    AutomationPartialUpdate,
    EventTrigger,
    Firing,
    Posture,
    ReceivedEvent,
    TriggeredAction,
    TriggerState,
)
from prefect.server.events.schemas.events import RelatedResource
from prefect.settings import (
    PREFECT_API_SERVICES_TRIGGERS_ENABLED,
    temporary_settings,
)
from prefect.types import DateTime
from prefect.types._datetime import now
from prefect.utilities.pydantic import parse_obj_as


@pytest.fixture
def enable_automations():
    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
        yield


@pytest.fixture(autouse=True, scope="module")
def triggers_disabled():
    """Because this test will modify automations, we want to suppress the async
    notifications they make to avoid a non-deterministic event loop issue in the test
    suite where the after-commit callback is invoked during teardown.  Disabling the
    triggers service for the duration of this test suite will accomplish this."""
    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: False}):
        yield


def test_source_determines_if_automation_id_is_required_or_allowed():
    with pytest.raises(ValidationError):
        actions.PauseAutomation(source="selected")

    with pytest.raises(ValidationError):
        actions.ResumeAutomation(source="selected")

    with pytest.raises(ValidationError):
        actions.PauseAutomation(source="inferred", automation_id=uuid4())

    with pytest.raises(ValidationError):
        actions.ResumeAutomation(source="inferred", automation_id=uuid4())


@pytest.fixture
async def sprinkler_automation(
    automations_session: AsyncSession,
) -> Automation:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Make sure the sprinklers stay on",
            trigger=EventTrigger(
                after={"sprinkler.off"},
                expect={"sprinkler.on"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(minutes=5),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    # as the target of the automations in this test suite, it must be committed to the
    # database; the other automations don't need to be
    await automations_session.commit()
    return automation


@pytest.fixture
def when_it_rains_turn_the_sprinklers_off(
    sprinkler_automation: Automation,
) -> Automation:
    return Automation(
        enabled=True,
        name="If it rains, don't keep the sprinklers on",
        trigger=EventTrigger(
            expect={"rain.start"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=0),
        ),
        actions=[
            actions.PauseAutomation(
                source="selected",
                automation_id=sprinkler_automation.id,
            )
        ],
    )


@pytest.fixture
def it_started_raining(
    start_of_test: DateTime,
) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="rain.start",
        resource={
            "prefect.resource.id": "front-lawn",
        },
        id=uuid4(),
    )


@pytest.fixture
def turn_off_the_sprinkler_automation(
    when_it_rains_turn_the_sprinklers_off: Automation,
    it_started_raining: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=when_it_rains_turn_the_sprinklers_off.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={},
        triggering_event=it_started_raining,
    )
    return TriggeredAction(
        automation=when_it_rains_turn_the_sprinklers_off,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=when_it_rains_turn_the_sprinklers_off.actions[0],
    )


async def test_pausing_automation(
    turn_off_the_sprinkler_automation: TriggeredAction,
    sprinkler_automation: Automation,
    automations_session: AsyncSession,
    enable_automations: None,
):
    before = await automations.read_automation(
        automations_session, sprinkler_automation.id
    )
    assert before
    assert before.enabled

    action = turn_off_the_sprinkler_automation.action
    await action.act(turn_off_the_sprinkler_automation)

    automations_session.expunge_all()

    after = await automations.read_automation(
        automations_session, sprinkler_automation.id
    )
    assert after
    assert not after.enabled


async def test_pausing_events_errors_are_reported_as_events(
    turn_off_the_sprinkler_automation: TriggeredAction,
):
    action = turn_off_the_sprinkler_automation.action
    assert isinstance(action, actions.PauseAutomation)

    action.automation_id = uuid4()  # this doesn't exist

    with pytest.raises(actions.ActionFailed, match="Unexpected status"):
        await action.act(turn_off_the_sprinkler_automation)


@pytest.fixture
def when_it_stops_raining_turn_the_sprinklers_on(
    sprinkler_automation: Automation,
) -> Automation:
    return Automation(
        enabled=True,
        name="If it stops raining, turn the sprinklers on",
        trigger=EventTrigger(
            expect={"rain.stop"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=0),
        ),
        actions=[
            actions.ResumeAutomation(
                source="selected",
                automation_id=sprinkler_automation.id,
            )
        ],
    )


@pytest.fixture
def it_stopped_raining(
    start_of_test: DateTime,
) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="rain.stop",
        resource={
            "prefect.resource.id": "front-lawn",
        },
        id=uuid4(),
    )


@pytest.fixture
def turn_on_the_sprinkler_automation(
    when_it_stops_raining_turn_the_sprinklers_on: Automation,
    it_stopped_raining: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=when_it_stops_raining_turn_the_sprinklers_on.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={},
        triggering_event=it_stopped_raining,
    )
    return TriggeredAction(
        automation=when_it_stops_raining_turn_the_sprinklers_on,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=when_it_stops_raining_turn_the_sprinklers_on.actions[0],
    )


async def test_resuming_automation(
    turn_on_the_sprinkler_automation: TriggeredAction,
    sprinkler_automation: Automation,
    automations_session: AsyncSession,
    enable_automations: None,
):
    await automations.update_automation(
        automations_session,
        AutomationPartialUpdate(enabled=False),
        sprinkler_automation.id,
    )
    await automations_session.commit()

    before = await automations.read_automation(
        automations_session, sprinkler_automation.id
    )
    assert before
    assert not before.enabled

    action = turn_on_the_sprinkler_automation.action
    await action.act(turn_on_the_sprinkler_automation)

    automations_session.expunge_all()

    after = await automations.read_automation(
        automations_session, sprinkler_automation.id
    )
    assert after
    assert after.enabled


async def test_resuming_events_errors_are_reported_as_events(
    turn_on_the_sprinkler_automation: TriggeredAction,
):
    action = turn_on_the_sprinkler_automation.action
    assert isinstance(action, actions.ResumeAutomation)

    action.automation_id = uuid4()  # this doesn't exist

    with pytest.raises(actions.ActionFailed, match="Unexpected status"):
        await action.act(turn_on_the_sprinkler_automation)


@pytest.fixture
async def self_managing_sprinkler_automation(
    automations_session: AsyncSession,
) -> Automation:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            enabled=True,
            name="Turn the sprinklers off after an hour",
            trigger=EventTrigger(
                after={"sprinkler.on"},
                expect={"sprinkler.off"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(hours=1),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    # as the target of the automations in this test suite, it must be committed to the
    # database; the other automations don't need to be
    await automations_session.commit()
    return automation


@pytest.fixture
def the_sprinklers_stopped(
    start_of_test: DateTime,
    self_managing_sprinkler_automation: Automation,
) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="sprinkler.off",
        resource={
            "prefect.resource.id": "sprinklers.front-lawn",
        },
        related=parse_obj_as(
            List[RelatedResource],
            [
                {
                    "prefect.resource.id": f"prefect.automation.{self_managing_sprinkler_automation.id}",
                    "prefect.resource.role": "i-automated-it",
                }
            ],
        ),
        id=uuid4(),
    )


@pytest.fixture
def turn_off_the_self_managing_automation(
    self_managing_sprinkler_automation: Automation,
    the_sprinklers_stopped: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=self_managing_sprinkler_automation.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={},
        triggering_event=the_sprinklers_stopped,
    )
    return TriggeredAction(
        automation=self_managing_sprinkler_automation,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=actions.PauseAutomation(source="inferred"),
    )


async def test_pausing_inferred_automation(
    self_managing_sprinkler_automation: Automation,
    turn_off_the_self_managing_automation: TriggeredAction,
    automations_session: AsyncSession,
    enable_automations,
):
    before = await automations.read_automation(
        automations_session,
        self_managing_sprinkler_automation.id,
    )
    assert before
    assert before.enabled

    action = turn_off_the_self_managing_automation.action
    await action.act(turn_off_the_self_managing_automation)

    after = await automations.read_automation(
        automations_session,
        self_managing_sprinkler_automation.id,
    )
    assert after
    assert not after.enabled


@pytest.fixture
def turn_on_the_self_managing_automation(
    self_managing_sprinkler_automation: Automation,
    the_sprinklers_stopped: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=self_managing_sprinkler_automation.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={},
        triggering_event=the_sprinklers_stopped,
    )
    return TriggeredAction(
        automation=self_managing_sprinkler_automation,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=actions.ResumeAutomation(source="inferred"),
    )


async def test_resuming_inferred_automation(
    self_managing_sprinkler_automation: Automation,
    turn_off_the_self_managing_automation: TriggeredAction,
    automations_session: AsyncSession,
    enable_automations,
):
    before = await automations.read_automation(
        automations_session,
        self_managing_sprinkler_automation.id,
    )
    assert before
    assert before.enabled

    action = turn_off_the_self_managing_automation.action
    await action.act(turn_off_the_self_managing_automation)

    after = await automations.read_automation(
        automations_session,
        self_managing_sprinkler_automation.id,
    )
    assert after
    assert not after.enabled


async def test_inferring_automation_requires_event(
    turn_on_the_self_managing_automation: TriggeredAction,
):
    turn_on_the_self_managing_automation.triggering_event = (
        None  # simulate a proactive trigger
    )

    action = turn_on_the_self_managing_automation.action

    with pytest.raises(actions.ActionFailed, match="No event to infer the automation"):
        await action.act(turn_on_the_self_managing_automation)


async def test_inferring_automation_requires_some_matching_resource(
    turn_on_the_self_managing_automation: TriggeredAction,
):
    assert turn_on_the_self_managing_automation.triggering_event
    turn_on_the_self_managing_automation.triggering_event.related = []  # no relevant related resources

    action = turn_on_the_self_managing_automation.action

    with pytest.raises(actions.ActionFailed, match="No automation could be inferred"):
        await action.act(turn_on_the_self_managing_automation)


async def test_inferring_automation_requires_recognizable_resource_id(
    turn_on_the_self_managing_automation: TriggeredAction,
):
    assert turn_on_the_self_managing_automation.triggering_event
    turn_on_the_self_managing_automation.triggering_event.related = parse_obj_as(
        List[RelatedResource],
        [
            {
                "prefect.resource.role": "i-automated-it",
                "prefect.resource.id": "prefect.automation.nope",  # not a uuid
            },
            {
                "prefect.resource.role": "i-automated-it",
                "prefect.resource.id": f"oh.so.close.{uuid4()}",  # not an automation
            },
            {
                "prefect.resource.role": "i-automated-it",
                "prefect.resource.id": "nah-ah",  # not a dotted name
            },
        ],
    )

    action = turn_on_the_self_managing_automation.action

    with pytest.raises(actions.ActionFailed, match="No automation could be inferred"):
        await action.act(turn_on_the_self_managing_automation)
