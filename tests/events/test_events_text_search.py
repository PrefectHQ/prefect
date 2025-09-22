"""Tests for text search functionality across events storage backends"""

from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional, Union
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.events.schemas.events import Event, Resource
from prefect.server.events.filters import (
    EventFilter,
    EventOccurredFilter,
    EventTextFilter,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage.database import query_events, write_events

# Define function types for our test variations
QueryEventsFn = Callable[..., Awaitable[tuple[list[Event], int, Optional[str]]]]


# In-memory event search that intentionally matches query_events() signature
async def query_events_memory(
    session: list[Event],  # For memory tests, this will be the list of events
    filter: EventFilter,
    page_size: int = 50,
) -> tuple[list[Event], int, Optional[str]]:
    """In-memory event filtering using EventFilter.includes() method.

    This function intentionally shares the signature of the database counterpart
    (query_events) and is used for filtering on WebSockets and other testing use cases
    where we need to filter events in memory rather than in the database.
    """

    # Alias for clarity - session is actually a list of events for memory tests
    events_list = session

    # Filter events using the EventFilter.includes() method
    filtered_events = []
    for event in events_list:
        # Check occurred filter
        if not filter.occurred.includes(event):
            continue
        # Check text filter
        if filter.text and not filter.text.includes(event):
            continue
        # Check other filters as needed
        if filter.event and not filter.event.includes(event):
            continue
        if filter.resource and not filter.resource.includes(event):
            continue
        if filter.id and not filter.id.includes(event):
            continue

        filtered_events.append(event)

    # Apply sorting based on order
    if filter.order.value == "ASC":
        filtered_events.sort(key=lambda event: event.occurred)
    else:  # DESC
        filtered_events.sort(key=lambda event: event.occurred, reverse=True)

    # Apply pagination - limit to page_size
    paginated_events = filtered_events[:page_size]
    total_count = len(filtered_events)

    # For simplicity, no pagination token in memory tests
    return paginated_events, total_count, None


VARIATIONS: list[tuple[str, QueryEventsFn]] = [
    ("memory", query_events_memory),
    ("database", query_events),
]


def pytest_generate_tests(metafunc: pytest.Metafunc):
    fixtures = set(metafunc.fixturenames)

    # If the test itself includes a marker saying that it is for only one variation,
    # then honor that marker and filter the test generation down to just that
    variation_names = {v[0] for v in VARIATIONS}
    marked_variations = {
        mark.name
        for mark in metafunc.definition.own_markers
        if mark.name in variation_names
    }
    if marked_variations:
        variation_names = variation_names.intersection(marked_variations)

    def marks(variation: str) -> list[pytest.MarkDecorator]:
        return []

    if fixtures.issuperset({"events_query_session", "query_events"}):
        metafunc.parametrize(
            "events_query_session, query_events",
            [
                pytest.param(
                    *values[:2],
                    id=values[0],
                    marks=marks(values[0]),
                )
                for values in VARIATIONS
                if values[0] in variation_names
            ],
            indirect=["events_query_session"],
        )


@pytest.fixture
def test_events() -> list[Event]:
    """Create test events with various text content for searching"""

    test_data = [
        # Basic error events
        {
            "event": "prefect.flow-run.Failed",
            "resource": {
                "prefect.resource.id": "prefect.flow-run.abc123",
                "prefect.resource.name": "error-flow",
            },
            "payload": {"error": "connection timeout"},
        },
        {
            "event": "prefect.task-run.Failed",
            "resource": {
                "prefect.resource.id": "prefect.task-run.def456",
                "prefect.resource.name": "debug-task",
            },
            "payload": {"message": "failed to process data"},
        },
        # Success events
        {
            "event": "prefect.flow-run.Completed",
            "resource": {
                "prefect.resource.id": "prefect.flow-run.xyz789",
                "prefect.resource.name": "success-flow",
            },
            "payload": {"result": "processed successfully"},
        },
        # Events with quoted phrases in names/payload
        {
            "event": "prefect.deployment.triggered",
            "resource": {
                "prefect.resource.id": "prefect.deployment.staging-env",
                "prefect.resource.name": "connection timeout handler",
            },
            "payload": {"message": "Unable to connect to database"},
        },
        # International characters - Japanese
        {
            "event": "prefect.flow-run.エラー",
            "resource": {
                "prefect.resource.id": "prefect.flow-run.japanese123",
                "prefect.resource.name": "フローテスト",
            },
            "payload": {"message": "データベース接続エラー", "environment": "本番"},
        },
        # International characters - Chinese
        {
            "event": "prefect.task-run.失败",
            "resource": {
                "prefect.resource.id": "prefect.task-run.chinese456",
                "prefect.resource.name": "数据处理任务",
            },
            "payload": {"error": "连接超时", "level": "错误"},
        },
        # Test environment events
        {
            "event": "prefect.flow-run.Running",
            "resource": {
                "prefect.resource.id": "prefect.flow-run.test123",
                "prefect.resource.name": "test-flow",
            },
            "payload": {"environment": "test", "debug": True},
        },
        # Production events
        {
            "event": "prefect.flow-run.Scheduled",
            "resource": {
                "prefect.resource.id": "prefect.flow-run.prod456",
                "prefect.resource.name": "prod-flow",
            },
            "payload": {"environment": "production", "warning": "high memory usage"},
        },
    ]

    events: list[Event] = []
    base_time = datetime.now(timezone.utc)
    for i, data in enumerate(test_data):
        occurred = base_time - timedelta(hours=i)

        events.append(
            Event(
                occurred=occurred,
                event=data["event"],
                resource=Resource(root=data["resource"]),
                related=[],
                payload=data["payload"],
                id=uuid4(),
            )
        )

    return events


@pytest.fixture
async def events_query_session(
    request: pytest.FixtureRequest,
    test_events: list[Event],
    session: AsyncSession,
):
    """Opens an appropriate session for the given backend, seeds it with the
    test events, and returns it for use in tests"""

    backend: str = request.param
    if backend == "memory":
        yield test_events
    elif backend == "database":
        # Convert Events to ReceivedEvents and write to database
        received_events = []
        for event in test_events:
            received_events.append(
                ReceivedEvent(
                    occurred=event.occurred,
                    event=event.event,
                    resource=event.resource.root,
                    related=[r.root for r in event.related],
                    payload=event.payload,
                    id=event.id,
                    received=event.occurred,
                )
            )

        # Write events to database using OSS write_events
        await write_events(session=session, events=received_events)
        await session.commit()
        yield session
    else:
        raise NotImplementedError(f"Unknown backend: {backend}")


@pytest.fixture
def full_occurred_range(test_events: list[Event]) -> EventOccurredFilter:
    """Create an occurred filter that includes all test events"""
    return EventOccurredFilter(
        since=min(e.occurred for e in test_events),
        until=max(e.occurred for e in test_events),
    )


# Test cases for basic text search functionality


async def test_single_term_search(
    events_query_session: Union[list[Event], AsyncSession],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test searching for a single term that appears in various fields"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="error")
        ),
    )

    # Should find events with "error" in resource name or payload
    assert len(events) >= 1
    for event in events:
        # Should contain "error" somewhere in the searchable text
        text_filter = EventTextFilter(query="error")
        searchable_text = text_filter._build_searchable_text(event).lower()
        assert "error" in searchable_text


async def test_multiple_terms_or_logic(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test space-separated terms should use OR logic"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="error success")
        ),
    )

    # Should find events with either "error" OR "success"
    assert len(events) >= 2
    for event in events:
        text_filter = EventTextFilter(query="error success")
        searchable_text = text_filter._build_searchable_text(event).lower()
        assert "error" in searchable_text or "success" in searchable_text


async def test_negative_terms_with_minus(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test excluding terms with minus prefix"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="flow -test")
        ),
    )

    # Should find events with "flow" but NOT "test"
    assert len(events) >= 1
    for event in events:
        text_filter = EventTextFilter(query="flow -test")
        searchable_text = text_filter._build_searchable_text(event).lower()
        assert "flow" in searchable_text
        assert "test" not in searchable_text


async def test_negative_terms_with_exclamation(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test excluding terms with exclamation prefix"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="flow !debug")
        ),
    )

    # Should find events with "flow" but NOT "debug"
    assert len(events) >= 1
    for event in events:
        text_filter = EventTextFilter(query="flow !debug")
        searchable_text = text_filter._build_searchable_text(event).lower()
        assert "flow" in searchable_text
        assert "debug" not in searchable_text


async def test_quoted_phrase_search(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test searching for exact phrases with quotes"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            text=EventTextFilter(query='"connection timeout"'),
        ),
    )

    # Should find events with exact phrase "connection timeout"
    assert len(events) >= 1
    for event in events:
        text_filter = EventTextFilter(query='"connection timeout"')
        searchable_text = text_filter._build_searchable_text(event).lower()
        assert "connection timeout" in searchable_text


async def test_quoted_phrase_exclusion(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test excluding exact phrases with quotes and minus"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            text=EventTextFilter(query='flow -"connection timeout"'),
        ),
    )

    # Should find events with "flow" but NOT the exact phrase "connection timeout"
    for event in events:
        text_filter = EventTextFilter(query='flow -"connection timeout"')
        searchable_text = text_filter._build_searchable_text(event).lower()
        assert "flow" in searchable_text
        assert "connection timeout" not in searchable_text


async def test_complex_combined_search(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test complex query combining multiple features"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            text=EventTextFilter(query='flow error -debug -"connection timeout"'),
        ),
    )

    # Should find events with "flow" OR "error" but NOT "debug" or "connection timeout"
    for event in events:
        text_filter = EventTextFilter(query='flow error -debug -"connection timeout"')
        searchable_text = text_filter._build_searchable_text(event).lower()
        assert "flow" in searchable_text or "error" in searchable_text
        assert "debug" not in searchable_text
        assert "connection timeout" not in searchable_text


async def test_case_insensitive_search(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test that searches are case insensitive"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="FAILED")
        ),
    )

    # Should find events with "failed" (lowercase in event name)
    assert len(events) >= 1
    for event in events:
        text_filter = EventTextFilter(query="FAILED")
        searchable_text = text_filter._build_searchable_text(event).lower()
        assert "failed" in searchable_text


async def test_empty_query_returns_all(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
    test_events: list[Event],
):
    """Test that empty query returns all results like no text filter"""

    # Query with empty text
    events_with_empty_text, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="")
        ),
    )

    # Query without text filter
    events_no_text, _, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(occurred=full_occurred_range),
    )

    # Should return same results
    assert len(events_with_empty_text) == len(events_no_text)


async def test_searches_event_field(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test that search covers event type/name field"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="deployment")
        ),
    )

    assert len(events) >= 1
    # Should find events with "deployment" in event name
    assert any("deployment" in event.event.lower() for event in events)


async def test_searches_resource_labels(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test that search covers resource label values (not keys)"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="abc123")
        ),
    )

    assert len(events) >= 1
    # Should find events with "abc123" in resource values
    assert any("abc123" in str(event.resource.root.values()) for event in events)


async def test_searches_payload_content(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test that search covers payload content"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="processed")
        ),
    )

    assert len(events) >= 1
    # Should find events with "processed" in payload
    assert any("processed" in str(event.payload).lower() for event in events)


async def test_no_matches_returns_empty(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test that searches with no matches return empty results"""

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            text=EventTextFilter(query="nonexistentterm12345"),
        ),
    )

    assert len(events) == 0


async def test_does_not_search_resource_label_keys(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test that search does NOT cover resource label keys, only values"""

    # Search for "prefect.resource.id" which is a key, not a value
    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range,
            text=EventTextFilter(query="prefect.resource.id"),
        ),
    )

    # Should find no events since we only search values, not keys
    # Note: This might find some if "prefect.resource.id" appears in payload as a value
    # The test validates the principle that keys are not automatically searched
    for event in events:
        text_filter = EventTextFilter(query="prefect.resource.id")
        searchable_text = text_filter._build_searchable_text(event)
        # If found, it should be in payload, not as a resource key
        if "prefect.resource.id" in searchable_text:
            assert "prefect.resource.id" in str(event.payload)


async def test_multilingual_character_search(
    events_query_session: list[Event],
    query_events: QueryEventsFn,
    full_occurred_range: EventOccurredFilter,
):
    """Test that international characters work through the full stack"""

    # Test Japanese characters in event name
    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="エラー")
        ),
    )

    assert len(events) >= 1
    # Should find events with Japanese characters
    assert any("エラー" in event.event for event in events)

    # Test Chinese characters in payload
    # Note: This fails on SQLite database tests due to Unicode handling
    # issues with Chinese characters in case-insensitive LIKE queries
    if isinstance(events_query_session, AsyncSession):
        from prefect.server.database import provide_database_interface

        db = provide_database_interface()
        if db.dialect.name == "sqlite":
            pytest.xfail(
                "SQLite Unicode handling issue with Chinese characters in lower() + LIKE queries"
            )

    events, count, _ = await query_events(
        session=events_query_session,
        filter=EventFilter(
            occurred=full_occurred_range, text=EventTextFilter(query="连接超时")
        ),
    )

    assert len(events) >= 1
    # Should find events with Chinese characters in payload
    assert any("连接超时" in str(event.payload) for event in events)
