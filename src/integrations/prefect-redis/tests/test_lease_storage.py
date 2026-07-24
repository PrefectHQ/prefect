import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from prefect_redis.lease_storage import ConcurrencyLeaseStorage
from redis.asyncio import Redis, RedisCluster
from redis.cluster import key_slot

from prefect.server.concurrency.lease_storage import ConcurrencyLimitLeaseMetadata
from prefect.server.utilities.leasing import ResourceLease
from prefect.types._concurrency import ConcurrencyLeaseHolder


class TestConcurrencyLeaseStorage:
    """Test suite for Redis-based ConcurrencyLeaseStorage implementation."""

    @pytest.fixture
    async def storage(self, redis: Redis) -> ConcurrencyLeaseStorage:
        """Create a ConcurrencyLeaseStorage instance with the test Redis client."""
        return ConcurrencyLeaseStorage(redis_client=redis)

    def test_keys_share_cluster_hash_slot(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "PREFECT_REDIS_MESSAGING_URL",
            "redis+cluster://redis.example.com:6379",
        )
        monkeypatch.setattr(
            "prefect_redis.lease_storage.get_async_redis_client", lambda: None
        )
        storage = ConcurrencyLeaseStorage()
        lease_id = uuid4()
        limit_id = uuid4()
        keys = [
            storage._lease_key(lease_id),
            storage.expirations_key,
            storage._expiration_key(lease_id),
            storage._limit_holders_key(limit_id),
        ]

        assert keys == [
            f"{{prefect:concurrency}}:lease:{lease_id}",
            "{prefect:concurrency}:expirations",
            f"{{prefect:concurrency}}:expiration:{lease_id}",
            f"{{prefect:concurrency}}:limit:{limit_id}:holders",
        ]
        assert len({key_slot(key.encode()) for key in keys}) == 1

    def test_keys_preserve_standalone_names(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("PREFECT_REDIS_MESSAGING_URL", raising=False)
        monkeypatch.setattr(
            "prefect_redis.lease_storage.get_async_redis_client", lambda: None
        )
        storage = ConcurrencyLeaseStorage()
        lease_id = uuid4()
        limit_id = uuid4()

        assert storage._lease_key(lease_id) == f"prefect:concurrency:lease:{lease_id}"
        assert storage.expirations_key == "prefect:concurrency:expirations"
        assert storage._expiration_key(lease_id) == (
            f"prefect:concurrency:expiration:{lease_id}"
        )
        assert storage._limit_holders_key(limit_id) == (
            f"prefect:concurrency:limit:{limit_id}:holders"
        )

    @pytest.mark.skipif(
        not os.environ.get("PREFECT_REDIS_CLUSTER_TEST_URL"),
        reason="requires PREFECT_REDIS_CLUSTER_TEST_URL",
    )
    async def test_runs_against_real_redis_cluster(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        cluster_url = os.environ["PREFECT_REDIS_CLUSTER_TEST_URL"]
        client_url = cluster_url.replace("redis+cluster://", "redis://", 1).replace(
            "rediss+cluster://", "rediss://", 1
        )
        settings_url = cluster_url
        if settings_url.startswith("redis://"):
            settings_url = settings_url.replace("redis://", "redis+cluster://", 1)
        elif settings_url.startswith("rediss://"):
            settings_url = settings_url.replace("rediss://", "rediss+cluster://", 1)

        redis_client = RedisCluster.from_url(client_url, decode_responses=True)
        await redis_client.flushall()
        try:
            monkeypatch.setenv("PREFECT_REDIS_MESSAGING_URL", settings_url)
            storage = ConcurrencyLeaseStorage(redis_client=redis_client)
            resource_ids = [uuid4(), uuid4()]
            holder_id = uuid4()
            metadata = ConcurrencyLimitLeaseMetadata(slots=2)
            setattr(
                metadata,
                "holder",
                {"type": "task_run", "id": str(holder_id)},
            )

            lease = await storage.create_lease(
                resource_ids, timedelta(minutes=5), metadata
            )

            read_lease = await storage.read_lease(lease.id)
            assert read_lease is not None
            assert read_lease.resource_ids == resource_ids
            assert lease.id in await storage.read_active_lease_ids()
            for resource_id in resource_ids:
                assert await storage.list_holders_for_limit(resource_id) == [
                    (
                        lease.id,
                        ConcurrencyLeaseHolder(type="task_run", id=holder_id),
                    )
                ]

            assert await storage.renew_lease(lease.id, timedelta(minutes=10))
            renewed_lease = await storage.read_lease(lease.id)
            assert renewed_lease is not None
            assert renewed_lease.expiration > lease.expiration

            await storage.revoke_lease(lease.id)
            assert await storage.read_lease(lease.id) is None
            for resource_id in resource_ids:
                assert await storage.list_holders_for_limit(resource_id) == []

            expired_lease = await storage.create_lease([uuid4()], timedelta(seconds=-1))
            assert expired_lease.id in await storage.read_expired_lease_ids()
            await storage.revoke_lease(expired_lease.id)
        finally:
            await redis_client.flushall()
            await redis_client.aclose()

    async def test_create_lease(self, storage: ConcurrencyLeaseStorage):
        """Test creating a new lease."""
        resource_ids = [uuid4(), uuid4()]
        ttl = timedelta(seconds=300)
        metadata = ConcurrencyLimitLeaseMetadata(slots=5)

        lease = await storage.create_lease(resource_ids, ttl, metadata)

        assert isinstance(lease, ResourceLease)
        assert lease.resource_ids == resource_ids
        assert lease.metadata == metadata
        assert lease.expiration > datetime.now(timezone.utc)
        assert isinstance(lease.id, UUID)

    async def test_create_lease_without_metadata(
        self, storage: ConcurrencyLeaseStorage
    ):
        """Test creating a lease without metadata."""
        resource_ids = [uuid4()]
        ttl = timedelta(seconds=300)

        lease = await storage.create_lease(resource_ids, ttl)

        assert lease.resource_ids == resource_ids
        assert lease.metadata is None

    async def test_read_lease(self, storage: ConcurrencyLeaseStorage):
        """Test reading an existing lease."""
        resource_ids = [uuid4()]
        ttl = timedelta(seconds=300)
        metadata = ConcurrencyLimitLeaseMetadata(slots=3)

        # Create a lease first
        created_lease = await storage.create_lease(resource_ids, ttl, metadata)

        # Read it back
        read_lease = await storage.read_lease(created_lease.id)

        assert read_lease is not None
        assert read_lease.id == created_lease.id
        assert read_lease.resource_ids == resource_ids
        assert read_lease.metadata is not None
        assert read_lease.metadata.slots == metadata.slots
        assert read_lease.expiration == created_lease.expiration

    async def test_read_nonexistent_lease(self, storage: ConcurrencyLeaseStorage):
        """Test reading a lease that doesn't exist."""
        nonexistent_id = uuid4()
        lease = await storage.read_lease(nonexistent_id)
        assert lease is None

    async def test_renew_lease(self, storage: ConcurrencyLeaseStorage):
        """Test renewing an existing lease."""
        resource_ids = [uuid4()]
        initial_ttl = timedelta(seconds=300)
        metadata = ConcurrencyLimitLeaseMetadata(slots=2)

        # Create a lease
        lease = await storage.create_lease(resource_ids, initial_ttl, metadata)
        original_expiration = lease.expiration

        # Wait a small amount to ensure time difference
        await asyncio.sleep(0.1)

        # Renew the lease
        new_ttl = timedelta(seconds=600)
        await storage.renew_lease(lease.id, new_ttl)

        # Read the renewed lease
        renewed_lease = await storage.read_lease(lease.id)
        assert renewed_lease is not None
        assert renewed_lease.expiration > original_expiration

    async def test_renew_nonexistent_lease(self, storage: ConcurrencyLeaseStorage):
        """Test renewing a lease that doesn't exist (should not raise error)."""
        nonexistent_id = uuid4()
        ttl = timedelta(seconds=300)

        # Should not raise an error
        await storage.renew_lease(nonexistent_id, ttl)

    async def test_revoke_lease(self, storage: ConcurrencyLeaseStorage):
        """Test revoking an existing lease."""
        resource_ids = [uuid4()]
        ttl = timedelta(seconds=300)

        # Create a lease
        lease = await storage.create_lease(resource_ids, ttl)

        # Verify it exists
        assert await storage.read_lease(lease.id) is not None

        # Revoke it
        await storage.revoke_lease(lease.id)

        # Verify it's gone
        assert await storage.read_lease(lease.id) is None

    async def test_revoke_nonexistent_lease(self, storage: ConcurrencyLeaseStorage):
        """Test revoking a lease that doesn't exist (should not raise error)."""
        nonexistent_id = uuid4()

        # Should not raise an error
        await storage.revoke_lease(nonexistent_id)

    async def test_read_active_lease_ids(self, storage: ConcurrencyLeaseStorage):
        """Test reading active lease IDs."""
        resource_ids = [uuid4()]

        # Create an active lease (expires in future)
        active_ttl = timedelta(seconds=300)
        active_lease = await storage.create_lease(resource_ids, active_ttl)

        # Create an expired lease (expires in past)
        expired_ttl = timedelta(seconds=-300)  # Negative TTL for expired lease
        expired_lease = await storage.create_lease(resource_ids, expired_ttl)

        # Read active lease IDs
        active_ids = await storage.read_active_lease_ids()

        assert active_lease.id in active_ids
        assert expired_lease.id not in active_ids

    async def test_read_expired_lease_ids(self, storage: ConcurrencyLeaseStorage):
        """Test reading expired lease IDs."""
        resource_ids = [uuid4()]

        # Create an active lease (expires in future)
        active_ttl = timedelta(seconds=300)
        active_lease = await storage.create_lease(resource_ids, active_ttl)

        # Create an expired lease (expires in past)
        expired_ttl = timedelta(seconds=-300)  # Negative TTL for expired lease
        expired_lease = await storage.create_lease(resource_ids, expired_ttl)

        # Read expired lease IDs
        expired_ids = await storage.read_expired_lease_ids()

        assert expired_lease.id in expired_ids
        assert active_lease.id not in expired_ids

    async def test_read_active_lease_ids_with_limit(
        self, storage: ConcurrencyLeaseStorage
    ):
        """Test reading active lease IDs with a limit."""
        resource_ids = [uuid4()]
        ttl = timedelta(seconds=300)

        # Create multiple active leases
        leases: list[ResourceLease[ConcurrencyLimitLeaseMetadata]] = []
        for _ in range(5):
            lease = await storage.create_lease(resource_ids, ttl)
            leases.append(lease)

        # Read with limit
        active_ids = await storage.read_active_lease_ids(limit=3)

        assert len(active_ids) == 3
        # All returned IDs should be from our created leases
        assert all(
            lease_id in [lease.id for lease in leases] for lease_id in active_ids
        )

    async def test_read_expired_lease_ids_with_limit(
        self, storage: ConcurrencyLeaseStorage
    ):
        """Test reading expired lease IDs with a limit."""
        resource_ids = [uuid4()]
        expired_ttl = timedelta(seconds=-300)

        # Create multiple expired leases
        leases: list[ResourceLease[ConcurrencyLimitLeaseMetadata]] = []
        for _ in range(5):
            lease = await storage.create_lease(resource_ids, expired_ttl)
            leases.append(lease)

        # Read with limit
        expired_ids = await storage.read_expired_lease_ids(limit=3)

        assert len(expired_ids) == 3
        # All returned IDs should be from our created leases
        assert all(
            lease_id in [lease.id for lease in leases] for lease_id in expired_ids
        )

    async def test_lease_serialization_deserialization(
        self, storage: ConcurrencyLeaseStorage
    ):
        """Test that lease serialization and deserialization work correctly."""
        resource_ids = [uuid4(), uuid4()]
        ttl = timedelta(seconds=300)
        metadata = ConcurrencyLimitLeaseMetadata(slots=10)

        # Create lease
        original_lease = await storage.create_lease(resource_ids, ttl, metadata)

        # Read it back
        deserialized_lease = await storage.read_lease(original_lease.id)

        assert deserialized_lease is not None
        assert deserialized_lease.id == original_lease.id
        assert deserialized_lease.resource_ids == original_lease.resource_ids
        assert deserialized_lease.expiration == original_lease.expiration
        assert deserialized_lease.created_at == original_lease.created_at
        assert deserialized_lease.metadata is not None
        assert deserialized_lease.metadata.slots == original_lease.metadata.slots

    async def test_concurrent_operations(self, storage: ConcurrencyLeaseStorage):
        """Test concurrent lease operations."""
        resource_ids = [uuid4()]
        ttl = timedelta(seconds=300)

        # Create multiple leases concurrently
        tasks = [
            storage.create_lease(
                resource_ids, ttl, ConcurrencyLimitLeaseMetadata(slots=i)
            )
            for i in range(10)
        ]
        leases = await asyncio.gather(*tasks)

        # Verify all leases were created successfully
        assert len(leases) == 10
        assert len(set(lease.id for lease in leases)) == 10  # All unique IDs

        # Read all leases back concurrently
        read_tasks = [storage.read_lease(lease.id) for lease in leases]
        read_leases = await asyncio.gather(*read_tasks)

        # Verify all reads succeeded
        assert all(read_lease is not None for read_lease in read_leases)
        assert len(read_leases) == 10

    async def test_redis_key_management(
        self, storage: ConcurrencyLeaseStorage, redis: Redis
    ):
        """Test that Redis keys are managed correctly."""
        resource_ids = [uuid4()]
        ttl = timedelta(seconds=300)

        # Create a lease
        lease = await storage.create_lease(resource_ids, ttl)

        # Verify keys exist in Redis
        lease_key = storage._lease_key(lease.id)
        assert await redis.exists(lease_key) == 1
        assert (
            await redis.zrank("prefect:concurrency:expirations", str(lease.id))
            is not None
        )

        # Revoke the lease
        await storage.revoke_lease(lease.id)

        # Verify keys are removed
        assert await redis.exists(lease_key) == 0
        assert (
            await redis.zrank("prefect:concurrency:expirations", str(lease.id)) is None
        )

    async def test_storage_isolation(self, redis: Redis):
        """Test that different storage instances are properly isolated."""
        storage1 = ConcurrencyLeaseStorage(redis_client=redis)
        storage2 = ConcurrencyLeaseStorage(redis_client=redis)

        resource_ids = [uuid4()]
        ttl = timedelta(seconds=300)

        # Create lease with first storage
        lease = await storage1.create_lease(resource_ids, ttl)

        # Read with second storage (should work since they share Redis)
        read_lease = await storage2.read_lease(lease.id)
        assert read_lease is not None
        assert read_lease.id == lease.id

    async def test_holder_round_trip(self, storage: ConcurrencyLeaseStorage):
        """Holder data is preserved through serialize/deserialize."""
        resource_ids = [uuid4()]
        ttl = timedelta(seconds=60)
        holder = {"type": "task_run", "id": str(uuid4())}

        metadata = ConcurrencyLimitLeaseMetadata(slots=2)
        # Support both models that define 'holder' and legacy ones
        setattr(metadata, "holder", holder)

        lease = await storage.create_lease(resource_ids, ttl, metadata)
        read_back = await storage.read_lease(lease.id)

        assert read_back is not None
        assert getattr(read_back.metadata, "holder", None) == holder

    async def test_holder_indexes_and_lookup(self, storage: ConcurrencyLeaseStorage):
        rid = uuid4()
        ttl = timedelta(seconds=120)
        holder_id = uuid4()
        holder = {"type": "task_run", "id": str(holder_id)}
        meta = ConcurrencyLimitLeaseMetadata(slots=1)
        setattr(meta, "holder", holder)

        lease = await storage.create_lease([rid], ttl, meta)

        holders = await storage.list_holders_for_limit(rid)
        assert len(holders) == 1
        lease_id, holder = holders[0]
        assert holder.type == "task_run"
        assert holder.id == holder_id
        assert lease_id == lease.id

        await storage.revoke_lease(lease.id)

        holders_after = await storage.list_holders_for_limit(rid)
        assert len(holders_after) == 0
        # Reverse lookup removed; ensure holder entry is gone via list

    async def test_create_without_holder_does_not_index(
        self, storage: ConcurrencyLeaseStorage
    ):
        rid = uuid4()
        ttl = timedelta(seconds=60)
        # No holder
        lease = await storage.create_lease([rid], ttl)
        assert lease is not None

        holders = await storage.list_holders_for_limit(rid)
        assert holders == []
        # Reverse lookup removed; nothing to check here beyond empty list

    async def test_multiple_resource_ids_index_all_and_cleanup(
        self, storage: ConcurrencyLeaseStorage
    ):
        rid1, rid2 = uuid4(), uuid4()
        ttl = timedelta(seconds=60)
        holder_id = uuid4()
        holder = {"type": "task_run", "id": str(holder_id)}
        meta = ConcurrencyLimitLeaseMetadata(slots=1)
        setattr(meta, "holder", holder)

        lease = await storage.create_lease([rid1, rid2], ttl, meta)

        holders_rid1 = await storage.list_holders_for_limit(rid1)
        assert len(holders_rid1) == 1
        lease_id, holder = holders_rid1[0]
        assert holder.type == "task_run"
        assert holder.id == holder_id
        assert lease_id == lease.id

        holders_rid2 = await storage.list_holders_for_limit(rid2)
        assert len(holders_rid2) == 1
        lease_id, holder = holders_rid2[0]
        assert holder.type == "task_run"
        assert holder.id == holder_id
        assert lease_id == lease.id

        await storage.revoke_lease(lease.id)

        holders_rid1_after = await storage.list_holders_for_limit(rid1)
        assert len(holders_rid1_after) == 0

        holders_rid2_after = await storage.list_holders_for_limit(rid2)
        assert len(holders_rid2_after) == 0

    async def test_list_holders_for_limit_returns_typed_holders(
        self, storage: ConcurrencyLeaseStorage
    ):
        """Test that list_holders_for_limit returns properly typed ConcurrencyLeaseHolder objects."""
        limit_id = uuid4()
        ttl = timedelta(seconds=60)

        # Create multiple leases with different holders
        holder1_id = uuid4()
        holder2_id = uuid4()
        holder1_data = {"type": "task_run", "id": str(holder1_id)}
        holder2_data = {"type": "flow_run", "id": str(holder2_id)}

        meta1 = ConcurrencyLimitLeaseMetadata(slots=2)
        setattr(meta1, "holder", holder1_data)

        meta2 = ConcurrencyLimitLeaseMetadata(slots=1)
        setattr(meta2, "holder", holder2_data)

        # Create leases
        lease1 = await storage.create_lease([limit_id], ttl, meta1)
        lease2 = await storage.create_lease([limit_id], ttl, meta2)

        # Get holders - should return ConcurrencyLeaseHolder objects
        holders = await storage.list_holders_for_limit(limit_id)

        assert len(holders) == 2

        # Check that they are ConcurrencyLeaseHolder instances
        for _, holder in holders:
            assert isinstance(holder, ConcurrencyLeaseHolder)

        # Check that the data matches (IDs are UUIDs in the returned objects)
        holder_types = {holder.type for _, holder in holders}
        holder_ids = {holder.id for _, holder in holders}
        assert "task_run" in holder_types
        assert "flow_run" in holder_types
        assert holder1_id in holder_ids
        assert holder2_id in holder_ids

        # Clean up
        await storage.revoke_lease(lease1.id)
        await storage.revoke_lease(lease2.id)

    async def test_list_holders_for_limit_empty_when_no_holders(
        self, storage: ConcurrencyLeaseStorage
    ):
        """Test that list_holders_for_limit returns empty list when no holders exist."""
        limit_id = uuid4()
        holders = await storage.list_holders_for_limit(limit_id)
        assert holders == []
        assert isinstance(holders, list)

    async def test_read_active_lease_ids_with_pagination(
        self, storage: ConcurrencyLeaseStorage
    ):
        """Test pagination of active lease IDs."""
        # Create 10 active leases
        active_ttl = timedelta(minutes=5)
        lease_ids: list[UUID] = []
        for _ in range(10):
            lease = await storage.create_lease([uuid4()], active_ttl)
            lease_ids.append(lease.id)

        # Test getting first page
        first_page = await storage.read_active_lease_ids(limit=3, offset=0)
        assert len(first_page) == 3
        assert all(lid in lease_ids for lid in first_page)

        # Test getting second page
        second_page = await storage.read_active_lease_ids(limit=3, offset=3)
        assert len(second_page) == 3
        assert all(lid in lease_ids for lid in second_page)

        # Ensure no overlap between pages
        assert set(first_page).isdisjoint(set(second_page))

        # Test getting third page
        third_page = await storage.read_active_lease_ids(limit=3, offset=6)
        assert len(third_page) == 3
        assert all(lid in lease_ids for lid in third_page)

        # Test getting partial last page
        fourth_page = await storage.read_active_lease_ids(limit=3, offset=9)
        assert len(fourth_page) == 1
        assert all(lid in lease_ids for lid in fourth_page)

        # Test offset beyond available items
        empty_page = await storage.read_active_lease_ids(limit=3, offset=100)
        assert empty_page == []

        # Clean up
        for lease_id in lease_ids:
            await storage.revoke_lease(lease_id)

    async def test_read_active_lease_ids_default_pagination(
        self, storage: ConcurrencyLeaseStorage
    ):
        """Test default pagination behavior."""
        # Create 150 active leases (more than default limit)
        active_ttl = timedelta(minutes=5)
        lease_ids: list[UUID] = []
        for _ in range(150):
            lease = await storage.create_lease([uuid4()], active_ttl)
            lease_ids.append(lease.id)

        # Test default limit of 100
        default_page = await storage.read_active_lease_ids()
        assert len(default_page) == 100
        assert all(lid in lease_ids for lid in default_page)

        # Test with offset
        offset_page = await storage.read_active_lease_ids(offset=100)
        assert len(offset_page) == 50  # remaining leases
        assert all(lid in lease_ids for lid in offset_page)

        # Ensure no overlap with first page
        assert set(default_page).isdisjoint(set(offset_page))

        # Clean up
        for lease_id in lease_ids:
            await storage.revoke_lease(lease_id)
