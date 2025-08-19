import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.concurrency_limits import (
    MigratableGlobalConcurrencyLimit,
)
from prefect.client.schemas.actions import GlobalConcurrencyLimitCreate
from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse
from prefect.exceptions import ObjectAlreadyExists


class TestMigratableGlobalConcurrencyLimit:
    async def test_construct_creates_new_instance(
        self, transfer_global_concurrency_limit: GlobalConcurrencyLimitResponse
    ):
        """Test that construct creates a new MigratableGlobalConcurrencyLimit instance."""
        migratable = await MigratableGlobalConcurrencyLimit.construct(
            transfer_global_concurrency_limit
        )

        assert isinstance(migratable, MigratableGlobalConcurrencyLimit)
        assert (
            migratable.source_global_concurrency_limit
            == transfer_global_concurrency_limit
        )
        assert migratable.source_id == transfer_global_concurrency_limit.id
        assert migratable.destination_global_concurrency_limit is None
        assert migratable.destination_id is None

    async def test_construct_returns_cached_instance(
        self, transfer_global_concurrency_limit: GlobalConcurrencyLimitResponse
    ):
        """Test that construct returns cached instance for same ID."""
        # Clear any existing instances
        MigratableGlobalConcurrencyLimit._instances.clear()

        # Create first instance
        migratable1 = await MigratableGlobalConcurrencyLimit.construct(
            transfer_global_concurrency_limit
        )

        # Create second instance with same limit
        migratable2 = await MigratableGlobalConcurrencyLimit.construct(
            transfer_global_concurrency_limit
        )

        # Should be the same instance
        assert migratable1 is migratable2
        assert len(MigratableGlobalConcurrencyLimit._instances) == 1

    async def test_construct_different_limits_create_different_instances(
        self, session: AsyncSession
    ):
        """Test that different concurrency limits create different instances."""
        from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse
        from prefect.server import models, schemas

        # Create two different concurrency limits
        orm_limit1 = await models.concurrency_limits_v2.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimitV2(
                name=f"test-limit-1-{uuid.uuid4()}",
                limit=3,
                active=True,
                active_slots=0,
            ),
        )
        orm_limit2 = await models.concurrency_limits_v2.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimitV2(
                name=f"test-limit-2-{uuid.uuid4()}",
                limit=10,
                active=False,
                active_slots=5,
            ),
        )
        await session.commit()

        # Convert to client schema objects
        limit1 = GlobalConcurrencyLimitResponse(
            id=orm_limit1.id,
            name=orm_limit1.name,
            limit=orm_limit1.limit,
            active=orm_limit1.active,
            active_slots=orm_limit1.active_slots,
            slot_decay_per_second=orm_limit1.slot_decay_per_second,
            created=orm_limit1.created,
            updated=orm_limit1.updated,
        )
        limit2 = GlobalConcurrencyLimitResponse(
            id=orm_limit2.id,
            name=orm_limit2.name,
            limit=orm_limit2.limit,
            active=orm_limit2.active,
            active_slots=orm_limit2.active_slots,
            slot_decay_per_second=orm_limit2.slot_decay_per_second,
            created=orm_limit2.created,
            updated=orm_limit2.updated,
        )

        # Clear any existing instances
        MigratableGlobalConcurrencyLimit._instances.clear()

        migratable1 = await MigratableGlobalConcurrencyLimit.construct(limit1)
        migratable2 = await MigratableGlobalConcurrencyLimit.construct(limit2)

        assert migratable1 is not migratable2
        assert len(MigratableGlobalConcurrencyLimit._instances) == 2
        assert migratable1.source_id != migratable2.source_id

    async def test_get_instance_returns_cached_instance(
        self, transfer_global_concurrency_limit: GlobalConcurrencyLimitResponse
    ):
        """Test that get_instance returns cached instance."""
        # Clear any existing instances
        MigratableGlobalConcurrencyLimit._instances.clear()

        # Create instance
        migratable = await MigratableGlobalConcurrencyLimit.construct(
            transfer_global_concurrency_limit
        )

        # Retrieve instance
        retrieved = await MigratableGlobalConcurrencyLimit.get_instance(
            transfer_global_concurrency_limit.id
        )

        assert retrieved is migratable

    async def test_get_instance_returns_none_for_unknown_id(self):
        """Test that get_instance returns None for unknown ID."""
        # Clear any existing instances
        MigratableGlobalConcurrencyLimit._instances.clear()

        unknown_id = uuid.uuid4()
        retrieved = await MigratableGlobalConcurrencyLimit.get_instance(unknown_id)

        assert retrieved is None

    async def test_get_dependencies_returns_empty_list(
        self, transfer_global_concurrency_limit: GlobalConcurrencyLimitResponse
    ):
        """Test that get_dependencies returns empty list (concurrency limits have no dependencies)."""
        migratable = await MigratableGlobalConcurrencyLimit.construct(
            transfer_global_concurrency_limit
        )
        dependencies = await migratable.get_dependencies()

        assert dependencies == []

    @patch("prefect.cli.transfer._migratable_resources.concurrency_limits.get_client")
    async def test_migrate_success(
        self,
        mock_get_client: MagicMock,
        transfer_global_concurrency_limit: GlobalConcurrencyLimitResponse,
    ):
        """Test successful concurrency limit migration."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock successful creation and read
        destination_limit = GlobalConcurrencyLimitResponse(
            id=uuid.uuid4(),
            name=transfer_global_concurrency_limit.name,
            limit=transfer_global_concurrency_limit.limit,
            active=transfer_global_concurrency_limit.active,
            active_slots=transfer_global_concurrency_limit.active_slots,
            slot_decay_per_second=transfer_global_concurrency_limit.slot_decay_per_second,
            created=transfer_global_concurrency_limit.created,
            updated=transfer_global_concurrency_limit.updated,
        )
        mock_client.create_global_concurrency_limit.return_value = (
            None  # This method doesn't return the object
        )
        mock_client.read_global_concurrency_limit_by_name.return_value = (
            destination_limit
        )

        migratable = await MigratableGlobalConcurrencyLimit.construct(
            transfer_global_concurrency_limit
        )
        await migratable.migrate()

        # Verify client was called correctly
        mock_client.create_global_concurrency_limit.assert_called_once_with(
            concurrency_limit=GlobalConcurrencyLimitCreate(
                name=transfer_global_concurrency_limit.name,
                limit=transfer_global_concurrency_limit.limit,
                active=transfer_global_concurrency_limit.active,
                active_slots=transfer_global_concurrency_limit.active_slots,
            )
        )
        mock_client.read_global_concurrency_limit_by_name.assert_called_once_with(
            transfer_global_concurrency_limit.name
        )

        # Verify destination_global_concurrency_limit is set
        assert migratable.destination_global_concurrency_limit == destination_limit
        assert migratable.destination_id == destination_limit.id

    @patch("prefect.cli.transfer._migratable_resources.concurrency_limits.get_client")
    async def test_migrate_already_exists_raises_transfer_skipped(
        self,
        mock_get_client: MagicMock,
        transfer_global_concurrency_limit: GlobalConcurrencyLimitResponse,
    ):
        """Test migration when concurrency limit already exists raises TransferSkipped."""
        # Mock the client
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock ObjectAlreadyExists exception on create
        mock_http_exc = Exception("Conflict")
        mock_client.create_global_concurrency_limit.side_effect = ObjectAlreadyExists(
            mock_http_exc
        )

        # Mock successful read of existing limit
        existing_limit = GlobalConcurrencyLimitResponse(
            id=uuid.uuid4(),
            name=transfer_global_concurrency_limit.name,
            limit=10,  # Different limit to show it reads existing
            active=False,  # Different active state
            active_slots=2,
            slot_decay_per_second=1.5,
            created=transfer_global_concurrency_limit.created,
            updated=transfer_global_concurrency_limit.updated,
        )
        mock_client.read_global_concurrency_limit_by_name.return_value = existing_limit

        migratable = await MigratableGlobalConcurrencyLimit.construct(
            transfer_global_concurrency_limit
        )

        # Should raise TransferSkipped
        with pytest.raises(TransferSkipped, match="Already exists"):
            await migratable.migrate()

        # Verify client calls
        mock_client.create_global_concurrency_limit.assert_called_once()
        mock_client.read_global_concurrency_limit_by_name.assert_called_once_with(
            transfer_global_concurrency_limit.name
        )

        # Verify destination_global_concurrency_limit is still set to the existing limit
        assert migratable.destination_global_concurrency_limit == existing_limit
        assert migratable.destination_id == existing_limit.id

    @pytest.mark.parametrize(
        "active,active_slots,limit",
        [
            (True, 0, 5),
            (False, 2, 10),
            (True, 8, 8),  # At capacity
        ],
    )
    async def test_concurrency_limit_with_different_states(
        self, session: AsyncSession, active: bool, active_slots: int, limit: int
    ):
        """Test concurrency limits with different active states."""
        from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse
        from prefect.server import models, schemas

        # Clear instances before test
        MigratableGlobalConcurrencyLimit._instances.clear()

        orm_limit = await models.concurrency_limits_v2.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimitV2(
                name=f"test-limit-{uuid.uuid4()}",
                limit=limit,
                active=active,
                active_slots=active_slots,
            ),
        )
        await session.commit()

        # Convert to client schema object
        client_limit = GlobalConcurrencyLimitResponse(
            id=orm_limit.id,
            name=orm_limit.name,
            limit=orm_limit.limit,
            active=orm_limit.active,
            active_slots=orm_limit.active_slots,
            slot_decay_per_second=orm_limit.slot_decay_per_second,
            created=orm_limit.created,
            updated=orm_limit.updated,
        )

        # Test construction works with different states
        migratable = await MigratableGlobalConcurrencyLimit.construct(client_limit)
        assert migratable.source_global_concurrency_limit.active == active
        assert migratable.source_global_concurrency_limit.active_slots == active_slots
        assert migratable.source_global_concurrency_limit.limit == limit

    @pytest.mark.parametrize(
        "name_prefix,limit,active_slots",
        [
            ("zero-limit", 0, 0),
            ("large-limit", 1000000, 0),
            ("single-limit", 1, 1),
        ],
    )
    async def test_concurrency_limit_with_edge_case_values(
        self, session: AsyncSession, name_prefix: str, limit: int, active_slots: int
    ):
        """Test concurrency limits with edge case values."""
        from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse
        from prefect.server import models, schemas

        # Clear instances before test
        MigratableGlobalConcurrencyLimit._instances.clear()

        orm_limit = await models.concurrency_limits_v2.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimitV2(
                name=f"{name_prefix}-{uuid.uuid4()}",
                limit=limit,
                active=True,
                active_slots=active_slots,
            ),
        )
        await session.commit()

        # Convert to client schema object
        client_limit = GlobalConcurrencyLimitResponse(
            id=orm_limit.id,
            name=orm_limit.name,
            limit=orm_limit.limit,
            active=orm_limit.active,
            active_slots=orm_limit.active_slots,
            slot_decay_per_second=orm_limit.slot_decay_per_second,
            created=orm_limit.created,
            updated=orm_limit.updated,
        )

        # Test construction works with edge case values
        migratable = await MigratableGlobalConcurrencyLimit.construct(client_limit)
        assert migratable.source_global_concurrency_limit.limit == limit
        assert migratable.source_global_concurrency_limit.active_slots == active_slots
