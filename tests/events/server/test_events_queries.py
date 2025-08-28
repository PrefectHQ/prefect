"""Tests for parity when querying events across our storage backends and streaming"""

import datetime
from base64 import b64encode
from datetime import timedelta
from typing import AsyncGenerator, List
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events.filters import (
    EventAnyResourceFilter,
    EventFilter,
    EventIDFilter,
    EventNameFilter,
    EventOccurredFilter,
    EventOrder,
    EventRelatedFilter,
    EventResourceFilter,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage import from_page_token
from prefect.server.events.storage.database import (
    query_events,
    query_next_page,
    write_events,
)
from prefect.types._datetime import Date, now, start_of_day


@pytest.fixture(scope="module")
def known_dates() -> tuple[Date, ...]:
    dates = [Date.today() - timedelta(days=days_ago) for days_ago in [5, 4, 3, 2, 1]]
    return tuple(dates)


@pytest.fixture
def all_events(
    known_dates: tuple[Date, ...],
) -> list[ReceivedEvent]:
    event_options = [
        "things.happened",
        "things.happened",
        "things.happened",
        "things.didn't",
        "things.didn't",
        "other.stuff",
        "nope.not.this",
    ]

    resource_options: list[dict[str, str]] = [
        {
            "prefect.resource.id": "foo.1",
            "hello": "world",
            "a-label": "a-good-value",
        },
        {
            "prefect.resource.id": "foo.1",
            "hello": "world",
            "a-label": "some other value",
        },
        {
            "prefect.resource.id": "other.3",
            "goodbye": "moon",
            "hello": "mars",
            "a-label": "a-good-string",
        },
    ]
    related_options: list[list[dict[str, str]]] = [
        [],
        [
            {
                "prefect.resource.id": "foo.1",
                "prefect.resource.role": "thing",
                "a-label": "a-good-related-value",
            },
            {
                "prefect.resource.id": "foo.2",
                "prefect.resource.role": "another-thing",
            },
            {
                "prefect.resource.id": "foo.3",
                "prefect.resource.role": "the-other-thing",
            },
            {
                "prefect.resource.id": "related.4",
                "prefect.resource.role": "that-other-thing",
                "goodbye": "moon",
            },
        ],
        [
            {
                "prefect.resource.id": "foo.1",
                "prefect.resource.role": "thing",
                "hello": "world",
                "another": "label",
                "a-label": "a-good-other-value",
            },
            {
                "prefect.resource.id": "foo.2",
                "prefect.resource.role": "another-thing",
                "hello": "world",
            },
            {
                "prefect.resource.id": "foo.3",
                "prefect.resource.role": "that-other-thing",
                "goodbye": "moon",
                "hello": "mars",
            },
            {
                "prefect.resource.id": "related.4",
                "prefect.resource.role": "that-other-thing",
                "goodbye": "moon",
                "hello": "mars",
            },
            {
                "prefect.resource.id": "related.5",
                "prefect.resource.role": "that-other-thing",
                "goodbye": "moon",
            },
        ],
        [
            {
                "prefect.resource.id": "foo.1",
                "prefect.resource.role": "actor",
            },
            {
                "prefect.resource.id": "foo.2",
                "prefect.resource.role": "not-the-actor",
            },
        ],
    ]

    events: list[ReceivedEvent] = []
    for date in known_dates:
        midnight = start_of_day(
            now("UTC").replace(year=date.year, month=date.month, day=date.day)
        )
        for i in range(22):
            occurred = midnight + datetime.timedelta(seconds=i * 10)
            related = list(related_options[i % len(related_options)])

            events.append(
                ReceivedEvent(
                    occurred=occurred,
                    event=event_options[i % len(event_options)],
                    resource=resource_options[i % len(resource_options)],
                    related=related,
                    payload={"hello": "world"},
                    id=uuid4(),
                    received=occurred + timedelta(seconds=0.5),
                )
            )
    return events


@pytest.fixture
async def events_query_session(
    all_events: List[ReceivedEvent],
    session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Opens a session, seeds the database with the
    test events, and returns it for use in tests
    """
    await write_events(session, all_events)
    yield session


@pytest.fixture
def full_occurred_range(all_events: List[ReceivedEvent]) -> EventOccurredFilter:
    return EventOccurredFilter(
        since=min(e.occurred for e in all_events),
        until=max(e.occurred for e in all_events),
    )


def assert_events_ordered_descending(events: List[ReceivedEvent]):
    if len(events) < 2:
        return

    last = events[0]
    for i, event in enumerate(events[1:]):
        assert event.occurred <= last.occurred, (
            f"Event at index {i + 1} is out of order"
        )
        last = event


def assert_events_ordered_ascending(events: List[ReceivedEvent]):
    if len(events) < 2:
        return

    last = events[0]
    for i, event in enumerate(events[1:]):
        assert event.occurred >= last.occurred, (
            f"Event at index {i + 1} is out of order"
        )
        last = event


async def test_returns_empty_results(
    session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
):
    filter = EventFilter(
        occurred=full_occurred_range,
    )

    events, count, page_token = await query_events(
        session=session,
        filter=filter,
        page_size=5,
    )

    assert len(events) == 0
    assert count == 0
    assert page_token is None
    assert_events_ordered_descending(events)


async def test_returns_pages(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
    all_events: List[ReceivedEvent],
):
    # Usually, we'd prefer to use exact counts, but this test is very sensitive to the
    # structure of the test data, so we'll make the page_size variable in order to
    # adapt as we change the test suite
    expected = len(
        [event for event in all_events if (event.event == "things.happened")]
    )
    # Let's make sure we're getting a decent test here by requiring a certain size of
    # results, etc; if these assertions fail, try changing the test setup data to meet
    # these criteria instead
    assert expected >= 10
    page_size = expected // 3
    assert page_size > 2
    remainder = expected % page_size
    assert remainder > 0

    filter = EventFilter(
        occurred=full_occurred_range,
        event=EventNameFilter(name=["things.happened"]),
    )

    events, count, page_token = await query_events(
        session=events_query_session,
        filter=filter,
        page_size=page_size,
    )

    assert len(events) == page_size
    assert count == expected
    assert page_token is not None
    assert_events_ordered_descending(events)

    events, count, page_token = await query_next_page(
        session=events_query_session,
        page_token=page_token,
    )

    assert len(events) == page_size
    assert count == expected
    assert page_token is not None
    assert_events_ordered_descending(events)

    events, count, page_token = await query_next_page(
        session=events_query_session,
        page_token=page_token,
    )

    assert len(events) == page_size
    assert count == expected
    assert page_token is not None
    assert_events_ordered_descending(events)

    events, count, page_token = await query_next_page(
        session=events_query_session,
        page_token=page_token,
    )

    assert len(events) == remainder
    assert count == expected
    assert page_token is None
    assert_events_ordered_descending(events)


async def test_can_request_in_ascending_order(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(occurred=full_occurred_range, order=EventOrder.ASC),
    )

    assert events
    assert len(events) > 2
    assert len({e.occurred for e in events}) > 1
    assert_events_ordered_ascending(events)


async def test_can_request_in_descending_order(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            order=EventOrder.DESC,
        ),
    )

    assert events
    assert len(events) > 2
    assert len({e.occurred for e in events}) > 1
    assert_events_ordered_descending(events)


async def test_descending_is_the_default(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    filter = EventFilter(
        occurred=full_occurred_range,
    )
    assert filter.order == EventOrder.DESC

    events, _, _ = await query_events(session=events_query_session, filter=filter)

    assert events
    assert len(events) > 2
    assert len({e.occurred for e in events}) > 1
    assert_events_ordered_descending(events)


async def test_querying_by_event_prefixes(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            event=EventNameFilter(prefix=["things."]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.event.startswith("things.")


async def test_querying_by_event_names(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            event=EventNameFilter(name=["things.happened", "other.stuff"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.event in {"things.happened", "other.stuff"}


async def test_querying_by_event_names_but_excluding_others(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    """Regression test for https://github.com/PrefectHQ/nebula/issues/6634, where
    combining an event name search with an exclude_name search results in no
    results."""
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            event=EventNameFilter(
                name=["things.happened", "other.stuff"],
                exclude_name=["prefect.log.write"],
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.event in {"things.happened", "other.stuff"}


async def test_excluding_event_prefixes(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            event=EventNameFilter(exclude_prefix=["things."]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert not event.event.startswith("things.")


async def test_excluding_event_names(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            event=EventNameFilter(exclude_name=["things.happened", "other.stuff"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.event not in {"things.happened", "other.stuff"}


async def test_querying_by_any_resource_id(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(id=["foo.1", "foo.2"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id in {"foo.1", "foo.2"} or (
            any(related.id in {"foo.1", "foo.2"} for related in event.related)
        )


async def test_distinct_querying_by_any_resource_id(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(
                distinct=True, id=None, id_prefix=None, labels=None
            ),
            any_resource=EventAnyResourceFilter(id=["foo.1", "foo.2"]),
        ),
    )
    assert events
    received_resources = [event.resource.id for event in events]
    assert len(received_resources) == len(set(received_resources))


async def test_querying_by_any_resource_id_prefix(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(id_prefix=["foo"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id.startswith("foo") or (
            any(related.id.startswith("foo") for related in event.related)
        )


async def test_querying_by_any_resource_id_prefix_can_match_full_ids_too(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(id_prefix=["foo.1"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id == "foo.1" or (
            any(related.id == "foo.1" for related in event.related)
        )


async def test_querying_by_any_resource_id_label_is_equivalent_to_id(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(
                labels={"prefect.resource.id": "foo.1"}
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id == "foo.1" or (
            any(related.id == "foo.1" for related in event.related)
        )


async def test_querying_by_any_resource_id_labels_with_other_labels_positive(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(
                labels={"prefect.resource.id": "foo.1", "hello": "world"}
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id == "foo.1" or (
            any(related.id == "foo.1" for related in event.related)
        )


async def test_querying_by_any_resource_id_labels_with_other_labels_negative(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(
                labels={"prefect.resource.id": "foo.1", "not": "a thing"}
            ),
        ),
    )

    assert not events


async def test_querying_by_any_resource_wildcards(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(labels={"a-label": ["a-good*"]}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert (event.resource.get("a-label") or "").startswith("a-good") or (
            any(
                (related.get("a-label") or "").startswith("a-good")
                for related in event.related
            )
        )


async def test_querying_by_any_resource_wildcards_even_for_ids(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(
                labels={"prefect.resource.id": ["foo.*"]}
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id.startswith("foo.") or (
            any(related.id.startswith("foo.") for related in event.related)
        )


async def test_querying_by_any_related_labels_with_resource_ids_as_only_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(
                labels={"prefect.resource.id": "foo.1"}
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id == "foo.1" or (
            event.related and any(related.id == "foo.1" for related in event.related)
        )


async def test_querying_by_any_related_labels_with_resource_roles_as_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(
                labels={
                    "prefect.resource.role": "thing",
                    "hello": "world",
                }
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        assert any(
            related.role == "thing" and related["hello"] == "world"
            for related in event.related
        )


async def test_querying_by_any_resource_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(labels={"hello": "world"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.get("hello") == "world" or (
            any(related.get("hello") == "world" for related in event.related)
        )


async def test_querying_by_any_negative_resource_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
    all_events: List[ReceivedEvent],
) -> None:
    assert any(
        resource.get("hello") == "world"
        for event in all_events
        for resource in event.involved_resources
    )

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(labels={"hello": "!world"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        with_hello_label = [r for r in event.involved_resources if r.get("hello")]
        assert with_hello_label, repr(event)
        assert any(r["hello"] != "world" for r in with_hello_label), repr(event)


async def test_querying_by_any_negative_prefix(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
    all_events: List[ReceivedEvent],
) -> None:
    assert any(
        resource.get("hello") and resource["hello"].startswith("wor")
        for event in all_events
        for resource in event.involved_resources
    )

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(labels={"hello": "!wor*"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        all_resources = [event.resource] + event.related
        with_hello_label = [r for r in all_resources if r.get("hello")]
        assert with_hello_label, repr(event)
        assert any(not r["hello"].startswith("wor") for r in with_hello_label), repr(
            event
        )


async def test_querying_by_any_multiple_resource_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=EventAnyResourceFilter(labels={"hello": ["world", "mars"]}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)

    matched_on_world = 0
    matched_on_mars = 0

    for event in events:
        if event.resource.get("hello") == "world" or (
            any(related.get("hello") == "world" for related in event.related)
        ):
            matched_on_world += 1
        elif event.resource.get("hello") == "mars" or (
            any(related.get("hello") == "mars" for related in event.related)
        ):
            matched_on_mars += 1
        else:
            assert False, f"Event {event} matched on neither world nor mars"

    # There should be some events that matched both of these, or else the test setup
    # may not be covering all of the options
    assert matched_on_world > 0
    assert matched_on_mars > 0


async def test_querying_by_multiple_any_resource_filters(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            any_resource=[
                EventAnyResourceFilter(labels={"prefect.resource.id": "foo.3"}),
                EventAnyResourceFilter(labels={"prefect.resource.id": "related.5"}),
            ],
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        print([event.resource.id, *[r.id for r in event.related]])
        assert (
            event.resource.get("prefect.resource.id") == "foo.3"
            or any(
                related.get("prefect.resource.id") == "foo.3"
                for related in event.related
            )
        ) and (
            event.resource.get("prefect.resource.id") == "related.5"
            or any(
                related.get("prefect.resource.id") == "related.5"
                for related in event.related
            )
        )


async def test_querying_by_resource_id(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(id=["foo.1", "foo.2"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id in {"foo.1", "foo.2"}


async def test_querying_by_resource_id_is_not_interfered_by_noop_related_filter(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    """Regression test for an issue where the related filter was imposing an extra
    filter on normal resource ID queries where the events would only match if they
    had at least one related resource."""
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(id_prefix=["foo.1"]),
            # An empty related filter should have no bearing on the query
            related=EventRelatedFilter(),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    had_no_related = 0
    for event in events:
        assert event.resource.id == "foo.1"
        if not event.related:
            had_no_related += 1

    # At least one of the events should have no related resources, which is the criteria
    # we missed in the original implementation; but make sure we don't _only_ match
    # events with no related resources.  We expect a mix here
    assert 0 < had_no_related < len(events)


async def test_querying_by_resource_id_prefix(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(id_prefix=["foo"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id.startswith("foo")


async def test_querying_by_resource_id_prefix_can_match_full_ids_too(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(id_prefix=["foo.1"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id == "foo.1"


async def test_querying_by_resource_id_label_is_equivalent_to_id(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(labels={"prefect.resource.id": "foo.1"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id == "foo.1"


async def test_querying_by_resource_id_labels_with_other_labels_positive(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(
                labels={"prefect.resource.id": "foo.1", "hello": "world"}
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id == "foo.1"


async def test_querying_by_resource_id_labels_with_other_labels_negative(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(
                labels={"prefect.resource.id": "foo.1", "not": "a thing"}
            ),
        ),
    )

    assert not events


async def test_querying_by_resource_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(labels={"hello": "world"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource["hello"] == "world"


async def test_querying_by_negative_resource_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
    all_events: List[ReceivedEvent],
) -> None:
    assert any(event.resource.get("hello") == "world" for event in all_events)

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(labels={"hello": "!world"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource["hello"]
        assert event.resource["hello"] != "world"


async def test_querying_by_negative_resource_prefix(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
    all_events: List[ReceivedEvent],
) -> None:
    assert any(
        event.resource.get("hello") and event.resource["hello"].startswith("world")
        for event in all_events
    )

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(labels={"hello": "!wor*"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource["hello"]
        assert not event.resource["hello"].startswith("wor")


async def test_querying_by_resource_wildcards(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(labels={"a-label": ["a-good*"]}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert (event.resource.get("a-label") or "").startswith("a-good")


async def test_querying_by_resource_wildcards_even_for_ids(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(labels={"prefect.resource.id": ["foo.*"]}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource.id.startswith("foo.")


async def test_querying_by_related_nothing(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            resource=EventResourceFilter(labels={"hello": "world"}),
            related=EventRelatedFilter(),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.resource["hello"] == "world"
        # we aren't filtering on related, so we should get all events that match the
        # resource filter


async def test_querying_by_related_ids(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(id=["foo.1", "foo.2"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        assert any(related.id in {"foo.1", "foo.2"} for related in event.related)


async def test_querying_by_related_roles(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(role=["thing", "another-thing"]),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        assert any(
            related.role in {"thing", "another-thing"} for related in event.related
        )


async def test_querying_by_resource_in_roles(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(
                resources_in_roles=[
                    ["foo.1", "thing"],
                    ["foo.2", "another-thing"],
                ]
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        assert any(
            related.id == "foo.1" and related.role == "thing"
            for related in event.related
        )
        assert any(
            related.id == "foo.2" and related.role == "another-thing"
            for related in event.related
        )


async def test_querying_by_related_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(labels={"hello": "world", "another": "label"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        assert any(
            related["hello"] == "world" and related["another"] == "label"
            for related in event.related
        )


async def test_querying_by_related_negative_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
    all_events: List[ReceivedEvent],
) -> None:
    assert any(
        resource.get("hello") == "world"
        for event in all_events
        for resource in event.related
    )

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(labels={"hello": "!world"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        with_hello_label = [r for r in event.related if r.get("hello")]
        assert with_hello_label, repr(event)
        assert any(r["hello"] != "world" for r in with_hello_label), repr(event)


async def test_querying_by_related_negative_prefix(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
    all_events: List[ReceivedEvent],
) -> None:
    assert any(
        resource.get("hello") and resource["hello"].startswith("world")
        for event in all_events
        for resource in event.related
    )

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(labels={"hello": "!wor*"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        with_hello_label = [r for r in event.related if r.get("hello")]
        assert with_hello_label, repr(event)
        assert any(not r["hello"].startswith("wor") for r in with_hello_label), repr(
            event
        )


async def test_querying_by_related_labels_with_resource_ids_as_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(
                labels={
                    "prefect.resource.id": "foo.1",
                    "hello": "world",
                }
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        assert any(
            related.id == "foo.1" and related["hello"] == "world"
            for related in event.related
        )


async def test_querying_by_related_labels_with_resource_ids_as_only_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(labels={"prefect.resource.id": "foo.1"}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        assert any(related.id == "foo.1" for related in event.related)


async def test_querying_by_related_labels_with_resource_roles_as_labels(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(
                labels={
                    "prefect.resource.role": "thing",
                    "hello": "world",
                }
            ),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert event.related
        assert any(
            related.role == "thing" and related["hello"] == "world"
            for related in event.related
        )


async def test_querying_by_related_resource_wildcards(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(labels={"a-label": ["a-good*"]}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert any(
            (related.get("a-label") or "").startswith("a-good")
            for related in event.related
        )


async def test_querying_by_related_resource_wildcards_even_for_ids(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=EventRelatedFilter(labels={"prefect.resource.id": ["foo.*"]}),
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert any(related.id.startswith("foo.") for related in event.related)


async def test_querying_by_multiple_related_resources(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=[
                EventRelatedFilter(labels={"prefect.resource.id": ["foo.3"]}),
                EventRelatedFilter(labels={"prefect.resource.id": ["related.5"]}),
            ],
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        assert any(related.id == "foo.3" for related in event.related) and any(
            related.id == "related.5" for related in event.related
        )

    # now do it in the reverse order to make sure we aren't depending on order and that
    # we really are filtering on both

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            related=[
                EventRelatedFilter(labels={"prefect.resource.id": ["related.5"]}),
                EventRelatedFilter(labels={"prefect.resource.id": ["foo.3"]}),
            ],
        ),
    )

    assert events
    assert_events_ordered_descending(events)
    for event in events:
        print([event.resource.id, *[r.id for r in event.related]])
        assert any(related.id == "foo.3" for related in event.related) and any(
            related.id == "related.5" for related in event.related
        )


async def test_querying_by_ids(
    events_query_session: AsyncSession,
    all_events: List[ReceivedEvent],
    full_occurred_range: EventOccurredFilter,
) -> None:
    expected_ids = set([event.id for event in all_events][:3])

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            id=EventIDFilter(id=list(expected_ids)),
        ),
    )

    assert events
    assert_events_ordered_descending(events)

    ids_seen = set([event.id for event in events])
    assert ids_seen == expected_ids


async def test_querying_by_ids_with_lower_limit(
    events_query_session: AsyncSession,
    all_events: List[ReceivedEvent],
    full_occurred_range: EventOccurredFilter,
) -> None:
    expected_ids = set([event.id for event in all_events][:3])

    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            id=EventIDFilter(id=list(expected_ids)),
        ),
        page_size=2,
    )

    assert events
    assert_events_ordered_descending(events)

    ids_seen = set([event.id for event in events])
    assert len(ids_seen) == 2
    assert ids_seen.issubset(expected_ids)


async def test_querying_by_nonexistant_ids(
    events_query_session: AsyncSession,
    all_events: List[ReceivedEvent],
    full_occurred_range: EventOccurredFilter,
) -> None:
    events, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            id=EventIDFilter(id=[uuid4() for _ in range(10)]),
        ),
    )

    assert not events


async def test_event_dates_always_have_timezones(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    """Regression test for https://github.com/PrefectHQ/nebula/issues/2282, where
    date fields were returned from the API without timezone specifiers"""

    page_one, _, next_page = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
        ),
        page_size=5,
    )

    assert page_one
    assert_events_ordered_descending(page_one)

    assert next_page

    page_two, _, next_page = await query_next_page(
        session=events_query_session, page_token=next_page
    )

    assert page_two
    assert_events_ordered_descending(page_two)

    for event in page_one + page_two:
        assert event.occurred.tzinfo is not None
        assert event.received.tzinfo is not None

        event_dict = event.model_dump(mode="json")

        occurred = event_dict["occurred"]
        assert isinstance(occurred, str)
        assert occurred.endswith("+00:00") or occurred.endswith("Z")

        received = event_dict["received"]
        assert isinstance(received, str)
        assert received.endswith("+00:00") or received.endswith("Z")


@pytest.mark.parametrize(
    "busted_token",
    [
        # not base64
        "foo",
        # not JSON
        b64encode(b"foo").decode("utf-8"),
        # not UTF-8
        "\x89",
    ],
)
async def test_corrupted_page_tokens_are_treated_as_noops(busted_token: str):
    with pytest.raises(ValueError):
        from_page_token(busted_token)


async def test_resource_filter_empty_label_values(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    """Test that resource labels with empty values array return no results."""

    filter = EventFilter(
        occurred=full_occurred_range,
        resource=EventResourceFilter(labels={"hello": []}),  # Empty values = no matches
    )

    events, count, _ = await query_events(session=events_query_session, filter=filter)

    # Empty label values should match nothing
    assert count == 0
    assert events == []


async def test_related_filter_empty_label_values(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    """Test that related resource labels with empty values array return no results."""

    filter = EventFilter(
        occurred=full_occurred_range,
        related=EventRelatedFilter(labels={"hello": []}),  # Empty values = no matches
    )

    events, count, _ = await query_events(session=events_query_session, filter=filter)

    # Empty label values should match nothing
    assert count == 0
    assert events == []


async def test_any_resource_filter_empty_label_values(
    events_query_session: AsyncSession,
    full_occurred_range: EventOccurredFilter,
) -> None:
    """Test that any resource labels with empty values array return no results."""

    filter = EventFilter(
        occurred=full_occurred_range,
        any_resource=EventAnyResourceFilter(
            labels={"hello": []}
        ),  # Empty values = no matches
    )

    events, count, _ = await query_events(session=events_query_session, filter=filter)

    # Empty label values should match nothing
    assert count == 0
    assert events == []
