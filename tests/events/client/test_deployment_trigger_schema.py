import datetime
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from prefect.events import (
    AutomationCore,
    CompoundTrigger,
    EventTrigger,
    MetricTrigger,
    MetricTriggerQuery,
    Posture,
    SequenceTrigger,
)
from prefect.events.actions import RunDeployment
from prefect.events.schemas.deployment_triggers import (
    DeploymentCompoundTrigger,
    DeploymentEventTrigger,
    DeploymentMetricTrigger,
    DeploymentSequenceTrigger,
    DeploymentTriggerTypes,
)

deployment_trigger_adapter = TypeAdapter(DeploymentTriggerTypes)


def test_deployment_trigger_defaults_to_empty_reactive_trigger():
    trigger = deployment_trigger_adapter.validate_python(
        {"name": "A deployment automation"}
    )
    assert isinstance(trigger, DeploymentEventTrigger)
    trigger.set_deployment_id(uuid4())

    automation = trigger.as_automation()

    assert isinstance(automation.trigger, EventTrigger)
    assert automation.name == "A deployment automation"
    assert automation.trigger.posture == Posture.Reactive
    assert automation.trigger.threshold == 1
    assert automation.trigger.within == datetime.timedelta(0)
    assert automation.trigger.after == set()
    assert automation.trigger.expect == set()


def test_deployment_trigger_defaults_name_but_can_have_it_overridden():
    trigger = deployment_trigger_adapter.validate_python({})
    assert isinstance(trigger, DeploymentEventTrigger)

    deployment_id = uuid4()

    trigger.set_deployment_id(deployment_id)

    automation = trigger.as_automation()
    assert automation.name == f"Automation for deployment {deployment_id}"

    trigger.name = "A deployment automation"
    automation = trigger.as_automation()

    assert automation.name == "A deployment automation"


def test_deployment_trigger_defaults_to_reactive_event_trigger():
    trigger = deployment_trigger_adapter.validate_python(
        {"name": "A deployment automation"}
    )
    assert isinstance(trigger, DeploymentEventTrigger)
    trigger.set_deployment_id(uuid4())

    automation = trigger.as_automation()

    assert automation == AutomationCore(
        name="A deployment automation",
        description="",
        enabled=True,
        trigger=EventTrigger(
            posture=Posture.Reactive,
            threshold=1,
            within=datetime.timedelta(0),
        ),
        actions=[
            RunDeployment(
                type="run-deployment",
                source="selected",
                parameters=None,
                deployment_id=trigger._deployment_id,
            )
        ],
        owner_resource=f"prefect.deployment.{trigger._deployment_id}",
    )


def test_deployment_trigger_proactive_trigger_with_defaults():
    trigger = deployment_trigger_adapter.validate_python(
        {"name": "A deployment automation", "posture": "Proactive"},
    )
    assert isinstance(trigger, DeploymentEventTrigger)
    trigger.set_deployment_id(uuid4())

    automation = trigger.as_automation()

    assert automation == AutomationCore(
        name="A deployment automation",
        description="",
        enabled=True,
        trigger=EventTrigger(
            posture=Posture.Proactive,
            threshold=1,
            within=datetime.timedelta(seconds=10),
        ),
        actions=[
            RunDeployment(
                type="run-deployment",
                source="selected",
                parameters=None,
                deployment_id=trigger._deployment_id,
            )
        ],
        owner_resource=f"prefect.deployment.{trigger._deployment_id}",
    )


def test_deployment_reactive_trigger_disallows_negative_withins():
    with pytest.raises(ValidationError, match="greater than or equal to 0 seconds"):
        deployment_trigger_adapter.validate_python(
            {
                "name": "A deployment automation",
                "posture": "Reactive",
                "within": -1,
            },
        )


def test_deployment_proactive_trigger_disallows_negative_withins():
    with pytest.raises(ValidationError, match="greater than or equal to 10 seconds"):
        deployment_trigger_adapter.validate_python(
            {
                "name": "A deployment automation",
                "posture": "Proactive",
                "within": -1,
            },
        )


def test_deployment_trigger_proactive_trigger_disallows_short_withins():
    with pytest.raises(ValidationError, match="greater than or equal to 10 seconds"):
        deployment_trigger_adapter.validate_python(
            {
                "name": "A deployment automation",
                "posture": "Proactive",
                "within": 9,
            },
        )


def test_deployment_trigger_metric_trigger():
    trigger = deployment_trigger_adapter.validate_python(
        {
            "name": "A deployment automation",
            "posture": "Metric",
            "metric": {"name": "successes", "operator": "<", "threshold": 1},
        },
    )
    assert isinstance(trigger, DeploymentMetricTrigger)
    trigger.set_deployment_id(uuid4())

    automation = trigger.as_automation()

    assert automation == AutomationCore(
        name="A deployment automation",
        description="",
        enabled=True,
        trigger=MetricTrigger(
            metric=MetricTriggerQuery(name="successes", operator="<", threshold=1),
        ),
        actions=[
            RunDeployment(
                type="run-deployment",
                source="selected",
                parameters=None,
                deployment_id=trigger._deployment_id,
            )
        ],
        owner_resource=f"prefect.deployment.{trigger._deployment_id}",
    )


def test_compound_deployment_trigger_as_automation():
    trigger = deployment_trigger_adapter.validate_python(
        {
            "name": "A deployment automation",
            "type": "compound",
            "require": "all",
            "within": 42,
            "triggers": [
                {"expect": ["foo.bar"]},
                {"expect": ["buz.baz"]},
            ],
        },
    )
    assert isinstance(trigger, DeploymentCompoundTrigger)
    trigger.set_deployment_id(uuid4())

    automation = trigger.as_automation()

    assert automation == AutomationCore(
        name="A deployment automation",
        description="",
        enabled=True,
        trigger=CompoundTrigger(
            require="all",
            triggers=[
                EventTrigger(
                    posture=Posture.Reactive,
                    threshold=1,
                    within=datetime.timedelta(0),
                    expect=["foo.bar"],
                ),
                EventTrigger(
                    posture=Posture.Reactive,
                    threshold=1,
                    within=datetime.timedelta(0),
                    expect=["buz.baz"],
                ),
            ],
            within=datetime.timedelta(seconds=42),
        ),
        actions=[
            RunDeployment(
                type="run-deployment",
                source="selected",
                parameters=None,
                deployment_id=trigger._deployment_id,
            )
        ],
        owner_resource=f"prefect.deployment.{trigger._deployment_id}",
    )


def test_deeply_nested_compound_deployment_trigger_as_automation():
    trigger = deployment_trigger_adapter.validate_python(
        {
            "name": "A deployment automation",
            "type": "compound",
            "require": "all",
            "within": 42,
            "triggers": [
                {
                    "type": "compound",
                    "require": "any",
                    "triggers": [
                        {"expect": ["foo.bar"]},
                        {"expect": ["buz.baz"]},
                    ],
                },
                {
                    "type": "sequence",
                    "triggers": [
                        {"expect": ["flibbdy.jibbidy"]},
                        {"expect": ["floobity.bop"]},
                    ],
                },
            ],
        },
    )
    assert isinstance(trigger, DeploymentCompoundTrigger)
    trigger.set_deployment_id(uuid4())

    automation = trigger.as_automation()

    assert automation == AutomationCore(
        name="A deployment automation",
        description="",
        enabled=True,
        trigger=CompoundTrigger(
            require="all",
            triggers=[
                CompoundTrigger(
                    require="any",
                    triggers=[
                        EventTrigger(
                            posture=Posture.Reactive,
                            threshold=1,
                            within=datetime.timedelta(0),
                            expect=["foo.bar"],
                        ),
                        EventTrigger(
                            posture=Posture.Reactive,
                            threshold=1,
                            within=datetime.timedelta(0),
                            expect=["buz.baz"],
                        ),
                    ],
                ),
                SequenceTrigger(
                    triggers=[
                        EventTrigger(
                            posture=Posture.Reactive,
                            threshold=1,
                            within=datetime.timedelta(0),
                            expect=["flibbdy.jibbidy"],
                        ),
                        EventTrigger(
                            posture=Posture.Reactive,
                            threshold=1,
                            within=datetime.timedelta(0),
                            expect=["floobity.bop"],
                        ),
                    ],
                ),
            ],
            within=datetime.timedelta(seconds=42),
        ),
        actions=[
            RunDeployment(
                type="run-deployment",
                source="selected",
                parameters=None,
                deployment_id=trigger._deployment_id,
            )
        ],
        owner_resource=f"prefect.deployment.{trigger._deployment_id}",
    )


def test_sequence_deployment_trigger_as_automation():
    trigger = deployment_trigger_adapter.validate_python(
        {
            "name": "A deployment automation",
            "type": "sequence",
            "triggers": [
                {"posture": "Reactive", "expect": ["foo.bar"]},
                {"posture": "Reactive", "expect": ["buz.baz"]},
            ],
        },
    )
    assert isinstance(trigger, DeploymentSequenceTrigger)
    trigger.set_deployment_id(uuid4())

    automation = trigger.as_automation()

    assert automation == AutomationCore(
        name="A deployment automation",
        description="",
        enabled=True,
        trigger=SequenceTrigger(
            triggers=[
                EventTrigger(
                    posture=Posture.Reactive,
                    threshold=1,
                    within=datetime.timedelta(0),
                    expect=["foo.bar"],
                ),
                EventTrigger(
                    posture=Posture.Reactive,
                    threshold=1,
                    within=datetime.timedelta(0),
                    expect=["buz.baz"],
                ),
            ]
        ),
        actions=[
            RunDeployment(
                type="run-deployment",
                source="selected",
                parameters=None,
                deployment_id=trigger._deployment_id,
            )
        ],
        owner_resource=f"prefect.deployment.{trigger._deployment_id}",
    )
