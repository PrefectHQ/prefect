import json
from datetime import timedelta

import pytest

from prefect.server.events.schemas.automations import (
    AutomationCreate,
    CompoundTrigger,
    EventTrigger,
    Posture,
)


async def test_compound_trigger_requires_too_small():
    with pytest.raises(ValueError, match="require must be at least 1"):
        CompoundTrigger(
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
            require=0,
            within=timedelta(seconds=10),
        )


async def test_compound_trigger_requires_too_big():
    with pytest.raises(
        ValueError,
        match="require must be less than or equal to the number of triggers",
    ):
        CompoundTrigger(
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
            require=3,
            within=timedelta(seconds=10),
        )


def test_server_composite_triggers_validate_to_server_triggers():
    """
    Test that server-side composite triggers validate to server-side child triggers.

    This is a regression test for an issue observed where the childrn in composite
    triggers are parsed into their _client_ schemas, not their server ones.  Strangely,
    this test does _not_ reproduce the issue when run as part of the test suite, but it
    will when it is run from an Python isolated script.  This means the import order
    may be relevant to the issue.
    """

    # An example of an integration test automation that failed

    composite_trigger_info = {
        "name": "a compound automation",
        "trigger": {
            "type": "compound",
            "require": "all",
            "within": 60,
            "triggers": [
                {
                    "posture": "Reactive",
                    "expect": ["integration.example.event.A"],
                    "match": {
                        "prefect.resource.id": "integration:compound:b7083807-cdc8-4c72-89ed-40927a67f731"
                    },
                    "threshold": 1,
                    "within": 0,
                },
                {
                    "posture": "Reactive",
                    "expect": ["integration.example.event.B"],
                    "match": {
                        "prefect.resource.id": "integration:compound:b7083807-cdc8-4c72-89ed-40927a67f731"
                    },
                    "threshold": 1,
                    "within": 0,
                },
            ],
        },
        "actions": [{"type": "do-nothing"}],
    }
    automation_as_json = json.dumps(composite_trigger_info)
    trigger_as_json = json.dumps(composite_trigger_info["trigger"])

    assert CompoundTrigger.__module__ == "prefect.server.events.schemas.automations"
    assert EventTrigger.__module__ == "prefect.server.events.schemas.automations"

    # Parse the automation
    automation = AutomationCreate.model_validate(composite_trigger_info)
    assert isinstance(automation.trigger, CompoundTrigger), type(automation.trigger)
    assert isinstance(automation.trigger.triggers[0], EventTrigger), type(
        automation.trigger.triggers[0]
    )
    assert isinstance(automation.trigger.triggers[1], EventTrigger), type(
        automation.trigger.triggers[1]
    )

    # Parse from JSON
    automation = AutomationCreate.model_validate_json(automation_as_json)
    assert isinstance(automation.trigger, CompoundTrigger), type(automation.trigger)
    assert isinstance(automation.trigger.triggers[0], EventTrigger), type(
        automation.trigger.triggers[0]
    )
    assert isinstance(automation.trigger.triggers[1], EventTrigger), type(
        automation.trigger.triggers[1]
    )

    # Parse the trigger itself
    trigger = CompoundTrigger.model_validate(composite_trigger_info["trigger"])
    assert isinstance(trigger, CompoundTrigger), type(trigger)
    assert isinstance(trigger.triggers[0], EventTrigger), type(trigger.triggers[0])
    assert isinstance(trigger.triggers[1], EventTrigger), type(trigger.triggers[1])

    # And from JSON
    trigger = CompoundTrigger.model_validate_json(trigger_as_json)
    assert isinstance(trigger, CompoundTrigger), type(trigger)
    assert isinstance(trigger.triggers[0], EventTrigger), type(trigger.triggers[0])
    assert isinstance(trigger.triggers[1], EventTrigger), type(trigger.triggers[1])
