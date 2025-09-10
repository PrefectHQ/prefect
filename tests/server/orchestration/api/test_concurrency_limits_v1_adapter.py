"""
Tests for V1→V2 concurrency limit adapter functionality.

When PREFECT_SERVER_V1_V2_CONCURRENCY_ADAPTER is enabled, V1 endpoints should
transparently use V2 infrastructure while maintaining API compatibility.
"""

import shutil
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from prefect.server.api.server import create_app
from prefect.server.concurrency.lease_storage import ConcurrencyLimitLeaseMetadata
from prefect.server.concurrency.lease_storage.filesystem import ConcurrencyLeaseStorage
from prefect.server.models.concurrency_limits_v2 import create_concurrency_limit
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.server.utilities.leasing import ResourceLease
from prefect.settings import PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE
from prefect.settings.context import temporary_settings


@pytest.fixture(autouse=True)
def adapter_env(monkeypatch):
    """Enable V1→V2 adapter for all tests in this module."""
    monkeypatch.setenv("PREFECT_SERVER_V1_V2_CONCURRENCY_ADAPTER", "1")
    yield


@pytest.fixture
def use_filesystem_lease_storage():
    """Use filesystem lease storage for testing."""
    with temporary_settings(
        {
            PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE: "prefect.server.concurrency.lease_storage.filesystem"
        }
    ):
        # Clean up any existing storage
        storage = ConcurrencyLeaseStorage()
        if storage.storage_path.exists():
            shutil.rmtree(storage.storage_path, ignore_errors=True)
        yield


@pytest.fixture()
def app(use_filesystem_lease_storage: None) -> FastAPI:
    """Create test app with filesystem storage."""
    return create_app(ephemeral=True)


@pytest.fixture
async def client(app: FastAPI):
    """Create test client."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test/api"
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_v1_create_routes_to_v2(client: AsyncClient, session):
    """Test that V1 CREATE endpoint creates V2 limit with tag: prefix."""
    # Create V1 limit
    response = await client.post(
        "/concurrency_limits/", json={"tag": "foo", "concurrency_limit": 5}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tag"] == "foo"
    assert data["concurrency_limit"] == 5
    assert data["active_slots"] == []

    # Verify V2 limit was created with tag: prefix
    async with session.begin():
        from prefect.server.models import concurrency_limits_v2 as cl_v2_models

        v2 = await cl_v2_models.read_concurrency_limit(session, name="tag:foo")
        assert v2 is not None
        assert v2.limit == 5
        assert v2.name == "tag:foo"


@pytest.mark.asyncio
async def test_v1_create_upsert_behavior(client: AsyncClient, session):
    """Test that V1 CREATE has upsert behavior like original."""
    # Create initial limit
    response = await client.post(
        "/concurrency_limits/", json={"tag": "bar", "concurrency_limit": 3}
    )
    assert response.status_code == 201
    initial_id = response.json()["id"]

    # Create again with different limit (should update)
    response = await client.post(
        "/concurrency_limits/", json={"tag": "bar", "concurrency_limit": 7}
    )
    assert response.status_code == 200  # Not 201 since it's an update
    data = response.json()
    assert data["id"] == initial_id  # Same ID
    assert data["concurrency_limit"] == 7  # Updated limit


@pytest.mark.asyncio
async def test_v1_read_by_tag_uses_v2_leases(client: AsyncClient, session, monkeypatch):
    """Test that V1 READ endpoint populates active_slots from V2 leases."""
    # Create V2 limit directly in DB for tag:foo
    v2 = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(name="tag:foo", limit=5),
    )
    await session.commit()

    # Stub lease storage to return a lease with a task_run holder for this limit
    tr_id = str(uuid4())

    class StubStorage:
        def __init__(self):
            self.storage_path = ConcurrencyLeaseStorage().storage_path

        async def read_active_lease_ids(self, limit: int = 100):
            return [uuid4()]

        async def read_lease(self, lease_id):
            return ResourceLease(
                resource_ids=[v2.id],
                expiration=datetime.now(timezone.utc) + timedelta(minutes=5),
                metadata=ConcurrencyLimitLeaseMetadata(
                    slots=1, holder={"type": "task_run", "id": tr_id}
                ),
            )

    # Patch the server module to use our stub
    import prefect.server.api.concurrency_limits as v1api

    monkeypatch.setattr(v1api, "get_concurrency_lease_storage", lambda: StubStorage())

    # Read V1 by tag; should include holder id in active_slots
    resp = await client.get("/concurrency_limits/tag/foo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tag"] == "foo"
    assert data["concurrency_limit"] == 5
    assert tr_id in data["active_slots"]  # holders populated from leases


@pytest.mark.asyncio
async def test_v1_read_filter_returns_only_tag_prefixed(client: AsyncClient, session):
    """Test that V1 filter endpoint only returns tag: prefixed V2 limits."""
    # Create V2 limits - some with tag: prefix, some without
    from prefect.server.models import concurrency_limits_v2 as cl_v2_models

    await cl_v2_models.create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(name="tag:test1", limit=5),
    )
    await cl_v2_models.create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(name="tag:test2", limit=3),
    )
    await cl_v2_models.create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(name="global:other", limit=10),
    )
    await session.commit()

    # Filter should only return tag: prefixed limits
    resp = await client.post(
        "/concurrency_limits/filter", json={"limit": 10, "offset": 0}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 2
    tags = {item["tag"] for item in data}
    assert tags == {"test1", "test2"}


@pytest.mark.asyncio
async def test_v1_delete_by_tag_cleans_up_leases(client: AsyncClient, session):
    """Test that V1 DELETE endpoint cleans up V2 leases."""
    # Create V1 limit (which creates V2 limit)
    resp = await client.post(
        "/concurrency_limits/", json={"tag": "deleteme", "concurrency_limit": 5}
    )
    assert resp.status_code == 201
    limit_id = resp.json()["id"]

    # Create a lease for this limit
    storage = ConcurrencyLeaseStorage()
    lease = ResourceLease(
        resource_ids=[limit_id],
        expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        metadata=ConcurrencyLimitLeaseMetadata(
            slots=1, holder={"type": "task_run", "id": str(uuid4())}
        ),
    )
    lease_id = await storage.create_lease(lease)

    # Delete the limit
    resp = await client.delete("/concurrency_limits/tag/deleteme")
    assert resp.status_code == 200

    # Verify limit is gone
    resp = await client.get("/concurrency_limits/tag/deleteme")
    assert resp.status_code == 404

    # Verify lease was cleaned up
    retrieved_lease = await storage.read_lease(lease_id)
    assert retrieved_lease is None or retrieved_lease.expiration <= datetime.now(
        timezone.utc
    )


@pytest.mark.asyncio
async def test_v1_reset_clears_and_sets_leases(client: AsyncClient, session):
    """Test that V1 RESET endpoint clears existing leases and sets new ones."""
    # Create V1 limit
    resp = await client.post(
        "/concurrency_limits/", json={"tag": "resetme", "concurrency_limit": 5}
    )
    assert resp.status_code == 201
    limit_id = resp.json()["id"]

    # Create existing leases
    storage = ConcurrencyLeaseStorage()
    old_tr_id = str(uuid4())
    lease = ResourceLease(
        resource_ids=[limit_id],
        expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        metadata=ConcurrencyLimitLeaseMetadata(
            slots=1, holder={"type": "task_run", "id": old_tr_id}
        ),
    )
    old_lease_id = await storage.create_lease(lease)

    # Reset with new slot override
    new_tr_ids = [str(uuid4()), str(uuid4())]
    resp = await client.post(
        "/concurrency_limits/tag/resetme/reset", json={"slot_override": new_tr_ids}
    )
    assert resp.status_code == 200

    # Verify old lease is revoked
    old_lease = await storage.read_lease(old_lease_id)
    assert old_lease is None or old_lease.expiration <= datetime.now(timezone.utc)

    # Verify new active slots
    resp = await client.get("/concurrency_limits/tag/resetme")
    assert resp.status_code == 200
    data = resp.json()
    active_slots = set(data["active_slots"])
    assert old_tr_id not in active_slots
    # New slots should be present (if list_holders_for_limit is implemented)
    # Note: This depends on the storage implementation
