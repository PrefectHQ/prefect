import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.work_queues import MigratableWorkQueue
from prefect.client.schemas.filters import WorkQueueFilter, WorkQueueFilterName
from prefect.client.schemas.objects import WorkQueue
from prefect.exceptions import ObjectAlreadyExists


class TestMigratableWorkQueue:
    async def test_construct_creates_new_instance(self, transfer_work_queue: WorkQueue):
        """Test that construct creates a new MigratableWorkQueue instance."""
        # Clear any existing instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(transfer_work_queue)

        assert isinstance(migratable, MigratableWorkQueue)
        assert migratable.source_work_queue == transfer_work_queue
        assert migratable.source_id == transfer_work_queue.id
        assert migratable.destination_work_queue is None
        assert migratable.destination_id is None
        assert migratable._dependencies == []

    async def test_construct_returns_cached_instance(
        self, transfer_work_queue: WorkQueue
    ):
        """Test that construct returns cached instance for same ID."""
        # Clear any existing instances
        MigratableWorkQueue._instances.clear()

        # Create first instance
        migratable1 = await MigratableWorkQueue.construct(transfer_work_queue)

        # Create second instance with same work queue
        migratable2 = await MigratableWorkQueue.construct(transfer_work_queue)

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableWorkQueue._instances) == 1

    async def test_get_instance_returns_cached_instance(
        self, transfer_work_queue: WorkQueue
    ):
        """Test that get_instance returns cached instance."""
        # Clear any existing instances
        MigratableWorkQueue._instances.clear()

        # Create instance
        migratable = await MigratableWorkQueue.construct(transfer_work_queue)

        # Retrieve instance
        retrieved = await MigratableWorkQueue.get_instance(transfer_work_queue.id)

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableWorkQueue._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableWorkQueue.get_instance(unknown_id)

        assert retrieved is None

    @patch(
        "prefect.cli.transfer._migratable_resources.work_queues.construct_migratable_resource"
    )
    @patch("prefect.cli.transfer._migratable_resources.work_queues.get_client")
    async def test_get_dependencies_with_work_pool_name(
        self, mock_get_client: MagicMock, mock_construct_resource: AsyncMock
    ):
        """Test get_dependencies with work pool name dependency."""
        # Create work queue with work pool name
        work_queue = WorkQueue(
            id=uuid.uuid4(),
            name="test-queue",
            description="Test queue",
            priority=1,
            concurrency_limit=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=uuid.uuid4(),
            work_pool_name="test-work-pool",
        )

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock work pool read
        mock_work_pool = MagicMock()
        mock_work_pool.name = "test-work-pool"
        mock_client.read_work_pool.return_value = mock_work_pool

        mock_migratable_work_pool = MagicMock()
        mock_construct_resource.return_value = mock_migratable_work_pool

        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(work_queue)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_work_pool
        mock_client.read_work_pool.assert_called_once_with("test-work-pool")
        mock_construct_resource.assert_called_once_with(mock_work_pool)

    @patch(
        "prefect.cli.transfer._migratable_resources.work_pools.MigratableWorkPool.get_instance_by_name"
    )
    async def test_get_dependencies_with_cached_work_pool_dependency(
        self, mock_get_instance_by_name: AsyncMock
    ):
        """Test get_dependencies with cached work pool dependency."""
        # Create work queue with work pool name
        work_queue = WorkQueue(
            id=uuid.uuid4(),
            name="test-queue",
            description="Test queue",
            priority=1,
            concurrency_limit=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=uuid.uuid4(),
            work_pool_name="test-work-pool",
        )

        # Mock cached work pool dependency
        mock_migratable_work_pool = MagicMock()
        mock_get_instance_by_name.return_value = mock_migratable_work_pool

        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(work_queue)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_work_pool
        mock_get_instance_by_name.assert_called_once_with(name="test-work-pool")

    async def test_get_dependencies_with_no_work_pool_name(
        self, transfer_work_queue: WorkQueue
    ):
        """Test get_dependencies with no work pool name (standalone queue)."""
        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(transfer_work_queue)
        dependencies = await migratable.get_dependencies()

        assert dependencies == []

    async def test_get_dependencies_cached(self):
        """Test that dependencies are cached after first call."""
        # Create work queue with work pool name
        work_queue = WorkQueue(
            id=uuid.uuid4(),
            name="test-queue",
            description="Test queue",
            priority=1,
            concurrency_limit=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=uuid.uuid4(),
            work_pool_name="test-work-pool",
        )

        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(work_queue)

        # Set up some mock dependencies
        mock_dependency = MagicMock()
        migratable._dependencies = [mock_dependency]

        dependencies1 = await migratable.get_dependencies()
        dependencies2 = await migratable.get_dependencies()

        # Should return the same cached result
        assert dependencies1 == dependencies2
        assert dependencies1 == [mock_dependency]

    @patch("prefect.cli.transfer._migratable_resources.work_queues.get_client")
    async def test_migrate_success_standalone_queue(
        self, mock_get_client: MagicMock, transfer_work_queue: WorkQueue
    ):
        """Test successful migration of standalone work queue."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock successful work queue creation
        destination_work_queue = WorkQueue(
            id=uuid.uuid4(),
            name=transfer_work_queue.name,
            description=transfer_work_queue.description,
            priority=transfer_work_queue.priority,
            concurrency_limit=transfer_work_queue.concurrency_limit,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=None,
            work_pool_name=None,
        )
        mock_client.create_work_queue.return_value = destination_work_queue

        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(transfer_work_queue)
        await migratable.migrate()

        # Verify client calls
        mock_client.create_work_queue.assert_called_once_with(
            name=transfer_work_queue.name,
            description=transfer_work_queue.description,
            priority=transfer_work_queue.priority,
            concurrency_limit=transfer_work_queue.concurrency_limit,
            work_pool_name=transfer_work_queue.work_pool_name,
        )

        # Verify destination_work_queue is set
        assert migratable.destination_work_queue == destination_work_queue
        assert migratable.destination_id == destination_work_queue.id

    @patch("prefect.cli.transfer._migratable_resources.work_queues.get_client")
    async def test_migrate_success_with_work_pool(
        self, mock_get_client: MagicMock, transfer_work_queue_with_pool: WorkQueue
    ):
        """Test successful migration of work queue with work pool."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock successful work queue creation
        destination_work_queue = WorkQueue(
            id=uuid.uuid4(),
            name=transfer_work_queue_with_pool.name,
            description=transfer_work_queue_with_pool.description,
            priority=transfer_work_queue_with_pool.priority,
            concurrency_limit=transfer_work_queue_with_pool.concurrency_limit,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=uuid.uuid4(),
            work_pool_name="test-pool",
        )
        mock_client.create_work_queue.return_value = destination_work_queue

        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(transfer_work_queue_with_pool)
        await migratable.migrate()

        # Verify client calls
        mock_client.create_work_queue.assert_called_once_with(
            name=transfer_work_queue_with_pool.name,
            description=transfer_work_queue_with_pool.description,
            priority=transfer_work_queue_with_pool.priority,
            concurrency_limit=transfer_work_queue_with_pool.concurrency_limit,
            work_pool_name=transfer_work_queue_with_pool.work_pool_name,
        )

        # Verify destination_work_queue is set
        assert migratable.destination_work_queue == destination_work_queue
        assert migratable.destination_id == destination_work_queue.id

    @patch("prefect.cli.transfer._migratable_resources.work_queues.get_client")
    async def test_migrate_already_exists(
        self, mock_get_client: MagicMock, transfer_work_queue_with_pool: WorkQueue
    ):
        """Test migration when work queue already exists."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_work_queue.side_effect = ObjectAlreadyExists(mock_http_exc)

        # Mock existing work queue in read_work_queues response
        existing_work_queue = WorkQueue(
            id=uuid.uuid4(),
            name=transfer_work_queue_with_pool.name,
            description="existing description",  # Different to show it reads existing
            priority=2,
            concurrency_limit=10,
            is_paused=True,
            last_polled=None,
            status=None,
            work_pool_id=uuid.uuid4(),
            work_pool_name="test-pool",
        )
        mock_client.read_work_queues.return_value = [existing_work_queue]

        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(transfer_work_queue_with_pool)

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify client calls
        mock_client.create_work_queue.assert_called_once()
        mock_client.read_work_queues.assert_called_once_with(
            work_pool_name=transfer_work_queue_with_pool.work_pool_name,
            work_queue_filter=WorkQueueFilter(
                name=WorkQueueFilterName(any_=[transfer_work_queue_with_pool.name]),
            ),
        )

        # Verify destination_work_queue is set to existing
        assert migratable.destination_work_queue == existing_work_queue
        assert migratable.destination_id == existing_work_queue.id

    @patch("prefect.cli.transfer._migratable_resources.work_queues.get_client")
    async def test_migrate_already_exists_queue_not_found_in_list(
        self, mock_get_client: MagicMock, transfer_work_queue_with_pool: WorkQueue
    ):
        """Test migration when work queue already exists but is not found in list."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_work_queue.side_effect = ObjectAlreadyExists(mock_http_exc)

        # Mock empty work queues list (queue not found)
        mock_client.read_work_queues.return_value = []

        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(transfer_work_queue_with_pool)

        with pytest.raises(RuntimeError):
            await migratable.migrate()

        # Verify calls
        mock_client.create_work_queue.assert_called_once()
        mock_client.read_work_queues.assert_called_once()

        # destination_work_queue should remain None since we couldn't find it
        assert migratable.destination_work_queue is None

    @patch("prefect.cli.transfer._migratable_resources.work_queues.get_client")
    async def test_migrate_skips_default_work_queue(self, mock_get_client: MagicMock):
        """Test that migration skips work queues named 'default'."""
        # Create a work queue with name 'default'
        default_work_queue = WorkQueue(
            id=uuid.uuid4(),
            name="default",
            description="Default work queue",
            priority=1,
            concurrency_limit=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=uuid.uuid4(),
            work_pool_name="test-pool",
        )

        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock empty work queues list (queue not found)
        mock_client.read_work_queues.return_value = [default_work_queue]

        # Clear instances
        MigratableWorkQueue._instances.clear()

        migratable = await MigratableWorkQueue.construct(default_work_queue)

        # Should raise TransferSkipped for default work queue
        with pytest.raises(
            TransferSkipped,
            match="Default work queues are created with work pools",
        ):
            await migratable.migrate()

        # Verify no client calls were made since it's skipped early
        assert migratable.destination_work_queue is None
