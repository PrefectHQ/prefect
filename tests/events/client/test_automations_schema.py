"""Tests for client-side automation schema validation and deserialization."""

import uuid
from datetime import timedelta
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from prefect.events.actions import RunDeployment, UnknownAction
from prefect.events.schemas.automations import (
    Automation,
    AutomationCore,
    CompoundTrigger,
    EventTrigger,
    MetricTrigger,
    MetricTriggerQuery,
    Posture,
)


def test_metric_trigger_deserialization():
    """Test that metric triggers can be deserialized from API-like data (issue #18747)."""
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

    automation = Automation.model_validate(test_data)

    assert isinstance(automation.trigger, MetricTrigger)
    assert automation.trigger.type == "metric"
    assert automation.trigger.posture == Posture.Metric

    assert automation.trigger.metric.name.value == "duration"
    assert automation.trigger.metric.threshold == 100.0
    assert automation.trigger.metric.operator.value == ">"


def test_metric_trigger_round_trip():
    """Test that metric triggers can be serialized and deserialized."""
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

    data = automation.model_dump()
    restored = Automation.model_validate(data)

    assert isinstance(restored.trigger, MetricTrigger)
    assert restored.trigger.type == "metric"
    assert restored.trigger.metric.name.value == "successes"
    assert restored.trigger.metric.threshold == 10


def test_trigger_type_discrimination_with_metric():
    """Test that the discriminator correctly identifies metric triggers."""
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


class TestUnknownActions:
    """Prefect Cloud can return action types that this version does not know
    about, such as ones added to Cloud after this release"""

    @staticmethod
    def automation_data(**actions: list[dict]) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "name": "Automation with an unknown action",
            "trigger": {"type": "event", "posture": "Reactive", "expect": ["x"]},
            "actions": [],
            **actions,
        }

    def test_unknown_action_type_is_read_as_unknown_action(self):
        email = {
            "type": "send-email-notification",
            "emails": ["ops@example.com"],
            "subject": "Flow run failed",
            "body": "{{ flow_run.name }} failed",
        }
        automation = Automation.model_validate(
            self.automation_data(
                actions=[email, {"type": "run-deployment", "source": "inferred"}]
            )
        )

        unknown, known = automation.actions
        assert isinstance(unknown, UnknownAction)
        assert unknown.type == "send-email-notification"
        assert unknown.model_dump() == email
        assert unknown.describe_for_cli() == "Send email notification"
        assert isinstance(known, RunDeployment)

    def test_unknown_action_types_in_every_action_list(self):
        automation = Automation.model_validate(
            self.automation_data(
                actions=[{"type": "send-email-notification"}],
                actions_on_trigger=[{"type": "sla-violation"}],
                actions_on_resolve=[{"type": "pause-schedule-for-flow-run"}],
            )
        )

        assert isinstance(automation.actions[0], UnknownAction)
        assert isinstance(automation.actions_on_trigger[0], UnknownAction)
        assert isinstance(automation.actions_on_resolve[0], UnknownAction)

    def test_unknown_action_round_trips_unchanged(self):
        """`Automation.update` sends the automation back as an `AutomationCore`
        built from `model_dump`, so an unknown action must survive that"""
        sent = {
            "type": "send-email-notification",
            "emails": ["ops@example.com", "oncall@example.com"],
            "subject": "Flow run failed",
            "body": "{{ flow_run.name }} failed",
            "nested": {"key": ["value"]},
        }
        automation = Automation.model_validate(self.automation_data(actions=[sent]))

        core = AutomationCore(**automation.model_dump(exclude={"id", "owner_resource"}))

        assert isinstance(core.actions[0], UnknownAction)
        assert core.model_dump(mode="json")["actions"] == [sent]

    def test_invalid_known_action_still_fails_validation(self):
        """A known type with invalid fields is an error, not an unknown action"""
        with pytest.raises(ValidationError, match="deployment_id is required"):
            Automation.model_validate(
                self.automation_data(
                    actions=[{"type": "run-deployment", "source": "selected"}]
                )
            )

    def test_unknown_action_rejects_a_known_type(self):
        with pytest.raises(ValidationError, match="known action type"):
            UnknownAction(type="run-deployment")


ACTION_LISTS = ("actions", "actions_on_trigger", "actions_on_resolve")


class TestActionJSONSchema:
    """The generated JSON schema must accept the same actions as runtime parsing"""

    @staticmethod
    def automation_data(action_list: str, action: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": "example",
            "trigger": {"type": "event", "posture": "Reactive"},
            "actions": [],
            action_list: [action],
        }

    @staticmethod
    def schema_errors(data: dict[str, Any]) -> list[jsonschema.ValidationError]:
        validator = jsonschema.Draft202012Validator(AutomationCore.model_json_schema())
        return list(validator.iter_errors(data))

    @pytest.mark.parametrize("action_list", ACTION_LISTS)
    @pytest.mark.parametrize(
        "action",
        [
            {"type": "do-nothing"},
            {"type": "run-deployment", "source": "inferred"},
            {
                "type": "send-email-notification",
                "emails": ["ops@example.com"],
                "nested": {"key": ["value"]},
            },
        ],
        ids=["do-nothing", "run-deployment", "unknown"],
    )
    def test_valid_actions_match_the_schema(
        self, action_list: str, action: dict[str, Any]
    ):
        data = self.automation_data(action_list, action)

        core = AutomationCore.model_validate(data)

        assert self.schema_errors(data) == []
        assert self.schema_errors(core.model_dump(mode="json")) == []

    @pytest.mark.parametrize("action_list", ACTION_LISTS)
    def test_known_type_with_invalid_fields_does_not_match_the_schema(
        self, action_list: str
    ):
        data = self.automation_data(
            action_list, {"type": "change-flow-run-state", "state": 123}
        )

        with pytest.raises(ValidationError):
            AutomationCore.model_validate(data)
        assert self.schema_errors(data) != []


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_event_trigger_within_schema_publishes_its_lower_bound(mode: str):
    within = EventTrigger.model_json_schema(mode=mode)["properties"]["within"]
    validator = jsonschema.Draft202012Validator(within)

    assert not validator.is_valid(-5)
    assert validator.is_valid(0)


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_compound_trigger_within_schema_allows_negative_seconds(mode: str):
    trigger = CompoundTrigger.model_validate(
        {
            "triggers": [{"type": "event", "posture": "Reactive"}],
            "require": "all",
            "within": -5,
        }
    )
    assert trigger.within == timedelta(seconds=-5)

    schema = CompoundTrigger.model_json_schema(mode=mode)
    within = schema["$defs"]["CompoundTrigger"]["properties"]["within"]
    assert {"type": "number"} in within["anyOf"]
    assert "minimum" not in within
