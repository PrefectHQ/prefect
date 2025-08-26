import uuid
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.deployments import MigratableDeployment
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.responses import DeploymentResponse
from prefect.exceptions import ObjectAlreadyExists, ObjectLimitReached

# Suppress deprecation warnings from accessing deprecated fields in DeploymentResponse
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic.*")


class TestMigratableDeployment:
    async def test_construct_creates_new_instance(
        self, transfer_deployment: DeploymentResponse
    ):
        """Test that construct creates a new MigratableDeployment instance."""
        migratable = await MigratableDeployment.construct(transfer_deployment)

        assert isinstance(migratable, MigratableDeployment)
        assert migratable.source_deployment == transfer_deployment
        assert migratable.source_id == transfer_deployment.id
        assert migratable.destination_deployment is None
        assert migratable.destination_id is None
        assert migratable._dependencies == {}

    async def test_construct_returns_cached_instance(
        self, transfer_deployment: DeploymentResponse
    ):
        """Test that construct returns cached instance for same ID."""
        # Clear any existing instances
        MigratableDeployment._instances.clear()

        # Create first instance
        migratable1 = await MigratableDeployment.construct(transfer_deployment)

        # Create second instance with same deployment
        migratable2 = await MigratableDeployment.construct(transfer_deployment)

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableDeployment._instances) == 1

    async def test_get_instance_returns_cached_instance(
        self, transfer_deployment: DeploymentResponse
    ):
        """Test that get_instance returns cached instance."""
        # Clear any existing instances
        MigratableDeployment._instances.clear()

        # Create instance
        migratable = await MigratableDeployment.construct(transfer_deployment)

        # Retrieve instance
        retrieved = await MigratableDeployment.get_instance(transfer_deployment.id)

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableDeployment._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableDeployment.get_instance(unknown_id)

        assert retrieved is None

    @patch(
        "prefect.cli.transfer._migratable_resources.deployments.construct_migratable_resource"
    )
    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    async def test_get_dependencies_with_flow_only(
        self,
        mock_get_client: MagicMock,
        mock_construct_resource: AsyncMock,
        transfer_deployment: DeploymentResponse,
    ):
        """Test get_dependencies with only flow dependency."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow read
        mock_flow = MagicMock()
        mock_flow.id = transfer_deployment.flow_id
        mock_client.read_flow.return_value = mock_flow

        mock_migratable_flow = MagicMock()
        mock_construct_resource.return_value = mock_migratable_flow

        # Create deployment with no work queue, storage, or infrastructure
        deployment = DeploymentResponse(
            id=uuid.uuid4(),
            name="test-deployment",
            flow_id=transfer_deployment.flow_id,
            schedules=[],
            tags=[],
            parameters={},
            work_queue_id=None,
            storage_document_id=None,
            infrastructure_document_id=None,
            pull_steps=None,
        )

        migratable = await MigratableDeployment.construct(deployment)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_flow
        assert deployment.flow_id in migratable._dependencies
        mock_client.read_flow.assert_called_once_with(deployment.flow_id)
        mock_construct_resource.assert_called_once_with(mock_flow)

    @patch(
        "prefect.cli.transfer._migratable_resources.deployments.construct_migratable_resource"
    )
    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    async def test_get_dependencies_with_work_queue(
        self,
        mock_get_client: MagicMock,
        mock_construct_resource: AsyncMock,
        transfer_deployment: DeploymentResponse,
    ):
        """Test get_dependencies with work queue dependency."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow read
        mock_flow = MagicMock()
        mock_flow.id = transfer_deployment.flow_id
        mock_client.read_flow.return_value = mock_flow

        # Mock work queue read
        work_queue_id = uuid.uuid4()
        mock_work_queue = MagicMock()
        mock_work_queue.id = work_queue_id
        mock_client.read_work_queue.return_value = mock_work_queue

        mock_migratable_flow = MagicMock()
        mock_migratable_work_queue = MagicMock()
        mock_construct_resource.side_effect = [
            mock_migratable_flow,
            mock_migratable_work_queue,
        ]

        # Create deployment with work queue
        deployment = DeploymentResponse(
            id=uuid.uuid4(),
            name="test-deployment",
            flow_id=transfer_deployment.flow_id,
            schedules=[],
            tags=[],
            parameters={},
            work_queue_id=work_queue_id,
            storage_document_id=None,
            infrastructure_document_id=None,
            pull_steps=None,
        )

        migratable = await MigratableDeployment.construct(deployment)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 2
        assert mock_migratable_flow in dependencies
        assert mock_migratable_work_queue in dependencies
        assert deployment.flow_id in migratable._dependencies
        assert work_queue_id in migratable._dependencies
        mock_client.read_work_queue.assert_called_once_with(work_queue_id)

    @patch(
        "prefect.cli.transfer._migratable_resources.deployments.construct_migratable_resource"
    )
    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    async def test_get_dependencies_with_storage_document(
        self,
        mock_get_client: MagicMock,
        mock_construct_resource: AsyncMock,
        transfer_deployment: DeploymentResponse,
    ):
        """Test get_dependencies with storage document dependency."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow read
        mock_flow = MagicMock()
        mock_flow.id = transfer_deployment.flow_id
        mock_client.read_flow.return_value = mock_flow

        # Mock storage document read
        storage_document_id = uuid.uuid4()
        mock_storage_document = MagicMock()
        mock_storage_document.id = storage_document_id
        mock_client.read_block_document.return_value = mock_storage_document

        mock_migratable_flow = MagicMock()
        mock_migratable_storage = MagicMock()
        mock_construct_resource.side_effect = [
            mock_migratable_flow,
            mock_migratable_storage,
        ]

        # Create deployment with storage document
        deployment = DeploymentResponse(
            id=uuid.uuid4(),
            name="test-deployment",
            flow_id=transfer_deployment.flow_id,
            schedules=[],
            tags=[],
            parameters={},
            work_queue_id=None,
            storage_document_id=storage_document_id,
            infrastructure_document_id=None,
            pull_steps=None,
        )

        migratable = await MigratableDeployment.construct(deployment)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 2
        assert mock_migratable_flow in dependencies
        assert mock_migratable_storage in dependencies
        assert deployment.flow_id in migratable._dependencies
        assert storage_document_id in migratable._dependencies
        assert mock_client.read_block_document.call_count == 1
        mock_client.read_block_document.assert_any_call(storage_document_id)

    @patch(
        "prefect.cli.transfer._migratable_resources.deployments.construct_migratable_resource"
    )
    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    async def test_get_dependencies_with_infrastructure_document(
        self,
        mock_get_client: MagicMock,
        mock_construct_resource: AsyncMock,
        transfer_deployment: DeploymentResponse,
    ):
        """Test get_dependencies with infrastructure document dependency."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow read
        mock_flow = MagicMock()
        mock_flow.id = transfer_deployment.flow_id
        mock_client.read_flow.return_value = mock_flow

        # Mock infrastructure document read
        infrastructure_document_id = uuid.uuid4()
        mock_infrastructure_document = MagicMock()
        mock_infrastructure_document.id = infrastructure_document_id
        mock_client.read_block_document.return_value = mock_infrastructure_document

        mock_migratable_flow = MagicMock()
        mock_migratable_infrastructure = MagicMock()
        mock_construct_resource.side_effect = [
            mock_migratable_flow,
            mock_migratable_infrastructure,
        ]

        # Create deployment with infrastructure document
        deployment = DeploymentResponse(
            id=uuid.uuid4(),
            name="test-deployment",
            flow_id=transfer_deployment.flow_id,
            schedules=[],
            tags=[],
            parameters={},
            work_queue_id=None,
            storage_document_id=None,
            infrastructure_document_id=infrastructure_document_id,
            pull_steps=None,
        )

        migratable = await MigratableDeployment.construct(deployment)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 2
        assert mock_migratable_flow in dependencies
        assert mock_migratable_infrastructure in dependencies
        assert deployment.flow_id in migratable._dependencies
        assert infrastructure_document_id in migratable._dependencies
        assert mock_client.read_block_document.call_count == 1
        mock_client.read_block_document.assert_any_call(infrastructure_document_id)

    @patch(
        "prefect.cli.transfer._migratable_resources.deployments.construct_migratable_resource"
    )
    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    async def test_get_dependencies_with_all_dependencies(
        self,
        mock_get_client: MagicMock,
        mock_construct_resource: AsyncMock,
        transfer_deployment: DeploymentResponse,
    ):
        """Test get_dependencies with all possible dependencies."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow read
        mock_flow = MagicMock()
        mock_flow.id = transfer_deployment.flow_id
        mock_client.read_flow.return_value = mock_flow

        # Mock work queue read
        work_queue_id = uuid.uuid4()
        mock_work_queue = MagicMock()
        mock_work_queue.id = work_queue_id
        mock_client.read_work_queue.return_value = mock_work_queue

        # Mock storage and infrastructure document reads
        storage_document_id = uuid.uuid4()
        infrastructure_document_id = uuid.uuid4()
        mock_storage_document = MagicMock()
        mock_storage_document.id = storage_document_id
        mock_infrastructure_document = MagicMock()
        mock_infrastructure_document.id = infrastructure_document_id
        mock_client.read_block_document.side_effect = [
            mock_storage_document,
            mock_infrastructure_document,
        ]

        mock_migratable_flow = MagicMock()
        mock_migratable_work_queue = MagicMock()
        mock_migratable_storage = MagicMock()
        mock_migratable_infrastructure = MagicMock()
        mock_construct_resource.side_effect = [
            mock_migratable_flow,
            mock_migratable_work_queue,
            mock_migratable_storage,
            mock_migratable_infrastructure,
        ]

        # Create deployment with all dependencies
        deployment = DeploymentResponse(
            id=uuid.uuid4(),
            name="test-deployment",
            flow_id=transfer_deployment.flow_id,
            schedules=[],
            tags=[],
            parameters={},
            work_queue_id=work_queue_id,
            storage_document_id=storage_document_id,
            infrastructure_document_id=infrastructure_document_id,
            pull_steps=None,
        )

        migratable = await MigratableDeployment.construct(deployment)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 4
        assert mock_migratable_flow in dependencies
        assert mock_migratable_work_queue in dependencies
        assert mock_migratable_storage in dependencies
        assert mock_migratable_infrastructure in dependencies
        assert deployment.flow_id in migratable._dependencies
        assert work_queue_id in migratable._dependencies
        assert storage_document_id in migratable._dependencies
        assert infrastructure_document_id in migratable._dependencies

    async def test_get_dependencies_cached(
        self, transfer_deployment: DeploymentResponse
    ):
        """Test that dependencies are cached after first call."""
        migratable = await MigratableDeployment.construct(transfer_deployment)

        # Set up some mock dependencies
        mock_dependency = MagicMock()
        migratable._dependencies[uuid.uuid4()] = mock_dependency

        dependencies1 = await migratable.get_dependencies()
        dependencies2 = await migratable.get_dependencies()

        # Should return the same cached result
        assert dependencies1 == dependencies2
        assert dependencies1 == [mock_dependency]

    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    async def test_migrate_success(
        self, mock_get_client: MagicMock, transfer_deployment: DeploymentResponse
    ):
        """Test successful deployment migration."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow dependency with destination_id
        mock_flow_dependency = MagicMock()
        destination_flow_id = uuid.uuid4()
        mock_flow_dependency.destination_id = destination_flow_id

        # Mock storage dependency with destination_id
        mock_storage_dependency = MagicMock()
        destination_storage_id = uuid.uuid4()
        mock_storage_dependency.destination_id = destination_storage_id

        # Mock successful creation
        created_deployment_id = uuid.uuid4()
        mock_client.create_deployment.return_value = created_deployment_id

        destination_deployment = DeploymentResponse(
            id=created_deployment_id,
            name=transfer_deployment.name,
            flow_id=destination_flow_id,
            schedules=transfer_deployment.schedules,
            tags=transfer_deployment.tags,
            parameters=transfer_deployment.parameters,
        )
        mock_client.read_deployment.return_value = destination_deployment

        migratable = await MigratableDeployment.construct(transfer_deployment)
        # Set up the dependencies manually
        migratable._dependencies[transfer_deployment.flow_id] = mock_flow_dependency
        migratable._dependencies[transfer_deployment.storage_document_id] = (
            mock_storage_dependency
        )

        await migratable.migrate()

        # Verify client calls
        mock_client.create_deployment.assert_called_once()
        mock_client.read_deployment.assert_called_once_with(created_deployment_id)

        # Verify destination_deployment is set
        assert migratable.destination_deployment == destination_deployment
        assert migratable.destination_id == created_deployment_id

    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    async def test_migrate_with_schedules(
        self, mock_get_client: MagicMock, transfer_deployment: DeploymentResponse
    ):
        """Test migration with deployment schedules."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow dependency
        mock_flow_dependency = MagicMock()
        destination_flow_id = uuid.uuid4()
        mock_flow_dependency.destination_id = destination_flow_id

        # Mock storage dependency
        mock_storage_dependency = MagicMock()
        destination_storage_id = uuid.uuid4()
        mock_storage_dependency.destination_id = destination_storage_id

        # Mock successful creation
        created_deployment_id = uuid.uuid4()
        mock_client.create_deployment.return_value = created_deployment_id
        mock_client.read_deployment.return_value = MagicMock(id=created_deployment_id)

        migratable = await MigratableDeployment.construct(transfer_deployment)
        migratable._dependencies[transfer_deployment.flow_id] = mock_flow_dependency
        migratable._dependencies[transfer_deployment.storage_document_id] = (
            mock_storage_dependency
        )

        await migratable.migrate()

        # Verify schedules are properly converted
        create_call = mock_client.create_deployment.call_args[1]
        assert "schedules" in create_call
        schedules = create_call["schedules"]
        assert len(schedules) == len(transfer_deployment.schedules)
        for schedule in schedules:
            assert isinstance(schedule, DeploymentScheduleCreate)

    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    async def test_migrate_already_exists(
        self, mock_get_client: MagicMock, transfer_deployment: DeploymentResponse
    ):
        """Test migration when deployment already exists."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow dependency
        mock_flow_dependency = MagicMock()
        destination_flow_id = uuid.uuid4()
        mock_flow_dependency.destination_id = destination_flow_id

        # Mock storage dependency
        mock_storage_dependency = MagicMock()
        destination_storage_id = uuid.uuid4()
        mock_storage_dependency.destination_id = destination_storage_id

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_deployment.side_effect = ObjectAlreadyExists(mock_http_exc)

        # Mock successful read of existing deployment
        existing_deployment = DeploymentResponse(
            id=uuid.uuid4(),
            name=transfer_deployment.name,
            flow_id=destination_flow_id,
            schedules=[],
            tags=["existing"],
            parameters=transfer_deployment.parameters,
        )
        mock_client.read_deployment.return_value = existing_deployment

        migratable = await MigratableDeployment.construct(transfer_deployment)
        migratable._dependencies[transfer_deployment.flow_id] = mock_flow_dependency
        migratable._dependencies[transfer_deployment.storage_document_id] = (
            mock_storage_dependency
        )

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify calls
        mock_client.create_deployment.assert_called_once()
        mock_client.read_deployment.assert_called_once_with(transfer_deployment.id)

        # Verify destination_deployment is set to existing
        assert migratable.destination_deployment == existing_deployment
        assert migratable.destination_id == existing_deployment.id

    @patch("prefect.cli.transfer._migratable_resources.deployments.get_client")
    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    async def test_migrate_limit_reached(
        self, mock_get_client: MagicMock, transfer_deployment: DeploymentResponse
    ):
        """Test migration when deployment limit is reached."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock flow dependency
        mock_flow_dependency = MagicMock()
        destination_flow_id = uuid.uuid4()
        mock_flow_dependency.destination_id = destination_flow_id

        # Mock storage dependency
        mock_storage_dependency = MagicMock()
        destination_storage_id = uuid.uuid4()
        mock_storage_dependency.destination_id = destination_storage_id

        # Mock ObjectLimitReached exception on create
        mock_client.create_deployment.side_effect = ObjectLimitReached("Limit reached")

        migratable = await MigratableDeployment.construct(transfer_deployment)
        migratable._dependencies[transfer_deployment.flow_id] = mock_flow_dependency
        migratable._dependencies[transfer_deployment.storage_document_id] = (
            mock_storage_dependency
        )

        # Should raise TransferSkipped
        with pytest.raises(
            TransferSkipped, match=r"Deployment limit reached \(upgrade tier\)"
        ):
            await migratable.migrate()

        # Verify calls
        mock_client.create_deployment.assert_called_once()

    async def test_migrate_missing_flow_dependency_raises_error(
        self, transfer_deployment: DeploymentResponse
    ):
        """Test migrate raises error when flow dependency is missing."""
        migratable = await MigratableDeployment.construct(transfer_deployment)

        with pytest.raises(ValueError, match="Unable to find destination flow"):
            await migratable.migrate()

    async def test_migrate_missing_storage_dependency_raises_error(
        self, transfer_deployment_with_infra: DeploymentResponse
    ):
        """Test migrate raises error when storage dependency is missing."""
        # Mock flow dependency but not storage
        mock_flow_dependency = MagicMock()
        mock_flow_dependency.destination_id = uuid.uuid4()

        # Create deployment with storage document but missing dependency
        deployment = DeploymentResponse(
            id=uuid.uuid4(),
            name="test-deployment",
            flow_id=transfer_deployment_with_infra.flow_id,
            schedules=[],
            tags=[],
            parameters={},
            storage_document_id=uuid.uuid4(),  # Has storage but no dependency
            infrastructure_document_id=None,
        )

        migratable = await MigratableDeployment.construct(deployment)
        migratable._dependencies[deployment.flow_id] = mock_flow_dependency

        with pytest.raises(
            ValueError, match="Unable to find destination storage document"
        ):
            await migratable.migrate()

    async def test_migrate_missing_infrastructure_dependency_raises_error(
        self, transfer_deployment_with_infra: DeploymentResponse
    ):
        """Test migrate raises error when infrastructure dependency is missing."""
        # Mock flow dependency but not infrastructure
        mock_flow_dependency = MagicMock()
        mock_flow_dependency.destination_id = uuid.uuid4()

        # Create deployment with infrastructure document but missing dependency
        deployment = DeploymentResponse(
            id=uuid.uuid4(),
            name="test-deployment",
            flow_id=transfer_deployment_with_infra.flow_id,
            schedules=[],
            tags=[],
            parameters={},
            storage_document_id=None,
            infrastructure_document_id=uuid.uuid4(),  # Has infrastructure but no dependency
        )

        migratable = await MigratableDeployment.construct(deployment)
        migratable._dependencies[deployment.flow_id] = mock_flow_dependency

        with pytest.raises(
            ValueError, match="Unable to find destination infrastructure document"
        ):
            await migratable.migrate()
