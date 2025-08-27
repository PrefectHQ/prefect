from datetime import timedelta

import pytest
from pydantic import ValidationError

from prefect.events.schemas.deployment_triggers import DeploymentEventTrigger


async def test_deployment_trigger_can_omit_schedule_after_field():
    """Test that the schedule_after field defaults to timedelta(0)"""
    trigger = DeploymentEventTrigger.model_validate(
        {
            "expect": ["foo"],
        }
    )
    assert trigger.schedule_after == timedelta(0)


async def test_deployment_trigger_accepts_schedule_after_field():
    """Test that the schedule_after field accepts various timedelta values"""
    trigger = DeploymentEventTrigger.model_validate(
        {
            "expect": ["foo"],
            "schedule_after": 3600,  # seconds
        }
    )
    assert trigger.schedule_after == timedelta(hours=1)

    trigger = DeploymentEventTrigger.model_validate(
        {
            "expect": ["foo"],
            "schedule_after": "PT2H",  # ISO 8601 duration
        }
    )
    assert trigger.schedule_after == timedelta(hours=2)


async def test_deployment_trigger_rejects_negative_schedule_after():
    """Test that negative schedule_after values are rejected"""
    with pytest.raises(ValidationError, match="schedule_after must be non-negative"):
        DeploymentEventTrigger.model_validate(
            {
                "expect": ["foo"],
                "schedule_after": -3600,
            }
        )


async def test_deployment_trigger_passes_schedule_after_to_action():
    """Test that deployment trigger passes schedule_after to RunDeployment action"""
    from uuid import uuid4

    trigger = DeploymentEventTrigger.model_validate(
        {
            "expect": ["foo"],
            "schedule_after": timedelta(hours=1),
        }
    )

    deployment_id = uuid4()
    trigger.set_deployment_id(deployment_id)

    actions = trigger.actions()
    assert len(actions) == 1

    action = actions[0]
    assert action.schedule_after == timedelta(hours=1)
