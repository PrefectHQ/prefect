import asyncio
from datetime import timedelta
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events import actions, triggers
from prefect.server.events.models import automations
from prefect.server.events.schemas.automations import (
    Automation,
    AutomationCore,
    AutomationUpdate,
    EventTrigger,
    Posture,
)
from prefect.settings import PREFECT_API_SERVICES_TRIGGERS_ENABLED, temporary_settings


@pytest.fixture(autouse=True)
def enable_triggers():
    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
        yield


@pytest.fixture
async def starting_automations(
    cleared_buckets,
    cleared_automations,
    automations_session: AsyncSession,
):
    await automations.create_automation(
        automations_session,
        Automation(
            id=uuid4(),
            name="example automation 1",
            enabled=True,
            trigger=EventTrigger(
                expect={"stuff.happened"},
                match={"prefect.resource.id": "foo"},
                posture=Posture.Reactive,
                threshold=0,
                within=timedelta(seconds=10),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    await automations.create_automation(
        automations_session,
        Automation(
            id=uuid4(),
            name="example automation 2",
            enabled=True,
            trigger=EventTrigger(
                expect={"stuff.happened"},
                match={"prefect.resource.id": "bar"},
                posture=Posture.Reactive,
                threshold=0,
                within=timedelta(seconds=10),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    await automations_session.commit()


async def test_loads_new_automations_on_changes(
    starting_automations,
    automations_session: AsyncSession,
):
    async with triggers.consumer():
        await asyncio.sleep(0.1)

        new_automation = await automations.create_automation(
            automations_session,
            Automation(
                name="A new one!",
                trigger=EventTrigger(posture=Posture.Reactive, threshold=1),
                actions=[actions.DoNothing()],
                enabled=True,
            ),
        )
        await automations_session.commit()

        # committing the automation above will trigger the notification to the
        # triggers service, just wait a brief moment for it to make it through the
        # notification plumbing
        await asyncio.sleep(0.1)

        assert new_automation.id in triggers.automations_by_id

        (trigger,) = new_automation.triggers_of_type(EventTrigger)
        assert trigger.id in triggers.triggers


async def test_gracefully_handles_create_then_delete(
    starting_automations,
    automations_session: AsyncSession,
):
    async with triggers.consumer():
        await asyncio.sleep(0.1)

        new_automation = await automations.create_automation(
            automations_session,
            Automation(
                name="A new one!",
                trigger=EventTrigger(posture=Posture.Reactive, threshold=1),
                actions=[actions.DoNothing()],
                enabled=True,
            ),
        )
        await automations.delete_automation(automations_session, new_automation.id)
        await automations_session.commit()

        # committing the automation above will trigger the notification to the
        # triggers service, just wait a brief moment for it to make it through the
        # notification plumbing
        await asyncio.sleep(0.1)

        assert new_automation.id not in triggers.automations_by_id

        (trigger,) = new_automation.triggers_of_type(EventTrigger)
        assert trigger.id not in triggers.triggers


async def test_updates_existing_automations_on_changes(
    starting_automations,
    automations_session: AsyncSession,
):
    async with triggers.consumer():
        await asyncio.sleep(0.1)

        automation_to_update = list(triggers.automations_by_id.values())[0]
        assert automation_to_update.enabled
        assert automation_to_update.name != "Well this is new"

        update_to_apply = AutomationUpdate(
            **AutomationCore(**automation_to_update.model_dump()).model_dump()
        )
        update_to_apply.name = "Well this is new"

        await automations.update_automation(
            automations_session,
            update_to_apply,
            automation_to_update.id,
        )
        await automations_session.commit()

        # committing the automation above will trigger the notification to the
        # triggers service, just wait a brief moment for it to make it through the
        # notification plumbing
        await asyncio.sleep(0.1)

        updated = triggers.automations_by_id[automation_to_update.id]
        assert updated.name == "Well this is new"

        (trigger,) = automation_to_update.triggers_of_type(EventTrigger)
        assert trigger.id in triggers.triggers


async def test_removes_disabled_automations(
    starting_automations,
    automations_session: AsyncSession,
):
    async with triggers.consumer():
        await asyncio.sleep(0.1)

        automation = list(triggers.automations_by_id.values())[0]
        assert automation.enabled

        update_to_apply = AutomationUpdate(
            **AutomationCore(**automation.model_dump()).model_dump()
        )
        update_to_apply.enabled = False

        await automations.update_automation(
            automations_session,
            update_to_apply,
            automation.id,
        )
        await automations_session.commit()

        # committing the automation above will trigger the notification to the
        # triggers service, just wait a brief moment for it to make it through the
        # notification plumbing
        await asyncio.sleep(0.1)

        assert automation.id not in triggers.automations_by_id

        (trigger,) = automation.triggers_of_type(EventTrigger)
        assert trigger.id not in triggers.triggers


async def test_removes_existing_automations_on_changes(
    starting_automations,
    automations_session: AsyncSession,
):
    async with triggers.consumer():
        await asyncio.sleep(0.1)

        automation = list(triggers.automations_by_id.values())[0]

        await automations.delete_automation(
            automations_session,
            automation.id,
        )
        await automations_session.commit()

        # committing the automation above will trigger the notification to the
        # triggers service, just wait a brief moment for it to make it through the
        # notification plumbing
        await asyncio.sleep(0.1)

        assert automation.id not in triggers.automations_by_id

        (trigger,) = automation.triggers_of_type(EventTrigger)
        assert trigger.id not in triggers.triggers


async def test_gracefully_handles_errors_during_changes(
    starting_automations, automations_session: AsyncSession
):
    async with triggers.consumer():
        await asyncio.sleep(0.1)

        automation = list(triggers.automations_by_id.values())[0]

        # do it once and force an error to occur during the processing of the change
        with mock.patch.object(
            triggers, "forget_automation", side_effect=Exception
        ) as m:
            await automations.delete_automation(
                automations_session,
                automation.id,
            )
            await automations_session.commit()

            # committing the automation above will trigger the notification to the
            # triggers service, just wait a brief moment for it to make it through the
            # notification plumbing
            await asyncio.sleep(0.1)

            m.assert_called_once_with(automation.id)

        assert automation.id in triggers.automations_by_id

        (trigger,) = automation.triggers_of_type(EventTrigger)
        assert trigger.id in triggers.triggers

        # now do it again where no error will occur and ensure it takes effect
        automation = list(triggers.automations_by_id.values())[1]

        await automations.delete_automation(
            automations_session,
            automation.id,
        )
        await automations_session.commit()

        # committing the automation above will trigger the notification to the
        # triggers service, just wait a brief moment for it to make it through the
        # notification plumbing
        await asyncio.sleep(0.1)

        assert automation.id not in triggers.automations_by_id

        (trigger,) = automation.triggers_of_type(EventTrigger)
        assert trigger.id not in triggers.triggers
