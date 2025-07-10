from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from prefect.server.concurrency.lease_storage import ConcurrencyLimitLeaseMetadata
from prefect.server.concurrency.lease_storage.memory import (
    MemoryConcurrencyLeaseStorage,
)
from prefect.server.utilities.leasing import ResourceLease


class TestMemoryConcurrencyLeaseStorage:
    def test_singleton_pattern(self):
        instance1 = MemoryConcurrencyLeaseStorage()
        instance2 = MemoryConcurrencyLeaseStorage()
        assert instance1 is instance2

        instance1.leases = {
            uuid4(): ResourceLease(resource_ids=[uuid4()], metadata=None)
        }
        assert instance1.leases == instance2.leases

    @pytest.fixture
    def storage(self) -> MemoryConcurrencyLeaseStorage:
        storage = MemoryConcurrencyLeaseStorage()
        storage.leases.clear()
        storage.expirations.clear()
        return storage

    @pytest.fixture
    def sample_resource_ids(self) -> list[UUID]:
        return [uuid4(), uuid4()]

    @pytest.fixture
    def sample_metadata(self) -> ConcurrencyLimitLeaseMetadata:
        return ConcurrencyLimitLeaseMetadata(slots=5)

    async def test_create_lease_without_metadata(
        self, storage: MemoryConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        lease = await storage.create_lease(sample_resource_ids, ttl)

        assert lease.resource_ids == sample_resource_ids
        assert lease.metadata is None
        assert len(storage.leases) == 1
        assert len(storage.expirations) == 1

    async def test_create_lease_with_metadata(
        self,
        storage: MemoryConcurrencyLeaseStorage,
        sample_resource_ids: list[UUID],
        sample_metadata: ConcurrencyLimitLeaseMetadata,
    ):
        ttl = timedelta(minutes=5)
        lease = await storage.create_lease(sample_resource_ids, ttl, sample_metadata)

        assert lease.resource_ids == sample_resource_ids
        assert lease.metadata == sample_metadata
        assert len(storage.leases) == 1
        assert len(storage.expirations) == 1

    async def test_read_lease_existing(
        self, storage: MemoryConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        lease_id = list(storage.leases.keys())[0]
        read_lease = await storage.read_lease(lease_id)

        assert read_lease is not None
        assert read_lease.resource_ids == sample_resource_ids
        assert read_lease.metadata is None

    async def test_read_lease_non_existing(
        self, storage: MemoryConcurrencyLeaseStorage
    ):
        non_existing_id = uuid4()
        lease = await storage.read_lease(non_existing_id)
        assert lease is None

    async def test_renew_lease(
        self, storage: MemoryConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        lease_id = list(storage.leases.keys())[0]
        original_expiration = storage.expirations[lease_id]

        new_ttl = timedelta(minutes=10)
        await storage.renew_lease(lease_id, new_ttl)

        new_expiration = storage.expirations[lease_id]
        assert new_expiration > original_expiration

    async def test_release_lease(
        self, storage: MemoryConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        lease_id = list(storage.leases.keys())[0]
        assert lease_id in storage.leases
        assert lease_id in storage.expirations

        await storage.release_lease(lease_id)

        assert lease_id not in storage.leases
        assert lease_id not in storage.expirations

    async def test_release_lease_non_existing(
        self, storage: MemoryConcurrencyLeaseStorage
    ):
        non_existing_id = uuid4()
        # should not raise an exception
        await storage.release_lease(non_existing_id)

    async def test_read_expired_lease_ids_no_expired(
        self, storage: MemoryConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        expired_ids = await storage.read_expired_lease_ids()
        assert expired_ids == []

    async def test_read_expired_lease_ids_with_expired(
        self, storage: MemoryConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        expired_ttl = timedelta(seconds=-1)
        await storage.create_lease(sample_resource_ids, expired_ttl)

        expired_ids = await storage.read_expired_lease_ids()
        assert len(expired_ids) == 1
        assert expired_ids[0] in storage.leases

    async def test_read_expired_lease_ids_with_limit(
        self, storage: MemoryConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        expired_ttl = timedelta(seconds=-1)
        await storage.create_lease(sample_resource_ids, expired_ttl)
        await storage.create_lease(sample_resource_ids, expired_ttl)
        await storage.create_lease(sample_resource_ids, expired_ttl)

        expired_ids = await storage.read_expired_lease_ids(limit=2)
        assert len(expired_ids) == 2

    async def test_read_expired_lease_ids_mixed_expiration(
        self, storage: MemoryConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        expired_ttl = timedelta(seconds=-1)
        valid_ttl = timedelta(minutes=5)

        await storage.create_lease(sample_resource_ids, expired_ttl)
        await storage.create_lease(sample_resource_ids, valid_ttl)
        await storage.create_lease(sample_resource_ids, expired_ttl)

        expired_ids = await storage.read_expired_lease_ids()
        assert len(expired_ids) == 2
