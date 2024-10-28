import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.client import schemas as client_schemas
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.models.concurrency_limits_v2 import (
    bulk_update_denied_slots,
    create_concurrency_limit,
    read_concurrency_limit,
)
from prefect.server.schemas.core import ConcurrencyLimitV2


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


async def test_increment_concurrency_limit_slots_gt_zero_422(
    client: AsyncClient,
):
    response = await client.post(
        "/v2/concurrency_limits/increment",
        json={"names": ["my-limit"], "slots": 0, "mode": "concurrency"},
    )
    assert response.status_code == 422


async def test_increment_concurrency_limit_slots_with_unknown_name(
    client: AsyncClient,
):
    response = await client.post(
        "/v2/concurrency_limits/increment",
        json={"names": ["foo-bar-limit"], "slots": 1, "mode": "concurrency"},
    )
    assert response.status_code == 200
    assert response.json() == []


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


async def test_increment_concurrency_limit_multi(
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
        "/v2/concurrency_limits/increment",
        json={
            "names": [concurrency_limit.name, other.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 200
    assert sorted([limit["id"] for limit in response.json()]) == sorted(
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


async def test_increment_concurrency_limit_inactive(
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
        "/v2/concurrency_limits/increment",
        json={"names": [inactive.name], "slots": 1, "mode": "concurrency"},
    )
    assert response.status_code == 200
    assert [limit["id"] for limit in response.json()] == [str(inactive.id)]

    refreshed_limit = await read_concurrency_limit(
        session=session, concurrency_limit_id=inactive.id
    )
    assert refreshed_limit
    assert refreshed_limit.active_slots == 0  # Inactive limits are not incremented


async def test_increment_concurrency_limit_locked(
    locked_concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    assert locked_concurrency_limit.active_slots == locked_concurrency_limit.limit

    response = await client.post(
        "/v2/concurrency_limits/increment",
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


async def test_increment_concurrency_limit_locked_no_decay_retry_after_header(
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
        "/v2/concurrency_limits/increment",
        json={
            "names": [locked_concurrency_limit.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 423

    assert locked_concurrency_limit.avg_slot_occupancy_seconds == 2.0
    # avg occupancy * ((num slots requested + num denied slots) / limit)
    expected_retry_after = 2.0 * ((1 + 10) / 10)
    assert response.headers["Retry-After"] == str(expected_retry_after)


async def test_increment_concurrency_limit_with_decay_locked_retry_after_header(
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
        "/v2/concurrency_limits/increment",
        json={
            "names": [locked_concurrency_limit_with_decay.name],
            "slots": 1,
            "mode": "concurrency",
        },
    )
    assert response.status_code == 423

    assert locked_concurrency_limit_with_decay.slot_decay_per_second == 1.0
    # (1.0 / slot_decay) * (num slots requested + num denied slots)
    expected_retry_after = 1.0 * (1.0 + 10)
    assert response.headers["Retry-After"] == str(expected_retry_after)


async def test_increment_concurrency_limit_slot_request_higher_than_limit(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.post(
        "/v2/concurrency_limits/increment",
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


async def test_increment_concurrency_limit_rate_limit_mode(
    concurrency_limit_with_decay: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.post(
        "/v2/concurrency_limits/increment",
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


async def test_increment_concurrency_limit_rate_limit_mode_implicitly_created_limit(
    client: AsyncClient,
    session: AsyncSession,
    ignore_prefect_deprecation_warnings,
):
    # DEPRECATED BEHAVIOR
    response = await client.post(
        "/v2/concurrency_limits/increment",
        json={
            "names": ["implicitly_created_limit"],
            "slots": 1,
            "mode": "rate_limit",
            "create_if_missing": True,
        },
    )

    # The limit should have been created as inactive this will bypass the
    # validation of `slot_decay_per_second` being non-zero as the limit is
    # effectively ignored resulting in a 200 response.
    assert response.status_code == 200

    refreshed_limit = await read_concurrency_limit(
        session=session, name="implicitly_created_limit"
    )
    assert refreshed_limit
    assert not bool(refreshed_limit.active)
    assert refreshed_limit.active_slots == 0  # Inactive limits are not incremented


async def test_increment_concurrency_limit_rate_limit_mode_doesnt_create_by_default(
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.post(
        "/v2/concurrency_limits/increment",
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


async def test_increment_concurrency_limit_rate_limit_mode_limit_without_decay(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
):
    response = await client.post(
        "/v2/concurrency_limits/increment",
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


async def test_decrement_concurrency_limit(
    locked_concurrency_limit: ConcurrencyLimitV2,
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    session: AsyncSession,
    ignore_prefect_deprecation_warnings,
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
