from datetime import timedelta
from uuid import uuid4

import pytest

from prefect.server.events import actions, triggers
from prefect.server.events.schemas.automations import (
    Automation,
    CompoundTrigger,
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


@pytest.fixture
def completion_automation() -> Automation:
    return Automation(
        name="Named deployment",
        trigger=EventTrigger(
            expect={"prefect.flow-run.Completed"},
            match_related={"prefect.resource.name": "deployment-0"},
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def completion_event(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test,
        event="prefect.flow-run.Completed",
        resource={"prefect.resource.id": "prefect.flow-run.example"},
        related=[
            {
                "prefect.resource.id": "prefect.deployment.example",
                "prefect.resource.role": "deployment",
                "prefect.resource.name": "deployment-0",
            }
        ],
        id=uuid4(),
    )


@pytest.mark.parametrize(
    "name_filter, matches",
    [
        pytest.param("deployment-0", True, id="exact"),
        pytest.param("deployment-1", False, id="different-name"),
        pytest.param(["deployment-1", "deployment-0"], True, id="alternatives"),
        pytest.param("deployment-*", True, id="wildcard"),
        pytest.param("deployment-?", True, id="single-character-wildcard"),
        pytest.param("deployment-[01]", True, id="character-class"),
        pytest.param("!deployment-0", False, id="negated-match"),
        pytest.param("!deployment-1", True, id="negated-other-name"),
        pytest.param(["other", "deployment-*"], True, id="mixed-wildcard"),
        pytest.param(["other", "!deployment-1"], True, id="mixed-negation"),
        pytest.param([], False, id="empty-alternatives"),
        pytest.param("", False, id="empty-name"),
    ],
)
def test_related_resource_name_filtering(
    completion_automation: Automation,
    completion_event: ReceivedEvent,
    name_filter: str | list[str],
    matches: bool,
):
    completion_automation.trigger.match_related = ResourceSpecification(
        {"prefect.resource.name": name_filter}
    )
    triggers.load_automation(completion_automation)

    assert list(triggers.find_interested_triggers(completion_event)) == (
        [completion_automation.trigger] if matches else []
    )


@pytest.mark.parametrize(
    "match_related, related, matches",
    [
        pytest.param({}, [], True, id="unrestricted"),
        pytest.param(
            {"prefect.resource.name": "deployment-0"}, [], False, id="no-related"
        ),
        pytest.param(
            {"prefect.resource.name": "deployment-0"},
            [{"prefect.resource.role": "deployment"}],
            False,
            id="missing-name",
        ),
        pytest.param(
            {"prefect.resource.name": [""]},
            [{"prefect.resource.name": ""}],
            True,
            id="empty-label-value",
        ),
        pytest.param(
            {
                "prefect.resource.name": "deployment-0",
                "prefect.resource.role": "deployment",
            },
            [
                {
                    "prefect.resource.name": "deployment-0",
                    "prefect.resource.role": "flow",
                },
                {
                    "prefect.resource.name": "deployment-1",
                    "prefect.resource.role": "deployment",
                },
            ],
            False,
            id="labels-must-match-one-resource",
        ),
        pytest.param(
            [
                {"prefect.resource.name": "deployment-*"},
                {"prefect.resource.name": "deployment-0"},
            ],
            [{"prefect.resource.name": "deployment-0"}],
            True,
            id="wildcard-and-exact-specifications",
        ),
        pytest.param(
            [
                {"prefect.resource.name": "deployment-0"},
                {"prefect.resource.name": "deployment-1"},
            ],
            [{"prefect.resource.name": "deployment-0"}],
            False,
            id="all-specifications-required",
        ),
        pytest.param(
            [
                {"prefect.resource.name": "deployment-0"},
                {"prefect.resource.name": "deployment-1"},
            ],
            [
                {"prefect.resource.name": "deployment-0"},
                {"prefect.resource.name": "deployment-1"},
            ],
            True,
            id="different-related-resources",
        ),
        pytest.param(
            {"prefect.resource.name": "deployment-0"},
            [{"prefect.resource.name": "deployment-0"}] * 2,
            True,
            id="duplicate-related-names",
        ),
    ],
)
def test_related_resource_specifications(
    completion_automation: Automation,
    completion_event: ReceivedEvent,
    match_related: dict[str, str | list[str]] | list[dict[str, str | list[str]]],
    related: list[dict[str, str]],
    matches: bool,
):
    completion_automation.trigger.match_related = (
        [ResourceSpecification(specification) for specification in match_related]
        if isinstance(match_related, list)
        else ResourceSpecification(match_related)
    )
    triggers.load_automation(completion_automation)
    event = ReceivedEvent.model_validate(
        {
            **completion_event.model_dump(),
            "related": [
                {
                    "prefect.resource.id": f"resource-{index}",
                    "prefect.resource.role": "deployment",
                    **resource,
                }
                for index, resource in enumerate(related)
            ],
        }
    )

    assert list(triggers.find_interested_triggers(event)) == (
        [completion_automation.trigger] if matches else []
    )


@pytest.mark.parametrize(
    "expect, event_name, matches",
    [
        pytest.param(
            {"prefect.flow-run.Completed"}, "prefect.flow-run.Pending", True, id="after"
        ),
        pytest.param(
            {"prefect.flow-run.*"},
            "prefect.flow-run.Running",
            True,
            id="wildcard-event",
        ),
        pytest.param(set(), "prefect.task-run.Completed", True, id="catch-all"),
        pytest.param(
            {"prefect.flow-run.Completed"},
            "prefect.task-run.Completed",
            False,
            id="unrelated-event",
        ),
    ],
)
def test_event_patterns_with_related_name(
    completion_automation: Automation,
    completion_event: ReceivedEvent,
    expect: set[str],
    event_name: str,
    matches: bool,
):
    completion_automation.trigger.expect = expect
    completion_automation.trigger.after = {"prefect.flow-run.Pending"}
    triggers.load_automation(completion_automation)
    event = completion_event.model_copy(update={"event": event_name})

    assert list(triggers.find_interested_triggers(event)) == (
        [completion_automation.trigger] if matches else []
    )


def test_exact_and_wildcard_name_filters_can_match_the_same_event(
    completion_automation: Automation,
    completion_event: ReceivedEvent,
):
    automations = [
        Automation(
            name=name,
            trigger=EventTrigger(
                expect={"prefect.flow-run.Completed"},
                match_related={"prefect.resource.name": name},
                posture=Posture.Reactive,
                threshold=1,
            ),
            actions=[actions.DoNothing()],
        )
        for name in ("deployment-*", "deployment-1")
    ]
    triggers.load_automation(completion_automation)
    for automation in automations:
        triggers.load_automation(automation)

    assert {
        trigger.id for trigger in triggers.find_interested_triggers(completion_event)
    } == {completion_automation.trigger.id, automations[0].trigger.id}


def test_forgetting_compound_automation_removes_name_matches(
    completion_event: ReceivedEvent,
):
    automation = Automation(
        name="Compound names",
        trigger=CompoundTrigger(
            require="all",
            within=timedelta(minutes=1),
            triggers=[
                EventTrigger(
                    expect={"prefect.flow-run.Completed"},
                    match_related={"prefect.resource.name": name},
                    posture=Posture.Reactive,
                    threshold=1,
                )
                for name in ("deployment-0", "deployment-1")
            ],
        ),
        actions=[actions.DoNothing()],
    )
    triggers.load_automation(automation)
    assert len(triggers.find_interested_triggers(completion_event)) == 1

    triggers.forget_automation(automation.id)

    assert not triggers.find_interested_triggers(completion_event)
