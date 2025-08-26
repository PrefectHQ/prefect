import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.work_pools import MigratableWorkPool
from prefect.client.base import ServerType
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import WorkPool, WorkQueue
from prefect.exceptions import ObjectAlreadyExists, ObjectUnsupported


class TestMigratableWorkPool:
    async def test_construct_creates_new_instance_and_reads_default_queue(
        self, transfer_work_pool: WorkPool
    ):
        """Test that construct creates a new MigratableWorkPool instance and reads default queue."""
        # Clear any existing instances
        MigratableWorkPool._instances.clear()

        # Mock the client to return a default queue
        with patch(
            "prefect.cli.transfer._migratable_resources.work_pools.get_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client

            # Mock default queue
            default_queue = WorkQueue(
                id=transfer_work_pool.default_queue_id,
                name="default",
                description="Default queue",
                priority=1,
                concurrency_limit=None,
                filter=None,
                is_paused=False,
                last_polled=None,
                status=None,
                work_pool_id=transfer_work_pool.id,
            )
            mock_client.read_work_queue.return_value = default_queue

            migratable = await MigratableWorkPool.construct(transfer_work_pool)

            assert isinstance(migratable, MigratableWorkPool)
            assert migratable.source_work_pool == transfer_work_pool
            assert migratable.source_default_queue == default_queue
            assert migratable.source_id == transfer_work_pool.id
            assert migratable.destination_work_pool is None
            assert migratable.destination_id is None
            assert migratable._dependencies == []

            mock_client.read_work_queue.assert_called_once_with(
                transfer_work_pool.default_queue_id
            )

    async def test_construct_returns_cached_instance(
        self, transfer_work_pool: WorkPool
    ):
        """Test that construct returns cached instance for same ID."""
        # Clear any existing instances
        MigratableWorkPool._instances.clear()

        # Mock the client for both calls
        with patch(
            "prefect.cli.transfer._migratable_resources.work_pools.get_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client

            # Mock default queue
            default_queue = WorkQueue(
                id=transfer_work_pool.default_queue_id,
                name="default",
                description="Default queue",
                priority=1,
                concurrency_limit=None,
                filter=None,
                is_paused=False,
                last_polled=None,
                status=None,
                work_pool_id=transfer_work_pool.id,
            )
            mock_client.read_work_queue.return_value = default_queue

            # Create first instance
            migratable1 = await MigratableWorkPool.construct(transfer_work_pool)

            # Create second instance with same work pool
            migratable2 = await MigratableWorkPool.construct(transfer_work_pool)

            # Should be the same instance
            assert migratable1 is migratable2
            assert len(MigratableWorkPool._instances) == 1

            # Client should only be called once due to caching
            mock_client.read_work_queue.assert_called_once()

    async def test_get_instance_returns_cached_instance(
        self, transfer_work_pool: WorkPool
    ):
        """Test that get_instance returns cached instance."""
        # Clear any existing instances
        MigratableWorkPool._instances.clear()

        # Mock the client
        with patch(
            "prefect.cli.transfer._migratable_resources.work_pools.get_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client

            default_queue = WorkQueue(
                id=transfer_work_pool.default_queue_id,
                name="default",
                description="Default queue",
                priority=1,
                concurrency_limit=None,
                filter=None,
                is_paused=False,
                last_polled=None,
                status=None,
                work_pool_id=transfer_work_pool.id,
            )
            mock_client.read_work_queue.return_value = default_queue

            # Create instance
            migratable = await MigratableWorkPool.construct(transfer_work_pool)

            # Retrieve instance
            retrieved = await MigratableWorkPool.get_instance(transfer_work_pool.id)

            assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableWorkPool._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableWorkPool.get_instance(unknown_id)

        assert retrieved is None

    async def test_get_instance_by_name_returns_instance(
        self, transfer_work_pool: WorkPool
    ):
        """Test that get_instance_by_name returns cached instance."""
        # Clear any existing instances
        MigratableWorkPool._instances.clear()

        # Mock the client
        with patch(
            "prefect.cli.transfer._migratable_resources.work_pools.get_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client

            default_queue = WorkQueue(
                id=transfer_work_pool.default_queue_id,
                name="default",
                description="Default queue",
                priority=1,
                concurrency_limit=None,
                filter=None,
                is_paused=False,
                last_polled=None,
                status=None,
                work_pool_id=transfer_work_pool.id,
            )
            mock_client.read_work_queue.return_value = default_queue

            # Create instance
            migratable = await MigratableWorkPool.construct(transfer_work_pool)

            # Retrieve instance by name
            retrieved = await MigratableWorkPool.get_instance_by_name(
                transfer_work_pool.name
            )

            assert retrieved is migratable

    async def test_get_instance_by_name_returns_none_for_unknown_name(self):
        """Test that get_instance_by_name returns None for unknown name."""
        # Clear any existing instances
        MigratableWorkPool._instances.clear()

        retrieved = await MigratableWorkPool.get_instance_by_name("unknown-work-pool")

        assert retrieved is None

    @patch(
        "prefect.cli.transfer._migratable_resources.work_pools.construct_migratable_resource"
    )
    @patch("prefect.cli.transfer._migratable_resources.work_pools.get_client")
    async def test_get_dependencies_with_result_storage_block(
        self, mock_get_client: MagicMock, mock_construct_resource: AsyncMock
    ):
        """Test get_dependencies with result storage block dependency."""
        from prefect.client.schemas.objects import WorkPoolStorageConfiguration

        # Create work pool with result storage block
        storage_block_id = uuid.uuid4()
        work_pool = WorkPool(
            id=uuid.uuid4(),
            name="test-work-pool",
            type="test-type",
            base_job_template={},
            is_paused=False,
            concurrency_limit=None,
            storage_configuration=WorkPoolStorageConfiguration(
                default_result_storage_block_id=storage_block_id
            ),
            default_queue_id=uuid.uuid4(),
        )

        # Mock the client for construct
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        default_queue = WorkQueue(
            id=work_pool.default_queue_id,
            name="default",
            description="Default queue",
            priority=1,
            concurrency_limit=None,
            filter=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=work_pool.id,
        )

        # Mock for construct call
        mock_client.read_work_queue.return_value = default_queue

        # Mock for get_dependencies call
        mock_block_document = MagicMock()
        mock_block_document.id = storage_block_id
        mock_client.read_block_document.return_value = mock_block_document

        mock_migratable_block = MagicMock()
        mock_construct_resource.return_value = mock_migratable_block

        # Clear instances
        MigratableWorkPool._instances.clear()

        migratable = await MigratableWorkPool.construct(work_pool)
        dependencies = await migratable.get_dependencies()

        assert len(dependencies) == 1
        assert dependencies[0] == mock_migratable_block
        mock_client.read_block_document.assert_called_once_with(storage_block_id)
        mock_construct_resource.assert_called_once_with(mock_block_document)

    async def test_get_dependencies_with_no_storage_configuration(
        self, transfer_work_pool: WorkPool
    ):
        """Test get_dependencies with no storage configuration dependencies."""
        # Mock the client
        with patch(
            "prefect.cli.transfer._migratable_resources.work_pools.get_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client

            default_queue = WorkQueue(
                id=transfer_work_pool.default_queue_id,
                name="default",
                description="Default queue",
                priority=1,
                concurrency_limit=None,
                filter=None,
                is_paused=False,
                last_polled=None,
                status=None,
                work_pool_id=transfer_work_pool.id,
            )
            mock_client.read_work_queue.return_value = default_queue

            # Clear instances
            MigratableWorkPool._instances.clear()

            migratable = await MigratableWorkPool.construct(transfer_work_pool)
            dependencies = await migratable.get_dependencies()

            assert dependencies == []

    async def test_get_dependencies_cached(self, transfer_work_pool: WorkPool):
        """Test that dependencies are cached after first call."""
        # Mock the client
        with patch(
            "prefect.cli.transfer._migratable_resources.work_pools.get_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client

            default_queue = WorkQueue(
                id=transfer_work_pool.default_queue_id,
                name="default",
                description="Default queue",
                priority=1,
                concurrency_limit=None,
                filter=None,
                is_paused=False,
                last_polled=None,
                status=None,
                work_pool_id=transfer_work_pool.id,
            )
            mock_client.read_work_queue.return_value = default_queue

            # Clear instances
            MigratableWorkPool._instances.clear()

            migratable = await MigratableWorkPool.construct(transfer_work_pool)

            # Set up some mock dependencies
            mock_dependency = MagicMock()
            migratable._dependencies = [mock_dependency]

            dependencies1 = await migratable.get_dependencies()
            dependencies2 = await migratable.get_dependencies()

            # Should return the same cached result
            assert dependencies1 == dependencies2
            assert dependencies1 == [mock_dependency]

    @patch("prefect.cli.transfer._migratable_resources.work_pools.get_client")
    async def test_migrate_success_regular_pool(
        self, mock_get_client: MagicMock, transfer_work_pool: WorkPool
    ):
        """Test successful migration of regular work pool."""
        # Mock the client for construct
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        default_queue = WorkQueue(
            id=transfer_work_pool.default_queue_id,
            name="default",
            description="Default queue",
            priority=1,
            concurrency_limit=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=transfer_work_pool.id,
        )
        mock_client.read_work_queue.return_value = default_queue

        # Mock successful work pool creation
        destination_work_pool = WorkPool(
            id=uuid.uuid4(),
            name=transfer_work_pool.name,
            type=transfer_work_pool.type,
            base_job_template=transfer_work_pool.base_job_template,
            is_paused=transfer_work_pool.is_paused,
            concurrency_limit=transfer_work_pool.concurrency_limit,
            storage_configuration=transfer_work_pool.storage_configuration,
            default_queue_id=uuid.uuid4(),
        )
        mock_client.create_work_pool.return_value = destination_work_pool

        # Clear instances
        MigratableWorkPool._instances.clear()

        migratable = await MigratableWorkPool.construct(transfer_work_pool)
        await migratable.migrate()

        # Verify client calls
        mock_client.create_work_pool.assert_called_once_with(
            work_pool=WorkPoolCreate(
                name=transfer_work_pool.name,
                type=transfer_work_pool.type,
                base_job_template=transfer_work_pool.base_job_template,
                is_paused=transfer_work_pool.is_paused,
                concurrency_limit=transfer_work_pool.concurrency_limit,
                storage_configuration=transfer_work_pool.storage_configuration,
            )
        )
        mock_client.update_work_queue.assert_called_once_with(
            id=destination_work_pool.default_queue_id,
            description=default_queue.description,
            priority=default_queue.priority,
            concurrency_limit=default_queue.concurrency_limit,
        )

        # Verify destination_work_pool is set
        assert migratable.destination_work_pool == destination_work_pool
        assert migratable.destination_id == destination_work_pool.id

    @patch("prefect.cli.transfer._migratable_resources.work_pools.get_client")
    async def test_migrate_managed_pool_skipped(
        self, mock_get_client: MagicMock, transfer_managed_work_pool: WorkPool
    ):
        """Test that managed pools are skipped."""
        # Mock the client for construct
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        default_queue = WorkQueue(
            id=transfer_managed_work_pool.default_queue_id,
            name="default",
            description="Default queue",
            priority=1,
            concurrency_limit=None,
            filter=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=transfer_managed_work_pool.id,
        )
        mock_client.read_work_queue.return_value = default_queue

        # Clear instances
        MigratableWorkPool._instances.clear()

        migratable = await MigratableWorkPool.construct(transfer_managed_work_pool)

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Skipped managed pool"):
            await migratable.migrate()

        # Should not try to create work pool
        mock_client.create_work_pool.assert_not_called()

    @patch("prefect.cli.transfer._migratable_resources.work_pools.get_client")
    async def test_migrate_push_pool_with_cloud_server(
        self, mock_get_client: MagicMock, transfer_push_work_pool: WorkPool
    ):
        """Test that push pools work with cloud server."""
        # Mock the client for construct
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_client.server_type = ServerType.CLOUD  # Set server type to cloud

        default_queue = WorkQueue(
            id=transfer_push_work_pool.default_queue_id,
            name="default",
            description="Default queue",
            priority=1,
            concurrency_limit=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=transfer_push_work_pool.id,
        )
        mock_client.read_work_queue.return_value = default_queue

        # Mock successful work pool creation
        destination_work_pool = WorkPool(
            id=uuid.uuid4(),
            name=transfer_push_work_pool.name,
            type=transfer_push_work_pool.type,
            base_job_template=transfer_push_work_pool.base_job_template,
            is_paused=transfer_push_work_pool.is_paused,
            concurrency_limit=transfer_push_work_pool.concurrency_limit,
            storage_configuration=transfer_push_work_pool.storage_configuration,
            default_queue_id=uuid.uuid4(),
        )
        mock_client.create_work_pool.return_value = destination_work_pool

        # Clear instances
        MigratableWorkPool._instances.clear()

        migratable = await MigratableWorkPool.construct(transfer_push_work_pool)
        await migratable.migrate()

        # Should successfully create work pool
        mock_client.create_work_pool.assert_called_once()
        assert migratable.destination_work_pool == destination_work_pool

    @patch("prefect.cli.transfer._migratable_resources.work_pools.get_client")
    async def test_migrate_push_pool_without_cloud_server_skipped(
        self, mock_get_client: MagicMock, transfer_push_work_pool: WorkPool
    ):
        """Test that push pools are skipped without cloud server."""
        # Mock the client for construct
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_client.server_type = ServerType.EPHEMERAL  # Set server type to non-cloud

        default_queue = WorkQueue(
            id=transfer_push_work_pool.default_queue_id,
            name="default",
            description="Default queue",
            priority=1,
            concurrency_limit=None,
            filter=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=transfer_push_work_pool.id,
        )
        mock_client.read_work_queue.return_value = default_queue

        # Clear instances
        MigratableWorkPool._instances.clear()

        migratable = await MigratableWorkPool.construct(transfer_push_work_pool)

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Skipped push pool"):
            await migratable.migrate()

        # Should not try to create work pool
        mock_client.create_work_pool.assert_not_called()

    @patch("prefect.cli.transfer._migratable_resources.work_pools.get_client")
    async def test_migrate_unsupported_work_pool_skipped(
        self, mock_get_client: MagicMock, transfer_work_pool: WorkPool
    ):
        """Test that unsupported work pools are skipped."""
        # Mock the client for construct
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        default_queue = WorkQueue(
            id=transfer_work_pool.default_queue_id,
            name="default",
            description="Default queue",
            priority=1,
            concurrency_limit=None,
            filter=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=transfer_work_pool.id,
        )
        mock_client.read_work_queue.return_value = default_queue

        # Mock ObjectUnsupported exception on create
        mock_client.create_work_pool.side_effect = ObjectUnsupported("Unsupported")

        # Clear instances
        MigratableWorkPool._instances.clear()

        migratable = await MigratableWorkPool.construct(transfer_work_pool)

        # Should raise TransferSkipped
        with pytest.raises(
            TransferSkipped, match="Destination requires Standard/Pro tier"
        ):
            await migratable.migrate()

        # Verify client calls
        mock_client.create_work_pool.assert_called_once()

    @patch("prefect.cli.transfer._migratable_resources.work_pools.get_client")
    async def test_migrate_already_exists(
        self, mock_get_client: MagicMock, transfer_work_pool: WorkPool
    ):
        """Test migration when work pool already exists."""
        # Mock the client for construct
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        default_queue = WorkQueue(
            id=transfer_work_pool.default_queue_id,
            name="default",
            description="Default queue",
            priority=1,
            concurrency_limit=None,
            filter=None,
            is_paused=False,
            last_polled=None,
            status=None,
            work_pool_id=transfer_work_pool.id,
        )
        mock_client.read_work_queue.return_value = default_queue

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_work_pool.side_effect = ObjectAlreadyExists(mock_http_exc)

        # Mock successful read of existing work pool
        existing_work_pool = WorkPool(
            id=uuid.uuid4(),
            name=transfer_work_pool.name,
            type="existing-type",  # Different to show it reads existing
            base_job_template={"existing": "template"},
            is_paused=True,
            concurrency_limit=10,
            storage_configuration=transfer_work_pool.storage_configuration,
            default_queue_id=uuid.uuid4(),
        )
        mock_client.read_work_pool.return_value = existing_work_pool

        # Clear instances
        MigratableWorkPool._instances.clear()

        migratable = await MigratableWorkPool.construct(transfer_work_pool)

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify client calls
        mock_client.create_work_pool.assert_called_once()
        mock_client.read_work_pool.assert_called_once_with(transfer_work_pool.name)

        # Verify destination_work_pool is set to existing
        assert migratable.destination_work_pool == existing_work_pool
        assert migratable.destination_id == existing_work_pool.id
