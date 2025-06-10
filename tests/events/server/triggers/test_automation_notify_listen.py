"""Tests for automation cache synchronization via PostgreSQL NOTIFY/LISTEN."""

import asyncio
from datetime import timedelta
from unittest import mock
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import orjson
import pytest

from prefect.server.events.actions import DoNothing
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Posture,
)
from prefect.server.events.triggers import (
    automation_changed,
    automations_by_id,
    forget_automation,
    listen_for_automation_changes,
    load_automation,
    triggers,
)


@pytest.fixture
def test_automation():
    """Create a test automation."""
    return Automation(
        id=uuid4(),
        name="Test Automation",
        description="Test automation for unit tests",
        enabled=True,
        trigger=EventTrigger(
            id=uuid4(),
            expect=["prefect.flow-run.Completed"],
            match={"prefect.resource.id": "prefect.flow-run.*"},
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(seconds=30),
        ),
        actions=[DoNothing()],
    )


@pytest.fixture(autouse=True)
def clear_automation_cache():
    """Clear automation cache before and after each test."""
    automations_by_id.clear()
    triggers.clear()
    yield
    automations_by_id.clear()
    triggers.clear()


class TestListenForAutomationChanges:
    """Tests for the listen_for_automation_changes function."""

    @pytest.fixture
    def mock_pg_connection(self):
        """Mock PostgreSQL connection and listener."""
        with mock.patch(
            "prefect.server.events.triggers.get_pg_notify_connection"
        ) as mock_get_conn:
            with mock.patch("prefect.server.events.triggers.pg_listen") as mock_listen:
                mock_conn = MagicMock()
                mock_conn.is_closed.return_value = False
                mock_conn.close = AsyncMock()
                mock_get_conn.return_value = mock_conn
                yield mock_get_conn, mock_listen, mock_conn

    async def test_exits_when_no_postgres_connection(self):
        """Test that function exits gracefully when PostgreSQL is not available."""
        with mock.patch(
            "prefect.server.events.triggers.get_pg_notify_connection", return_value=None
        ):
            # Function should return immediately
            await listen_for_automation_changes()
            # No exception should be raised

    async def test_processes_automation_created(
        self, mock_pg_connection, test_automation
    ):
        """Test processing of automation created notifications."""
        mock_get_conn, mock_listen, mock_conn = mock_pg_connection

        # Mock the pg_listen to yield a single created notification then raise CancelledError
        async def mock_notifications(*args, **kwargs):
            yield orjson.dumps(
                {"automation_id": str(test_automation.id), "event_type": "created"}
            ).decode()
            # Force exit after processing
            raise asyncio.CancelledError()

        mock_listen.side_effect = mock_notifications

        # Mock read_automation to return our test automation
        with mock.patch(
            "prefect.server.events.triggers.read_automation",
            return_value=test_automation,
        ):
            # Run listen_for_automation_changes
            try:
                await listen_for_automation_changes()
            except asyncio.CancelledError:
                pass  # Expected

            # Verify automation was loaded
            assert test_automation.id in automations_by_id
            assert test_automation.trigger.id in triggers

    async def test_processes_automation_updated(
        self, mock_pg_connection, test_automation
    ):
        """Test processing of automation updated notifications."""
        mock_get_conn, mock_listen, mock_conn = mock_pg_connection

        # First, load the automation
        load_automation(test_automation)
        assert test_automation.id in automations_by_id

        # Create updated version
        updated_automation = test_automation.model_copy()
        updated_automation.name = "Updated Automation"

        # Mock the pg_listen to yield an updated notification
        async def mock_notifications(*args, **kwargs):
            yield orjson.dumps(
                {"automation_id": str(test_automation.id), "event_type": "updated"}
            ).decode()
            raise asyncio.CancelledError()

        mock_listen.side_effect = mock_notifications

        # Mock read_automation to return updated automation
        with mock.patch(
            "prefect.server.events.triggers.read_automation",
            return_value=updated_automation,
        ):
            try:
                await listen_for_automation_changes()
            except asyncio.CancelledError:
                pass

            # Verify automation was updated
            assert automations_by_id[test_automation.id].name == "Updated Automation"

    async def test_processes_automation_deleted(
        self, mock_pg_connection, test_automation
    ):
        """Test processing of automation deleted notifications."""
        mock_get_conn, mock_listen, mock_conn = mock_pg_connection

        # First, load the automation
        load_automation(test_automation)
        assert test_automation.id in automations_by_id

        # Mock the pg_listen to yield a deleted notification
        async def mock_notifications(*args, **kwargs):
            yield orjson.dumps(
                {"automation_id": str(test_automation.id), "event_type": "deleted"}
            ).decode()
            raise asyncio.CancelledError()

        mock_listen.side_effect = mock_notifications

        try:
            await listen_for_automation_changes()
        except asyncio.CancelledError:
            pass

        # Verify automation was removed
        assert test_automation.id not in automations_by_id
        assert test_automation.trigger.id not in triggers

    async def test_handles_invalid_json(self, mock_pg_connection):
        """Test that invalid JSON payloads are handled gracefully."""
        mock_get_conn, mock_listen, mock_conn = mock_pg_connection

        # Mock pg_listen to yield invalid JSON
        async def mock_notifications(*args, **kwargs):
            yield "invalid json {"
            raise asyncio.CancelledError()

        mock_listen.side_effect = mock_notifications

        # Should not raise exception
        try:
            await listen_for_automation_changes()
        except asyncio.CancelledError:
            pass

    async def test_handles_unknown_event_type(self, mock_pg_connection):
        """Test that unknown event types are handled gracefully."""
        mock_get_conn, mock_listen, mock_conn = mock_pg_connection

        # Mock pg_listen to yield unknown event type
        async def mock_notifications(*args, **kwargs):
            yield orjson.dumps(
                {"automation_id": str(uuid4()), "event_type": "unknown_event"}
            ).decode()
            raise asyncio.CancelledError()

        mock_listen.side_effect = mock_notifications

        # Should not raise exception
        try:
            await listen_for_automation_changes()
        except asyncio.CancelledError:
            pass

    async def test_reconnects_on_error(self, mock_pg_connection):
        """Test that the listener reconnects after errors."""
        mock_get_conn, mock_listen, mock_conn = mock_pg_connection

        # Track reconnection attempts
        connection_attempts = []

        async def track_connections():
            connection_attempts.append(1)
            return mock_conn

        mock_get_conn.side_effect = track_connections

        # Mock pg_listen to raise an exception then exit
        call_count = 0

        async def fail_then_exit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: immediately raise exception
                if False:  # Make this an async generator
                    yield
                raise Exception("Connection lost")
            else:
                # Second call: cancel to exit
                if False:  # Make this an async generator
                    yield
                raise asyncio.CancelledError()

        mock_listen.side_effect = fail_then_exit

        # Mock settings for reconnect interval
        with mock.patch(
            "prefect.server.events.triggers.get_current_settings"
        ) as mock_settings:
            mock_settings.return_value.server.services.triggers.pg_notify_reconnect_interval_seconds = 0.01

            try:
                await listen_for_automation_changes()
            except asyncio.CancelledError:
                pass

            # Should have attempted multiple connections
            assert len(connection_attempts) >= 2


class TestAutomationChanged:
    """Tests for the automation_changed function."""

    async def test_automation_created(self, test_automation):
        """Test handling of automation created event."""
        with mock.patch(
            "prefect.server.events.triggers.read_automation",
            return_value=test_automation,
        ):
            await automation_changed(test_automation.id, "automation__created")

            assert test_automation.id in automations_by_id
            assert test_automation.trigger.id in triggers

    async def test_automation_updated(self, test_automation):
        """Test handling of automation updated event."""
        # First load the automation
        load_automation(test_automation)

        # Create updated version
        updated = test_automation.model_copy()
        updated.name = "Updated"

        with mock.patch(
            "prefect.server.events.triggers.read_automation", return_value=updated
        ):
            await automation_changed(test_automation.id, "automation__updated")

            assert automations_by_id[test_automation.id].name == "Updated"

    async def test_automation_deleted(self, test_automation):
        """Test handling of automation deleted event."""
        # First load the automation
        load_automation(test_automation)

        await automation_changed(test_automation.id, "automation__deleted")

        assert test_automation.id not in automations_by_id
        assert test_automation.trigger.id not in triggers

    async def test_automation_not_found(self):
        """Test handling when automation is not found in database."""
        automation_id = uuid4()

        with mock.patch(
            "prefect.server.events.triggers.read_automation", return_value=None
        ):
            await automation_changed(automation_id, "automation__created")

            # Should not be in cache
            assert automation_id not in automations_by_id

    async def test_disabled_automation_not_loaded(self, test_automation):
        """Test that disabled automations are not loaded into cache."""
        test_automation.enabled = False

        with mock.patch(
            "prefect.server.events.triggers.read_automation",
            return_value=test_automation,
        ):
            await automation_changed(test_automation.id, "automation__created")

            # Should not be in cache
            assert test_automation.id not in automations_by_id


class TestLoadAutomation:
    """Tests for the load_automation function."""

    def test_loads_enabled_automation(self, test_automation):
        """Test that enabled automations are loaded."""
        load_automation(test_automation)

        assert test_automation.id in automations_by_id
        assert test_automation.trigger.id in triggers

    def test_does_not_load_disabled_automation(self, test_automation):
        """Test that disabled automations are not loaded."""
        test_automation.enabled = False
        load_automation(test_automation)

        assert test_automation.id not in automations_by_id
        assert test_automation.trigger.id not in triggers

    def test_removes_automation_when_disabled(self, test_automation):
        """Test that automations are removed when disabled."""
        # First load it
        load_automation(test_automation)
        assert test_automation.id in automations_by_id

        # Now disable and reload
        test_automation.enabled = False
        load_automation(test_automation)

        assert test_automation.id not in automations_by_id
        assert test_automation.trigger.id not in triggers

    def test_handles_none_automation(self):
        """Test that None automation is handled gracefully."""
        load_automation(None)
        # Should not raise exception


class TestForgetAutomation:
    """Tests for the forget_automation function."""

    def test_removes_automation_and_triggers(self, test_automation):
        """Test that automation and its triggers are removed."""
        # First load it
        load_automation(test_automation)
        assert test_automation.id in automations_by_id

        # Now forget it
        forget_automation(test_automation.id)

        assert test_automation.id not in automations_by_id
        assert test_automation.trigger.id not in triggers

    def test_handles_unknown_automation(self):
        """Test that unknown automation ID is handled gracefully."""
        forget_automation(uuid4())
        # Should not raise exception
