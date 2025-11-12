import shutil
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Generator

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.client import schemas as client_schemas
from prefect.server.api.server import create_app
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLimitLeaseMetadata,
    get_concurrency_lease_storage,
)
from prefect.server.concurrency.lease_storage.filesystem import ConcurrencyLeaseStorage
from prefect.server.database import PrefectDBInterface
from prefect.server.models.concurrency_limits_v2 import (
    bulk_update_denied_slots,
    create_concurrency_limit,
    read_concurrency_limit,
)
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.server.utilities.leasing import ResourceLease
from prefect.settings import (
    PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE,
    PREFECT_SERVER_DOCKET_NAME,
)
from prefect.settings.context import temporary_settings


@pytest.fixture
def use_filesystem_lease_storage():
    with temporary_settings(
        {
            PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE: "prefect.server.concurrency.lease_storage.filesystem"
        }
    ):
        shutil.rmtree(ConcurrencyLeaseStorage().storage_path, ignore_errors=True)
        yield


@pytest.fixture()
def app(use_filesystem_lease_storage: None) -> Generator[FastAPI, Any, None]:
    # Use a unique Docket name for each test to avoid Redis key collisions
    # when using memory:// backend (fakeredis) which shares a single FakeServer
    unique_name = f"test-docket-{uuid.uuid4().hex[:8]}"
    with temporary_settings({PREFECT_SERVER_DOCKET_NAME: unique_name}):
        yield create_app(ephemeral=True)


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, Any]:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test/api"
    ) as async_client:
        yield async_client


@pytest.fixture
async def concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test_limit",
            limit=10,
        ),
    )
    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit)


@pytest.fixture
async def concurrency_limit_with_decay(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test_limit_with_decay", limit=10, slot_decay_per_second=1.0
        ),
    )
    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit)


@pytest.fixture
async def locked_concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="locked_limit",
            limit=10,
            active_slots=10,
        ),
    )
    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit)


@pytest.fixture
async def locked_concurrency_limit_with_decay(
    session: AsyncSession,
) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test_limit_with_decay",
            limit=10,
            active_slots=10,
            slot_decay_per_second=1.0,
        ),
    )
    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit)


@pytest.fixture
async def expiring_concurrency_lease(
    concurrency_limit: ConcurrencyLimitV2,
    use_filesystem_lease_storage: None,
) -> ResourceLease[ConcurrencyLimitLeaseMetadata]:
    return await get_concurrency_lease_storage().create_lease(
        resource_ids=[concurrency_limit.id],
        metadata=ConcurrencyLimitLeaseMetadata(slots=1),
        ttl=timedelta(seconds=20),
    )


async def test_create_concurrency_limit(client: AsyncClient):
    data = client_schemas.actions.ConcurrencyLimitV2Create(
        name="limiter",
        limit=42,
    ).model_dump(mode="json")

    response = await client.post("/v2/concurrency_limits/", json=data)
    assert response.status_code == 201
    assert response.json()["id"]


async def test_read_concurrency_limit_by_id(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
):
    response = await client.get(f"/v2/concurrency_limits/{concurrency_limit.id}")
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["id"] == str(concurrency_limit.id)


async def test_read_concurrency_limit_by_name(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
):
    response = await client.get(f"/v2/concurrency_limits/{concurrency_limit.name}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == str(concurrency_limit.id)


async def test_read_concurrency_non_existent_limit(
    client: AsyncClient,
):
    response = await client.get(f"/v2/concurrency_limits/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_read_all_concurrency_limits(
    concurrency_limit: ConcurrencyLimitV2,
    locked_concurrency_limit: ConcurrencyLimitV2,
    concurrency_limit_with_decay: ConcurrencyLimitV2,
    client: AsyncClient,
):
    response = await client.post("/v2/concurrency_limits/filter")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 3
    assert {limit["id"] for limit in data} == {
        str(concurrency_limit.id),
        str(locked_concurrency_limit.id),
        str(concurrency_limit_with_decay.id),
    }


async def test_update_concurrency_limit_by_id(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.patch(
        f"/v2/concurrency_limits/{concurrency_limit.id}",
        json=client_schemas.actions.ConcurrencyLimitV2Update(
            name="new-name"
        ).model_dump(mode="json", exclude_unset=True),
    )
    assert response.status_code == 204, response.text

    limit = await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )
    assert limit
    assert str(limit.name) == "new-name"


async def test_update_concurrency_limit_by_name(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.patch(
        f"/v2/concurrency_limits/{concurrency_limit.name}",
        json=client_schemas.actions.ConcurrencyLimitV2Update(
            name="new-name"
        ).model_dump(mode="json", exclude_unset=True),
    )
    assert response.status_code == 204

    limit = await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )
    assert limit
    assert str(limit.name) == "new-name"


async def test_update_concurrency_non_existent_limit(
    client: AsyncClient,
):
    response = await client.patch(
        f"/v2/concurrency_limits/{uuid.uuid4()}",
        json=client_schemas.actions.ConcurrencyLimitV2Update(
            name="new-name"
        ).model_dump(mode="json", exclude_unset=True),
    )
    assert response.status_code == 404


async def test_delete_concurrency_limit_by_id(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.delete(f"/v2/concurrency_limits/{concurrency_limit.id}")
    assert response.status_code == 204, response.text

    assert not await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )


async def test_delete_concurrency_limit_by_name(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.delete(f"/v2/concurrency_limits/{concurrency_limit.name}")
    assert response.status_code == 204

    assert not await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )


async def test_delete_concurrency_non_existent_limit(
    client: AsyncClient,
):
    response = await client.delete(f"/v2/concurrency_limits/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_slots_gt_zero_422(
    endpoint: str,
    client: AsyncClient,
):
    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={"names": ["my-limit"], "slots": 0, "mode": "concurrency"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_slots_with_unknown_name(
    endpoint: str,
    client: AsyncClient,
):
    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={"names": ["foo-bar-limit"], "slots": 1, "mode": "concurrency"},
    )
    assert response.status_code == 200
    limits = response.json() if endpoint == "increment" else response.json()["limits"]
    assert limits == []


async def test_increment_concurrency_limit_simple(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    assert concurrency_limit.active_slots == 0
    response = await client.post(
        "/v2/concurrency_limits/increment",
        json={"names": [concurrency_limit.name], "slots": 1, "mode": "concurrency"},
    )
    assert response.status_code == 200
    assert [limit["id"] for limit in response.json()] == [str(concurrency_limit.id)]

    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=concurrency_limit.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == 1


@pytest.mark.usefixtures("use_filesystem_lease_storage")
async def test_increment_concurrency_limit_with_lease_simple(
    client: AsyncClient,
    concurrency_limit: ConcurrencyLimitV2,
):
    assert concurrency_limit.active_slots == 0
    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 200
    assert [limit["id"] for limit in response.json()["limits"]] == [
        str(concurrency_limit.id)
    ]
    lease_storage = get_concurrency_lease_storage()
    lease = await lease_storage.read_lease(uuid.UUID(response.json()["lease_id"]))
    assert lease
    assert lease.resource_ids == [concurrency_limit.id]
    assert lease.metadata == ConcurrencyLimitLeaseMetadata(slots=1)


async def test_increment_concurrency_limit_with_lease_and_holder(
    client: AsyncClient,
    concurrency_limit: ConcurrencyLimitV2,
):
    # Test with flow_run holder
    flow_run_holder = {"type": "flow_run", "id": str(uuid.uuid4())}

    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "holder": flow_run_holder,
        },
    )
    assert response.status_code == 200
    assert response.json()["lease_id"]
    # Holder should not be in response
    assert "holder" not in response.json()

    lease_id = response.json()["lease_id"]

    # Verify the lease has the holder information internally
    lease_storage = get_concurrency_lease_storage()
    lease = await lease_storage.read_lease(uuid.UUID(lease_id))
    assert lease
    assert lease.metadata.holder.model_dump(mode="json") == flow_run_holder


async def test_increment_concurrency_limit_with_different_holder_types(
    client: AsyncClient,
    concurrency_limit: ConcurrencyLimitV2,
):
    # Test with task_run holder
    task_run_holder = {
        "type": "task_run",
        "id": str(uuid.uuid4()),
    }

    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "holder": task_run_holder,
        },
    )
    assert response.status_code == 200
    assert "holder" not in response.json()

    # Clean up
    await client.post(
        "/v2/concurrency_limits/decrement-with-lease",
        json={"lease_id": response.json()["lease_id"]},
    )

    # Test with deployment holder
    deployment_holder = {
        "type": "deployment",
        "id": str(uuid.uuid4()),
    }

    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "holder": deployment_holder,
        },
    )
    assert response.status_code == 200
    assert "holder" not in response.json()


async def test_increment_concurrency_limit_with_invalid_holder(
    client: AsyncClient,
    concurrency_limit: ConcurrencyLimitV2,
):
    # Test with invalid holder type
    invalid_holder = {
        "type": "invalid_type",
        "id": str(uuid.uuid4()),
    }

    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "holder": invalid_holder,
        },
    )
    assert response.status_code == 422

    # Test with extra fields (should be rejected)
    holder_with_extra = {
        "type": "task_run",
        "id": str(uuid.uuid4()),
        "extra_field": "should_not_be_allowed",
    }

    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "holder": holder_with_extra,
        },
    )
    assert response.status_code == 422

    # Test with missing id field
    holder_missing_id = {
        "type": "flow_run",
    }

    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "holder": holder_missing_id,
        },
    )
    assert response.status_code == 422


async def test_increment_concurrency_limit_with_lease_no_holder(
    client: AsyncClient,
    concurrency_limit: ConcurrencyLimitV2,
):
    # Test without holder (should still work for backward compatibility)
    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 200
    assert response.json()["lease_id"]


async def test_increment_concurrency_limit_with_lease_ttl(
    client: AsyncClient,
    concurrency_limit: ConcurrencyLimitV2,
):
    assert concurrency_limit.active_slots == 0
    now = datetime.now(timezone.utc)
    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "lease_duration": 60,
        },
    )
    assert response.status_code == 200
    assert [limit["id"] for limit in response.json()["limits"]] == [
        str(concurrency_limit.id)
    ]
    lease_storage = get_concurrency_lease_storage()
    lease = await lease_storage.read_lease(uuid.UUID(response.json()["lease_id"]))
    assert lease
    assert lease.resource_ids == [concurrency_limit.id]
    assert lease.metadata == ConcurrencyLimitLeaseMetadata(slots=1)
    assert (
        now + timedelta(seconds=60) <= lease.expiration <= now + timedelta(seconds=62)
    )


async def test_increment_concurrency_limit_with_lease_ttl_out_of_range(
    client: AsyncClient,
    concurrency_limit: ConcurrencyLimitV2,
):
    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "lease_duration": 60 * 60 * 24 * 30,
        },
    )
    assert response.status_code == 422

    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
            "lease_duration": 1,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_multi(
    endpoint: str,
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    db: PrefectDBInterface,
):
    async with db.session_context() as session:
        other_model = await create_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2(
                name="other_limit",
                limit=10,
            ),
        )
        await session.commit()

    other = ConcurrencyLimitV2.model_validate(other_model)

    assert concurrency_limit.active_slots == 0
    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [concurrency_limit.name, other.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 200
    limits = response.json() if endpoint == "increment" else response.json()["limits"]
    assert sorted([limit["id"] for limit in limits]) == sorted(
        [
            str(concurrency_limit.id),
            str(other.id),
        ]
    )

    async with db.session_context() as session:
        for limit in [concurrency_limit, other]:
            refreshed_limit = await read_concurrency_limit(
                session=session, concurrency_limit_id=limit.id
            )
            assert refreshed_limit
            assert refreshed_limit.active_slots == 1


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_inactive(
    endpoint: str,
    client: AsyncClient,
    session: AsyncSession,
):
    inactive = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            active=False,
            name="inactive_limit",
            limit=10,
        ),
    )
    await session.commit()

    assert inactive.active_slots == 0
    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={"names": [inactive.name], "slots": 1, "mode": "concurrency"},
    )
    assert response.status_code == 200
    limits = response.json() if endpoint == "increment" else response.json()["limits"]
    assert [limit["id"] for limit in limits] == [str(inactive.id)]

    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=inactive.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == 0  # Inactive limits are not incremented


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_locked(
    endpoint: str,
    locked_concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    assert locked_concurrency_limit.active_slots == locked_concurrency_limit.limit

    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [locked_concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 423

    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=locked_concurrency_limit.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == refreshed_limit.limit


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_locked_no_decay_retry_after_header(
    endpoint: str,
    locked_concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    await bulk_update_denied_slots(
        session=session,
        concurrency_limit_ids=[locked_concurrency_limit.id],
        slots=10,
    )
    await session.commit()

    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [locked_concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 423

    assert locked_concurrency_limit.avg_slot_occupancy_seconds == 2.0
    # avg occupancy * ((num slots requested + num denied slots) / limit)
    # clamped_poisson_interval adds jitter, so check approximate value
    expected_retry_after = 2.0 * ((1 + 10) / 10)
    actual_retry_after = float(response.headers["Retry-After"])
    assert abs(actual_retry_after - expected_retry_after) < expected_retry_after * 0.5


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_with_decay_locked_retry_after_header(
    endpoint: str,
    locked_concurrency_limit_with_decay: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    await bulk_update_denied_slots(
        session=session,
        concurrency_limit_ids=[locked_concurrency_limit_with_decay.id],
        slots=10,
    )
    await session.commit()

    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [locked_concurrency_limit_with_decay.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 423

    assert locked_concurrency_limit_with_decay.slot_decay_per_second == 1.0
    # (1.0 / slot_decay) * (num slots requested + num denied slots)
    # clamped_poisson_interval adds jitter, so check approximate value
    expected_retry_after = 1.0 * (1.0 + 10)
    actual_retry_after = float(response.headers["Retry-After"])
    assert abs(actual_retry_after - expected_retry_after) < expected_retry_after * 0.5


@pytest.fixture
async def locked_tag_concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    """
    A locked concurrency limit with high avg occupancy.
    Uses tag prefix to match scenario where long-running tasks
    caused excessive retry delays.
    """
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="tag:long-running",
            limit=10,
            active_slots=10,
            avg_slot_occupancy_seconds=10800.0,  # 3 hours
        ),
    )
    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit)


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_locked_caps_excessive_retry_after(
    endpoint: str,
    locked_tag_concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    """
    Test that concurrency limits cap excessive avg_slot_occupancy_seconds.

    When a limit has very high avg occupancy (e.g., 3 hours from long-running tasks),
    the Retry-After should be capped at the configured max (default 30s) rather than
    calculating based on the actual occupancy which would result in excessive delays
    (e.g., 3 hours * 30 slots = 90 hours).

    This applies to all concurrency limits, not just tag-based ones.
    """
    await bulk_update_denied_slots(
        session=session,
        concurrency_limit_ids=[locked_tag_concurrency_limit.id],
        slots=10,
    )
    await session.commit()

    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [locked_tag_concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 423

    # For limits with excessive avg occupancy, Retry-After should be capped
    # at the configured max (default 30s) rather than using the full avg_slot_occupancy_seconds
    retry_after = float(response.headers["Retry-After"])

    # Should be around 30 seconds (the default tag_concurrency_slot_wait_seconds cap)
    # with some randomization from clamped_poisson_interval. Check for reasonable bounds
    # rather than exact value due to jitter.
    assert 15 < retry_after < 60, (
        f"Expected ~30s with jitter, got {retry_after}s. "
        f"If much higher, capping may be broken and using full avg_slot_occupancy_seconds "
        f"({locked_tag_concurrency_limit.avg_slot_occupancy_seconds}s)"
    )


@pytest.fixture
async def locked_tag_concurrency_limit_low_avg(
    session: AsyncSession,
) -> ConcurrencyLimitV2:
    """
    A locked tag-based concurrency limit with low avg occupancy.
    This verifies we still use the actual avg when it's reasonable.
    """
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="tag:quick-tasks",
            limit=10,
            active_slots=10,
            avg_slot_occupancy_seconds=2.0,  # 2 seconds
        ),
    )
    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit)


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_locked_respects_low_avg(
    endpoint: str,
    locked_tag_concurrency_limit_low_avg: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    """
    Test that concurrency limits respect low avg_slot_occupancy_seconds.

    When a limit has reasonable avg occupancy (e.g., 2 seconds), we should use
    that value rather than forcing it up to the configured max (default 30s).
    This ensures fast-running tasks retry quickly.

    This applies to all concurrency limits, not just tag-based ones.
    """
    await bulk_update_denied_slots(
        session=session,
        concurrency_limit_ids=[locked_tag_concurrency_limit_low_avg.id],
        slots=10,
    )
    await session.commit()

    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [locked_tag_concurrency_limit_low_avg.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 423

    # For limits with low avg occupancy, Retry-After should use the actual
    # avg_slot_occupancy_seconds rather than forcing it up to the configured max
    retry_after = float(response.headers["Retry-After"])

    # Should be around 2 seconds (the actual avg_slot_occupancy_seconds)
    # with some randomization from clamped_poisson_interval. Check for reasonable bounds.
    assert 1 < retry_after < 5, (
        f"Expected ~2s with jitter, got {retry_after}s. "
        f"avg_slot_occupancy_seconds is {locked_tag_concurrency_limit_low_avg.avg_slot_occupancy_seconds}s, "
        f"should not be forced up to the configured max"
    )


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_slot_request_higher_than_limit(
    endpoint: str,
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [concurrency_limit.name],
            "slots": concurrency_limit.limit + 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Slots requested is greater than the limit"}

    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=concurrency_limit.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == 0


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_rate_limit_mode(
    endpoint: str,
    concurrency_limit_with_decay: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [concurrency_limit_with_decay.name],
            "slots": 1,
            "mode": "rate_limit",
        },
    )
    assert response.status_code == 200

    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=concurrency_limit_with_decay.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == 1


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_rate_limit_mode_doesnt_create_by_default(
    endpoint: str,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": ["ignored_limit"],
            "slots": 1,
            "mode": "rate_limit",
        },
    )

    assert response.status_code == 200

    refreshed_limit = await read_concurrency_limit(
        session=session, name="ignored_limit"
    )
    assert refreshed_limit is None


@pytest.mark.parametrize("endpoint", ["increment", "increment-with-lease"])
async def test_increment_concurrency_limit_rate_limit_mode_limit_without_decay(
    endpoint: str,
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.post(
        f"/v2/concurrency_limits/{endpoint}",
        json={
            "names": [concurrency_limit.name],
            "slots": 1,
            "mode": "rate_limit",
        },
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": (
            "Only concurrency limits with slot decay can be used for rate "
            "limiting. The following limits do not have a decay configured: "
            "'test_limit'"
        ),
    }

    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=concurrency_limit.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == 0


async def test_decrement_concurrency_limit_slots_gt_zero_422(client: AsyncClient):
    response = await client.post(
        "/v2/concurrency_limits/decrement",
        json={"names": ["my-limit"], "slots": 0, "mode": "concurrency"},
    )
    assert response.status_code == 422


@pytest.mark.usefixtures("ignore_prefect_deprecation_warnings")
async def test_decrement_concurrency_limit(
    locked_concurrency_limit: ConcurrencyLimitV2,
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    assert concurrency_limit.active_slots == 0
    response = await client.post(
        "/v2/concurrency_limits/decrement",
        json={
            "names": [concurrency_limit.name, locked_concurrency_limit.name],
            "slots": 1,
        },
    )
    assert response.status_code == 200
    assert sorted([limit["id"] for limit in response.json()]) == sorted(
        [
            str(concurrency_limit.id),
            str(locked_concurrency_limit.id),
        ]
    )

    # `concurrency_limit` should still be at 0.
    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=concurrency_limit.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == 0

    # `locked_concurrency_limit` should still be one less than its limit.
    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=locked_concurrency_limit.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == refreshed_limit.limit - 1


@pytest.mark.usefixtures("use_filesystem_lease_storage")
async def test_decrement_concurrency_limit_with_lease(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    assert concurrency_limit.active_slots == 0
    response = await client.post(
        "/v2/concurrency_limits/increment-with-lease",
        json={"names": [concurrency_limit.name], "slots": 2, "mode": "concurrency"},
    )
    assert response.status_code == 200

    limit = await client.get(f"/v2/concurrency_limits/{concurrency_limit.id}")
    assert limit.status_code == 200
    assert limit.json()["active_slots"] == 2

    lease = await get_concurrency_lease_storage().read_lease(
        response.json()["lease_id"]
    )
    assert lease
    assert lease.resource_ids == [concurrency_limit.id]
    assert lease.metadata
    assert lease.metadata.slots == 2

    lease_id = response.json()["lease_id"]
    response = await client.post(
        "/v2/concurrency_limits/decrement-with-lease",
        json={"lease_id": lease_id},
    )
    assert response.status_code == 204, response.text

    lease = await get_concurrency_lease_storage().read_lease(lease_id)
    assert not lease

    refreshed_limit = await client.get(f"/v2/concurrency_limits/{concurrency_limit.id}")
    assert refreshed_limit.status_code == 200
    assert refreshed_limit.json()["active_slots"] == 0


async def test_renew_concurrency_lease(
    expiring_concurrency_lease: ResourceLease[ConcurrencyLimitLeaseMetadata],
    client: AsyncClient,
):
    lease_storage = get_concurrency_lease_storage()
    expired_lease_ids = await lease_storage.read_expired_lease_ids()
    now = datetime.now(timezone.utc)
    assert not expired_lease_ids

    response = await client.post(
        f"/v2/concurrency_limits/leases/{expiring_concurrency_lease.id}/renew",
        json={"lease_duration": 600},
    )
    assert response.status_code == 204, response.text

    lease = await lease_storage.read_lease(expiring_concurrency_lease.id)
    assert lease
    assert (
        now + timedelta(seconds=600) <= lease.expiration <= now + timedelta(seconds=602)
    )


async def test_renew_concurrency_lease_not_found(
    client: AsyncClient,
):
    response = await client.post(
        f"/v2/concurrency_limits/leases/{uuid.uuid4()}/renew",
        json={"lease_duration": 600},
    )
    assert response.status_code == 410, response.text


async def test_renew_concurrency_lease_with_legacy_implementation(
    expiring_concurrency_lease: ResourceLease[ConcurrencyLimitLeaseMetadata],
    client: AsyncClient,
    monkeypatch,
):
    """Test that None return value from legacy implementations is treated as success when lease exists."""

    # Get the original implementation
    lease_storage = get_concurrency_lease_storage()
    original_renew = lease_storage.renew_lease

    # Create a wrapper that calls the original but returns None (simulating legacy behavior)
    async def legacy_renew_wrapper(lease_id, ttl):
        # Call the original to actually renew the lease
        await original_renew(lease_id, ttl)
        # But return None like legacy implementations
        return None

    # Patch the renew_lease method on the storage instance
    monkeypatch.setattr(lease_storage, "renew_lease", legacy_renew_wrapper)

    # Should succeed (204) even though implementation returned None, because lease exists
    response = await client.post(
        f"/v2/concurrency_limits/leases/{expiring_concurrency_lease.id}/renew",
        json={"lease_duration": 600},
    )
    assert response.status_code == 204, response.text

    # Verify the lease was actually renewed
    lease = await lease_storage.read_lease(expiring_concurrency_lease.id)
    assert lease is not None
    assert lease.expiration > expiring_concurrency_lease.expiration


async def test_renew_concurrency_lease_with_legacy_implementation_not_found(
    client: AsyncClient,
    monkeypatch,
):
    """Test that None return value from legacy implementations is treated as error when lease doesn't exist."""

    # Get the lease storage
    lease_storage = get_concurrency_lease_storage()

    # Create a mock that always returns None (simulating legacy behavior)
    async def legacy_renew_returns_none(lease_id, ttl):
        # Legacy implementation returns None regardless of success
        return None

    # Patch the renew_lease method
    monkeypatch.setattr(lease_storage, "renew_lease", legacy_renew_returns_none)

    # Should return 410 GONE because lease doesn't exist (even though renew returned None)
    response = await client.post(
        f"/v2/concurrency_limits/leases/{uuid.uuid4()}/renew",
        json={"lease_duration": 600},
    )
    assert response.status_code == 410, response.text
