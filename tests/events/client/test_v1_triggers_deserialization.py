"""
Tests that confirm that the deserialization of the triggers stored in the "v1" style
(prior to the introduction of various subclasses) can be deserialized into "v2" classes.

These tests will help to ensure that as we're refactoring Triggers as part of
#raft-fan-in-triggers
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Set, Type

import orjson
import pytest

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
    from pydantic.v1 import Field
else:
    import pydantic
    from pydantic import Field

from prefect.events.schemas.automations import (
    EventTrigger,
    MetricTrigger,
    MetricTriggerQuery,
    Posture,
    ResourceSpecification,
    ResourceTrigger,
    TriggerTypes,
)
from prefect.server.utilities.schemas import PrefectBaseModel


class V1Trigger(PrefectBaseModel):
    """A copy of the original events.automations.Trigger class for reference."""

    match: ResourceSpecification = Field(  # pragma: no branch
        default_factory=lambda: ResourceSpecification.parse_obj({}),
        description="Labels for resources which this Automation will match.",
    )
    match_related: ResourceSpecification = Field(  # pragma: no branch
        default_factory=lambda: ResourceSpecification.parse_obj({}),
        description="Labels for related resources which this Automation will match.",
    )

    after: Set[str] = Field(
        default_factory=set,
        description=(
            "The event(s) which must first been seen to start this automation.  If "
            "empty, then start this Automation immediately.  Events may include "
            "trailing wildcards, like `prefect.flow-run.*`"
        ),
    )
    expect: Set[str] = Field(
        default_factory=set,
        description=(
            "The event(s) this automation is expecting to see.  If empty, this "
            "automation will match any event.  Events may include trailing wildcards, "
            "like `prefect.flow-run.*`"
        ),
    )

    for_each: Set[str] = Field(
        default_factory=set,
        description=(
            "Evaluate the Automation separately for each distinct value of these labels "
            "on the resource.  By default, labels refer to the primary resource of the "
            "triggering event.  You may also refer to labels from related "
            "resources by specifying `related:<role>:<label>`.  This will use the "
            "value of that label for the first related resource in that role.  For "
            'example, `"for_each": ["related:flow:prefect.resource.id"]` would '
            "evaluate the automation for each flow."
        ),
    )
    posture: Posture = Field(
        ...,
        description=(
            "The posture of this Automation, either Reactive or Proactive.  Reactive "
            "automations respond to the _presence_ of the expected events, while "
            "Proactive automations respond to the _absence_ of those expected events. "
            "Metric automations are unique in that they are not triggered by the "
            "presence or absence of events, but rather by periodically evaluating a "
            "configured metric query."
        ),
    )
    threshold: int = Field(
        1,
        description=(
            "The number of events required for this Automation to trigger (for "
            "Reactive automations), or the number of events expected (for Proactive "
            "automations)"
        ),
    )
    within: timedelta = Field(
        timedelta(0),
        minimum=0.0,
        exclusiveMinimum=False,
        description=(
            "The time period over which the events must occur.  For Reactive triggers, "
            "this may be as low as 0 seconds, but must be at least 10 seconds for "
            "Proactive triggers"
        ),
    )

    metric: Optional[MetricTriggerQuery] = Field(
        None,
        description=(
            "The metric query configuration for this trigger. "
            "This field is only applicable to Metric automations."
        ),
    )


def pytest_generate_tests(metafunc: pytest.Metafunc):
    fixtures = set(metafunc.fixturenames)

    if fixtures.issuperset({"trigger_type", "json"}):
        metafunc.parametrize(
            "trigger_type, json",
            [
                pytest.param(
                    MetricTrigger if kind == "metric-triggers" else EventTrigger,
                    orjson.loads(json),
                    id=f"{kind}-{i}",
                )
                for kind, examples in V1_TRIGGERS.items()
                for i, json in enumerate(examples)
            ],
        )


def test_deserializing_as_v1_trigger(
    trigger_type: Type[ResourceTrigger], json: Dict[str, Any]
):
    """A baseline test that just confirms that all of the example JSON triggers are
    actually parseable as v1 Triggers."""
    v1_trigger = V1Trigger.parse_obj(json)
    assert isinstance(v1_trigger, V1Trigger)


def assert_triggers_match(v1_trigger: V1Trigger, v2_trigger: ResourceTrigger):
    assert isinstance(v1_trigger, V1Trigger)
    assert isinstance(v2_trigger, ResourceTrigger)

    assert v2_trigger.match == v1_trigger.match
    assert v2_trigger.match_related == v1_trigger.match_related

    if isinstance(v2_trigger, EventTrigger):
        assert v2_trigger.type == "event"
        assert v2_trigger.dict()["type"] == "event"

        assert v1_trigger.posture in {Posture.Reactive, Posture.Proactive}
        assert v2_trigger.posture == v1_trigger.posture

        assert v2_trigger.after == v1_trigger.after
        assert v2_trigger.expect == v1_trigger.expect
        assert v2_trigger.for_each == v1_trigger.for_each
        assert v2_trigger.threshold == v1_trigger.threshold
        assert v2_trigger.within == v1_trigger.within

    elif isinstance(v2_trigger, MetricTrigger):  # pragma: no branch
        assert v2_trigger.type == "metric"
        assert v2_trigger.dict()["type"] == "metric"

        assert v1_trigger.posture == Posture.Metric
        assert v2_trigger.posture == Posture.Metric

        assert v2_trigger.metric == v1_trigger.metric


def test_deserializing_as_v2_trigger(
    trigger_type: Type[ResourceTrigger], json: Dict[str, Any]
):
    """A test that confirms that the example JSON triggers can be deserialized directly
    into their corresponding v2 classes."""
    v1_trigger = V1Trigger.parse_obj(json)
    v2_trigger = trigger_type.parse_obj(json)

    assert isinstance(v2_trigger, trigger_type)

    assert_triggers_match(v1_trigger, v2_trigger)


def test_deserializing_polymorphic(
    trigger_type: Type[ResourceTrigger], json: Dict[str, Any]
):
    """A test that confirms that the example JSON triggers can be deserialized into
    their corresponding v2 classes using polymorphism."""
    v1_trigger = V1Trigger.parse_obj(json)
    v2_trigger: ResourceTrigger = pydantic.parse_obj_as(TriggerTypes, json)  # type: ignore[arg-type]

    assert isinstance(v2_trigger, trigger_type)

    assert_triggers_match(v1_trigger, v2_trigger)


class Referencer(PrefectBaseModel):
    trigger: TriggerTypes


def test_deserializing_into_polymorphic_attribute(
    trigger_type: Type[ResourceTrigger], json: Dict[str, Any]
):
    """A test that confirms that the example JSON triggers can be deserialized into
    their corresponding v2 classes when referenced in an attribute."""
    v1_trigger = V1Trigger.parse_obj(json)

    v2_container = Referencer.parse_obj({"trigger": json})
    v2_trigger = v2_container.trigger

    assert isinstance(v2_trigger, trigger_type)

    assert_triggers_match(v1_trigger, v2_trigger)


class Container(PrefectBaseModel):
    triggers: List[TriggerTypes]


def test_deserializing_into_polymorphic_collection_attribute():
    """A test that confirms that the example JSON triggers can be deserialized into
    their corresponding v2 classes when referenced in a mixed collection."""
    json = [
        orjson.loads(trigger)
        for trigger in V1_TRIGGERS["event-triggers"] + V1_TRIGGERS["metric-triggers"]
    ]
    v1_triggers = pydantic.parse_obj_as(List[V1Trigger], json)

    v2_container = Container.parse_obj({"triggers": json})
    v2_triggers = v2_container.triggers

    for v1_trigger, v2_trigger in zip(v1_triggers, v2_triggers):
        assert_triggers_match(v1_trigger, v2_trigger)


# The following triggers were sampled from Prefect Cloud as of 2024-03-06.  Feel free to
# add any additional examples that may represent edge cases.

V1_TRIGGERS = {
    "event-triggers": [
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.Crashed"], "within": 10.0, "posture": "Reactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.632cee21-fea1-490c-91cc-d97abbcf6870"], "prefect.resource.role": "flow"}}""",
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.Late"], "within": 10.0, "posture": "Reactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.158dd08b-c0fb-4898-af4a-d7d2737bb4ba"], "prefect.resource.role": "flow"}}""",
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.*"], "within": 10.0, "posture": "Reactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {}}""",
        """{"after": [], "match": {"prefect.resource.id": "file.normalized-data.*"}, "expect": ["file.uploaded"], "metric": null, "within": 0.0, "posture": "Reactive", "for_each": [], "threshold": 1, "match_related": {}}""",
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.Running"], "metric": null, "within": 10.0, "posture": "Reactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.64767c2a-f6b6-44b6-8a84-aaa2d21534ae"], "prefect.resource.role": "flow"}}""",
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.Crashed", "prefect.flow-run.TimedOut", "prefect.flow-run.Failed"], "metric": null, "within": 10.0, "posture": "Reactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.ab9279f8-0c24-4ff0-b3c4-a9562afcf30f", "prefect.flow.1b384893-b552-4cfa-9496-c4a7bc99f27d", "prefect.flow.bf237a78-d460-4e84-9fb7-f6ee02f2f3d8"], "prefect.resource.role": "flow"}}""",
        """{"after": ["prefect.flow-run.Late"], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.*"], "within": 180.0, "posture": "Proactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {}}""",
        """{"after": ["prefect.flow-run.Pending", "prefect.flow-run.Late"], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.*"], "within": 1800.0, "posture": "Proactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {}}""",
        """{"after": ["prefect.flow-run.Pending"], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.*"], "within": 3600.0, "posture": "Proactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.80544b38-1f76-4ddf-95e8-4910b4b1fbf1"], "prefect.resource.role": "flow"}}""",
        """{"after": ["prefect.flow-run.Running"], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.*"], "metric": null, "within": 900.0, "posture": "Proactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.bf2a955a-7394-41eb-b690-f7f54dd6d194"], "prefect.resource.role": "flow"}}""",
        """{"after": ["prefect.flow-run.Running"], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.*"], "metric": null, "within": 900.0, "posture": "Proactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.5ff0e4e7-7da8-476e-b9df-91f3069375d8", "prefect.flow.14c16080-21f8-4d2f-ba0d-aeff18f5e2d1", "prefect.flow.8ca556d3-6c7b-4598-80bf-5bff306931da", "..."], "prefect.resource.role": "flow"}}""",
        """{"after": ["prefect.flow-run.Late", "prefect.flow-run.Pending"], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": ["prefect.flow-run.*"], "metric": null, "within": 600.0, "posture": "Proactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.ab9279f8-0c24-4ff0-b3c4-a9562afcf30f", "prefect.flow.1b384893-b552-4cfa-9496-c4a7bc99f27d", "..."], "prefect.resource.role": "flow"}}""",
        """{"after": [], "match": {"prefect.resource.id": "prefect.work-queue.*"}, "expect": ["prefect.work-queue.unhealthy"], "metric": null, "within": 300.0, "posture": "Proactive", "for_each": ["prefect.resource.id"], "threshold": 1, "match_related": {}}""",
    ],
    "metric-triggers": [
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": [], "metric": {"name": "successes", "range": 10800.0, "operator": "<", "threshold": 0.99, "firing_for": 21600.0}, "within": 0.0, "posture": "Metric", "for_each": [], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.tag.3-hour-sla"], "prefect.resource.role": "tag"}}""",
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": [], "metric": {"name": "successes", "range": 3600.0, "operator": "<", "threshold": 0.99, "firing_for": 7200.0}, "within": 0.0, "posture": "Metric", "for_each": [], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.tag.hourly-sla"], "prefect.resource.role": "tag"}}""",
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": [], "metric": {"name": "lateness", "range": 3600.0, "operator": ">", "threshold": 1200.0, "firing_for": 600.0}, "within": 0.0, "posture": "Metric", "for_each": [], "threshold": 1, "match_related": {}}""",
        """{"after": [], "match": {"prefect.resource.id": "prefect.flow-run.*"}, "expect": [], "metric": {"name": "successes", "range": 86400.0, "operator": "<", "threshold": 0.9, "firing_for": 60.0}, "within": 0.0, "posture": "Metric", "for_each": [], "threshold": 1, "match_related": {"prefect.resource.id": ["prefect.flow.a447ae13-3e6e-4ed2-9248-88addc3af2ca"], "prefect.resource.role": "flow"}}""",
    ],
}
