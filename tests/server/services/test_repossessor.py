from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.concurrency.lease_storage import ConcurrencyLimitLeaseMetadata
from prefect.server.concurrency.lease_storage.memory import (
    ConcurrencyLeaseStorage,
)
from prefect.server.models.concurrency_limits_v2 import (
    bulk_increment_active_slots,
    bulk_read_concurrency_limits,
    create_concurrency_limit,
)
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.server.services.repossessor import Repossessor
from prefect.settings.context import get_current_settings


def test_service_settings():
    """Test that service_settings returns correct configuration"""
    settings = Repossessor.service_settings()
    assert settings == get_current_settings().server.services.repossessor


class TestRepossessor:
    @pytest.fixture
    def lease_storage(self):
        """Create a fresh concurrency lease storage for testing"""
        storage = ConcurrencyLeaseStorage()
        storage.leases.clear()
        storage.expirations.clear()
        return storage

    @pytest.fixture
    def repossessor(self, lease_storage):
        """Create repossessor with test lease storage"""
        repossessor = Repossessor()
        repossessor.concurrency_lease_storage = lease_storage
        return repossessor

    @pytest.fixture
    async def concurrency_limit(self, session: AsyncSession):
        """Create a concurrency limit in the database"""
        limit = await create_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2(
                name="test_limit",
                limit=10,
                avg_slot_occupancy_seconds=0.5,
            ),
        )
        await session.commit()
        return limit

    async def test_run_once_with_expired_leases(
        self, repossessor, lease_storage, concurrency_limit, session: AsyncSession
    ):
        """Test processing expired leases successfully"""
        # Take a couple of slots
        await bulk_increment_active_slots(session, [concurrency_limit.id], 2)
        await session.commit()

        # Create a lease with metadata
        resource_ids = [concurrency_limit.id]
        metadata = ConcurrencyLimitLeaseMetadata(slots=2)
        await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(seconds=-1),  # Already expired
            metadata=metadata,
        )

        # Verify initial state - lease should exist
        assert len(lease_storage.leases) == 1

        # Run the repossessor
        await repossessor.run_once()

        # Verify the lease was processed and removed
        assert len(lease_storage.leases) == 0

        # Verify the slots were decremented
        limits = await bulk_read_concurrency_limits(session, [concurrency_limit.name])
        assert len(limits) == 1
        assert limits[0].active_slots == 0

    async def test_run_once_with_multiple_expired_leases(
        self, repossessor, lease_storage, session: AsyncSession
    ):
        """Test processing multiple expired leases"""
        # Create multiple concurrency limits
        limits = []
        for i in range(3):
            limit = await create_concurrency_limit(
                session=session,
                concurrency_limit=ConcurrencyLimitV2(
                    name=f"test_limit_{i}",
                    limit=10,
                    slot_decay_per_second=0.0,
                    avg_slot_occupancy_seconds=2.0,
                ),
            )
            limits.append(limit)

        await session.commit()

        # Create multiple expired leases
        for i, limit in enumerate(limits):
            slots = i + 1
            metadata = ConcurrencyLimitLeaseMetadata(slots=slots)
            await lease_storage.create_lease(
                resource_ids=[limit.id],
                ttl=timedelta(seconds=-1),  # Already expired
                metadata=metadata,
            )

        # Verify initial state - all leases should exist
        assert len(lease_storage.leases) == 3

        # Run the repossessor
        await repossessor.run_once()

        # Verify all leases were processed
        assert len(lease_storage.leases) == 0

    async def test_run_once_with_no_expired_leases(
        self, repossessor, lease_storage, concurrency_limit
    ):
        """Test behavior when no expired leases exist"""
        # Create a non-expired lease
        resource_ids = [concurrency_limit.id]
        metadata = ConcurrencyLimitLeaseMetadata(slots=2)
        await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(minutes=5),  # Not expired
            metadata=metadata,
        )

        # Verify initial state - lease should exist
        assert len(lease_storage.leases) == 1

        # Run the repossessor
        await repossessor.run_once()

        # Verify lease was not processed (still exists)
        assert len(lease_storage.leases) == 1

    async def test_run_once_with_missing_lease(
        self, repossessor, lease_storage, concurrency_limit
    ):
        """Test handling of missing lease (lease returns None)"""
        # Create a lease but manually remove it to simulate missing lease
        resource_ids = [concurrency_limit.id]
        metadata = ConcurrencyLimitLeaseMetadata(slots=1)
        await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(seconds=-1),  # Already expired
            metadata=metadata,
        )

        # Manually remove the lease to simulate it being missing
        lease_storage.leases.clear()

        # Run the repossessor
        await repossessor.run_once()

        # Verify no leases remain (should handle missing lease gracefully)
        assert len(lease_storage.leases) == 0

    async def test_run_once_with_lease_missing_metadata(
        self, repossessor, lease_storage, concurrency_limit
    ):
        """Test handling of lease with missing metadata"""
        # Create a lease without metadata
        resource_ids = [concurrency_limit.id]
        await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(seconds=-1),  # Already expired
            metadata=None,  # No metadata
        )

        # Verify initial state - lease should exist
        assert len(lease_storage.leases) == 1

        # Run the repossessor
        await repossessor.run_once()

        # Verify lease was not processed due to missing metadata
        assert len(lease_storage.leases) == 1  # Lease should still exist

    async def test_run_once_handles_mixed_valid_invalid_leases(
        self, repossessor, lease_storage, session: AsyncSession
    ):
        """Test processing mixed valid and invalid leases"""
        # Create multiple concurrency limits
        limits = []
        for i in range(3):
            limit = await create_concurrency_limit(
                session=session,
                concurrency_limit=ConcurrencyLimitV2(
                    name=f"test_limit_{i}",
                    limit=10,
                    slot_decay_per_second=0.0,
                    avg_slot_occupancy_seconds=2.0,
                ),
            )
            limits.append(limit)

        await session.commit()

        # First lease is valid
        valid_metadata = ConcurrencyLimitLeaseMetadata(slots=1)
        await lease_storage.create_lease(
            resource_ids=[limits[0].id],
            ttl=timedelta(seconds=-1),
            metadata=valid_metadata,
        )

        # Second lease has no metadata
        await lease_storage.create_lease(
            resource_ids=[limits[1].id],
            ttl=timedelta(seconds=-1),
            metadata=None,
        )

        # Third lease is valid
        valid_metadata2 = ConcurrencyLimitLeaseMetadata(slots=2)
        await lease_storage.create_lease(
            resource_ids=[limits[2].id],
            ttl=timedelta(seconds=-1),
            metadata=valid_metadata2,
        )

        # Verify initial state - all leases should exist
        assert len(lease_storage.leases) == 3

        # Run the repossessor
        await repossessor.run_once()

        # Only valid leases should be processed, invalid lease should remain
        assert len(lease_storage.leases) == 1  # Only the invalid lease should remain
