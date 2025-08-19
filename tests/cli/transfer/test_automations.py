import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.automations import MigratableAutomation
from prefect.events.actions import (
    CallWebhook,
    DoNothing,
    PauseAutomation,
    PauseWorkPool,
    PauseWorkQueue,
    RunDeployment,
    SendNotification,
)
from prefect.events.schemas.automations import Automation, EventTrigger, Posture
from prefect.events.schemas.events import ResourceSpecification


def create_test_trigger() -> EventTrigger:
    """Helper to create a proper EventTrigger for testing."""
    return EventTrigger(
        expect={"prefect.flow-run.Failed"},
        match=ResourceSpecification(root={}),
        match_related=[],
        posture=Posture.Reactive,
        threshold=1,
        within=timedelta(seconds=30),
    )


class TestMigratableAutomation:
    async def test_construct_creates_new_instance(
        self, transfer_automation: Automation
    ):
        """Test that construct creates a new MigratableAutomation instance."""
        migratable = await MigratableAutomation.construct(transfer_automation)

        assert isinstance(migratable, MigratableAutomation)
        assert migratable.source_automation == transfer_automation
        assert migratable.source_id == transfer_automation.id
        assert migratable.destination_automation is None
        assert migratable.destination_id is None
        assert migratable._dependencies == {}

    async def test_construct_returns_cached_instance(
        self, transfer_automation: Automation
    ):
        """Test that construct returns cached instance for same ID."""

        # Clear any existing instances
        MigratableAutomation._instances.clear()

        # Create first instance
        migratable1 = await MigratableAutomation.construct(transfer_automation)

        # Create second instance with same automation
        migratable2 = await MigratableAutomation.construct(transfer_automation)

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableAutomation._instances) == 1

    async def test_get_instance_returns_cached_instance(
        self, transfer_automation: Automation
    ):
        """Test that get_instance returns cached instance."""

        # Clear any existing instances
        MigratableAutomation._instances.clear()

        # Create instance
        migratable = await MigratableAutomation.construct(transfer_automation)

        # Retrieve instance
        retrieved = await MigratableAutomation.get_instance(transfer_automation.id)

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableAutomation._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableAutomation.get_instance(unknown_id)

        assert retrieved is None

    async def test_get_dependencies_no_dependencies(
        self, transfer_automation: Automation
    ):
        """Test automation with actions that have no dependencies."""
        migratable = await MigratableAutomation.construct(transfer_automation)
        dependencies = await migratable.get_dependencies()

        assert dependencies == []
        assert migratable._dependencies == {}

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.automations.construct_migratable_resource"
    )
    async def test_get_dependencies_deployment_action(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test automation with DeploymentAction dependencies."""
        deployment_id = uuid.uuid4()
        automation = Automation(
            id=uuid.uuid4(),
            name="test-automation",
            description="Test automation",
            enabled=True,
            tags=[],
            trigger=create_test_trigger(),
            actions=[
                RunDeployment(
                    deployment_id=deployment_id,
                    source="selected",
                    parameters=None,
                    job_variables=None,
                ),
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )

        # Mock the client and deployment
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        mock_deployment = MagicMock()
        mock_deployment.id = deployment_id
        mock_client.read_deployment.return_value = mock_deployment

        mock_migratable_deployment = MagicMock()
        mock_construct_resource.return_value = mock_migratable_deployment

        migratable = await MigratableAutomation.construct(automation)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_deployment
        assert deployment_id in migratable._dependencies
        mock_client.read_deployment.assert_called_once_with(deployment_id)
        mock_construct_resource.assert_called_once_with(mock_deployment)

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.automations.construct_migratable_resource"
    )
    async def test_get_dependencies_work_pool_action(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test automation with WorkPoolAction dependencies."""
        work_pool_id = uuid.uuid4()
        automation = Automation(
            id=uuid.uuid4(),
            name="test-automation",
            description="Test automation",
            enabled=True,
            tags=[],
            trigger=create_test_trigger(),
            actions=[
                PauseWorkPool(work_pool_id=work_pool_id, source="selected"),
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )

        # Mock the client and work pool
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        mock_work_pool = MagicMock()
        mock_work_pool.id = work_pool_id
        mock_client.read_work_pools.return_value = [mock_work_pool]

        mock_migratable_work_pool = MagicMock()
        mock_construct_resource.return_value = mock_migratable_work_pool

        migratable = await MigratableAutomation.construct(automation)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_work_pool
        assert work_pool_id in migratable._dependencies
        mock_construct_resource.assert_called_once_with(mock_work_pool)

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.automations.construct_migratable_resource"
    )
    async def test_get_dependencies_work_queue_action(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test automation with WorkQueueAction dependencies."""
        work_queue_id = uuid.uuid4()
        automation = Automation(
            id=uuid.uuid4(),
            name="test-automation",
            description="Test automation",
            enabled=True,
            tags=[],
            trigger=create_test_trigger(),
            actions=[
                PauseWorkQueue(work_queue_id=work_queue_id, source="selected"),
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )

        # Mock the client and work queue
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        mock_work_queue = MagicMock()
        mock_work_queue.id = work_queue_id
        mock_client.read_work_queue.return_value = mock_work_queue

        mock_migratable_work_queue = MagicMock()
        mock_construct_resource.return_value = mock_migratable_work_queue

        migratable = await MigratableAutomation.construct(automation)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_work_queue
        assert work_queue_id in migratable._dependencies
        mock_client.read_work_queue.assert_called_once_with(work_queue_id)
        mock_construct_resource.assert_called_once_with(mock_work_queue)

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.automations.construct_migratable_resource"
    )
    async def test_get_dependencies_automation_action(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test automation with AutomationAction dependencies."""
        automation_id = uuid.uuid4()
        automation = Automation(
            id=uuid.uuid4(),
            name="test-automation",
            description="Test automation",
            enabled=True,
            tags=[],
            trigger=create_test_trigger(),
            actions=[
                PauseAutomation(automation_id=automation_id, source="selected"),
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )

        # Mock the client and automation
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        mock_automation = MagicMock()
        mock_automation.id = automation_id
        mock_client.find_automation.return_value = mock_automation

        mock_migratable_automation = MagicMock()
        mock_construct_resource.return_value = mock_migratable_automation

        migratable = await MigratableAutomation.construct(automation)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_automation
        assert automation_id in migratable._dependencies
        mock_client.find_automation.assert_called_once_with(automation_id)
        mock_construct_resource.assert_called_once_with(mock_automation)

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.automations.construct_migratable_resource"
    )
    async def test_get_dependencies_call_webhook(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test automation with CallWebhook block document dependencies."""
        block_document_id = uuid.uuid4()
        automation = Automation(
            id=uuid.uuid4(),
            name="test-automation",
            description="Test automation",
            enabled=True,
            tags=[],
            trigger=create_test_trigger(),
            actions=[
                CallWebhook(block_document_id=block_document_id),
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )

        # Mock the client and block document
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        mock_block_document = MagicMock()
        mock_block_document.id = block_document_id
        mock_client.read_block_document.return_value = mock_block_document

        mock_migratable_block = MagicMock()
        mock_construct_resource.return_value = mock_migratable_block

        migratable = await MigratableAutomation.construct(automation)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_block
        assert block_document_id in migratable._dependencies
        mock_client.read_block_document.assert_called_once_with(block_document_id)
        mock_construct_resource.assert_called_once_with(mock_block_document)

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.automations.construct_migratable_resource"
    )
    async def test_get_dependencies_send_notification(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test automation with SendNotification block document dependencies."""
        block_document_id = uuid.uuid4()
        automation = Automation(
            id=uuid.uuid4(),
            name="test-automation",
            description="Test automation",
            enabled=True,
            tags=[],
            trigger=create_test_trigger(),
            actions=[
                SendNotification(
                    block_document_id=block_document_id,
                    subject="Test notification",
                    body="Test body",
                ),
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )

        # Mock the client and block document
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        mock_block_document = MagicMock()
        mock_block_document.id = block_document_id
        mock_client.read_block_document.return_value = mock_block_document

        mock_migratable_block = MagicMock()
        mock_construct_resource.return_value = mock_migratable_block

        migratable = await MigratableAutomation.construct(automation)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_block
        assert block_document_id in migratable._dependencies
        mock_client.read_block_document.assert_called_once_with(block_document_id)
        mock_construct_resource.assert_called_once_with(mock_block_document)

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    @patch(
        "prefect.cli.transfer._migratable_resources.automations.construct_migratable_resource"
    )
    async def test_get_dependencies_multiple_actions(
        self, mock_construct_resource: AsyncMock, mock_get_client: MagicMock
    ):
        """Test automation with multiple actions that have dependencies."""
        deployment_id = uuid.uuid4()
        block_document_id = uuid.uuid4()
        automation = Automation(
            id=uuid.uuid4(),
            name="test-automation",
            description="Test automation",
            enabled=True,
            tags=[],
            trigger=create_test_trigger(),
            actions=[
                RunDeployment(
                    deployment_id=deployment_id,
                    source="selected",
                    parameters=None,
                    job_variables=None,
                ),
                CallWebhook(block_document_id=block_document_id),
                DoNothing(),  # No dependencies
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock deployment
        mock_deployment = MagicMock()
        mock_deployment.id = deployment_id
        mock_client.read_deployment.return_value = mock_deployment

        # Mock block document
        mock_block_document = MagicMock()
        mock_block_document.id = block_document_id
        mock_client.read_block_document.return_value = mock_block_document

        # Mock migratable resources
        mock_migratable_deployment = MagicMock()
        mock_migratable_block = MagicMock()
        mock_construct_resource.side_effect = [
            mock_migratable_deployment,
            mock_migratable_block,
        ]

        migratable = await MigratableAutomation.construct(automation)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 2
        assert mock_migratable_deployment in dependencies
        assert mock_migratable_block in dependencies
        assert deployment_id in migratable._dependencies
        assert block_document_id in migratable._dependencies

    async def test_get_dependencies_cached(self, transfer_automation: Automation):
        """Test that dependencies are cached after first call."""
        migratable = await MigratableAutomation.construct(transfer_automation)

        # Set up some mock dependencies
        mock_dependency = MagicMock()
        migratable._dependencies[uuid.uuid4()] = mock_dependency

        dependencies1 = await migratable.get_dependencies()
        dependencies2 = await migratable.get_dependencies()

        # Should return the same cached result
        assert dependencies1 == dependencies2
        assert dependencies1 == [mock_dependency]

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    async def test_migrate_already_exists(
        self, mock_get_client: MagicMock, transfer_automation: Automation
    ):
        """Test migration when automation already exists."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock existing automation
        existing_automation = Automation(
            id=uuid.uuid4(),
            name=transfer_automation.name,
            description="Existing automation",
            enabled=False,
            tags=["existing"],
            trigger=transfer_automation.trigger,
            actions=[DoNothing()],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )
        mock_client.read_automations_by_name.return_value = [existing_automation]

        migratable = await MigratableAutomation.construct(transfer_automation)

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify calls
        mock_client.read_automations_by_name.assert_called_once_with(
            name=transfer_automation.name
        )

        # Verify destination_automation is set to existing
        assert migratable.destination_automation == existing_automation
        assert migratable.destination_id == existing_automation.id

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    async def test_migrate_success_no_dependencies(
        self, mock_get_client: MagicMock, transfer_automation: Automation
    ):
        """Test successful migration of automation with no dependencies."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock no existing automations
        mock_client.read_automations_by_name.return_value = []

        # Mock successful creation
        created_automation_id = uuid.uuid4()
        mock_client.create_automation.return_value = created_automation_id

        destination_automation = Automation(
            id=created_automation_id,
            name=transfer_automation.name,
            description=transfer_automation.description,
            enabled=transfer_automation.enabled,
            tags=transfer_automation.tags,
            trigger=transfer_automation.trigger,
            actions=transfer_automation.actions,
            actions_on_trigger=transfer_automation.actions_on_trigger,
            actions_on_resolve=transfer_automation.actions_on_resolve,
        )
        mock_client.read_automation.return_value = destination_automation

        migratable = await MigratableAutomation.construct(transfer_automation)
        await migratable.migrate()

        # Verify calls
        mock_client.read_automations_by_name.assert_called_once_with(
            name=transfer_automation.name
        )
        mock_client.create_automation.assert_called_once()
        mock_client.read_automation.assert_called_once_with(
            automation_id=created_automation_id
        )

        # Verify destination_automation is set
        assert migratable.destination_automation == destination_automation
        assert migratable.destination_id == created_automation_id

    @patch("prefect.cli.transfer._migratable_resources.automations.get_client")
    async def test_migrate_success_with_dependencies(self, mock_get_client: MagicMock):
        """Test successful migration of automation with dependencies."""
        deployment_id = uuid.uuid4()
        automation = Automation(
            id=uuid.uuid4(),
            name="test-automation-with-deps",
            description="Test automation with dependencies",
            enabled=True,
            tags=["test"],
            trigger=create_test_trigger(),
            actions=[
                RunDeployment(
                    deployment_id=deployment_id,
                    source="selected",
                    parameters=None,
                    job_variables=None,
                ),
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock no existing automations
        mock_client.read_automations_by_name.return_value = []

        # Mock successful creation
        created_automation_id = uuid.uuid4()
        mock_client.create_automation.return_value = created_automation_id

        # Mock dependency with destination_id
        mock_dependency = MagicMock()
        destination_deployment_id = uuid.uuid4()
        mock_dependency.destination_id = destination_deployment_id

        migratable = await MigratableAutomation.construct(automation)
        # Set up the dependency manually
        migratable._dependencies[deployment_id] = mock_dependency

        # Mock the read automation response
        expected_automation = Automation(
            id=created_automation_id,
            name=automation.name,
            description=automation.description,
            enabled=automation.enabled,
            tags=automation.tags,
            trigger=automation.trigger,
            actions=[
                RunDeployment(
                    deployment_id=destination_deployment_id,
                    source="selected",
                    parameters=None,
                    job_variables=None,
                ),
            ],
            actions_on_trigger=[],
            actions_on_resolve=[],
        )
        mock_client.read_automation.return_value = expected_automation

        await migratable.migrate()

        # Verify the automation was created with updated IDs
        create_call = mock_client.create_automation.call_args[1]["automation"]
        assert create_call.actions[0].deployment_id == destination_deployment_id

        # Verify destination_automation is set
        assert migratable.destination_automation == expected_automation
        assert migratable.destination_id == created_automation_id
