from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from prefect.server.concurrency.lease_storage import ConcurrencyLimitLeaseMetadata
from prefect.server.concurrency.lease_storage.memory import (
    ConcurrencyLeaseStorage,
)
from prefect.server.utilities.leasing import ResourceLease


class TestMemoryConcurrencyLeaseStorage:
    def test_singleton_pattern(self):
        instance1 = ConcurrencyLeaseStorage()
        instance2 = ConcurrencyLeaseStorage()
        assert instance1 is instance2

        instance1.leases = {
            uuid4(): ResourceLease(
                resource_ids=[uuid4()],
                metadata=None,
                expiration=datetime.now(timezone.utc),
            )
        }
        assert instance1.leases == instance2.leases

    @pytest.fixture
    def storage(self) -> ConcurrencyLeaseStorage:
        storage = ConcurrencyLeaseStorage()
        storage.leases.clear()
        storage.expirations.clear()
        return storage

    @pytest.fixture
    def sample_resource_ids(self) -> list[UUID]:
        return [uuid4(), uuid4()]

    @pytest.fixture
    def sample_metadata(self) -> ConcurrencyLimitLeaseMetadata:
        return ConcurrencyLimitLeaseMetadata(slots=5)

    @pytest.fixture
    def sample_metadata_with_holder(self) -> ConcurrencyLimitLeaseMetadata:
        return ConcurrencyLimitLeaseMetadata(
            slots=3,
            holder={"type": "flow_run", "id": uuid4()},
        )

    async def test_create_lease_without_metadata(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        lease = await storage.create_lease(sample_resource_ids, ttl)

        assert lease.resource_ids == sample_resource_ids
        assert lease.metadata is None
        assert len(storage.leases) == 1
        assert len(storage.expirations) == 1

    async def test_create_lease_with_metadata(
        self,
        storage: ConcurrencyLeaseStorage,
        sample_resource_ids: list[UUID],
        sample_metadata: ConcurrencyLimitLeaseMetadata,
    ):
        ttl = timedelta(minutes=5)
        lease = await storage.create_lease(sample_resource_ids, ttl, sample_metadata)

        assert lease.resource_ids == sample_resource_ids
        assert lease.metadata == sample_metadata
        assert len(storage.leases) == 1
        assert len(storage.expirations) == 1

    async def test_create_lease_with_holder(
        self,
        storage: ConcurrencyLeaseStorage,
        sample_resource_ids: list[UUID],
        sample_metadata_with_holder: ConcurrencyLimitLeaseMetadata,
    ):
        ttl = timedelta(minutes=5)
        lease = await storage.create_lease(
            sample_resource_ids, ttl, sample_metadata_with_holder
        )

        assert lease.resource_ids == sample_resource_ids
        assert lease.metadata == sample_metadata_with_holder
        assert lease.metadata.holder.model_dump() == {
            "type": "flow_run",
            "id": lease.metadata.holder.id,
        }
        assert len(storage.leases) == 1
        assert len(storage.expirations) == 1

    async def test_read_lease_existing(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        lease_id = list(storage.leases.keys())[0]
        read_lease = await storage.read_lease(lease_id)

        assert read_lease is not None
        assert read_lease.resource_ids == sample_resource_ids
        assert read_lease.metadata is None

    async def test_read_lease_with_holder(
        self,
        storage: ConcurrencyLeaseStorage,
        sample_resource_ids: list[UUID],
        sample_metadata_with_holder: ConcurrencyLimitLeaseMetadata,
    ):
        ttl = timedelta(minutes=5)
        created_lease = await storage.create_lease(
            sample_resource_ids, ttl, sample_metadata_with_holder
        )

        read_lease = await storage.read_lease(created_lease.id)

        assert read_lease is not None
        assert read_lease.resource_ids == sample_resource_ids
        assert read_lease.metadata.slots == 3
        assert read_lease.metadata.holder.model_dump() == {
            "type": "flow_run",
            "id": read_lease.metadata.holder.id,
        }

    async def test_read_lease_non_existing(self, storage: ConcurrencyLeaseStorage):
        non_existing_id = uuid4()
        lease = await storage.read_lease(non_existing_id)
        assert lease is None

    async def test_renew_lease(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        lease_id = list(storage.leases.keys())[0]
        original_expiration = storage.expirations[lease_id]

        new_ttl = timedelta(minutes=10)
        await storage.renew_lease(lease_id, new_ttl)

        new_expiration = storage.expirations[lease_id]
        assert new_expiration > original_expiration

    async def test_revoke_lease(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        lease_id = list(storage.leases.keys())[0]
        assert lease_id in storage.leases
        assert lease_id in storage.expirations

        await storage.revoke_lease(lease_id)

        assert lease_id not in storage.leases
        assert lease_id not in storage.expirations

    async def test_revoke_lease_non_existing(self, storage: ConcurrencyLeaseStorage):
        non_existing_id = uuid4()
        # should not raise an exception
        await storage.revoke_lease(non_existing_id)

    async def test_read_expired_lease_ids_no_expired(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        expired_ids = await storage.read_expired_lease_ids()
        assert expired_ids == []

    async def test_read_expired_lease_ids_with_expired(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        expired_ttl = timedelta(seconds=-1)
        await storage.create_lease(sample_resource_ids, expired_ttl)

        expired_ids = await storage.read_expired_lease_ids()
        assert len(expired_ids) == 1
        assert expired_ids[0] in storage.leases

    async def test_read_expired_lease_ids_with_limit(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        expired_ttl = timedelta(seconds=-1)
        await storage.create_lease(sample_resource_ids, expired_ttl)
        await storage.create_lease(sample_resource_ids, expired_ttl)
        await storage.create_lease(sample_resource_ids, expired_ttl)

        expired_ids = await storage.read_expired_lease_ids(limit=2)
        assert len(expired_ids) == 2

    async def test_read_expired_lease_ids_mixed_expiration(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        expired_ttl = timedelta(seconds=-1)
        valid_ttl = timedelta(minutes=5)

        await storage.create_lease(sample_resource_ids, expired_ttl)
        await storage.create_lease(sample_resource_ids, valid_ttl)
        await storage.create_lease(sample_resource_ids, expired_ttl)

        expired_ids = await storage.read_expired_lease_ids()
        assert len(expired_ids) == 2

    async def test_list_holders_for_limit_returns_holders(
        self, storage: ConcurrencyLeaseStorage
    ):
        rid1, rid2 = uuid4(), uuid4()
        ttl = timedelta(minutes=5)
        holder = {"type": "flow_run", "id": str(uuid4())}
        meta = ConcurrencyLimitLeaseMetadata(slots=1, holder=holder)

        await storage.create_lease([rid1, rid2], ttl, meta)

        holders1 = await storage.list_holders_for_limit(rid1)
        holders2 = await storage.list_holders_for_limit(rid2)
        assert {"holder": holder, "slots": 1} in holders1
        assert {"holder": holder, "slots": 1} in holders2

    async def test_list_holders_for_limit_excludes_expired_and_no_holder(
        self, storage: ConcurrencyLeaseStorage
    ):
        rid = uuid4()
        # Expired lease with holder
        await storage.create_lease(
            [rid],
            timedelta(seconds=-1),
            ConcurrencyLimitLeaseMetadata(
                slots=1, holder={"type": "flow_run", "id": str(uuid4())}
            ),
        )
        # Valid lease without holder
        await storage.create_lease(
            [rid], timedelta(minutes=1), ConcurrencyLimitLeaseMetadata(slots=1)
        )
        holders = await storage.list_holders_for_limit(rid)
        assert holders == []
