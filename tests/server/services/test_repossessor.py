from datetime import timedelta
from uuid import uuid4

import pytest
from docket import Docket
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.concurrency.lease_storage import ConcurrencyLimitLeaseMetadata
from prefect.server.concurrency.lease_storage.memory import (
    ConcurrencyLeaseStorage,
)
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.models.concurrency_limits_v2 import (
    bulk_increment_active_slots,
    bulk_read_concurrency_limits,
    create_concurrency_limit,
)
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.server.services.repossessor import (
    monitor_expired_leases,
    revoke_expired_lease,
)


class TestRevokeExpiredLease:
    @pytest.fixture
    def lease_storage(self):
        """Create a fresh concurrency lease storage for testing"""
        storage = ConcurrencyLeaseStorage()
        storage.leases.clear()
        storage.expirations.clear()
        return storage

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

    async def test_revoke_expired_lease(
        self, lease_storage, concurrency_limit, session: AsyncSession
    ):
        """Test revoking an expired lease successfully"""
        # Take a couple of slots
        await bulk_increment_active_slots(session, [concurrency_limit.id], 2)
        await session.commit()

        # Create a lease with metadata
        resource_ids = [concurrency_limit.id]
        metadata = ConcurrencyLimitLeaseMetadata(slots=2)
        lease = await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(seconds=-1),  # Already expired
            metadata=metadata,
        )

        # Verify initial state - lease should exist
        assert len(lease_storage.leases) == 1

        # Revoke the lease
        db = provide_database_interface()
        await revoke_expired_lease(
            lease.id,
            db=db,
            lease_storage=lease_storage,
        )

        # Verify the lease was processed and removed
        assert len(lease_storage.leases) == 0

        # Verify the slots were decremented
        limits = await bulk_read_concurrency_limits(session, [concurrency_limit.name])
        assert len(limits) == 1
        assert limits[0].active_slots == 0

    async def test_revoke_expired_lease_missing_lease(
        self, lease_storage, concurrency_limit
    ):
        """Test handling of missing lease (lease returns None)"""
        # Create a lease but manually remove it to simulate missing lease
        resource_ids = [concurrency_limit.id]
        metadata = ConcurrencyLimitLeaseMetadata(slots=1)
        lease = await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(seconds=-1),  # Already expired
            metadata=metadata,
        )

        # Manually remove the lease to simulate it being missing
        lease_storage.leases.clear()

        # Revoke the lease - should handle gracefully
        db = provide_database_interface()
        await revoke_expired_lease(
            lease.id,
            db=db,
            lease_storage=lease_storage,
        )

        # Verify no error was raised and no leases remain
        assert len(lease_storage.leases) == 0

    async def test_revoke_expired_lease_missing_metadata(
        self, lease_storage, concurrency_limit
    ):
        """Test handling of lease with missing metadata"""
        # Create a lease without metadata
        resource_ids = [concurrency_limit.id]
        lease = await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(seconds=-1),  # Already expired
            metadata=None,  # No metadata
        )

        # Verify initial state - lease should exist
        assert len(lease_storage.leases) == 1

        # Revoke the lease - should handle gracefully and not revoke
        db = provide_database_interface()
        await revoke_expired_lease(
            lease.id,
            db=db,
            lease_storage=lease_storage,
        )

        # Verify lease was not processed due to missing metadata
        assert len(lease_storage.leases) == 1  # Lease should still exist


class TestMonitorExpiredLeases:
    @pytest.fixture
    def lease_storage(self):
        """Create a fresh concurrency lease storage for testing"""
        storage = ConcurrencyLeaseStorage()
        storage.leases.clear()
        storage.expirations.clear()
        return storage

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

    async def test_monitor_finds_expired_leases(self, lease_storage, concurrency_limit):
        """Test that monitor_expired_leases finds expired leases"""
        # Create an expired lease
        resource_ids = [concurrency_limit.id]
        metadata = ConcurrencyLimitLeaseMetadata(slots=2)
        await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(seconds=-1),  # Already expired
            metadata=metadata,
        )

        # Verify initial state
        assert len(lease_storage.leases) == 1

        # Use a real Docket instance with unique name for isolation
        async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
            docket.register(revoke_expired_lease)

            await monitor_expired_leases(
                docket=docket,
                lease_storage=lease_storage,
            )

            # Verify a task was scheduled via snapshot
            snapshot = await docket.snapshot()
            assert snapshot.total_tasks == 1

    async def test_monitor_ignores_non_expired_leases(
        self, lease_storage, concurrency_limit
    ):
        """Test that monitor_expired_leases ignores non-expired leases"""
        # Create a non-expired lease
        resource_ids = [concurrency_limit.id]
        metadata = ConcurrencyLimitLeaseMetadata(slots=2)
        await lease_storage.create_lease(
            resource_ids=resource_ids,
            ttl=timedelta(minutes=5),  # Not expired
            metadata=metadata,
        )

        # Verify initial state
        assert len(lease_storage.leases) == 1

        # Use a real Docket instance with unique name for isolation
        async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
            docket.register(revoke_expired_lease)

            await monitor_expired_leases(
                docket=docket,
                lease_storage=lease_storage,
            )

            # Verify no tasks were scheduled
            snapshot = await docket.snapshot()
            assert snapshot.total_tasks == 0

    async def test_monitor_schedules_multiple_tasks(
        self, lease_storage, session: AsyncSession
    ):
        """Test that monitor schedules tasks for multiple expired leases"""
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

        # Verify initial state
        assert len(lease_storage.leases) == 3

        # Use a real Docket instance with unique name for isolation
        async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
            docket.register(revoke_expired_lease)

            await monitor_expired_leases(
                docket=docket,
                lease_storage=lease_storage,
            )

            # Verify all tasks were scheduled
            snapshot = await docket.snapshot()
            assert snapshot.total_tasks == 3
