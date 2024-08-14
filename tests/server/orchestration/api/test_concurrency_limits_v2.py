import base64
import uuid
from typing import Generator, List, Literal
from unittest import mock

import pytest
from httpx import AsyncClient
from pendulum import DateTime
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.client import schemas as client_schemas
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events import ReceivedEvent
from prefect.server.models.concurrency_limits_v2 import (
    bulk_update_denied_slots,
    create_concurrency_limit,
    read_concurrency_limit,
)
from prefect.server.schemas.core import ConcurrencyLimitV2

MOCK_PAGE_TOKEN = "THAT:SWEETSWEETTOKEN"
ENCODED_MOCK_PAGE_TOKEN = base64.b64encode(MOCK_PAGE_TOKEN.encode()).decode()


def make_received_event(
    event_type: Literal["acquired", "released"],
    concurrency_limit: ConcurrencyLimitV2,
    index: int,
) -> ReceivedEvent:
    return ReceivedEvent(
        event=f"prefect.concurrency-limit.{event_type}",
        resource={
            "limit": "1",
            "slots-acquired": "1",
            "prefect.resource.id": f"prefect.concurrency-limit.{concurrency_limit.id}",
            "prefect.resource.name": "database",
        },
        occurred=DateTime(2023, 3, 1, 12, 39, 28),
        related=[
            {
                "prefect.resource.id": f"prefect.flow-run.{uuid.UUID(int=index)}",
                "prefect.resource.name": "something-special",
                "prefect.resource.role": "flow-run",
            },
            {
                "prefect.resource.id": f"prefect.task-run.{uuid.UUID(int=index)}",
                "prefect.resource.name": "process_data-10",
                "prefect.resource.role": "task-run",
            },
            {
                "prefect.resource.id": f"prefect.flow.{uuid.UUID(int=index)}",
                "prefect.resource.name": "my-flow-2",
                "prefect.resource.role": "flow",
            },
        ],
        payload={},
        id=uuid.UUID(int=1),
    )


@pytest.fixture
def acquired_events_page_one(concurrency_limit) -> List[ReceivedEvent]:
    return [make_received_event("acquired", concurrency_limit, i) for i in range(5)]


@pytest.fixture
def acquired_events_page_two(concurrency_limit) -> List[ReceivedEvent]:
    return [make_received_event("acquired", concurrency_limit, i) for i in range(5)]


@pytest.fixture
def released_events_page_one(concurrency_limit) -> List[ReceivedEvent]:
    return [make_received_event("released", concurrency_limit, i) for i in range(5)]


@pytest.fixture
def released_events_page_two(concurrency_limit) -> List[ReceivedEvent]:
    return [make_received_event("released", concurrency_limit, i) for i in range(5)]


@pytest.fixture
def acquired_events_page_three(concurrency_limit) -> List[ReceivedEvent]:
    return [
        ReceivedEvent(
            event="prefect.concurrency-limit.acquired",
            resource={
                "limit": "1",
                "slots-acquired": "1",
                "prefect.resource.id": f"prefect.concurrency-limit.{concurrency_limit.id}",
                "prefect.resource.name": "database",
            },
            occurred=DateTime(2023, 3, 1, 13, 39, 28),
            related=[
                {
                    "prefect.resource.id": f"prefect.flow-run.{uuid.UUID(int=42)}",
                    "prefect.resource.name": "something-special",
                    "prefect.resource.role": "flow-run",
                },
                {
                    "prefect.resource.id": f"prefect.task-run.{uuid.UUID(int=42)}",
                    "prefect.resource.name": "process_data-10",
                    "prefect.resource.role": "task-run",
                },
                {
                    "prefect.resource.id": f"prefect.flow.{uuid.UUID(int=42)}",
                    "prefect.resource.name": "my-flow-2",
                    "prefect.resource.role": "flow",
                },
            ],
            payload={},
            id=uuid.UUID(int=1),
        )
    ]


@pytest.fixture
def query_events(
    acquired_events_page_one, released_events_page_one
) -> Generator[mock.AsyncMock, None, None]:
    with mock.patch("prefect.server.api.events.database.query_events") as query_events:
        query_events.side_effect = [
            (
                acquired_events_page_one,
                123,
                ENCODED_MOCK_PAGE_TOKEN,
            ),
            (
                released_events_page_one,
                123,
                ENCODED_MOCK_PAGE_TOKEN,
            ),
        ]
        yield query_events


@pytest.fixture
def query_next_page(
    acquired_events_page_two, released_events_page_two
) -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.server.api.events.database.query_next_page",
        new_callable=mock.AsyncMock,
    ) as query_next_page:
        query_next_page.side_effect = [
            (
                acquired_events_page_two,
                123,
                ENCODED_MOCK_PAGE_TOKEN,
            ),
            (
                released_events_page_two,
                123,
                ENCODED_MOCK_PAGE_TOKEN,
            ),
        ]
        yield query_next_page


@pytest.fixture
def last_events_page(
    acquired_events_page_three,
) -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.server.api.events.database.query_next_page",
        new_callable=mock.AsyncMock,
    ) as query_next_page:
        query_next_page.side_effect = [
            (
                acquired_events_page_three,
                123,
                None,
            ),
            (
                [],
                123,
                None,
            ),
        ]
        yield query_next_page


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


async def test_get_concurrency_limit_active_owners(
    concurrency_limit: ConcurrencyLimitV2,
    client: AsyncClient,
    query_events,
    query_next_page,
    last_events_page,
):
    response = await client.post(
        "/v2/concurrency_limits/active_owners",
        json={"names": [concurrency_limit.name]},
    )
    assert response.status_code == 200
    data = response.json()
    assert list(data) == ["database"]
    assert sorted(data["database"], key=lambda x: x["name"]) == sorted(
        [
            {
                "id": "00000000-0000-0000-0000-00000000002a",
                "name": "something-special",
                "type": "flow-run",
            },
            {
                "id": "00000000-0000-0000-0000-00000000002a",
                "name": "process_data-10",
                "type": "task-run",
            },
        ],
        key=lambda x: x["name"],
    )


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
):
    response = await client.post(
        "/v2/concurrency_limits/increment",
        json={
            "names": ["implicitly_created_limit"],
            "slots": 1,
            "mode": "rate_limit",
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
