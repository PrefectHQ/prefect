from datetime import timedelta
from uuid import uuid4

import pytest

from prefect.server.events import actions, triggers
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Posture,
)
from prefect.server.events.schemas.events import ReceivedEvent, ResourceSpecification
from prefect.types import DateTime


@pytest.fixture
def spider_automation() -> Automation:
    return Automation(
        name="React to spiders walking",
        trigger=EventTrigger(
            expect={"animal.walked"},
            match={"class": "Arachnida"},
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def wildcard_automation() -> Automation:
    return Automation(
        name="React to any animal event",
        trigger=EventTrigger(
            expect={"animal.*"},
            match=ResourceSpecification.model_validate({}),
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def catch_all_automation() -> Automation:
    return Automation(
        name="React to everything",
        trigger=EventTrigger(
            expect=set(),
            match=ResourceSpecification.model_validate({}),
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def spider_walked(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=1),
        event="animal.walked",
        resource={
            "prefect.resource.id": "daddy-long-legs",
            "class": "Arachnida",
        },
        id=uuid4(),
    )


@pytest.fixture
def plant_grew(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=1),
        event="plant.grew",
        resource={"prefect.resource.id": "my-lily"},
        id=uuid4(),
    )


def test_finds_trigger_with_matching_event(
    spider_automation: Automation,
    spider_walked: ReceivedEvent,
):
    triggers.load_automation(spider_automation)
    assert len(triggers.find_interested_triggers(spider_walked)) == 1


def test_skips_trigger_when_event_does_not_match(
    spider_automation: Automation,
    plant_grew: ReceivedEvent,
):
    triggers.load_automation(spider_automation)
    assert len(triggers.find_interested_triggers(plant_grew)) == 0


def test_wildcard_matches_events_with_same_prefix(
    wildcard_automation: Automation,
    spider_walked: ReceivedEvent,
    plant_grew: ReceivedEvent,
):
    triggers.load_automation(wildcard_automation)
    assert len(triggers.find_interested_triggers(spider_walked)) == 1
    assert len(triggers.find_interested_triggers(plant_grew)) == 0


def test_catch_all_matches_any_event(
    catch_all_automation: Automation,
    spider_walked: ReceivedEvent,
    plant_grew: ReceivedEvent,
):
    triggers.load_automation(catch_all_automation)
    assert len(triggers.find_interested_triggers(spider_walked)) == 1
    assert len(triggers.find_interested_triggers(plant_grew)) == 1


def test_event_can_match_multiple_triggers(
    spider_automation: Automation,
    wildcard_automation: Automation,
    catch_all_automation: Automation,
    spider_walked: ReceivedEvent,
):
    triggers.load_automation(spider_automation)
    triggers.load_automation(wildcard_automation)
    triggers.load_automation(catch_all_automation)
    assert len(triggers.find_interested_triggers(spider_walked)) == 3


def test_forgotten_automation_no_longer_matches(
    spider_automation: Automation,
    spider_walked: ReceivedEvent,
):
    triggers.load_automation(spider_automation)
    assert len(triggers.find_interested_triggers(spider_walked)) == 1

    triggers.forget_automation(spider_automation.id)
    assert len(triggers.find_interested_triggers(spider_walked)) == 0


def test_resource_filtering_still_applies(
    start_of_test: DateTime,
):
    auto = Automation(
        name="Only specific spiders",
        trigger=EventTrigger(
            expect={"animal.walked"},
            match={"class": "Arachnida"},
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )
    triggers.load_automation(auto)

    mammal_walked = ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=1),
        event="animal.walked",
        resource={"prefect.resource.id": "woodchonk", "class": "Mammalia"},
        id=uuid4(),
    )
    assert len(triggers.find_interested_triggers(mammal_walked)) == 0


def test_empty_expect_with_after_matches_any_event(
    start_of_test: DateTime,
):
    # SLA-style trigger: react to any event after a flow run goes pending.
    # `expect=set()` means the trigger's event_pattern is `.+` (matches
    # anything), so the index must register it as a catch-all rather than only
    # under its `after` patterns -- otherwise post-`after` events get dropped.
    sla = Automation(
        name="Any state after pending",
        trigger=EventTrigger(
            match={"prefect.resource.id": "prefect.flow-run.*"},
            for_each={"prefect.resource.id"},
            after={"prefect.flow-run.pending"},
            expect=set(),
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )
    triggers.load_automation(sla)

    pending = ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=1),
        event="prefect.flow-run.pending",
        resource={"prefect.resource.id": "prefect.flow-run.abc"},
        id=uuid4(),
    )
    completed = ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="prefect.flow-run.completed",
        resource={"prefect.resource.id": "prefect.flow-run.abc"},
        id=uuid4(),
    )

    assert sla.trigger.covers(pending)
    assert sla.trigger.covers(completed)
    assert len(triggers.find_interested_triggers(pending)) == 1
    assert len(triggers.find_interested_triggers(completed)) == 1
