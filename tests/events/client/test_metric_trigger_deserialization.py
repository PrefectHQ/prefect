"""
Test for issue #18747: Metric Triggers aren't included in Automations Schema

This test ensures that metric triggers can be properly deserialized from API responses.
"""

import uuid

from prefect.events.schemas.automations import (
    Automation,
    MetricTrigger,
    MetricTriggerQuery,
    Posture,
)


def test_metric_trigger_deserialization():
    """Test that metric triggers can be deserialized from API-like data."""
    # This is the type of data that would come from the API
    test_data = {
        "id": str(uuid.uuid4()),
        "name": "Test Metric Automation",
        "description": "Test metric trigger validation",
        "enabled": True,
        "trigger": {
            "type": "metric",
            "posture": "Metric",
            "metric": {
                "name": "duration",
                "threshold": 100.0,
                "operator": ">",
                "range": 300.0,
                "firing_for": 300.0,
            },
            "match": {"prefect.resource.id": "prefect.flow-run.*"},
        },
        "actions": [],
    }

    # Should not raise validation error
    automation = Automation.model_validate(test_data)

    # Verify correct type
    assert isinstance(automation.trigger, MetricTrigger)
    assert automation.trigger.type == "metric"
    assert automation.trigger.posture == Posture.Metric

    # Verify metric details
    assert automation.trigger.metric.name.value == "duration"
    assert automation.trigger.metric.threshold == 100.0
    assert automation.trigger.metric.operator.value == ">"


def test_metric_trigger_round_trip():
    """Test that metric triggers can be serialized and deserialized."""
    # Create an automation with a metric trigger
    automation = Automation(
        id=uuid.uuid4(),
        name="Test Metric Automation",
        description="Test",
        enabled=True,
        trigger=MetricTrigger(
            posture=Posture.Metric,
            metric=MetricTriggerQuery(
                name="successes",
                threshold=10,
                operator="<",
                range=600.0,
                firing_for=300.0,
            ),
            match={"prefect.resource.id": "prefect.flow-run.*"},
        ),
        actions=[],
    )

    # Serialize and deserialize
    data = automation.model_dump()
    restored = Automation.model_validate(data)

    # Should maintain the same structure
    assert isinstance(restored.trigger, MetricTrigger)
    assert restored.trigger.type == "metric"
    assert restored.trigger.metric.name.value == "successes"
    assert restored.trigger.metric.threshold == 10


def test_trigger_type_discrimination():
    """Test that the discriminator correctly identifies metric triggers."""
    # Test with explicit type field
    data_with_type = {
        "id": str(uuid.uuid4()),
        "name": "Test",
        "trigger": {
            "type": "metric",
            "posture": "Metric",
            "metric": {
                "name": "lateness",
                "threshold": 5,
                "operator": ">",
                "range": 300.0,
                "firing_for": 300.0,
            },
        },
        "actions": [],
    }

    automation = Automation.model_validate(data_with_type)
    assert isinstance(automation.trigger, MetricTrigger)
    assert automation.trigger.type == "metric"
