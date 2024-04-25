import base64
import re
from typing import Generator, List
from unittest import mock
from uuid import UUID

import pendulum
import pytest
from httpx import AsyncClient
from pendulum.datetime import DateTime

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.server.events.counting import Countable, TimeUnit
from prefect.server.events.filters import (
    EventFilter,
    EventOccurredFilter,
    EventResourceFilter,
)
from prefect.server.events.schemas.events import (
    EventCount,
    EventPage,
    ReceivedEvent,
    Resource,
)
from prefect.server.events.storage import INTERACTIVE_PAGE_SIZE, InvalidTokenError

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic


@pytest.fixture
def filter(frozen_time: DateTime) -> EventFilter:
    return EventFilter(
        occurred=EventOccurredFilter(),
    )


@pytest.fixture
def events_page_one() -> List[ReceivedEvent]:
    return [
        ReceivedEvent(
            occurred=pendulum.now("UTC"),
            event="first.page.material",
            resource=Resource(__root__={"prefect.resource.id": "my.resource"}),
            payload={"goodbye": "moon"},
            id=UUID(int=i),
        )
        for i in range(5)
    ]


@pytest.fixture
def events_page_two() -> List[ReceivedEvent]:
    return [
        ReceivedEvent(
            occurred=pendulum.now("UTC"),
            event="second.page.material",
            resource=Resource(__root__={"prefect.resource.id": "my.resource"}),
            payload={"goodbye": "moon"},
            id=UUID(int=i),
        )
        for i in range(5)
    ]


@pytest.fixture
def events_page_three() -> List[ReceivedEvent]:
    return [
        ReceivedEvent(
            occurred=pendulum.now("UTC"),
            event="second.page.material",
            resource=Resource(__root__={"prefect.resource.id": "my.resource"}),
            payload={"goodbye": "moon"},
            id=UUID(int=i),
        )
        for i in range(5)
    ]


MOCK_PAGE_TOKEN = "THAT:SWEETSWEETTOKEN"
ENCODED_MOCK_PAGE_TOKEN = base64.b64encode(MOCK_PAGE_TOKEN.encode()).decode()


@pytest.fixture
def query_events(
    events_page_one: List[ReceivedEvent],
) -> Generator[mock.AsyncMock, None, None]:
    with mock.patch("prefect.server.api.events.database.query_events") as query_events:
        query_events.return_value = (events_page_one, 123, MOCK_PAGE_TOKEN)
        yield query_events


@pytest.fixture
def query_next_page(
    events_page_two: List[ReceivedEvent],
) -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.server.api.events.database.query_next_page",
        new_callable=mock.AsyncMock,
    ) as query_next_page:
        query_next_page.return_value = (events_page_two, 123, "THAT:NEXTNEXTTOKEN")
        yield query_next_page


@pytest.fixture
def last_events_page(
    events_page_three: List[ReceivedEvent],
) -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.server.api.events.database.query_next_page",
        new_callable=mock.AsyncMock,
    ) as query_next_page:
        query_next_page.return_value = (events_page_three, 123, None)
        yield query_next_page


async def test_returns_404_when_events_are_disabled(
    client: AsyncClient, events_disabled: None
):
    response = await client.post(
        "http://test/api/events/filter",
        json={"filter": {}},
    )

    assert response.status_code == 404, response.content


async def test_querying_for_events_returns_first_page(
    client: AsyncClient,
    filter: EventFilter,
    query_events: mock.AsyncMock,
    events_page_one: List[ReceivedEvent],
):
    response = await client.post(
        "http://test/api/events/filter",
        json={"filter": filter.dict(json_compatible=True)},
    )

    assert response.status_code == 200, response.content

    query_events.assert_awaited_once_with(
        session=mock.ANY,
        filter=filter,
        page_size=INTERACTIVE_PAGE_SIZE,
    )

    first_page = EventPage.parse_obj(response.json())

    assert first_page.events == events_page_one
    assert first_page.total == 123
    assert first_page.next_page == (
        f"http://test/api/events/filter/next" f"?page-token={ENCODED_MOCK_PAGE_TOKEN}"
    )


async def test_querying_for_events_returns_first_page_with_no_more(
    client: AsyncClient,
    filter: EventFilter,
    query_events: mock.AsyncMock,
    events_page_one: List[ReceivedEvent],
    frozen_time: DateTime,
):
    query_events.return_value = (events_page_one, len(events_page_one), None)

    response = await client.post(
        "http://test/api/events/filter",
        json={"filter": filter.dict(json_compatible=True)},
    )

    assert response.status_code == 200, response.content

    query_events.assert_awaited_once_with(
        session=mock.ANY,
        filter=filter,
        page_size=INTERACTIVE_PAGE_SIZE,
    )

    first_page = EventPage.parse_obj(response.json())

    assert first_page.events == events_page_one
    assert first_page.total == len(events_page_one)
    assert first_page.next_page is None


async def test_querying_for_events_with_not_arguments_uses_the_default_filter(
    client: AsyncClient,
    query_events: mock.AsyncMock,
    filter: EventFilter,
    events_page_one: List[ReceivedEvent],
    frozen_time: DateTime,
):
    response = await client.post(
        "http://test/api/events/filter",
    )

    assert response.status_code == 200, response.content

    query_events.assert_awaited_once_with(
        session=mock.ANY,
        filter=filter,
        page_size=INTERACTIVE_PAGE_SIZE,
    )


async def test_querying_for_subsequent_page_returns_it(
    client: AsyncClient,
    query_events: mock.AsyncMock,
    events_page_two: List[ReceivedEvent],
    query_next_page: mock.AsyncMock,
):
    response = await client.get(
        f"http://test/api/events/filter/next?page-token={ENCODED_MOCK_PAGE_TOKEN}",
    )

    assert response.status_code == 200

    query_events.assert_not_awaited()
    query_next_page.assert_awaited_once_with(
        session=mock.ANY,
        page_token=MOCK_PAGE_TOKEN,
    )

    second_page = EventPage.parse_obj(response.json())

    assert second_page.events == events_page_two
    assert second_page.total == 123
    assert second_page.next_page == (
        f"http://test/api/events/filter/next?page-token={base64.b64encode('THAT:NEXTNEXTTOKEN'.encode()).decode()}"
    )


async def test_querying_for_last_page_returns_no_token(
    client: AsyncClient,
    query_events: mock.AsyncMock,
    events_page_three: List[ReceivedEvent],
    last_events_page: mock.AsyncMock,
):
    response = await client.get(
        f"http://test/api/events/filter/next?page-token={ENCODED_MOCK_PAGE_TOKEN}",
    )

    assert response.status_code == 200

    query_events.assert_not_awaited()
    last_events_page.assert_awaited_once_with(
        session=mock.ANY,
        page_token=MOCK_PAGE_TOKEN,
    )

    third_page = EventPage.parse_obj(response.json())

    assert third_page.events == events_page_three
    assert third_page.total == 123
    assert third_page.next_page is None


async def test_token_shenanigans_will_not_be_tolerated(
    client: AsyncClient,
    query_events: mock.AsyncMock,
    query_next_page: mock.AsyncMock,
):
    response = await client.get(
        "http://test/api/events/filter/next?page-token=just-bad",
    )
    assert response.status_code == 403, response.text
    query_events.assert_not_awaited()
    query_next_page.assert_not_awaited()


async def test_inner_token_shenanigans_will_not_be_tolerated(
    client: AsyncClient,
    query_events: mock.AsyncMock,
    query_next_page: mock.AsyncMock,
):
    passes_sniff_test = base64.b64encode(MOCK_PAGE_TOKEN.encode()).decode()
    query_next_page.side_effect = InvalidTokenError("nope")
    response = await client.get(
        f"http://test/api/events/filter/next?page-token={passes_sniff_test}",
    )
    assert response.status_code == 403
    query_events.assert_not_awaited()


async def test_events_api_returns_times_with_timezone_offsets(
    client: AsyncClient,
    filter: EventFilter,
    query_events,
):
    response = await client.post(
        "http://test/api/events/filter",
        json={"filter": filter.dict(json_compatible=True)},
    )

    assert response.status_code == 200, response.content

    for event in response.json()["events"]:
        occurred = event["occurred"]
        assert isinstance(occurred, str)
        assert occurred.endswith("+00:00")

        received = event["received"]
        assert isinstance(received, str)
        assert received.endswith("+00:00")


@pytest.fixture
def count_events() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch("prefect.server.api.events.database.count_events") as count_events:
        count_events.return_value = [
            EventCount(
                value="hello",
                label="world",
                count=42,
                start_time=pendulum.now("UTC").subtract(days=7),
                end_time=pendulum.now("UTC"),
            ),
            EventCount(
                value="goodbye",
                label="moon",
                count=24,
                start_time=pendulum.now("UTC").subtract(days=7),
                end_time=pendulum.now("UTC"),
            ),
        ]
        yield count_events


async def test_counting_events_by_day(
    client: AsyncClient,
    filter: EventFilter,
    count_events: mock.AsyncMock,
    frozen_time: DateTime,
):
    response = await client.post(
        "http://test/api/events/count-by/day",
        json={"filter": filter.dict(json_compatible=True)},
    )

    assert response.status_code == 200, response.content
    assert pydantic.parse_obj_as(List[EventCount], response.json()) == [
        EventCount(
            value="hello",
            label="world",
            count=42,
            start_time=pendulum.now("UTC").subtract(days=7),
            end_time=pendulum.now("UTC"),
        ),
        EventCount(
            value="goodbye",
            label="moon",
            count=24,
            start_time=pendulum.now("UTC").subtract(days=7),
            end_time=pendulum.now("UTC"),
        ),
    ]

    count_events.assert_awaited_once_with(
        session=mock.ANY,
        filter=EventFilter(
            occurred=filter.occurred,
        ),
        countable=Countable.day,
        time_unit=TimeUnit.day,
        time_interval=1.0,
    )


async def test_counting_events_by_time(
    client: AsyncClient,
    filter: EventFilter,
    count_events: mock.AsyncMock,
    frozen_time: DateTime,
):
    response = await client.post(
        "http://test/api/events/count-by/time",
        json={
            "filter": filter.dict(json_compatible=True),
            "time_unit": "hour",
            "time_interval": 2,
        },
    )

    assert response.status_code == 200, response.content
    assert pydantic.parse_obj_as(List[EventCount], response.json()) == [
        EventCount(
            value="hello",
            label="world",
            count=42,
            start_time=pendulum.now("UTC").subtract(days=7),
            end_time=pendulum.now("UTC"),
        ),
        EventCount(
            value="goodbye",
            label="moon",
            count=24,
            start_time=pendulum.now("UTC").subtract(days=7),
            end_time=pendulum.now("UTC"),
        ),
    ]

    count_events.assert_awaited_once_with(
        session=mock.ANY,
        filter=EventFilter(
            occurred=filter.occurred,
        ),
        countable=Countable.time,
        time_unit=TimeUnit.hour,
        time_interval=2.0,
    )


async def test_counting_events_by_time_minimum_time_interval(
    client: AsyncClient,
    filter: EventFilter,
    count_events: mock.AsyncMock,
):
    response = await client.post(
        "http://test/api/events/count-by/time",
        json={
            "filter": filter.dict(json_compatible=True),
            "time_unit": "hour",
            "time_interval": 0.009,
        },
    )

    assert response.status_code == 422, response.content
    assert "0.01" in response.text

    count_events.assert_not_called()


async def test_counting_events_by_event_with_a_filter(
    client: AsyncClient,
    filter: EventFilter,
    count_events: mock.AsyncMock,
    frozen_time: DateTime,
):
    filter.resource = EventResourceFilter(id=["resource-a", "resource-b"])

    response = await client.post(
        "http://test/api/events/count-by/event",
        json={"filter": filter.dict(json_compatible=True)},
    )

    assert response.status_code == 200, response.content
    assert pydantic.parse_obj_as(List[EventCount], response.json()) == [
        EventCount(
            value="hello",
            label="world",
            count=42,
            start_time=pendulum.now("UTC").subtract(days=7),
            end_time=pendulum.now("UTC"),
        ),
        EventCount(
            value="goodbye",
            label="moon",
            count=24,
            start_time=pendulum.now("UTC").subtract(days=7),
            end_time=pendulum.now("UTC"),
        ),
    ]

    count_events.assert_awaited_once_with(
        session=mock.ANY,
        filter=EventFilter(
            occurred=filter.occurred,
            resource=EventResourceFilter(id=["resource-a", "resource-b"]),
        ),
        countable=Countable.event,
        time_unit=TimeUnit.day,
        time_interval=1.0,
    )


async def test_counting_events_too_many_buckets(
    client: AsyncClient,
    filter: EventFilter,
):
    response = await client.post(
        "http://test/api/events/count-by/time",
        json={
            "filter": filter.dict(json_compatible=True),
            "time_unit": "second",
            "time_interval": 0.01,
        },
    )

    assert response.status_code == 422, response.content
    assert re.search(
        r"The given interval would create \d+ buckets, which is too many.",
        response.text,
    )
