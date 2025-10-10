import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from prefect.server.concurrency.lease_storage import ConcurrencyLimitLeaseMetadata
from prefect.server.concurrency.lease_storage.filesystem import (
    ConcurrencyLeaseStorage,
)
from prefect.types._concurrency import ConcurrencyLeaseHolder


class TestFilesystemConcurrencyLeaseStorage:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def storage(self, temp_dir: Path) -> ConcurrencyLeaseStorage:
        return ConcurrencyLeaseStorage(storage_path=temp_dir)

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
            holder=ConcurrencyLeaseHolder(type="task_run", id=uuid4()),
        )

    async def test_create_lease_without_metadata(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        lease = await storage.create_lease(sample_resource_ids, ttl)

        assert lease.resource_ids == sample_resource_ids
        assert lease.metadata is None

        # Verify lease file was created (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 1

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

        # Verify lease file was created with correct data (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 1

        with open(lease_files[0], "r") as f:
            data = json.load(f)

        assert data["metadata"]["slots"] == 5
        assert len(data["resource_ids"]) == 2

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
        assert lease.metadata is not None
        assert lease.metadata == sample_metadata_with_holder
        assert lease.metadata.holder is not None
        assert lease.metadata.holder.model_dump() == {
            "type": "task_run",
            "id": lease.metadata.holder.id,
        }

        # Verify lease file was created with correct data
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 1

        with open(lease_files[0], "r") as f:
            data = json.load(f)

        assert data["metadata"]["slots"] == 3
        assert data["metadata"]["holder"] == {
            "type": "task_run",
            "id": str(lease.metadata.holder.id),
        }

    async def test_read_lease_existing(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        # Get the lease ID from the file (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        lease_id = UUID(lease_files[0].stem)

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
        assert read_lease.metadata is not None
        assert read_lease.metadata.slots == 3
        assert read_lease.metadata.holder is not None
        assert read_lease.metadata.holder.model_dump() == {
            "type": "task_run",
            "id": read_lease.metadata.holder.id,
        }

    async def test_read_lease_non_existing(self, storage: ConcurrencyLeaseStorage):
        non_existing_id = uuid4()
        lease = await storage.read_lease(non_existing_id)
        assert lease is None

    async def test_read_lease_expired(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        # Create an expired lease
        expired_ttl = timedelta(seconds=-1)
        await storage.create_lease(sample_resource_ids, expired_ttl)

        # Get the lease ID from the file (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        lease_id = UUID(lease_files[0].stem)

        # Reading should return return the lease
        read_lease = await storage.read_lease(lease_id)
        assert read_lease is not None
        assert read_lease.expiration < datetime.now(timezone.utc)

    async def test_read_lease_corrupted_file(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        # Create a valid lease first
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        # Get the lease ID and corrupt the file (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        lease_id = UUID(lease_files[0].stem)

        with open(lease_files[0], "w") as f:
            f.write("invalid json content")

        # Reading should return None and clean up the corrupted file
        read_lease = await storage.read_lease(lease_id)
        assert read_lease is None

        # File should be cleaned up (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 0

    async def test_renew_lease(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        # Get the lease ID and original expiration (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        lease_id = UUID(lease_files[0].stem)

        with open(lease_files[0], "r") as f:
            original_data = json.load(f)
        original_expiration = datetime.fromisoformat(original_data["expiration"])

        # Renew the lease
        new_ttl = timedelta(minutes=10)
        await storage.renew_lease(lease_id, new_ttl)

        # Check that expiration was updated
        with open(lease_files[0], "r") as f:
            updated_data = json.load(f)
        new_expiration = datetime.fromisoformat(updated_data["expiration"])

        assert new_expiration > original_expiration

    async def test_renew_lease_non_existing(self, storage: ConcurrencyLeaseStorage):
        non_existing_id = uuid4()
        # Should not raise an exception
        await storage.renew_lease(non_existing_id, timedelta(minutes=5))

    async def test_renew_lease_corrupted_file(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        # Create a valid lease first
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        # Get the lease ID and corrupt the file (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        lease_id = UUID(lease_files[0].stem)

        with open(lease_files[0], "w") as f:
            f.write("invalid json content")

        # Renewing should clean up the corrupted file
        await storage.renew_lease(lease_id, timedelta(minutes=10))

        # File should be cleaned up (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 0

    async def test_revoke_lease(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        # Verify file exists (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 1
        lease_id = UUID(lease_files[0].stem)

        # Release the lease
        await storage.revoke_lease(lease_id)

        # File should be deleted (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 0

    async def test_revoke_lease_non_existing(self, storage: ConcurrencyLeaseStorage):
        non_existing_id = uuid4()
        # Should not raise an exception
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

        # Verify the lease ID is correct
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 1
        expected_lease_id = UUID(lease_files[0].stem)
        assert expired_ids[0] == expected_lease_id

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

    async def test_read_expired_lease_ids_corrupted_files(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        # Create a valid lease and a corrupted file
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)

        # Create a corrupted file
        corrupted_file = storage.storage_path / f"{uuid4()}.json"
        with open(corrupted_file, "w") as f:
            f.write("invalid json content")

        # Should return no expired leases (corrupted files are ignored)
        expired_ids = await storage.read_expired_lease_ids()
        assert expired_ids == []

        # Corrupted file still exists (only cleaned up when accessed)
        assert corrupted_file.exists()

    async def test_storage_path_creation(self, temp_dir: Path):
        # Test that storage path is created only when needed
        storage_path = temp_dir / "nested" / "path"
        assert not storage_path.exists()

        # Creating the storage instance should not create the directory
        storage = ConcurrencyLeaseStorage(storage_path=storage_path)
        assert not storage_path.exists()

        # Creating a lease should create the directory
        sample_resource_ids = [uuid4(), uuid4()]
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)
        assert storage_path.exists()
        assert storage_path.is_dir()

    async def test_multiple_leases_persistence(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        # Create multiple leases
        ttl = timedelta(minutes=5)
        await storage.create_lease(sample_resource_ids, ttl)
        await storage.create_lease(sample_resource_ids, ttl)
        await storage.create_lease(sample_resource_ids, ttl)

        # Verify all files exist (excluding expiration index)
        lease_files = [
            f
            for f in storage.storage_path.glob("*.json")
            if f.name != "expirations.json"
        ]
        assert len(lease_files) == 3

        # Verify we can read all leases
        lease_ids = [UUID(f.stem) for f in lease_files]
        for lease_id in lease_ids:
            read_lease = await storage.read_lease(lease_id)
            assert read_lease is not None
            assert read_lease.resource_ids == sample_resource_ids

    async def test_list_holders_for_limit_empty(self, storage: ConcurrencyLeaseStorage):
        limit_id = uuid4()
        holders = await storage.list_holders_for_limit(limit_id)
        assert holders == []

    async def test_list_holders_for_limit_no_holders(
        self, storage: ConcurrencyLeaseStorage, sample_resource_ids: list[UUID]
    ):
        # Create a lease without a holder
        ttl = timedelta(minutes=5)
        metadata = ConcurrencyLimitLeaseMetadata(slots=2)
        await storage.create_lease(sample_resource_ids, ttl, metadata)

        holders = await storage.list_holders_for_limit(sample_resource_ids[0])
        assert holders == []

    async def test_list_holders_for_limit_with_holders(
        self, storage: ConcurrencyLeaseStorage
    ):
        limit_id = uuid4()

        # Create leases with different holders
        holder1 = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        holder2 = ConcurrencyLeaseHolder(type="flow_run", id=uuid4())

        metadata1 = ConcurrencyLimitLeaseMetadata(slots=2, holder=holder1)
        metadata2 = ConcurrencyLimitLeaseMetadata(slots=1, holder=holder2)

        ttl = timedelta(minutes=5)
        await storage.create_lease([limit_id], ttl, metadata1)
        await storage.create_lease([limit_id], ttl, metadata2)

        # Create a lease for a different limit to ensure it's not included
        other_limit_id = uuid4()
        metadata3 = ConcurrencyLimitLeaseMetadata(
            slots=1, holder=ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        )
        await storage.create_lease([other_limit_id], ttl, metadata3)

        holders_with_leases = await storage.list_holders_for_limit(limit_id)
        assert len(holders_with_leases) == 2
        holders = [holder for _, holder in holders_with_leases]

        assert holder1 in holders
        assert holder2 in holders

    async def test_list_holders_for_limit_expired_leases(
        self, storage: ConcurrencyLeaseStorage
    ):
        limit_id = uuid4()

        # Create an expired lease with a holder
        expired_ttl = timedelta(seconds=-1)
        holder = ConcurrencyLeaseHolder(type="task_run", id=uuid4())
        metadata = ConcurrencyLimitLeaseMetadata(slots=1, holder=holder)
        await storage.create_lease([limit_id], expired_ttl, metadata)

        # Create an active lease with a holder
        active_ttl = timedelta(minutes=5)
        active_holder = ConcurrencyLeaseHolder(type="flow_run", id=uuid4())
        active_metadata = ConcurrencyLimitLeaseMetadata(slots=1, holder=active_holder)
        active_lease = await storage.create_lease(
            [limit_id], active_ttl, active_metadata
        )

        holders = await storage.list_holders_for_limit(limit_id)
        assert len(holders) == 1
        lease_id, holder = holders[0]
        assert lease_id == active_lease.id
        assert holder == active_holder

    async def test_read_active_lease_ids_with_pagination(
        self, storage: ConcurrencyLeaseStorage
    ):
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

    async def test_read_active_lease_ids_default_pagination(
        self, storage: ConcurrencyLeaseStorage
    ):
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
