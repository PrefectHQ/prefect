import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events.clients import AssertingEventsClient
from prefect.server.events.models import automations
from prefect.server.events.schemas.automations import (
    Automation,
    AutomationPartialUpdate,
)

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def reset_events():
    AssertingEventsClient.reset()


class TestAutomationLifecycleEvents:
    async def test_create_automation_emits_created_event(
        self, automations_session: AsyncSession, arachnophobia: Automation
    ):
        created = await automations.create_automation(
            automations_session, arachnophobia
        )
        await automations_session.commit()

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.automation.created",
            resource={
                "prefect.resource.id": f"prefect.automation.{created.id}",
                "prefect.resource.name": created.name,
            },
            payload={
                "name": "React immediately to spiders",
                "enabled": True,
            },
        )

    async def test_update_automation_emits_updated_event(
        self, automations_session: AsyncSession, arachnophobia: Automation
    ):
        created = await automations.create_automation(
            automations_session, arachnophobia
        )
        await automations_session.commit()
        AssertingEventsClient.reset()

        await automations.update_automation(
            automations_session,
            AutomationPartialUpdate(enabled=False),
            created.id,
        )
        await automations_session.commit()

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.automation.updated",
            resource={
                "prefect.resource.id": f"prefect.automation.{created.id}",
                "prefect.resource.name": created.name,
            },
            payload={
                "name": "React immediately to spiders",
                "enabled": False,
            },
        )

    async def test_delete_automation_emits_deleted_event(
        self, automations_session: AsyncSession, arachnophobia: Automation
    ):
        created = await automations.create_automation(
            automations_session, arachnophobia
        )
        await automations_session.commit()
        AssertingEventsClient.reset()

        deleted = await automations.delete_automation(automations_session, created.id)
        await automations_session.commit()
        assert deleted is True

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.automation.deleted",
            resource={
                "prefect.resource.id": f"prefect.automation.{created.id}",
                "prefect.resource.name": created.name,
            },
            payload={"name": "React immediately to spiders"},
        )

    async def test_update_nonexistent_automation_does_not_emit_event(
        self, automations_session: AsyncSession
    ):
        from uuid import uuid4

        result = await automations.update_automation(
            automations_session,
            AutomationPartialUpdate(enabled=False),
            uuid4(),
        )
        assert result is False

        AssertingEventsClient.assert_no_emitted_event_with(
            event="prefect.automation.updated",
        )
