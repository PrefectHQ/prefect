"""Test that automation changes trigger notifications."""

import asyncio
from unittest.mock import patch
from uuid import UUID, uuid4

import orjson
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect._internal.testing import retry_asserts
from prefect.server.events.actions import DoNothing
from prefect.server.events.models.automations import (
    AUTOMATION_CHANGES_CHANNEL,
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
from prefect.server.events.triggers import listen_for_automation_changes
from prefect.server.utilities.database import get_dialect
from prefect.settings import PREFECT_API_SERVICES_TRIGGERS_ENABLED, temporary_settings

pytestmark = pytest.mark.clear_db


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
    and verify cache updates happen correctly.
    """
    from prefect.server.events import triggers
    from prefect.server.utilities.database import get_dialect

    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
        # Clear any existing automations for a clean test
        triggers.automations_by_id.clear()
        triggers.triggers.clear()

        # Check if we're using PostgreSQL
        dialect_name = get_dialect(automations_session.sync_session).name
        is_postgres = dialect_name == "postgresql"

        # Create automation
        created = await create_automation(automations_session, sample_automation)
        await automations_session.commit()
        assert created.id is not None

        # For PostgreSQL, manually trigger cache update since listener isn't running in tests
        if is_postgres:
            from prefect.server.events.triggers import automation_changed

            await automation_changed(created.id, "automation__created")
        else:
            # Allow time for SQLite after_commit handler
            await asyncio.sleep(0.1)

        # Verify automation was loaded into cache
        assert created.id in triggers.automations_by_id
        assert len(triggers.triggers) > 0  # Should have at least one trigger

        # Update automation
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

        # For PostgreSQL, manually trigger cache update
        if is_postgres:
            await automation_changed(created.id, "automation__updated")
        else:
            # Allow time for SQLite after_commit handler
            await asyncio.sleep(0.1)

        # Verify automation was updated in cache
        assert created.id in triggers.automations_by_id
        cached_automation = triggers.automations_by_id[created.id]
        assert cached_automation.name == "Updated Name"

        # Delete automation
        result = await delete_automation(automations_session, created.id)
        await automations_session.commit()
        assert result is True

        # For PostgreSQL, manually trigger cache update
        if is_postgres:
            await automation_changed(created.id, "automation__deleted")
        else:
            # Allow time for SQLite after_commit handler
            await asyncio.sleep(0.1)

        # Verify automation was removed from cache
        assert created.id not in triggers.automations_by_id


async def test_automation_listener_receives_notifications_and_processes_them(
    automations_session: AsyncSession, sample_automation: Automation
):
    """Test that the listener receives notifications and processes them correctly.

    This test validates:
    1. NOTIFY is sent when automations are created/updated/deleted
    2. The listener receives these notifications
    3. The automation_changed function is called with correct parameters
    """
    if get_dialect(automations_session.sync_session).name != "postgresql":
        pytest.skip("This test requires PostgreSQL for NOTIFY/LISTEN")

    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
        # Track all calls to automation_changed
        automation_changed_calls = []

        async def mock_automation_changed(automation_id: UUID, event: str) -> None:
            automation_changed_calls.append((automation_id, event))

        with patch(
            "prefect.server.events.triggers.automation_changed", mock_automation_changed
        ):
            # Start the listener
            listener_task = asyncio.create_task(listen_for_automation_changes())

            try:
                # Postgres only delivers a NOTIFY to connections that are already
                # listening, so send probes until one comes back to confirm the
                # listener is subscribed before making any real changes
                probe_id = uuid4()
                probe_payload = orjson.dumps(
                    {"automation_id": str(probe_id), "event_type": "created"}
                ).decode()
                while not any(call[0] == probe_id for call in automation_changed_calls):
                    await automations_session.execute(
                        sa.text(
                            f"NOTIFY {AUTOMATION_CHANGES_CHANNEL}, '{probe_payload}'"
                        )
                    )
                    await automations_session.commit()
                    await asyncio.sleep(0.1)

                # Create automation - should trigger "created" notification
                created = await create_automation(
                    automations_session, sample_automation
                )
                await automations_session.commit()

                # Update automation - should trigger "updated" notification
                update = AutomationUpdate(
                    name="Updated Name",
                    description="Updated",
                    enabled=True,
                    trigger=created.trigger,
                    actions=created.actions,
                )
                await update_automation(automations_session, update, created.id)
                await automations_session.commit()

                # Delete automation - should trigger "deleted" notification
                await delete_automation(automations_session, created.id)
                await automations_session.commit()

                # Retry assertions to handle NOTIFY propagation delays under load
                async for attempt in retry_asserts(max_attempts=10, delay=0.25):
                    with attempt:
                        calls = [
                            call
                            for call in automation_changed_calls
                            if call[0] == created.id
                        ]
                        assert calls == [
                            (created.id, "automation__created"),
                            (created.id, "automation__updated"),
                            (created.id, "automation__deleted"),
                        ]

            finally:
                listener_task.cancel()
                try:
                    await listener_task
                except asyncio.CancelledError:
                    pass
