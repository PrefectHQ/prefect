import pytest
import asyncio
import json
from unittest import mock
from uuid import uuid4, UUID

from prefect.server.events import triggers # to mock automation_changed
from prefect.server.events.triggers import automations_notification_consumer # the consumer to test
from prefect.server.utilities.messaging import Message # for crafting mock messages


# Basic test structure for the consumer
class TestAutomationsNotificationConsumer:

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "raw_event_type, expected_mapped_event_type",
        [
            ("automation_created", "automation__created"),
            ("automation_updated", "automation__updated"),
            ("automation_deleted", "automation__deleted"),
        ],
    )
    @mock.patch.object(triggers, "automation_changed", new_callable=mock.AsyncMock)
    async def test_valid_messages_call_automation_changed(
        self, mock_automation_changed_fn, raw_event_type, expected_mapped_event_type
    ):
        automation_id = uuid4()
        message_payload = {
            "event_type": raw_event_type,
            "automation_id": str(automation_id),
        }
        mock_message = mock.MagicMock(spec=Message)
        mock_message.data = json.dumps(message_payload).encode()

        # Get the handler from the consumer
        handler = None
        async with automations_notification_consumer() as h:
            handler = h
        
        assert handler is not None, "Failed to get message handler from consumer"

        await handler(mock_message)

        mock_automation_changed_fn.assert_called_once_with(
            automation_id, expected_mapped_event_type
        )

    @pytest.mark.asyncio
    @mock.patch.object(triggers, "automation_changed", new_callable=mock.AsyncMock)
    @mock.patch("prefect.server.events.triggers.logger") # To check error logging
    async def test_invalid_json_logs_error_and_does_not_call_automation_changed(
        self, mock_logger, mock_automation_changed_fn
    ):
        mock_message = mock.MagicMock(spec=Message)
        mock_message.data = b"this is not valid json"

        handler = None
        async with automations_notification_consumer() as h:
            handler = h
        
        assert handler is not None

        await handler(mock_message)

        mock_automation_changed_fn.assert_not_called()
        # Based on consumer code, it uses logger.exception for JSONDecodeError
        mock_logger.exception.assert_called_once()
        assert "Failed to decode JSON" in mock_logger.exception.call_args[0][0]


    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload_missing_field",
        [
            ({"automation_id": str(uuid4())}),  # Missing event_type
            ({"event_type": "automation_created"}),  # Missing automation_id
        ],
    )
    @mock.patch.object(triggers, "automation_changed", new_callable=mock.AsyncMock)
    @mock.patch("prefect.server.events.triggers.logger")
    async def test_missing_fields_logs_error_and_does_not_call_automation_changed(
        self, mock_logger, mock_automation_changed_fn, payload_missing_field
    ):
        mock_message = mock.MagicMock(spec=Message)
        mock_message.data = json.dumps(payload_missing_field).encode()

        handler = None
        async with automations_notification_consumer() as h:
            handler = h
        
        assert handler is not None

        await handler(mock_message)

        mock_automation_changed_fn.assert_not_called()
        # Based on consumer code, it uses logger.error for missing fields
        mock_logger.error.assert_called_once()
        assert "Missing 'event_type' or 'automation_id'" in mock_logger.error.call_args[0][0]


    @pytest.mark.asyncio
    @mock.patch.object(triggers, "automation_changed", new_callable=mock.AsyncMock)
    @mock.patch("prefect.server.events.triggers.logger")
    async def test_invalid_uuid_logs_error_and_does_not_call_automation_changed(
        self, mock_logger, mock_automation_changed_fn
    ):
        payload_with_invalid_uuid = {
            "event_type": "automation_created",
            "automation_id": "this-is-not-a-uuid",
        }
        mock_message = mock.MagicMock(spec=Message)
        mock_message.data = json.dumps(payload_with_invalid_uuid).encode()

        handler = None
        async with automations_notification_consumer() as h:
            handler = h
        
        assert handler is not None

        await handler(mock_message)

        mock_automation_changed_fn.assert_not_called()
        # Based on consumer code, it uses logger.error for invalid UUID
        mock_logger.error.assert_called_once()
        assert "Invalid UUID for automation_id" in mock_logger.error.call_args[0][0]
