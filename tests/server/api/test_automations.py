import pytest
import asyncio
from unittest import mock
from uuid import uuid4, UUID

from prefect.server.schemas.core import Automation
from prefect.server.events.schemas.automations import (
    AutomationCreate,
    AutomationUpdate,
    AutomationPartialUpdate, # Added for patch
    EventTrigger,
    Posture,
    TriggerState,
)
from prefect.server.events import actions
from prefect.server.api import automations as automations_api # to call the API functions
from prefect.server.database import provide_database_interface # for db mock if needed


# Basic test structure
class TestAutomationPublishing:
    # Fixtures for AutomationCreate, AutomationUpdate can be added here later
    # For now, we can create them directly in tests

    @pytest.mark.asyncio
    @mock.patch("prefect.server.events.models.automations.create_automation")
    @mock.patch("prefect.server.utilities.messaging.create_publisher")
    async def test_create_automation_publishes_message(
        self, mock_create_publisher, mock_db_create_automation
    ):
        mock_publisher = mock.AsyncMock()
        mock_create_publisher.return_value.__aenter__.return_value = mock_publisher

        mock_automation_obj = Automation(
            id=uuid4(),
            name="test-automation",
            trigger=EventTrigger(expect={"test.event"}, posture=Posture.Reactive),
            actions=[actions.DoNothing()],
        )
        mock_db_create_automation.return_value = mock_automation_obj

        automation_create_data = AutomationCreate(
            name="test-automation",
            trigger=EventTrigger(expect={"test.event"}, posture=Posture.Reactive),
            actions=[actions.DoNothing()],
        )
        
        # Mock the db dependency for the API function
        mock_db = mock.AsyncMock(spec=provide_database_interface)
        
        await automations_api.create_automation(
            automation=automation_create_data, db=mock_db
        )

        mock_create_publisher.assert_called_once_with(topic="automations-notifications")
        
        expected_payload = {
            "event_type": "automation_created",
            "automation_id": str(mock_automation_obj.id),
        }
        # Check that publish_data was called once
        assert mock_publisher.publish_data.call_count == 1
        
        # Get the actual call arguments
        actual_call_args = mock_publisher.publish_data.call_args[0]
        
        # The first argument is the data (bytes)
        import json
        actual_payload_bytes = actual_call_args[0]
        actual_payload_dict = json.loads(actual_payload_bytes.decode())

        assert actual_payload_dict == expected_payload
        # The second argument is attributes (empty dict)
        assert actual_call_args[1] == {}


    @pytest.mark.asyncio
    @mock.patch("prefect.server.events.models.automations.update_automation")
    @mock.patch("prefect.server.utilities.messaging.create_publisher")
    async def test_update_automation_publishes_message(
        self, mock_create_publisher, mock_db_update_automation
    ):
        mock_publisher = mock.AsyncMock()
        mock_create_publisher.return_value.__aenter__.return_value = mock_publisher

        mock_db_update_automation.return_value = True  # Simulate successful update

        automation_update_data = AutomationUpdate(
            name="updated-automation",
            trigger=EventTrigger(expect={"test.event.updated"}, posture=Posture.Reactive),
            actions=[actions.DoNothing(), actions.DoNothing()], # e.g. changed actions
        )
        
        automation_id_to_update = uuid4()
        mock_db = mock.AsyncMock(spec=provide_database_interface)
        
        await automations_api.update_automation(
            automation=automation_update_data,
            automation_id=automation_id_to_update,
            db=mock_db
        )

        mock_create_publisher.assert_called_once_with(topic="automations-notifications")
        
        expected_payload = {
            "event_type": "automation_updated",
            "automation_id": str(automation_id_to_update),
        }
        assert mock_publisher.publish_data.call_count == 1
        
        import json
        actual_payload_bytes = mock_publisher.publish_data.call_args[0][0]
        actual_payload_dict = json.loads(actual_payload_bytes.decode())

        assert actual_payload_dict == expected_payload
        assert mock_publisher.publish_data.call_args[0][1] == {}


    @pytest.mark.asyncio
    @mock.patch("prefect.server.events.models.automations.update_automation")
    @mock.patch("prefect.server.utilities.messaging.create_publisher")
    async def test_patch_automation_publishes_message(
        self, mock_create_publisher, mock_db_update_automation # Reusing update_automation mock as patch calls it
    ):
        mock_publisher = mock.AsyncMock()
        mock_create_publisher.return_value.__aenter__.return_value = mock_publisher

        mock_db_update_automation.return_value = True # Simulate successful update/patch

        automation_patch_data = AutomationPartialUpdate(
            name="patched-automation-name" # Example: only name is patched
        )
        
        automation_id_to_patch = uuid4()
        mock_db = mock.AsyncMock(spec=provide_database_interface)
        
        await automations_api.patch_automation(
            automation=automation_patch_data,
            automation_id=automation_id_to_patch,
            db=mock_db
        )

        mock_create_publisher.assert_called_once_with(topic="automations-notifications")
        
        expected_payload = {
            "event_type": "automation_updated", # Patch also results in 'updated'
            "automation_id": str(automation_id_to_patch),
        }
        assert mock_publisher.publish_data.call_count == 1
        
        import json
        actual_payload_bytes = mock_publisher.publish_data.call_args[0][0]
        actual_payload_dict = json.loads(actual_payload_bytes.decode())

        assert actual_payload_dict == expected_payload
        assert mock_publisher.publish_data.call_args[0][1] == {}

    
    @pytest.mark.asyncio
    @mock.patch("prefect.server.events.models.automations.delete_automation")
    @mock.patch("prefect.server.utilities.messaging.create_publisher")
    async def test_delete_automation_publishes_message(
        self, mock_create_publisher, mock_db_delete_automation
    ):
        mock_publisher = mock.AsyncMock()
        mock_create_publisher.return_value.__aenter__.return_value = mock_publisher

        mock_db_delete_automation.return_value = True # Simulate successful delete

        automation_id_to_delete = uuid4()
        mock_db = mock.AsyncMock(spec=provide_database_interface)
        
        await automations_api.delete_automation(
            automation_id=automation_id_to_delete,
            db=mock_db
        )

        mock_create_publisher.assert_called_once_with(topic="automations-notifications")
        
        expected_payload = {
            "event_type": "automation_deleted",
            "automation_id": str(automation_id_to_delete),
        }
        assert mock_publisher.publish_data.call_count == 1
        
        import json
        actual_payload_bytes = mock_publisher.publish_data.call_args[0][0]
        actual_payload_dict = json.loads(actual_payload_bytes.decode())

        assert actual_payload_dict == expected_payload
        assert mock_publisher.publish_data.call_args[0][1] == {}

# Example of how a fixture might look (if complex objects are needed repeatedly)
# @pytest.fixture
# def sample_automation_create() -> AutomationCreate:
#     return AutomationCreate(
#         name="test-automation",
#         trigger=EventTrigger(expect={"test.event"}, posture=Posture.Reactive),
#         actions=[actions.DoNothing()]
#     )
