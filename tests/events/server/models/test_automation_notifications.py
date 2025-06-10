"""Test that automation changes trigger notifications."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events.actions import DoNothing
from prefect.server.events.models.automations import (
    create_automation,
    delete_automation,
    update_automation,
)
from prefect.server.events.schemas.automations import (
    Automation,
    AutomationUpdate,
    EventTrigger,
    Posture,
)
from prefect.settings import PREFECT_API_SERVICES_TRIGGERS_ENABLED, temporary_settings


@pytest.fixture
def sample_automation() -> Automation:
    """Create a sample automation."""
    return Automation(
        name="Test Automation",
        description="Test",
        enabled=True,
        trigger=EventTrigger(
            expect={"test.event"},
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[DoNothing()],
    )


async def test_automation_crud_operations_complete_successfully(
    automations_session: AsyncSession, sample_automation: Automation
):
    """Test that automation CRUD operations work with NOTIFY enabled
    (for sqlite where it skips and postgres).
    """
    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
        created = await create_automation(automations_session, sample_automation)
        await automations_session.commit()
        assert created.id is not None

        update = AutomationUpdate(
            name="Updated Name",
            description="Updated",
            enabled=True,
            trigger=created.trigger,
            actions=created.actions,
        )
        result = await update_automation(automations_session, update, created.id)
        await automations_session.commit()
        assert result is True

        result = await delete_automation(automations_session, created.id)
        await automations_session.commit()
        assert result is True
